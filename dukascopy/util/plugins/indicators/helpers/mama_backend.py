import numpy as np

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

@numba.jit(nopython=True, cache=True, nogil=True)
def _mama_backend(price: np.ndarray, fastlimit: float, slowlimit: float):
    """
    TA-Lib style exact match for MESA Adaptive Moving Average (MAMA).
    Executes Ehlers' recursive Hilbert Transform logic at C-speed.
    """
    n = len(price)
    mama = np.full(n, np.nan)
    fama = np.full(n, np.nan)

    if n < 7:
        return mama, fama

    # Pre-allocate state arrays for DSP math
    smooth = np.zeros(n)
    detrender = np.zeros(n)
    I1 = np.zeros(n)
    Q1 = np.zeros(n)
    jI = np.zeros(n)
    jQ = np.zeros(n)
    I2 = np.zeros(n)
    Q2 = np.zeros(n)
    Re = np.zeros(n)
    Im = np.zeros(n)
    Period = np.zeros(n)
    Phase = np.zeros(n)

    # Warmup synchronization
    for i in range(6):
        mama[i] = price[i]
        fama[i] = price[i]

    for i in range(6, n):
        # 4-bar WMA to smooth price data
        smooth[i] = (4.0*price[i] + 3.0*price[i-1] + 2.0*price[i-2] + price[i-3]) / 10.0
        
        # Compute Detrender
        detrender[i] = (0.0962*smooth[i] + 0.5769*smooth[i-2] - 
                        0.5769*smooth[i-4] - 0.0962*smooth[i-6]) * (0.075*Period[i-1] + 0.54)
        
        # Compute InPhase and Quadrature components
        Q1[i] = (0.0962*detrender[i] + 0.5769*detrender[i-2] - 
                 0.5769*detrender[i-4] - 0.0962*detrender[i-6]) * (0.075*Period[i-1] + 0.54)
        I1[i] = detrender[i-3]
        
        # Advance phase by 90 degrees
        jI[i] = (0.0962*I1[i] + 0.5769*I1[i-2] - 
                 0.5769*I1[i-4] - 0.0962*I1[i-6]) * (0.075*Period[i-1] + 0.54)
        jQ[i] = (0.0962*Q1[i] + 0.5769*Q1[i-2] - 
                 0.5769*Q1[i-4] - 0.0962*Q1[i-6]) * (0.075*Period[i-1] + 0.54)
                 
        # Phasor addition for 3-bar averaging
        I2[i] = I1[i] - jQ[i]
        Q2[i] = Q1[i] + jI[i]
        
        # Smooth I and Q components before applying discriminator
        I2[i] = 0.2*I2[i] + 0.8*I2[i-1]
        Q2[i] = 0.2*Q2[i] + 0.8*Q2[i-1]
        
        # Homodyne Discriminator
        Re[i] = I2[i]*I2[i-1] + Q2[i]*Q2[i-1]
        Im[i] = I2[i]*Q2[i-1] - Q2[i]*I2[i-1]
        
        Re[i] = 0.2*Re[i] + 0.8*Re[i-1]
        Im[i] = 0.2*Im[i] + 0.8*Im[i-1]
        
        # Extract Period
        if Im[i] != 0.0 and Re[i] != 0.0:
            # Convert radians to degrees equivalent mathematically
            Period[i] = 360.0 / (np.arctan(Im[i]/Re[i]) * 180.0 / np.pi)
        else:
            Period[i] = Period[i-1]
            
        # Restrict Period changes to prevent wild swings
        if Period[i] > 1.5 * Period[i-1]:
            Period[i] = 1.5 * Period[i-1]
        if Period[i] < 0.67 * Period[i-1]:
            Period[i] = 0.67 * Period[i-1]
            
        if Period[i] < 6.0:
            Period[i] = 6.0
        if Period[i] > 50.0:
            Period[i] = 50.0
            
        Period[i] = 0.2*Period[i] + 0.8*Period[i-1]
        
        # Compute Phase
        if I1[i] != 0.0:
            Phase[i] = np.arctan(Q1[i]/I1[i]) * 180.0 / np.pi
            
        # Phase change creates the dynamic alpha
        DeltaPhase = Phase[i-1] - Phase[i]
        if DeltaPhase < 1.0:
            DeltaPhase = 1.0
            
        alpha = fastlimit / DeltaPhase
        if alpha < slowlimit:
            alpha = slowlimit
        if alpha > fastlimit:
            alpha = fastlimit
            
        # Final MAMA and FAMA Equations
        mama[i] = alpha*price[i] + (1.0 - alpha)*mama[i-1]
        fama[i] = 0.5*alpha*mama[i] + (1.0 - 0.5*alpha)*fama[i-1]

    return mama, fama