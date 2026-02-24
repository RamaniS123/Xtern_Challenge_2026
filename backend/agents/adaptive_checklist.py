from agents import call_llm

def run_adaptive_checklist(current_item, tech_observation):
    prompt = f"""
    You are a Cummins generator PM inspection guide helping 
    a junior technician.
    
    Current inspection item: {current_item}
    What the technician just observed: {tech_observation}
    
    Based on what they observed, tell them what to check next.
    If the observation sounds abnormal go deeper on this system.
    If it sounds normal move toward completing this item.
    
    Return JSON only, no other text, in this exact format:
    
    {{
        "next_step": "what to check next",
        "instruction": "plain language instruction",
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
    - Confidence score must be below 0.95, never equal to 0.95
    - Always return valid JSON only
    """
    return call_llm(prompt)

if __name__ == "__main__":
    result = run_adaptive_checklist(
        current_item="battery terminals",
        tech_observation="I can see corrosion on both terminals and one cable looks loose"
    )
    print(result)