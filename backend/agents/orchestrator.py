from agents.risk_assessment import run_risk_assessment
from agents.adaptive_checklist import run_adaptive_checklist, get_checklist_step
from agents.findings_analysis import run_findings_analysis
from agents.escalation import run_escalation
from agents.safety import classify_safety_level

import csv
import os

def load_asset(asset_id: str) -> dict:
    csv_path = os.path.join(os.path.dirname(__file__), "../../data/generator_assets.csv")
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["asset_id"].strip() == asset_id.strip():
                return dict(row)
    return {}

def run_pm_session(asset_id: str, tech_id: str) -> dict:
    asset = load_asset(asset_id)
    if not asset:
        return {"error": f"Asset {asset_id} not found"}

    print(f"Loaded asset: {asset['model_name']} at {asset['site_type']}")

    # Step 2 - risk assessment
    print("Running risk assessment...")
    risk_result = run_risk_assessment(session_id="test_session", asset=asset)
    print(f"Risk result: {risk_result}")

    # Guardrail: ensure priorities exist (risk_assessment already tries, but don't crash here)
    priorities = risk_result.get("priorities") or []
    if not priorities:
        return {"error": "risk_assessment_failed", "detail": risk_result}

    # Step 3 - checklist
    first_priority = priorities[0]["category"]
    print(f"Running checklist for: {first_priority}")

    # Screen 3 content (what tech sees BEFORE typing)
    step0 = get_checklist_step(first_priority, 2)  # your CSV battery voltage is item_id 28, often step index 2
    if step0:
        print("\n--- SCREEN 3 (Checklist Step) ---")
        print(f"{step0['category'].upper()} • Step {step0['step_index']+1} of {step0['step_count']}")
        print(f"Task: {step0['inspection_item']}")
        print(f"NORMAL: {step0['normal_hint']}")
        print(f"ABNORMAL: {step0['abnormal_hint']}")
        print("--------------------------------\n")

    tech_observation = "battery voltage reads 12.3V, white powder visible on both terminals"
    checklist_result = run_adaptive_checklist(
        session_id="test_session",
        current_item=first_priority,
        tech_observation=tech_observation
    )
    print(f"Checklist result: {checklist_result}")

    # Step 4 - findings analysis
    print("Running findings analysis...")
    obs = "voltage 12.3V below threshold, white powder on terminals, load test voltage dropped to 11.4V"
    safety_level = classify_safety_level(obs, asset)

    findings = [{
        "item": first_priority,
        "observation": obs,
        "safety_level": safety_level
    }]

    findings_result = run_findings_analysis(
        session_id="test_session",
        findings=findings,
        asset=asset
    )
    print(f"Findings result: {findings_result}")

    # Step 5 - escalation
    escalation_result = None
    if findings_result.get("escalation_required"):
        print("Escalation required - running escalation agent...")
        escalation_result = run_escalation(
            session_id="test_session",
            findings_summary=findings_result,
            asset=asset,
            escalation_reason=findings_result.get("escalation_reason", "Escalation required")
        )
        print(f"Escalation result: {escalation_result}")

    return {
        "asset": asset,
        "risk_assessment": risk_result,
        "checklist_guidance": checklist_result,
        "findings_analysis": findings_result,
        "escalation": escalation_result
    }

if __name__ == "__main__":
    result = run_pm_session("GEN013", "TECH01")
    print("\nFinal result:")
    print(result)