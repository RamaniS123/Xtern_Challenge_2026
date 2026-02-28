import re
from typing import Dict


def classify_safety_level(observation: str, asset: Dict[str, str]) -> str:
    """
    Deterministic safety classification from the text observation.
    Keeps the demo stable (no LLM randomness for safety_color).
    """
    o = (observation or "").lower()

    # hard red conditions
    red_keywords = [
        "arcing", "burned", "burnt", "fuel leak", "coolant leak",
        "swelling", "bulging", "cracked", "seized", "failed load test",
        "won't start", "no start", "shutdown", "overheating",
        "white powder", "corrosion"
    ]
    if any(k in o for k in red_keywords):
        return "yellow" if "white powder" in o or "corrosion" in o else "red"

    # numeric voltage parsing -> yellow if <12.4V
    m = re.search(r"(\d{1,2}\.\d+)\s*v", o)
    if m:
        try:
            v = float(m.group(1))
            if v < 12.4:
                return "yellow"
        except Exception:
            pass

    # softer yellow conditions
    yellow_keywords = ["below threshold", "borderline", "marginal", "low", "unusual", "slightly off"]
    if any(k in o for k in yellow_keywords):
        return "yellow"

    return "green"