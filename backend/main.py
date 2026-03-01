# backend/main.py
import csv
import json
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from auth import (
    create_access_token,
    verify_password,
    get_current_user,
    hash_password,
    require_role,
)

from database import (
    init_db,
    create_session,
    save_findings,
    create_escalation,
    get_escalation_status,
    save_approval,
    get_pending_escalations,
    get_audit_log,
    queue_offline_request,
    get_unsynced_queue,
    mark_queue_item_synced,
    get_connection,
    upsert_user,
    get_user,
)

from supabase_sync import sync_session_to_supabase

from agents.risk_assessment import run_risk_assessment
from agents.adaptive_checklist import run_adaptive_checklist, get_checklist_step
from agents.findings_analysis import run_findings_analysis
from agents.escalation import run_escalation

load_dotenv()
init_db()

app = FastAPI(title="PMAdapt API", version="1.0.0")

# For demo: open CORS. For stricter: set to your frontend origin(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# data folder is OUTSIDE backend (../data)
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_asset(asset_id: str) -> dict:
    csv_path = os.path.join(DATA_PATH, "generator_assets.csv")
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=500, detail=f"Missing dataset file: {csv_path}")

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["asset_id"].strip() == asset_id.strip():
                return dict(row)
    return {}


def load_assets_minimal() -> List[Dict]:
    csv_path = os.path.join(DATA_PATH, "generator_assets.csv")
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=500, detail=f"Missing dataset file: {csv_path}")

    assets = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            assets.append({
                "asset_id": row.get("asset_id"),
                "model_name": row.get("model_name"),
                "site_type": row.get("site_type"),
                "environment_type": row.get("environment_type"),
                "age_years": row.get("age_years"),
                "region": row.get("region", ""),
            })
    return assets


# -------------------- Request Models --------------------

class RegisterRequest(BaseModel):
    tech_id: str = Field(..., min_length=5, max_length=5)
    password: str = Field(..., min_length=4)
    role: str = Field(default="tech")  # tech | supervisor


class LoginRequest(BaseModel):
    tech_id: str = Field(..., min_length=5, max_length=5)
    password: str


class StartSessionRequest(BaseModel):
    asset_id: str


class NextStepRequest(BaseModel):
    current_item: str
    tech_observation: str


class Finding(BaseModel):
    item: str
    observation: str
    safety_level: str  # green/yellow/red


class FindingsRequest(BaseModel):
    findings: List[Finding]


class ApprovalRequest(BaseModel):
    decision: str  # approve / reject / etc
    instruction: str


class OfflineQueueRequest(BaseModel):
    session_id: Optional[str] = None
    endpoint: str
    payload: dict


class OfflineSyncRequest(BaseModel):
    sync_to_supabase: bool = True


# -------------------- Pure Logic Functions (for offline replay) --------------------

def start_session_logic(asset_id: str, tech_id: str):
    asset = load_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")

    session_id = str(uuid.uuid4())
    timestamp = now()
    create_session(session_id, asset_id, tech_id, timestamp)

    risk_result = run_risk_assessment(session_id, asset)
    if not isinstance(risk_result, dict) or "priorities" not in risk_result:
        raise HTTPException(status_code=500, detail=f"Risk assessment failed: {risk_result}")

    return {
        "session_id": session_id,
        "asset": {
            "asset_id": asset.get("asset_id"),
            "model_name": asset.get("model_name"),
            "site_type": asset.get("site_type"),
            "environment_type": asset.get("environment_type"),
            "age_years": asset.get("age_years"),
            "engine_model": asset.get("engine_model"),
        },
        "priority_agenda": risk_result.get("priorities", []),
        "hours_overdue": risk_result.get("hours_overdue"),
        "pre_visit_summary": risk_result.get("pre_visit_summary"),
    }


