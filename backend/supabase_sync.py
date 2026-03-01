# backend/supabase_sync.py
import os
import json
from typing import Dict
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

from database import get_connection

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


def _client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _fetch_all(query: str, params=()):
    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def sync_session_to_supabase(session_id: str) -> Dict:
    """
    Pushes canonical local SQLite data for a session up to Supabase.
    Uses upsert to avoid dupes. Syncs in foreign key dependency order.
    """
    sb = _client()

    # load session first
    sessions = _fetch_all("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
    if not sessions:
        return {"ok": False, "error": "session not found in sqlite"}

    # load user for this session (needed before sessions due to FK)
    tech_id = sessions[0].get("tech_id")
    users = _fetch_all("SELECT * FROM users WHERE tech_id = ?", (tech_id,)) if tech_id else []

    # load remaining tables
    agent_logs = _fetch_all("SELECT * FROM agent_logs WHERE session_id = ?", (session_id,))
    for r in agent_logs:
        try:
            r["output_json"] = json.loads(r["output_json"])
        except Exception:
            r["output_json"] = {"raw": r["output_json"]}

    findings = _fetch_all("SELECT * FROM findings WHERE session_id = ?", (session_id,))
    escalations = _fetch_all("SELECT * FROM escalations WHERE session_id = ?", (session_id,))
    approvals = _fetch_all("SELECT * FROM approvals WHERE session_id = ?", (session_id,))
    offline_queue = _fetch_all("SELECT * FROM offline_queue WHERE session_id = ?", (session_id,))

    for r in offline_queue:
        try:
            r["payload"] = json.loads(r["payload"])
        except Exception:
            r["payload"] = {"raw": r["payload"]}
        r["synced"] = bool(r.get("synced"))

    # push in dependency order: users -> sessions -> everything else
    if users:
        sb.table("users").upsert(users).execute()

    sb.table("sessions").upsert(sessions).execute()

    if agent_logs:
        sb.table("agent_logs").upsert(agent_logs).execute()
    if findings:
        sb.table("findings").upsert(findings).execute()
    if escalations:
        sb.table("escalations").upsert(escalations).execute()
    if approvals:
        sb.table("approvals").upsert(approvals).execute()
    if offline_queue:
        sb.table("offline_queue").upsert(offline_queue).execute()

    return {
        "ok": True,
        "session_id": session_id,
        "counts": {
            "users": len(users),
            "sessions": len(sessions),
            "agent_logs": len(agent_logs),
            "findings": len(findings),
            "escalations": len(escalations),
            "approvals": len(approvals),
            "offline_queue": len(offline_queue),
        }
    }