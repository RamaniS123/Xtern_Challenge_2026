from typing import Any, Dict, List, Optional, Tuple

def compute_hours_overdue(asset: Dict[str, str]) -> int:
    try:
        rhsls = int(asset.get("runtime_hours_since_last_service", "0"))
        interval = int(asset.get("pm_interval_hours", "0"))
        return max(0, rhsls - interval)
    except Exception:
        return 0

def compute_operational_risk_index(
    asset: Dict[str, str],
    findings: List[Dict[str, Any]],
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Deterministic ORI scoring based on YOUR rubric.
    Returns (risk_index, breakdown).
    """
    breakdown: List[Dict[str, Any]] = []
    score = 0

    safety_levels = [str(f.get("safety_level", "green")).lower() for f in findings]
    has_red = any(s == "red" for s in safety_levels)
    has_yellow = any(s == "yellow" for s in safety_levels)
    all_green = len(safety_levels) > 0 and all(s == "green" for s in safety_levels)

    # Findings contribution
    if has_red:
        score += 40
        breakdown.append({"factor": "red_finding", "points": 40})
    elif has_yellow:
        score += 25
        breakdown.append({"factor": "yellow_finding", "points": 25})
    elif all_green:
        score += 10
        breakdown.append({"factor": "all_green_baseline", "points": 10})

    # Asset age contribution
    try:
        age = int(asset.get("age_years", "0"))
    except Exception:
        age = 0

    if age > 7:
        score += 15
        breakdown.append({"factor": "age_over_7", "points": 15})
    elif 5 <= age <= 7:
        score += 10
        breakdown.append({"factor": "age_5_to_7", "points": 10})

    # Environment contribution
    env = (asset.get("environment_type", "") or "").lower()
    if env in ("hot_dusty", "coastal"):
        score += 10
        breakdown.append({"factor": f"environment_{env}", "points": 10})

    # Site criticality contribution
    site = (asset.get("site_type", "") or "").lower()
    if site in ("hospital", "data_center"):
        score += 10
        breakdown.append({"factor": f"mission_critical_{site}", "points": 10})

    # PM overdue contribution
    if compute_hours_overdue(asset) > 0:
        score += 5
        breakdown.append({"factor": "pm_overdue", "points": 5})

    score = min(100, score)
    return score, breakdown

def operational_status_from_index(risk_index: int) -> str:
    if risk_index < 40:
        return "READY"
    if risk_index < 70:
        return "CAUTION"
    return "NOT_READY"

def site_clearance_from_status(status: str) -> str:
    if status == "READY":
        return "CLEARED FOR OPERATION"
    if status == "CAUTION":
        return "MONITOR CLOSELY"
    return "DO NOT RELEASE AS OPERATIONAL"

def compute_escalation(
    asset: Dict[str, str],
    findings: List[Dict[str, Any]],
    risk_index: int
) -> Tuple[bool, Optional[str]]:
    """
    Deterministic escalation rules from your prompt:
      - red safety finding
      - yellow and age > 6
      - mission-critical (hospital/data_center) with any non-green finding
      - ORI >= 70
    """
    site = (asset.get("site_type", "") or "").lower()
    try:
        age = int(asset.get("age_years", "0"))
    except Exception:
        age = 0

    safety_levels = [str(f.get("safety_level", "green")).lower() for f in findings]
    has_red = any(s == "red" for s in safety_levels)
    has_yellow = any(s == "yellow" for s in safety_levels)
    any_not_green = any(s != "green" for s in safety_levels)

    if has_red:
        return True, "red safety finding requires senior approval"
    if has_yellow and age > 6:
        return True, "yellow finding on asset age > 6 requires senior review"
    if site in ("hospital", "data_center") and any_not_green:
        return True, f"mission-critical site ({site}) with non-green finding requires senior review"
    if risk_index >= 70:
        return True, "operational risk index >= 70 requires senior approval"

    return False, None

def apply_mission_critical_release_gate(
    asset: Dict[str, str],
    findings: List[Dict[str, Any]]
) -> Tuple[bool, Optional[str]]:
    """
    UI gate only (doesn't change ORI). If mission-critical site and any finding is not green,
    we treat the unit as "DO NOT RELEASE" until fixed.
    """
    site = (asset.get("site_type", "") or "").lower()
    safety_levels = [str(f.get("safety_level", "green")).lower() for f in findings]
    any_not_green = any(s != "green" for s in safety_levels)

    if site in ("hospital", "data_center") and any_not_green:
        return True, f"mission-critical site ({site}) requires all findings green before release"

    return False, None