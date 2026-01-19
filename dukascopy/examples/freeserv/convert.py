import json
import re
import numpy as np

def convert_freeserv_to_jetta(input_data_str, multiplier=1e-5, shift=60000):
    # 1. Strip the JSONP callback wrapper: _callbacks____(...)
    json_str = re.sub(r'^[a-zA-Z0-9_]+\s*\(', '', input_data_str)
    json_str = re.sub(r'\);?\s*$', '', json_str)
    
    # 2. Load the raw list: [[ts, o, h, l, c, v], ...]
    raw_data = json.loads(json_str)
    
    # 3. Sort ascending by timestamp
    raw_data.sort(key=lambda x: x[0])
    
    if not raw_data:
        return None

    # 4. Establish Base Values from the first candle
    base_ts, base_o, base_h, base_l, base_c, base_v = raw_data[0]
    
    output = {
        "timestamp": base_ts,
        "multiplier": multiplier,
        "open": base_o,
        "high": base_h,
        "low": base_l,
        "close": base_c,
        "shift": shift,
        "times": [0],
        "opens": [0],
        "highs": [0],
        "lows": [0],
        "closes": [0],
        "volumes": [base_v]
    }
    
    # 5. Generate Deltas for subsequent candles
    for i in range(1, len(raw_data)):
        prev_ts, prev_o, prev_h, prev_l, prev_c, prev_v = raw_data[i-1]
        curr_ts, curr_o, curr_h, curr_l, curr_c, curr_v = raw_data[i]
        
        # Calculate time steps (usually [1, 1, 1...])
        output["times"].append(int((curr_ts - prev_ts) // shift))
        
        # Calculate integer price deltas: (Current - Previous) / Multiplier
        output["opens"].append(int(round((curr_o - prev_o) / multiplier)))
        output["highs"].append(int(round((curr_h - prev_h) / multiplier)))
        output["lows"].append(int(round((curr_l - prev_l) / multiplier)))
        output["closes"].append(int(round((curr_c - prev_c) / multiplier)))
        
        # Append volume
        output["volumes"].append(curr_v)

    return output

# Usage:
with open('example_input.txt', 'r') as f:
    converted = convert_freeserv_to_jetta(f.read())

with open('converted_output.json', 'w') as f:
    json.dump(converted, f)