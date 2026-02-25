import csv
import os
from agents import call_llm

def load_checklist_items(category: str) -> list:
    items = []
    csv_path = os.path.join(os.path.dirname(__file__), "../../data/checklist_items.csv")
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["category"].strip().lower() == category.strip().lower():
                items.append(row)
    return items

def run_adaptive_checklist(session_id: str, current_item: str, tech_observation: str) -> dict:
    
    checklist_items = load_checklist_items(current_item)
    
    if checklist_items:
        items_text = "\n".join([
            f"- {row['inspection_item']}: normal={row['normal_hint']} | abnormal={row['abnormal_hint']} | safety={row['safety_level']}"
            for row in checklist_items[:5]
        ])
    else:
        items_text = "No specific checklist items found for this category"
    
    prompt = f"""
    You are a Cummins generator PM inspection guide helping 
    a junior technician.
    
    Current inspection category: {current_item}
    What the technician just observed: {tech_observation}
    
    Reference checklist items for this category:
    {items_text}
    
    Based on the technician's observation and the checklist 
    reference above, tell them exactly what to check next.
    If the observation sounds abnormal go deeper.
    If it sounds normal move toward completing this item.
    
    Return JSON only, no other text, in this exact format:
    
    {{
        "next_step": "what to check next",
        "instruction": "plain language instruction for junior tech",
        "normal_looks_like": "what normal looks like",
        "abnormal_looks_like": "what abnormal looks like",
        "safety_level": "green",
        "follow_up_required": false,
        "confidence": 0.82
    }}
    
    Rules:
    - safety_level must be green, yellow, or red only
    - If observation mentions corrosion, leaks, or damage use red
    - If observation mentions borderline or worn use yellow
    - If observation sounds normal use green
    - Never invent observations the tech did not report
    - confidence must be between 0.70 and 0.94
    - Always return valid JSON only
    """
    return call_llm(prompt)

if __name__ == "__main__":
    result = run_adaptive_checklist(
        session_id="test_123",
        current_item="battery",
        tech_observation="I can see corrosion on both terminals and one cable looks loose"
    )
    print(result)