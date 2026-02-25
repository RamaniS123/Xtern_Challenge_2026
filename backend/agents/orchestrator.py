from agents.risk_assessment import run_risk_assessment
from agents.adaptive_checklist import run_adaptive_checklist
from agents.findings_analysis import run_findings_analysis
from agents.escalation import run_escalation
import csv
import os

def load_asset(asset_id: str) -> dict:
    csv_path = os.path.join(os.path.dirname(__file__), "../../data/generator_assets.csv")
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["asset_id"] == asset_id:
                return dict(row)
    return {}

def run_pm_session(asset_id: str, tech_id: str) -> dict:
    
    # Step 1 - load asset
    asset = load_asset(asset_id)
    if not asset:
        return {"error": f"Asset {asset_id} not found"}
    print(f"Loaded asset: {asset['model_name']} at {asset['site_type']}")
    
    # Step 2 - risk assessment
    print("Running risk assessment...")
    risk_result = run_risk_assessment(
        session_id="test_session",
        asset=asset
    )
    print(f"Risk result: {risk_result}")
    
    # Step 3 - adaptive checklist for top priority
    first_priority = risk_result["priorities"][0]["category"]
    print(f"Running checklist for: {first_priority}")
    checklist_result = run_adaptive_checklist(
        session_id="test_session",
        current_item=first_priority,
        tech_observation="visually inspecting now"
    )
    print(f"Checklist result: {checklist_result}")
    
    # Step 4 - findings analysis
    sample_findings = [
        {
            "item": first_priority,
            "observation": "borderline readings noted",
            "safety_level": "yellow"
        }
    ]
    print("Running findings analysis...")
    findings_result = run_findings_analysis(
        session_id="test_session",
        findings=sample_findings,
        asset=asset
    )
    print(f"Findings result: {findings_result}")
    
    # Step 5 - escalation if needed
    escalation_result = None
    if findings_result.get("escalation_required"):
        print("Escalation required - running escalation agent...")
        escalation_result = run_escalation(
            session_id="test_session",
            findings_summary=findings_result,
            asset=asset,
            escalation_reason=findings_result.get("escalation_reason", "Borderline findings require senior review")
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