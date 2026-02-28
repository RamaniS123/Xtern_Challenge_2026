import csv
import os
from agents import call_llm
from agents.scoring import (
    compute_operational_risk_index,
    operational_status_from_index,
    site_clearance_from_status,
    compute_escalation,
    apply_mission_critical_release_gate,
)

CATEGORY_MAP = {
    "battery": "electrical",
    "electrical": "electrical",
    "cooling": "cooling",
    "fuel": "fuel",
    "air_intake": "air_intake",
    "mechanical": "cooling",
    "air_filter": "air_intake",
}


def load_parts_for_categories(categories: list, engine_model: str) -> list:
    parts = []
    mapped_categories = [CATEGORY_MAP.get(c.strip().lower(), c.strip().lower()) for c in categories]
    csv_path = os.path.join(os.path.dirname(__file__), "../../data/parts_catalog.csv")
    with open(csv_path, newline="", encoding="utf-8") as f:
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
        allowed_part_names = [row["part_name"] for row in relevant_parts]
    else:
        parts_text = "No specific parts found for these categories"
        allowed_part_names = []

    findings_text = "\n".join([
        f"- {f['item']}: {f['observation']} (safety_level: {f['safety_level']})"
        for f in findings
    ])

    ori, breakdown = compute_operational_risk_index(asset, findings)
    status = operational_status_from_index(ori)

    # Mission-critical gate (if triggered, override status to NOT_READY)
    gate_triggered, gate_reason = apply_mission_critical_release_gate(asset, findings)
    if gate_triggered:
        status = "NOT_READY"

    clearance = site_clearance_from_status(status)

    escalation_required, escalation_reason = compute_escalation(asset, findings, ori)

    # If gate triggers, ensure escalation reason exists (helps UI & escalation copy)
    if gate_reason and not escalation_reason:
        escalation_reason = gate_reason

    prompt = f"""
Return JSON only. Start with {{ and end with }}.

You are a Cummins senior service engineer writing an action plan from PM visit findings.

Asset: {asset['model_name']} ({asset['engine_model']})
Age: {asset['age_years']} years
Environment: {asset['environment_type']}
Site type: {asset['site_type']}
Runtime hours since last service: {asset['runtime_hours_since_last_service']}
PM interval hours: {asset['pm_interval_hours']}

Findings from today's visit:
{findings_text}

Allowed parts list (ONLY choose from these exact names):
{allowed_part_names}

Parts catalog context:
{parts_text}

IMPORTANT:
- parts_needed must contain ONLY part names from the Allowed parts list.
- If Allowed parts list is empty, parts_needed must be [].

DO NOT change the following precomputed fields:
operational_risk_index={ori}
operational_status={status}
site_clearance={clearance}
escalation_required={str(escalation_required).lower()}
escalation_reason={escalation_reason}

Return JSON only, in this exact format:
{{
  "operational_risk_index": {ori},
  "operational_status": "{status}",
  "site_clearance": "{clearance}",
  "risk_breakdown": {breakdown},
  "action_plan": [
    {{
      "issue": "what the issue is (grounded in findings)",
      "urgency": "immediate",
      "recommended_action": "what to do",
      "parts_needed": [
        {{"part_name": "exact part name from allowed list", "stock_status": "in_stock"}}
      ]
    }}
  ],
  "escalation_required": {str(escalation_required).lower()},
  "escalation_reason": {("null" if not escalation_required else '"' + escalation_reason + '"')},
  "confidence": 0.87
}}

Rules:
- urgency must be immediate, schedule, or monitor only
- Never invent findings not reported
- If no matching part exists use [] for parts_needed
- Always return valid JSON only
"""

    result = call_llm(prompt, timeout_s=90, retries=1)

    ap = result.get("action_plan")
    if isinstance(ap, list) and len(ap) > 1:
        result["action_plan"] = [ap[0]]

    # If LLM failed, still return deterministic summary fields so demo doesn't die
    if "error" in result:
        result = {
            **result,
            "operational_risk_index": ori,
            "operational_status": status,
            "site_clearance": clearance,
            "risk_breakdown": breakdown,
            "action_plan": [],
            "escalation_required": escalation_required,
            "escalation_reason": escalation_reason if escalation_required else None,
            "confidence": 0.70,
        }

    # Mission-critical release gate info for UI
    result["release_gate"] = {
        "triggered": bool(gate_reason),
        "reason": gate_reason,
    }

    # Enforce deterministic fields
    result["operational_risk_index"] = ori
    result["operational_status"] = status
    result["site_clearance"] = clearance
    result["risk_breakdown"] = breakdown
    result["escalation_required"] = escalation_required
    result["escalation_reason"] = escalation_reason if escalation_required else None

    return result