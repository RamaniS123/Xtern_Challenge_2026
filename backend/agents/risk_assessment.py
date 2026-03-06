from agents import call_llm
from agents.scoring import compute_hours_overdue
from audit_log import audit

@audit("risk_assessment_agent")
def run_risk_assessment(session_id: str, asset: dict) -> dict:
    hours_overdue = compute_hours_overdue(asset)

    prompt = f"""
Return JSON only. Start with {{ and end with }}.

You are a Cummins generator service expert.

A technician is about to perform a preventive maintenance visit on this generator:

Model: {asset.get('model_name')}
Engine: {asset.get('engine_model')}
Age: {asset.get('age_years')} years
Environment: {asset.get('environment_type')}
Site type: {asset.get('site_type')}
Hours since last service: {asset.get('runtime_hours_since_last_service')}
PM interval: {asset.get('pm_interval_hours')} hours
Hours overdue (computed): {hours_overdue}
Last service notes: {asset.get('last_service_notes')}

Analyze the risk factors and return the top 3 inspection priorities for this asset today.
Priorities indicate where to go deeper (not what to skip).

Return JSON only, in this exact format:
{{
  "priorities": [
    {{"rank": 1, "category": "battery", "reason": "specific reason based on this asset", "confidence": 0.85}},
    {{"rank": 2, "category": "cooling", "reason": "specific reason based on this asset", "confidence": 0.80}},
    {{"rank": 3, "category": "fuel", "reason": "specific reason based on this asset", "confidence": 0.78}}
  ],
  "hours_overdue": {hours_overdue},
  "pre_visit_summary": "one sentence summary of the most important thing to watch for today"
}}

Rules:
- Always return exactly 3 priorities
- category must be one of: battery, cooling, fuel, air_intake, electrical, mechanical
- confidence must be between 0.70 and 0.94
- reason must reference specific asset details like age, environment, hours overdue, or last notes
- pre_visit_summary must be one sentence maximum
- pre_visit_summary must mention the #1 priority category AND one concrete evidence phrase from the asset
- pre_visit_summary must NOT be generic (avoid listing multiple systems)
- Always return valid JSON only
"""

    result = call_llm(prompt, timeout_s=90, retries=1)

    # If LLM failed, return a safe fallback so orchestrator won't crash
    if "error" in result:
        notes = (asset.get("last_service_notes", "") or "").strip()
        env = asset.get("environment_type", "")
        return {
            "priorities": [
                {"rank": 1, "category": "battery", "reason": notes or "Battery risk flagged", "confidence": 0.70},
                {"rank": 2, "category": "cooling", "reason": f"Environment: {env}", "confidence": 0.70},
                {"rank": 3, "category": "fuel", "reason": f"Hours overdue: {hours_overdue}", "confidence": 0.70},
            ],
            "hours_overdue": hours_overdue,
            "pre_visit_summary": f"Focus first on battery: {notes or 'elevated risk given ' + env}."
        }

    # Enforce deterministic hours_overdue
    result["hours_overdue"] = hours_overdue

    # Guardrail: ensure priorities exists
    if not isinstance(result.get("priorities"), list) or len(result["priorities"]) < 3:
        notes = (asset.get("last_service_notes", "") or "").strip()
        env = asset.get("environment_type", "")
        result["priorities"] = [
            {"rank": 1, "category": "battery", "reason": notes or "Battery risk flagged", "confidence": 0.70},
            {"rank": 2, "category": "cooling", "reason": f"Environment: {env}", "confidence": 0.70},
            {"rank": 3, "category": "fuel", "reason": f"Hours overdue: {hours_overdue}", "confidence": 0.70},
        ]

    # Guardrail: pre_visit_summary mentions top category + evidence
    try:
        top_cat = result["priorities"][0].get("category", "inspection")
        notes = (asset.get("last_service_notes", "") or "").strip()
        ev = notes or f"{hours_overdue} hours overdue"
        summary = (result.get("pre_visit_summary") or "").strip()
        if not summary or top_cat.lower() not in summary.lower():
            result["pre_visit_summary"] = f"Focus first on {top_cat}: {ev}."
    except Exception:
        pass

    # Clamp length for UI (Removed per user request to show full summary)
    # if "pre_visit_summary" in result and isinstance(result["pre_visit_summary"], str) and len(result["pre_visit_summary"]) > 120:
    #     result["pre_visit_summary"] = result["pre_visit_summary"][:117] + "..."

    return result