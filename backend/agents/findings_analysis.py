import csv
import os
from agents import call_llm

# maps agent category names to parts_catalog system_category names
CATEGORY_MAP = {
    "battery": "electrical",
    "electrical": "electrical",
    "cooling": "cooling",
    "fuel": "fuel",
    "air_intake": "air_intake",
    "mechanical": "cooling",
    "air_filter": "air_intake"
}

def load_parts_for_categories(categories: list, engine_model: str) -> list:
    parts = []
    mapped_categories = [CATEGORY_MAP.get(c.strip().lower(), c.strip().lower()) for c in categories]
    
    csv_path = os.path.join(os.path.dirname(__file__), "../../data/parts_catalog.csv")
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            category_match = row["system_category"].strip().lower() in mapped_categories
            model_match = any(engine_model.strip() == m.strip() for m in row["compatible_models"].split(";"))
            if category_match and model_match:
                parts.append(row)
    return parts

def run_findings_analysis(session_id: str, findings: list, asset: dict) -> dict:
    
    categories = list(set([f["item"] for f in findings]))
    relevant_parts = load_parts_for_categories(categories, asset["engine_model"])
    
    if relevant_parts:
        parts_text = "\n".join([
            f"- {row['part_name']}: action={row['typical_pm_action']} | probability={row['probability_needed']} | stock={row['synthetic_stock_local']}"
            for row in relevant_parts[:10]
        ])
    else:
        parts_text = "No specific parts found for these categories"
    
    findings_text = "\n".join([
        f"- {f['item']}: {f['observation']} (safety level: {f['safety_level']})"
        for f in findings
    ])
    
    prompt = f"""
    You are a Cummins senior service engineer reviewing 
    PM visit findings.
    
    Asset: {asset['model_name']}, {asset['age_years']} years old,
    {asset['environment_type']} environment, 
    site type: {asset['site_type']}
    Engine model: {asset['engine_model']}
    Asset age: {asset['age_years']} years
    
    Findings from today's visit:
    {findings_text}
    
    Available parts and stock status (compatible with this engine):
    {parts_text}
    
    IMPORTANT: parts_needed must only contain part names from the 
    Available parts list above. Use the exact part_name string.
    If the list is empty return an empty array for parts_needed.
    
    Return a structured action plan using only parts from 
    the list above. Include stock status for each part.
    
    Return JSON only, no other text, in this exact format:
    
    {{
        "action_plan": [
            {{
                "issue": "what the issue is",
                "urgency": "immediate",
                "recommended_action": "what to do",
                "parts_needed": [
                    {{
                        "part_name": "exact part name from catalog",
                        "stock_status": "in_stock"
                    }}
                ]
            }}
        ],
        "escalation_required": true,
        "escalation_reason": "why escalation is needed if required",
        "confidence": 0.87
    }}
    
    Rules:
    - urgency must be immediate, schedule, or monitor only
    - escalation_required must be true or false
    - If any finding has safety_level red set escalation_required to true
    - If safety_level is yellow AND asset age is {asset['age_years']} years which is over 6 you MUST set escalation_required to true
    - Only use parts from the parts list above
    - Never use generic names like Battery — use exact part_name from the list
    - Always include stock_status exactly as shown in the list
    - If no matching part exists use an empty array for parts_needed
    - If escalation_required is false set escalation_reason to null
    - Never invent findings not reported
    - Always return valid JSON only
    """
    return call_llm(prompt)

if __name__ == "__main__":
    test_asset = {
        "model_name": "DFEJ",
        "engine_model": "QSX15",
        "age_years": "8",
        "environment_type": "hot_dusty",
        "site_type": "hospital"
    }
    test_findings = [
        {
            "item": "battery",
            "observation": "borderline voltage reading noted, terminals showing early corrosion",
            "safety_level": "yellow"
        }
    ]
    result = run_findings_analysis("test_123", test_findings, test_asset)
    print(result)