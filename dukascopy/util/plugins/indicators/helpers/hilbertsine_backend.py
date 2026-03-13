import numpy as np

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

@numba.jit(nopython=True, cache=True, nogil=True)
def _hilbertsine_backend(price: np.ndarray):
    """
    Executes John Ehlers' Hilbert Transform Sine Wave algorithm at C-speed.
    Dynamically extracts the phase of the market's dominant cycle to plot 
    predictive Sine and Lead Sine waves.
    """
    n = len(price)
    sine = np.full(n, np.nan)
    leadsine = np.full(n, np.nan)

    if n < 7:
        return sine, leadsine

    # Pre-allocate state arrays for heavy DSP math
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

    for i in range(6, n):
        # 4-bar WMA to smooth price data and remove aliasing noise
        smooth[i] = (4.0*price[i] + 3.0*price[i-1] + 2.0*price[i-2] + price[i-3]) / 10.0
        
        # Compute Detrender
        detrender[i] = (0.0962*smooth[i] + 0.5769*smooth[i-2] - 
                        0.5769*smooth[i-4] - 0.0962*smooth[i-6]) * (0.075*Period[i-1] + 0.54)
        
        # Compute InPhase (I1) and Quadrature (Q1) components
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
        
        # Extract Phase from the I and Q components
        DCPhase = 0.0
        if I1[i] != 0.0:
            DCPhase = np.arctan(Q1[i] / I1[i]) * 180.0 / np.pi
            
        # Adjust phase to correct geometric quadrant
        if I1[i] < 0.0:
            DCPhase += 180.0
        elif Q1[i] < 0.0 and I1[i] > 0.0:
            DCPhase += 360.0
            
        Phase[i] = DCPhase
        
        # Calculate final Sine and LeadSine waves
        # Note: numpy trigonometric functions require radians
        sine[i] = np.sin(Phase[i] * np.pi / 180.0)
        leadsine[i] = np.sin((Phase[i] + 45.0) * np.pi / 180.0)

    return sine, leadsine

