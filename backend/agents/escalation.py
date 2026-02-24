from agents import call_llm

def run_escalation(findings_summary, asset, escalation_reason):
    prompt = f"""
    You are helping route a field escalation to a senior 
    Cummins engineer.
    
    Asset: {asset['model_name']} at a {asset['site_type']}
    Environment: {asset['environment_type']}
    Age: {asset['age_years']} years
    
    Escalation reason: {escalation_reason}
    
    Findings summary: {findings_summary}
    
    Write a clear concise escalation brief for the senior 
    engineer. Return JSON only, no other text, in this 
    exact format:
    
    {{
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