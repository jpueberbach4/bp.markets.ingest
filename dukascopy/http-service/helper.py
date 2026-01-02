
from typing import Dict, Any
from urllib.parse import unquote_plus

def parse_uri(uri: str) -> Dict[str, Any]:
    parts = [p for p in uri.split('/') if p]
    
    result = {
        "selections": [],
        "after": None,
        "output_format": None,
        "platform": None,
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
                    result["selections"].append(formatted_selection)
                else:
                    result["selections"].append(unquoted_val)
        
        elif part == "after":
            quoted_val = next(it, None)
            result["after"] = unquote_plus(quoted_val) if quoted_val else None
            
        elif part == "output":
            quoted_val = next(it, None)
            result["output_format"] = unquote_plus(quoted_val) if quoted_val else None
            quoted_val = next(it, None)
            result["platform"] = unquote_plus(quoted_val) if quoted_val else None

    return result