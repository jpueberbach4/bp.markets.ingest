import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates the Hurst Exponent (H).
    H < 0.5: Mean-reverting (Anti-persistent)
    H = 0.5: Random Walk (Brownian Motion)
    H > 0.5: Trending (Persistent)
    """

    # 1. Parse Parameters
    try:
        # A larger window (e.g., 50-100) provides more statistical stability
        period = int(options.get('period', 50))
    except (ValueError, TypeError):
        period = 50

    if not data or len(data) < period:
        return [[], []]

    # 2. Determine Price Precision
    # Though Hurst is a 0.0-1.0 index, we match the rounding logic of your examples
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 4

    # 3. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    # 4. Dynamic Column Mapping
    if is_mt4:
        output_cols = ['date', 'time', 'hurst', 'regime']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'hurst', 'regime']
        sort_cols = ['time']

    # Ensure numeric conversion
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    def get_hurst_exponent(series):
        """Internal helper for R/S analysis calculation"""
        if len(series) < 10: return np.nan
        lags = range(2, 20)
        # Calculate the variance of the difference between lag values
        tau = [np.sqrt(np.std(np.subtract(series[lag:], series[:-lag]))) for lag in lags]
        # Calculate the slope of the log-log plot
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return poly[0] * 2.0

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 5. Calculation Logic
        group['hurst'] = group['close'].rolling(window=period).apply(get_hurst_exponent, raw=True)
        
        # Categorize the market regime based on the score
        def identify_regime(h):
            if h > 0.55: return "Trending"
            if h < 0.45: return "Mean-Reverting"
            return "Random"

        group['regime'] = group['hurst'].apply(identify_regime)

        # 6. Apply Dynamic Rounding
        group['hurst'] = group['hurst'].round(precision)
        
        # 7. Filter and Collect
        all_results.append(group[output_cols].dropna(subset=['hurst']))

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # FINAL SAFETY GATE (JSON COMPLIANCE)
    data_as_list = final_df.values.tolist()
    clean_data = [
        [ (x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row ]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]