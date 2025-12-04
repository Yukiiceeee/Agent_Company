import json
import re
from typing import Dict, List, Set

def extract_json(text: str) -> Dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        if "```json" in text:
            pattern = r"```json(.*?)```"
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return json.loads(match.group(1).strip())
        
        pattern = r"\{.*\}"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return json.loads(match.group(0).strip())
            
    except Exception as e:
        print(f"JSON Parsing Error: {e}")
        
    return {}