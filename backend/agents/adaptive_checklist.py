import csv
import os
import re
from agents import call_llm
from audit_log import audit

CHECKLIST_CATEGORY_MAP = {
    "battery": "battery",
    "electrical": "electrical",
    "cooling": "cooling",
    "fuel": "fuel",
    "air_intake": "air_intake",
    "mechanical": "cooling",
    "air_filter": "air_intake",
}

def load_checklist_items(category: str) -> list:
    mapped_category = CHECKLIST_CATEGORY_MAP.get(category.strip().lower(), category.strip().lower())
    csv_path = os.path.join(os.path.dirname(__file__), "../../data/checklist_items.csv")
    items = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["category"].strip().lower() == mapped_category:
                items.append(row)

    # consistent ordering (Step 1/2/3)
    items.sort(key=lambda r: int(r["item_id"]))
    return items

def get_checklist_step(category: str, step_index: int) -> dict:
    steps = load_checklist_items(category)
    if not steps:
        return {}

    step_index = max(0, min(step_index, len(steps) - 1))
    step = steps[step_index]
    return {
        "category": category,
        "step_index": step_index,
        "step_count": len(steps),
        "item_id": int(step["item_id"]),
        "inspection_item": step["inspection_item"],
        "normal_hint": step["normal_hint"],
        "abnormal_hint": step["abnormal_hint"],
        "safety_level": step["safety_level"],
        "base_interval": step["base_interval"],
    }

def _should_force_followup(obs: str) -> bool:
    o = (obs or "").lower()

    triggers = [
        "white powder", "corrosion", "below threshold", "borderline",
        "marginal", "low voltage", "failed load test", "bulging",
        "swelling", "leak", "leaking"
    ]

    # detect numeric voltage like 12.3V / 12.3 vdc / 12.3 v
    m = re.search(r"(\d{1,2}\.\d+)\s*v", o)
    if m:
        try:
            if float(m.group(1)) < 12.4:
                return True
        except Exception:
            pass

    return any(t in o for t in triggers)

@audit("adaptive_checklist_agent")
def run_adaptive_checklist(session_id: str, current_item: str, tech_observation: str) -> dict:
    checklist_items = load_checklist_items(current_item)

    if checklist_items:
        items_text = "\n".join([
            f"- {row['inspection_item']}: normal={row['normal_hint']} | abnormal={row['abnormal_hint']}"
            for row in checklist_items[:8]
        ])
        next_standard = checklist_items[0]["inspection_item"]
    else:
        items_text = "No specific checklist items found for this category"
        next_standard = f"Continue standard {current_item} inspection"

    prompt = f"""
Return JSON only. Start with {{ and end with }}.

You are an expert Cummins generator service engineer guiding a junior technician through a PM inspection step by step.

Current inspection category: {current_item}
What the technician observed or measured: {tech_observation}

Reference checklist items for this category:
{items_text}

If the observation is ABNORMAL or BORDERLINE:
- Set follow_up_required to true
- next_step must contain exactly 3 numbered mandatory investigation steps the tech must complete before moving on
- instruction must explain WHY these steps matter and what failure mode they rule out

If the observation is NORMAL:
- Set follow_up_required to false
- next_step is the next standard checklist item: "{next_standard}"

STATE-AWARE RULES (very important):
- Never ask the tech to repeat a measurement or inspection they already reported.
- If tech_observation already includes a voltage reading (contains "V" or "volt"), DO NOT include any step to "measure voltage".
- If tech_observation mentions corrosion or "white powder", DO NOT include a step to "inspect terminals" (they already saw it).
- If voltage is low/borderline OR corrosion is present, your 3 mandatory steps MUST be:
  1) Perform a battery load test (confirm ability to hold under load)
  2) Inspect battery case for swelling/bulging (safety risk)
  3) Check battery charger output range (charger may be causing failure)
- Do not recommend cleaning as a mandatory step unless the tech specifically asked how to clean.
- Do not mention baking soda.
- Do NOT claim "electrolyte leakage" unless the tech_observation explicitly includes "leak", "leaking", or "wetness".
- If corrosion/white powder is present and no leak is mentioned, describe it as "corrosion / possible electrolyte residue" (not leakage).

Return JSON only, in this exact format:
{{
  "next_step": "1. First mandatory step. 2. Second mandatory step. 3. Third mandatory step.",
  "instruction": "plain language explanation of what to do and why",
  "normal_looks_like": "what normal looks like for this specific check",
  "abnormal_looks_like": "what abnormal looks like and what it indicates",
  "follow_up_required": false,
  "confidence": 0.82
}}

Rules:
- next_step must never be empty
- If follow_up_required is true next_step must be ONE string written as: 1. ... 2. ... 3. ...
- Never invent observations the tech did not report
- confidence must be between 0.70 and 0.94
- Always return valid JSON only
"""

    result = call_llm(prompt, timeout_s=90, retries=1)

    # If LLM is down, return deterministic fallback
    if "error" in result:
        forced = _should_force_followup(tech_observation)
        return {
            "next_step": (
                "1. Perform a battery load test and record pass/fail threshold. "
                "2. Inspect battery case for swelling/bulging and any leakage. "
                "3. Check battery charger output range and record voltage."
            ) if forced else next_standard,
            "instruction": "LLM unavailable. Continue checklist using standard procedure.",
            "normal_looks_like": "",
            "abnormal_looks_like": "",
            "follow_up_required": forced,
            "confidence": 0.70,
        }

    # Hard guardrail: if clearly abnormal/borderline, force expansion (keeps demo stable)
    if _should_force_followup(tech_observation):
        result["follow_up_required"] = True
        result["next_step"] = (
            "1. Perform a battery load test and record pass/fail threshold. "
            "2. Inspect battery case for swelling/bulging and any leakage. "
            "3. Check battery charger output range and record voltage."
        )
        result["instruction"] = result.get("instruction") or (
            "These checks confirm whether the battery can hold under load, "
            "whether there is a safety risk from internal failure, and "
            "whether the charger is contributing to the problem."
        )

    # Guardrail: ensure schema keys exist
    result.setdefault("normal_looks_like", "")
    result.setdefault("abnormal_looks_like", "")
    result.setdefault("follow_up_required", False)
    result.setdefault("confidence", 0.70)

    return result