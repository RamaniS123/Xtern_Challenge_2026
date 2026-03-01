import csv
import os
from agents import call_llm
from audit_log import audit

def load_approver(region: str = "Midwest") -> dict:
    csv_path = os.path.join(os.path.dirname(__file__), "../../data/approvers.csv")
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["region"].strip().lower() == region.strip().lower():
                return dict(row)
    # fallback: first approver
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            return dict(row)
    return {}

@audit("escalation_agent_run")
def run_escalation(session_id: str, findings_summary: dict, asset: dict, escalation_reason: str) -> dict:
    region = asset.get("region", "Southwest")
    approver = load_approver(region)
    approver_name = approver.get("name", "Senior Engineer")
    approver_email = approver.get("email", "")

    prompt = f"""
Return JSON only. Start with {{ and end with }}.

You are helping route a field escalation to a senior Cummins engineer.

Asset: {asset.get('model_name')} at a {asset.get('site_type')}
Environment: {asset.get('environment_type')}
Age: {asset.get('age_years')} years
Assigned approver: {approver_name}

Escalation reason: {escalation_reason}
Findings summary: {findings_summary}

WRITING RULES:
- findings_summary includes operational_status and site_clearance; reflect those exactly.
- Avoid the phrase "critical issues" unless there is a red safety finding.
- If site_clearance is "DO NOT RELEASE AS OPERATIONAL", say that explicitly.
- Be decision-ready: write what the approver should approve/deny.

Return JSON only, in this exact format:
{{
  "approver_name": "{approver_name}",
  "approver_email": "{approver_email}",
  "brief_summary": "2-3 sentence summary of situation",
  "key_findings": ["finding 1", "finding 2"],
  "recommended_decision": "Approve: <specific action> before releasing the unit.",
  "urgency_level": "high",
  "confidence": 0.83
}}

Rules:
- urgency_level must be high, medium, or low only
- brief_summary must be 2-3 sentences maximum
- key_findings MUST be a list of strings (not objects)
- recommended_decision MUST start with "Approve:" or "Deny:"
- recommended_decision must include the specific action + the release condition (before releasing / do not release until)
- Do NOT say "Request senior review" (the escalation is the review)
- If site_clearance is DO NOT RELEASE, brief_summary must include: "Do not release until corrective action completed."
- Always return valid JSON only
"""

    result = call_llm(prompt, timeout_s=90, retries=1)

    # Guardrail: enforce crisp approval language when unit is gated/not cleared
    try:
        site_clearance = findings_summary.get("site_clearance", "")
        action_plan = findings_summary.get("action_plan", []) or []
        parts = []
        if isinstance(action_plan, list) and action_plan:
            parts = (action_plan[0] or {}).get("parts_needed", []) or []

        if site_clearance == "DO NOT RELEASE AS OPERATIONAL" and parts:
            part_name = parts[0].get("part_name", "required part")
            result["recommended_decision"] = f"Approve: Replace {part_name} before releasing the unit."
        else:
            rd = (result.get("recommended_decision") or "").strip()
            if rd and not (rd.startswith("Approve:") or rd.startswith("Deny:")):
                result["recommended_decision"] = "Approve: " + rd
    except Exception:
        pass

    # Guardrail: key_findings must be list[str]
    kf = result.get("key_findings")
    if not isinstance(kf, list) or any(not isinstance(x, str) for x in kf):
        findings_list = []
        try:
            ap = findings_summary.get("action_plan", []) or []
            if isinstance(ap, list) and ap:
                findings_list.append(ap[0].get("issue", "Issue identified during PM"))
            findings_list.append(f"Site clearance: {findings_summary.get('site_clearance')}")
            findings_list.append(f"Operational risk index: {findings_summary.get('operational_risk_index')}")
        except Exception:
            findings_list = ["PM findings require review"]
        result["key_findings"] = findings_list[:3]

    # Guardrail: keep brief_summary short + include required phrase if gated
    bs = (result.get("brief_summary") or "").strip()
    site_clearance = findings_summary.get("site_clearance", "")
    if site_clearance == "DO NOT RELEASE AS OPERATIONAL" and "Do not release until" not in bs:
        bs = (bs + " Do not release until corrective action completed.").strip()

    if len(bs.split()) > 55:
        result["brief_summary"] = (
            f"{asset.get('model_name')} at {asset.get('site_type')} is gated "
            f"(site clearance: {site_clearance}). Approval required for corrective action. "
            "Do not release until corrective action completed."
        )
    else:
        result["brief_summary"] = bs

    return result