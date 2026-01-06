# config/plugins/rsi.py
import pandas as pd

def calculate(data, options):
    """
    Calculates RSI per unique Symbol and Timeframe pair, 
    returning results ordered by time ASC.
    """

    raw_period = options.get('period', 14)
    
    try:
        period = int(raw_period)
    except (ValueError, TypeError):
        period = 14

    options['period'] = str(period)

    if not data:
        return [[], []]

    # Convert to DataFrame and ensure numeric types
    df = pd.DataFrame(data)
    df['close'] = pd.to_numeric(df['close'])
    
    # Define columns to return
    output_cols = ['symbol', 'timeframe', 'time', 'rsi']
    all_results = []

    # Group by both symbol and timeframe to isolate calculations
    grouped = df.groupby(['symbol', 'timeframe'])

    for (symbol, timeframe), group in grouped:
        # Sort by time within the group to ensure chronological RSI calculation
        group = group.sort_values('time')
        
        # RSI Calculation Logic
        delta = group['close'].diff()
        gain = (delta.where(delta > 0, 0))
        loss = (-delta.where(delta < 0, 0))

        # Wilder's Smoothing / EMA
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

        rs = avg_gain / avg_loss
        group['rsi'] = 100 - (100 / (1 + rs))
        
        # Filter columns and remove the 'warm-up' rows (NaNs)
        all_results.append(group[output_cols].dropna(subset=['rsi']))

    if not all_results:
        return [output_cols, []]

    # Combine all individual group results back into one DataFrame
    final_df = pd.concat(all_results)
    final_df = final_df.sort_values(by='time', ascending=options.get('order')=="asc")
    
    # Return formatted as [columns, records] for generate_output compatibility
    return [output_cols, final_df.values.tolist()]