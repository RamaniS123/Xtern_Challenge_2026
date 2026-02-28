from agents import call_llm
from agents.scoring import compute_hours_overdue


def run_risk_assessment(session_id: str, asset: dict) -> dict:
    hours_overdue = compute_hours_overdue(asset)

    prompt = f"""
Return JSON only. Start with {{ and end with }}.

You are a Cummins generator service expert.

A technician is about to perform a preventive maintenance visit on this generator:

Model: {asset['model_name']}
Engine: {asset['engine_model']}
Age: {asset['age_years']} years
Environment: {asset['environment_type']}
Site type: {asset['site_type']}
Hours since last service: {asset['runtime_hours_since_last_service']}
PM interval: {asset['pm_interval_hours']} hours
Hours overdue (computed): {hours_overdue}
Last service notes: {asset['last_service_notes']}

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
- pre_visit_summary must mention the #1 priority category AND one concrete evidence phrase from the asset (last_service_notes OR hours_overdue OR environment)
- pre_visit_summary must NOT be generic (avoid listing multiple systems)
- Always return valid JSON only
- Never exceed 0.95 confidence
"""

    result = call_llm(prompt, timeout_s=90, retries=1)

    # If the LLM failed, return something safe + deterministic so orchestrator can handle it.
    if "error" in result:
        return {
            **result,
            "hours_overdue": hours_overdue,
            "pre_visit_summary": f"Focus first on inspection: {asset.get('last_service_notes', 'No prior notes')}".strip()[:120],
        }

    # Enforce deterministic hours_overdue
    result["hours_overdue"] = hours_overdue

    # Guardrail: summary references top category + evidence
    try:
        priorities = result.get("priorities", [])
        top_cat = priorities[0]["category"] if priorities else "inspection"
        notes = (asset.get("last_service_notes", "") or "").strip()
        env = (asset.get("environment_type", "") or "").strip()
        if not result.get("pre_visit_summary"):
            result["pre_visit_summary"] = f"Focus first on {top_cat}: {notes or 'elevated risk in ' + env}."
        else:
            summary = result["pre_visit_summary"].lower()
            if top_cat not in summary:
                result["pre_visit_summary"] = f"Focus first on {top_cat}: {result['pre_visit_summary']}"
    except Exception:
        pass

    if "pre_visit_summary" in result and len(result["pre_visit_summary"]) > 120:
        result["pre_visit_summary"] = result["pre_visit_summary"][:117] + "..."

    return result