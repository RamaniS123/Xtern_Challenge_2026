import csv
import os
from agents import call_llm

CHECKLIST_CATEGORY_MAP = {
    "battery": "battery",
    "electrical": "electrical",
    "cooling": "cooling",
    "fuel": "fuel",
    "air_intake": "air_intake",
    "mechanical": "cooling",
    "air_filter": "air_intake"
}

def load_checklist_items(category: str) -> list:
    items = []
    mapped_category = CHECKLIST_CATEGORY_MAP.get(
        category.strip().lower(), 
        category.strip().lower()
    )
    csv_path = os.path.join(os.path.dirname(__file__), "../../data/checklist_items.csv")
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["category"].strip().lower() == mapped_category:
                items.append(row)
    return items

def run_adaptive_checklist(session_id: str, current_item: str, tech_observation: str) -> dict:
    
    checklist_items = load_checklist_items(current_item)
    
    if checklist_items:
        items_text = "\n".join([
            f"- {row['inspection_item']}: normal={row['normal_hint']} | abnormal={row['abnormal_hint']} | safety={row['safety_level']}"
            for row in checklist_items[:8]
        ])
    else:
        items_text = "No specific checklist items found for this category"
    
    prompt = f"""
    You are an expert Cummins generator service engineer guiding 
    a junior technician through a PM inspection step by step.
    
    Current inspection category: {current_item}
    What the technician just observed or measured: {tech_observation}
    
    Reference checklist items for this category:
    {items_text}
    
    Your job is to respond like a senior engineer who has seen 
    this failure mode before. If the observation is abnormal, 
    do not just say replace it — tell the tech exactly what 
    to investigate next and why it matters.
    
    If the observation is ABNORMAL or BORDERLINE:
    - Set follow_up_required to true
    - next_step must contain exactly 3 numbered mandatory 
      investigation steps the tech must complete before moving on
    - instruction must explain WHY these steps matter and what 
      failure mode they are ruling out
    - safety_level must be yellow or red depending on severity
    
    If the observation is NORMAL:
    - Set follow_up_required to false
    - next_step is the next standard checklist item from the 
      reference list above
    - safety_level is green
    
    Return JSON only, no other text, in this exact format:
    
    {{
        "next_step": "1. First mandatory step. 2. Second mandatory step. 3. Third mandatory step.",
        "instruction": "plain language explanation of what to do and why",
        "normal_looks_like": "what normal looks like for this specific check",
        "abnormal_looks_like": "what abnormal looks like and what failure it indicates",
        "safety_level": "green",
        "follow_up_required": false,
        "confidence": 0.82
    }}
    
    Rules:
    - next_step must never be an empty string — always return a specific action
    - safety_level must be green, yellow, or red only
    - If observation mentions corrosion, leaks, damage, swelling, or failed test use red
    - If observation mentions borderline, marginal, low, unusual, or slightly off use yellow
    - If observation sounds completely normal use green
    - Never invent observations the tech did not report
    - If follow_up_required is true next_step must be a single string containing all 3 steps written as: 1. step one. 2. step two. 3. step three.
    - next_step must always be a plain string never an array or list
    - confidence must be between 0.70 and 0.94
    - Always return valid JSON only
    """
    return call_llm(prompt)

if __name__ == "__main__":
    print("=== NORMAL OBSERVATION ===")
    result1 = run_adaptive_checklist(
        session_id="test_123",
        current_item="battery",
        tech_observation="battery voltage reads 12.6V, terminals look clean and tight"
    )
    print(result1)
    print()
    
    print("=== ABNORMAL OBSERVATION ===")
    result2 = run_adaptive_checklist(
        session_id="test_123",
        current_item="battery",
        tech_observation="battery voltage reads 12.3V, white powder buildup on both terminals"
    )
    print(result2)