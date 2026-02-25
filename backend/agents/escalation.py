import csv
import os
from agents import call_llm

def load_approver(region: str = "Midwest") -> dict:
    csv_path = os.path.join(os.path.dirname(__file__), "../../data/approvers.csv")
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["region"].strip().lower() == region.strip().lower():
                return dict(row)
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            return dict(row)
    return {}

def run_escalation(session_id: str, findings_summary: dict, asset: dict, escalation_reason: str) -> dict:
    
    region = asset.get("region", "Southwest")
    approver = load_approver(region)
    approver_name = approver.get("name", "Senior Engineer")
    approver_email = approver.get("email", "")
    
    prompt = f"""
    You are helping route a field escalation to a senior 
    Cummins engineer.
    
    Asset: {asset['model_name']} at a {asset['site_type']}
    Environment: {asset['environment_type']}
    Age: {asset['age_years']} years
    Assigned approver: {approver_name}
    
    Escalation reason: {escalation_reason}
    Findings summary: {findings_summary}
    
    Write a clear concise escalation brief for {approver_name}.
    Return JSON only, no other text, in this exact format:
    
    {{
        "approver_name": "{approver_name}",
        "approver_email": "{approver_email}",
        "brief_summary": "2-3 sentence summary of situation",
        "key_findings": ["finding 1", "finding 2"],
        "recommended_decision": "what you recommend the senior engineer decide",
        "urgency_level": "high",
        "confidence": 0.83
    }}
    
    Rules:
    - urgency_level must be high, medium, or low only
    - brief_summary must be 2-3 sentences maximum
    - Never exceed 0.95 confidence
    - Always return valid JSON only
    """
    return call_llm(prompt)

if __name__ == "__main__":
    test_asset = {
        "model_name": "DFEJ",
        "age_years": "8",
        "environment_type": "hot_dusty",
        "site_type": "hospital"
    }
    test_findings = {
        "action_plan": [{"issue": "battery corrosion", "urgency": "immediate"}],
        "escalation_required": True,
        "escalation_reason": "Red safety finding on hospital generator"
    }
    result = run_escalation(
        session_id="test_123",
        findings_summary=test_findings,
        asset=test_asset,
        escalation_reason="Red safety finding requires senior approval"
    )
    print(result)