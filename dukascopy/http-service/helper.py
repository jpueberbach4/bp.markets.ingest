
from typing import Dict, Any
from urllib.parse import unquote_plus

def parse_uri(uri: str) -> Dict[str, Any]:
    parts = [p for p in uri.split('/') if p]
    
    result = {
        "select_data": [],
        "after": "1970-01-01 00:00:00",
        "until": "3000-01-01 00:00:00",
        "output_type": None,
        "mt4": None,
        "options": []
    }

    it = iter(parts)
    for part in it:
        if part == "select":
            val = next(it, None)
            if val:
                unquoted_val = unquote_plus(val)
                if "," in val:
                    symbol_part, tf_part = unquoted_val.split(",", 1)
                    formatted_selection = f"{symbol_part}/{tf_part}"
                    result["select_data"].append(formatted_selection)
                else:
                    result["select_data"].append(unquoted_val)
        
        elif part == "after":
            quoted_val = next(it, None)
            result["after"] = unquote_plus(quoted_val) if quoted_val else None

        elif part == "until":
            quoted_val = next(it, None)
            result["until"] = unquote_plus(quoted_val) if quoted_val else None
            
        elif part == "output":
            quoted_val = next(it, None)
            result["output_type"] = unquote_plus(quoted_val) if quoted_val else None
            quoted_val = next(it, None)
            result["mt4"] = True if quoted_val else None

    return result