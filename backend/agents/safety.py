import re
from typing import Dict, Optional

def classify_safety_level(observation: str, asset: Optional[Dict[str, str]] = None) -> str:
    o = (observation or "").lower()

    # RED = clear safety hazard or failed verification
    red_triggers = [
        "leak", "leaking", "swelling", "bulging", "crack", "cracked",
        "arcing", "burned", "burnt", "failed load test", "fails load test"
    ]

    # YELLOW = abnormal/borderline but not immediate hazard
    yellow_triggers = [
        "white powder", "corrosion",
        "borderline", "marginal", "low", "unusual", "slightly off", "below threshold"
    ]

    if any(t in o for t in red_triggers):
        return "red"
    if any(t in o for t in yellow_triggers):
        return "yellow"

    # Voltage parsing for battery-ish text
    m = re.search(r"(\d{1,2}\.\d+)\s*v", o)
    if m:
        try:
            v = float(m.group(1))
            if v < 12.4:
                return "yellow"
        except Exception:
            pass

    return "green"