def next_step_logic(session_id: str, current_item: str, tech_observation: str):
    checklist_result = run_adaptive_checklist(session_id, current_item, tech_observation)
    if isinstance(checklist_result, dict) and checklist_result.get("error"):
        raise HTTPException(status_code=500, detail=f"Checklist agent failed: {checklist_result}")
    return checklist_result


def submit_findings_logic(session_id: str, findings_list: List[Dict]):
    timestamp = now()
    save_findings(session_id, findings_list, timestamp)

    conn = get_connection()
    row = conn.execute("SELECT asset_id FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    asset = load_asset(row["asset_id"])
    if not asset:
        raise HTTPException(status_code=404, detail="Asset for session not found")

    findings_result = run_findings_analysis(session_id, findings_list, asset)
    if isinstance(findings_result, dict) and findings_result.get("error"):
        raise HTTPException(status_code=500, detail=f"Findings analysis failed: {findings_result}")

    if findings_result.get("escalation_required"):
        escalation_result = run_escalation(
            session_id,
            findings_result,
            asset,
            findings_result.get("escalation_reason", "Escalation required"),
        )

        if isinstance(escalation_result, dict) and not escalation_result.get("error"):
            create_escalation(
                session_id=session_id,
                approver_name=escalation_result.get("approver_name", "Senior Engineer"),
                approver_email=escalation_result.get("approver_email", ""),
                brief_summary=escalation_result.get("brief_summary", ""),
                urgency_level=escalation_result.get("urgency_level", "high"),
                escalation_reason=findings_result.get("escalation_reason", ""),
                timestamp=timestamp,
            )

        findings_result["escalation_details"] = escalation_result

    return findings_result


def replay_queued_request(session_id: Optional[str], endpoint: str, payload: dict, user: Dict):
    ep = endpoint.strip().lower()

    if ep in ["/sessions/start", "sessions/start", "start_session"]:
        body = StartSessionRequest(**payload)
        return start_session_logic(body.asset_id, user["tech_id"])

    if ep.endswith("/next-step") or ep in ["sessions/next-step", "next_step"]:
        if not session_id:
            raise ValueError("Queued next-step missing session_id")
        body = NextStepRequest(**payload)
        return next_step_logic(session_id, body.current_item, body.tech_observation)

    if ep.endswith("/findings") or ep in ["sessions/findings", "submit_findings"]:
        if not session_id:
            raise ValueError("Queued findings missing session_id")
        body = FindingsRequest(**payload)
        findings_list = [f.model_dump() for f in body.findings]
        return submit_findings_logic(session_id, findings_list)

    raise ValueError(f"Unsupported queued endpoint: {endpoint}")


# -------------------- Endpoints --------------------

@app.get("/")
def root():
    return {"status": "PMAdapt API running"}


# ---- Auth ----

@app.post("/auth/register")
def register(body: RegisterRequest):
    # demo helper endpoint
    if body.role not in ("tech", "supervisor"):
        raise HTTPException(status_code=400, detail="role must be tech or supervisor")

    upsert_user(body.tech_id, hash_password(body.password), body.role)
    return {"ok": True, "tech_id": body.tech_id, "role": body.role}


@app.post("/auth/login")
def login(body: LoginRequest):
    user = get_user(body.tech_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(body.tech_id, user["role"])
    return {"access_token": token, "token_type": "bearer", "tech_id": body.tech_id, "role": user["role"]}


# ---- Assets (optional convenience) ----

@app.get("/assets")
def get_assets(user: Dict = Depends(get_current_user)):
    return {"assets": load_assets_minimal()}


# ---- Start session (Screen 2) ----

@app.post("/sessions/start")
def start_session(body: StartSessionRequest, user: Dict = Depends(get_current_user)):
    return start_session_logic(body.asset_id, user["tech_id"])


# ---- Checklist step (Screen 3) ----

@app.get("/checklist/{category}/step/{step_index}")
def checklist_step(category: str, step_index: int, user: Dict = Depends(get_current_user)):
    step = get_checklist_step(category, step_index)
    if not step:
        raise HTTPException(status_code=404, detail="No checklist steps found")
    return step


# ---- Submit observation (Screen 4) ----

@app.post("/sessions/{session_id}/next-step")
def next_step(session_id: str, body: NextStepRequest, user: Dict = Depends(get_current_user)):
    return next_step_logic(session_id, body.current_item, body.tech_observation)


# ---- Submit findings (Screen 6) ----

@app.post("/sessions/{session_id}/findings")
def submit_findings(session_id: str, body: FindingsRequest, user: Dict = Depends(get_current_user)):
    findings_list = [f.model_dump() for f in body.findings]
    return submit_findings_logic(session_id, findings_list)


# ---- Back-office ----

@app.get("/escalations/pending")
def pending_escalations(user: Dict = Depends(require_role("supervisor"))):
    return {"escalations": get_pending_escalations()}


@app.get("/escalations/{session_id}/status")
def escalation_status(session_id: str, user: Dict = Depends(get_current_user)):
    status = get_escalation_status(session_id)
    if not status:
        raise HTTPException(status_code=404, detail="No escalation found for this session")
    return {
        "status": status.get("status", "pending"),
        "approver_name": status.get("approver_name"),
        "approver_email": status.get("approver_email"),
        "urgency_level": status.get("urgency_level"),
        "instruction": status.get("instruction"),
        "decision": status.get("decision"),
    }


@app.post("/escalations/{session_id}/approve")
def approve_escalation(session_id: str, body: ApprovalRequest, user: Dict = Depends(require_role("supervisor"))):
    timestamp = now()
    save_approval(session_id, user["tech_id"], body.decision, body.instruction, timestamp)
    return {"approval_id": f"APR-{session_id[:8]}", "logged": True, "timestamp": timestamp}


# ---- Audit log ----

@app.get("/sessions/{session_id}/audit-log")
def audit_log_endpoint(session_id: str, user: Dict = Depends(get_current_user)):
    return {"session_id": session_id, "audit_log": get_audit_log(session_id)}


# ---- Offline queue ----

@app.post("/offline/queue")
def queue_request(body: OfflineQueueRequest, user: Dict = Depends(get_current_user)):
    timestamp = now()
    queue_offline_request(
        endpoint=body.endpoint,
        payload=json.dumps(body.payload),
        timestamp=timestamp,
        session_id=body.session_id,
    )
    return {"queued": True, "timestamp": timestamp}


@app.post("/offline/sync")
def sync_offline_queue(body: OfflineSyncRequest, user: Dict = Depends(get_current_user)):
    unsynced = get_unsynced_queue()
    replayed = []
    errors = []

    for item in unsynced:
        try:
            payload = json.loads(item["payload"]) if isinstance(item["payload"], str) else item["payload"]
            sess = item.get("session_id")
            replay_queued_request(sess, item["endpoint"], payload, user=user)
            mark_queue_item_synced(item["event_id"], now())
            replayed.append({"event_id": item["event_id"], "endpoint": item["endpoint"], "session_id": sess})
        except Exception as e:
            errors.append({"event_id": item.get("event_id"), "endpoint": item.get("endpoint"), "error": str(e)})

    supabase_results = []
    if body.sync_to_supabase:
        session_ids = sorted({i.get("session_id") for i in unsynced if i.get("session_id")})
        for sid in session_ids:
            try:
                supabase_results.append(sync_session_to_supabase(sid))
            except Exception as e:
                supabase_results.append({"ok": False, "session_id": sid, "error": str(e)})

    return {
        "replayed_count": len(replayed),
        "errors": errors,
        "supabase": supabase_results[:10],
        "timestamp": now(),
    }


# ---- Manual Supabase sync ----

@app.post("/supabase/sync/{session_id}")
def supabase_sync(session_id: str, user: Dict = Depends(get_current_user)):
    return sync_session_to_supabase(session_id)