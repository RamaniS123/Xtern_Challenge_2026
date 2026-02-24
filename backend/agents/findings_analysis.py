from agents import call_llm

def run_findings_analysis(findings, asset):
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
    
    Findings from today's visit:
    {findings_text}
    
    Return a structured action plan. Return JSON only, 
    no other text, in this exact format:
    
    {{
        "action_plan": [
            {{
                "issue": "what the issue is",
                "urgency": "immediate",
                "recommended_action": "what to do",
                "parts_needed": ["part_name"]
            }}
        ],
        "escalation_required": true,
        "escalation_reason": "why escalation is needed",
        "confidence": 0.87
    }}
    
    Rules:
    - urgency must be immediate, schedule, or monitor only
    - escalation_required must be true or false
    - If any finding has safety_level red set escalation_required to true
    - Never invent findings that were not reported
    - Always return valid JSON only
    """
    return call_llm(prompt)