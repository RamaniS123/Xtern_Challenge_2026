import csv
import os
from agents import call_llm

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
    Return JSON only. No preamble. No explanation. No "Here is the solution".
    Start your response with {{ and end with }}.
    
    You are a Cummins senior service engineer reviewing 
    PM visit findings.
    
    Asset: {asset['model_name']}, {asset['age_years']} years old,
    {asset['environment_type']} environment, 
    site type: {asset['site_type']}
    Engine model: {asset['engine_model']}
    Runtime hours since last service: {asset['runtime_hours_since_last_service']}
    PM interval hours: {asset['pm_interval_hours']}
    
    Findings from today's visit:
    {findings_text}
    
    Available parts and stock status (compatible with this engine):
    {parts_text}
    
    IMPORTANT: parts_needed must only contain part names from the 
    Available parts list above. Use the exact part_name string.
    If the list is empty return an empty array for parts_needed.
    
    Return JSON only, no other text, in this exact format:
    
    {{
        "operational_risk_index": <calculated number>,
        "operational_status": "<READY or CAUTION or NOT_READY>",
        "site_clearance": "<clearance string>",
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
        "escalation_reason": "why escalation is needed",
        "confidence": 0.87
    }}
    
    Rules:
    - Calculate operational_risk_index using this exact formula:
      Start at 0
      Add 40 if any finding safety_level is red
      Add 25 if any finding safety_level is yellow
      Add 10 if all findings safety_level are green
      Add 15 if age_years is greater than 7
      Add 10 if age_years is 5 to 7
      Add 10 if environment_type is hot_dusty or coastal
      Add 10 if site_type is hospital or data_center
      Add 5 if runtime_hours_since_last_service exceeds pm_interval_hours
      Cap total at 100
    - operational_status rules — apply after calculating index:
      if operational_risk_index is less than 40 then operational_status is READY
      if operational_risk_index is 40 or more AND less than 70 then operational_status is CAUTION
      if operational_risk_index is 70 or more then operational_status is NOT_READY
    - site_clearance rules — must match operational_status:
      if operational_status is READY then site_clearance is CLEARED FOR OPERATION
      if operational_status is CAUTION then site_clearance is MONITOR CLOSELY
      if operational_status is NOT_READY then site_clearance is DO NOT RELEASE AS OPERATIONAL
    - index 80 must produce NOT_READY and DO NOT RELEASE AS OPERATIONAL
    - index 65 must produce CAUTION and MONITOR CLOSELY
    - double check your index against these rules before returning
    - urgency must be immediate, schedule, or monitor only
    - escalation_required must be true or false
    - escalation_required is true if ANY of these:
      safety_level is red
      safety_level is yellow AND age_years over 6
      site_type is hospital or data_center AND any finding is not green
      operational_risk_index is 70 or above
    - Only use parts from the parts list above
    - Never use generic names like Battery use exact part_name
    - Always include stock_status exactly as shown in the list
    - If no matching part exists use empty array for parts_needed
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
        "site_type": "hospital",
        "runtime_hours_since_last_service": "270",
        "pm_interval_hours": "125"
    }
    test_findings = [
        {
            "item": "battery",
            "observation": "voltage 12.3V, white powder on terminals, load test failed",
            "safety_level": "yellow"
        }
    ]
    result = run_findings_analysis("test_123", test_findings, test_asset)
    print(result)