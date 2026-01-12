import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Shannon Entropy.
    Measures the unpredictability/randomness of price action.
    Low Entropy = Strong Trend / High Order
    High Entropy = Sideways / High Disorder
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 20))
        # bins determine the granularity of the price distribution
        bins = int(options.get('bins', 10))
    except (ValueError, TypeError):
        period, bins = 20, 10

    if not data or len(data) < period:
        return [[], []]

    # 2. Determine Price Precision
    # Matches the detection logic in your example scripts
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 4

    # 3. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    if is_mt4:
        output_cols = ['date', 'time', 'entropy', 'efficiency']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'entropy', 'efficiency']
        sort_cols = ['time']

    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    def get_shannon_entropy(series):
        """Calculates Shannon Entropy for a window of price returns"""
        # Calculate returns to focus on movement rather than absolute price
        returns = np.diff(series)
        if len(returns) == 0: return 0.0
        
        # Create a histogram to get probabilities
        counts, _ = np.histogram(returns, bins=bins)
        probs = counts / counts.sum()
        probs = probs[probs > 0] # Remove zero probabilities for log calculation
        
        # Formula: H = -sum(p * log2(p))
        entropy = -np.sum(probs * np.log2(probs))
        return entropy

    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 4. Calculation Logic
        group['entropy'] = group['close'].rolling(window=period).apply(get_shannon_entropy, raw=True)
        
        # 5. Efficiency Ratio (Normalized 0-1)
        # Higher entropy means lower efficiency (more noise)
        max_entropy = np.log2(bins)
        group['efficiency'] = (1 - (group['entropy'] / max_entropy)).clip(0, 1)

        # 6. Apply Dynamic Rounding
        group['entropy'] = group['entropy'].round(precision)
        group['efficiency'] = group['efficiency'].round(4)
        
        # 7. Filter and Collect
        all_results.append(group[output_cols].dropna(subset=['entropy']))

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