from agents import call_llm

def run_risk_assessment(asset):
    prompt = f"""
    You are a Cummins generator service expert.
    
    A technician is about to perform a preventive maintenance 
    visit on this generator:
    
    Model: {asset['model_name']}
    Age: {asset['age_years']} years
    Environment: {asset['environment_type']}
    Hours since last service: {asset['runtime_hours_since_last_service']}
    PM interval hours: {asset['pm_interval_hours']}
    Last service notes: {asset['last_service_notes']}
    
    Return the top 3 inspection priorities for this specific 
    asset today. Return JSON only, no other text, in this 
    exact format:
    
    {{
        "priorities": [
            {{
                "rank": 1,
                "category": "battery",
                "reason": "why this needs attention today",
                "confidence": 0.85
            }}
        ]
    }}
    
    Rules:
    - Maximum 3 priorities
    - Each priority must be a different category — no duplicate categories
    - Confidence score never above 0.95
    - Always return valid JSON only
    - Base priorities on the asset data provided
    """
    return call_llm(prompt)

if __name__ == "__main__":
    test_asset = {
        "model_name": "DFEJ",
        "age_years": 8,
        "environment_type": "hot_dusty",
        "runtime_hours_since_last_service": 270,
        "pm_interval_hours": 125,
        "last_service_notes": "Aging battery borderline voltage reading flagged"
    }
    result = run_risk_assessment(test_asset)
    print(result)

if __name__ == "__main__":
    test_asset = {
        "model_name": "DFEJ",
        "age_years": 8,
        "environment_type": "hot_dusty",
        "runtime_hours_since_last_service": 270,
        "pm_interval_hours": 125,
        "last_service_notes": "Aging battery borderline voltage reading flagged"
    }
    result = run_risk_assessment(test_asset)
    print(result)