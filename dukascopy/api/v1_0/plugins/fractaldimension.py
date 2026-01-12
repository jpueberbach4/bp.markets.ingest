import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates the Fractal Dimension (D) using the Sevcik method.
    D = 1.0: Straight line (Perfect trend)
    D = 1.5: Random walk (Brownian motion)
    D = 2.0: Maximum complexity (Pure noise)
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 30))
    except (ValueError, TypeError):
        period = 30

    if not data or len(data) < period:
        return [[], []]

    # 2. Determine Price Precision
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 4

    # 3. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    if is_mt4:
        output_cols = ['date', 'time', 'fractal_dim', 'market_state']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'fractal_dim', 'market_state']
        sort_cols = ['time']

    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    def get_sevcik_dimension(series):
        """Calculates Sevcik Fractal Dimension for a price window"""
        n = len(series)
        if n < 2: return np.nan
        
        # Normalize prices between 0 and 1
        y_min, y_max = np.min(series), np.max(series)
        if y_min == y_max: return 1.0
        
        y = (series - y_min) / (y_max - y_min)
        x = np.linspace(0, 1, n)
        
        # Calculate length of the normalized curve
        l = np.sum(np.sqrt(np.diff(y)**2 + np.diff(x)**2))
        
        # Sevcik Formula
        return 1 + (np.log(l) + np.log(2)) / np.log(2 * (n - 1))

    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 4. Calculation Logic
        group['fractal_dim'] = group['close'].rolling(window=period).apply(get_sevcik_dimension, raw=True)
        
        # 5. Market State Classification
        def classify_fractal(d):
            if d < 1.3: return "Trending"
            if d > 1.6: return "Turbulent/Noise"
            return "Transition"

        group['market_state'] = group['fractal_dim'].apply(classify_fractal)

        # 6. Apply Dynamic Rounding (Standardized with provided examples)
        group['fractal_dim'] = group['fractal_dim'].round(precision)
        
        # 7. Filter and Collect
        all_results.append(group[output_cols].dropna(subset=['fractal_dim']))

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting & JSON Safety Gate
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]