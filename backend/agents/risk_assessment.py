from agents import call_llm

def run_risk_assessment(session_id: str, asset: dict) -> dict:
    prompt = f"""
    You are a Cummins generator service expert.
    
    A technician is about to perform a preventive maintenance 
    visit on this generator:
    
    Model: {asset['model_name']}
    Engine: {asset['engine_model']}
    Age: {asset['age_years']} years
    Environment: {asset['environment_type']}
    Site type: {asset['site_type']}
    Hours since last service: {asset['runtime_hours_since_last_service']}
    PM interval: {asset['pm_interval_hours']} hours
    Environment interval factor: {asset['environment_interval_factor']}
    Last service notes: {asset['last_service_notes']}
    
    Analyze the risk factors and return the top 3 inspection 
    priorities for this specific asset today.
    
    Return JSON only, no other text, in this exact format:
    
    {{
        "priorities": [
            {{
                "rank": 1,
                "category": "battery",
                "reason": "specific reason based on this asset",
                "confidence": 0.85
            }}
        ],
        "hours_overdue": 145,
        "pre_visit_summary": "one sentence summary of the most important thing to watch for today"
    }}
    
    Rules:
    - Always return exactly 3 priorities
    - category must be one of: battery, cooling, fuel, air_intake, electrical, mechanical
    - confidence must be between 0.70 and 0.94
    - reason must reference specific asset details like age or environment
    - hours_overdue is runtime_hours_since_last_service minus pm_interval_hours — if negative return 0
    - pre_visit_summary must be one sentence maximum referencing the most critical risk factor
    - Always return valid JSON only
    - Never exceed 0.95 confidence
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
        "pm_interval_hours": "125",
        "environment_interval_factor": "0.5",
        "last_service_notes": "Aging battery borderline voltage reading flagged"
    }
    result = run_risk_assessment("test_123", test_asset)
    print(result)