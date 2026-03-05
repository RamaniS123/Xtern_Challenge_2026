# backend/database.py
import os
import sqlite3
from typing import Optional, List, Dict
from datetime import datetime, timezone
import uuid
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "pmadapt.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # USERS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            tech_id TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'tech',
            created_at TEXT NOT NULL
        )
    """)

    # SESSIONS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            tech_id TEXT NOT NULL,
            status TEXT DEFAULT 'in_progress',
            created_at TEXT NOT NULL,
            closed_at TEXT
        )
    """)

    # AGENT LOGS (decision log)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_logs (
            event_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            input_summary TEXT NOT NULL,
            output_json TEXT NOT NULL,
            confidence REAL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)

    # FINDINGS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS findings (
            event_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            item TEXT NOT NULL,
            observation TEXT NOT NULL,
            safety_level TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)

    # ESCALATIONS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS escalations (
            event_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            approver_name TEXT NOT NULL,
            approver_email TEXT NOT NULL,
            brief_summary TEXT NOT NULL,
            urgency_level TEXT NOT NULL,
            escalation_reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)

    # APPROVALS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS approvals (
            event_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            approver_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            instruction TEXT NOT NULL,
            approved_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)

    # OFFLINE QUEUE
    cur.execute("""
        CREATE TABLE IF NOT EXISTS offline_queue (
            event_id TEXT PRIMARY KEY,
            session_id TEXT,
            endpoint TEXT NOT NULL,
            payload TEXT NOT NULL,
            queued_at TEXT NOT NULL,
            synced INTEGER DEFAULT 0,
            synced_at TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- USERS ----
def upsert_user(tech_id: str, password_hash: str, role: str = "tech"):
    conn = get_connection()
    conn.execute("""
        INSERT INTO users (tech_id, password_hash, role, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(tech_id) DO UPDATE SET
          password_hash=excluded.password_hash,
          role=excluded.role
    """, (tech_id, password_hash, role, now()))
    conn.commit()
    conn.close()


def get_user(tech_id: str) -> Optional[Dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE tech_id = ?", (tech_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---- SESSIONS ----
def create_session(session_id: str, asset_id: str, tech_id: str, timestamp: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO sessions (session_id, asset_id, tech_id, created_at) VALUES (?, ?, ?, ?)",
        (session_id, asset_id, tech_id, timestamp),
    )
    conn.commit()
    conn.close()


# ---- AGENT LOGS ----
def log_agent_action(session_id: str, agent_id: str, timestamp: str, input_summary: str, output_json: str, confidence: float):
    conn = get_connection()
    event_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO agent_logs (event_id, session_id, agent_id, timestamp, input_summary, output_json, confidence) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (event_id, session_id, agent_id, timestamp, input_summary, output_json, confidence),
    )
    conn.commit()
    conn.close()


# ---- FINDINGS ----
def save_findings(session_id: str, findings: List[Dict], timestamp: str):
    conn = get_connection()
    for f in findings:
        event_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO findings (event_id, session_id, item, observation, safety_level, submitted_at) VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, session_id, f["item"], f["observation"], f["safety_level"], timestamp),
        )
    conn.commit()
    conn.close()


# ---- ESCALATIONS ----
def create_escalation(session_id: str, approver_name: str, approver_email: str, brief_summary: str, urgency_level: str, escalation_reason: str, timestamp: str, operational_risk_index: int = 0):
    conn = get_connection()
    # Add operational_risk_index column if it doesn't exist (migration)
    try:
        conn.execute("ALTER TABLE escalations ADD COLUMN operational_risk_index INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass  # Column already exists
    event_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO escalations (event_id, session_id, approver_name, approver_email, brief_summary, urgency_level, escalation_reason, created_at, operational_risk_index)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_id, session_id, approver_name, approver_email, brief_summary, urgency_level, escalation_reason, timestamp, operational_risk_index),
    )
    conn.commit()
    conn.close()


def get_escalation_status(session_id: str) -> Dict:
    conn = get_connection()
    row = conn.execute("""
        SELECT e.*, a.instruction, a.approver_id, a.decision
        FROM escalations e
        LEFT JOIN approvals a ON e.session_id = a.session_id
        WHERE e.session_id = ?
        ORDER BY e.created_at DESC LIMIT 1
    """, (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def save_approval(session_id: str, approver_id: str, decision: str, instruction: str, timestamp: str):
    conn = get_connection()
    conn.execute("UPDATE escalations SET status = 'approved' WHERE session_id = ?", (session_id,))
    event_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO approvals (event_id, session_id, approver_id, decision, instruction, approved_at) VALUES (?, ?, ?, ?, ?, ?)",
        (event_id, session_id, approver_id, decision, instruction, timestamp),
    )
    conn.execute("UPDATE sessions SET status = 'closed', closed_at = ? WHERE session_id = ?", (timestamp, session_id))
    conn.commit()
    conn.close()


def get_pending_escalations() -> List[Dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT e.*, s.asset_id, s.tech_id
        FROM escalations e
        JOIN sessions s ON e.session_id = s.session_id
        WHERE e.status = 'pending'
        ORDER BY e.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sessions_for_tech(tech_id: str) -> List[Dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT 
            s.session_id, 
            s.asset_id, 
            s.tech_id, 
            s.created_at,
            s.status as session_status,
            e.status as escalation_status,
            e.brief_summary,
            e.operational_risk_index,
            e.urgency_level,
            a.decision,
            a.instruction,
            a.approved_at,
            (SELECT COUNT(*) FROM findings f WHERE f.session_id = s.session_id) as total_findings,
            (SELECT COUNT(*) FROM findings f WHERE f.session_id = s.session_id AND f.safety_level IN ('YELLOW', 'RED', 'ORANGE')) as issue_findings
        FROM sessions s
        LEFT JOIN escalations e ON s.session_id = e.session_id
        LEFT JOIN approvals a ON s.session_id = a.session_id
        WHERE s.tech_id = ? AND (SELECT COUNT(*) FROM findings f WHERE f.session_id = s.session_id) > 0
        ORDER BY s.created_at DESC
    """, (tech_id,)).fetchall()
    conn.close()
    
    results = []
    for r in rows:
        d = dict(r)
        
        # Calculate display status based on escalation presence
        if d["escalation_status"] == "pending":
            d["display_status"] = "pending"
        elif d["escalation_status"] == "approved":
            d["display_status"] = "approved"
        else:
            d["display_status"] = "completed"
            
        # Synthesize summary
        total = d.get("total_findings", 0)
        issues = d.get("issue_findings", 0)
        
        if d["brief_summary"]:
            d["display_summary"] = f"Inspection found {issues} issues out of {total} checked items. Action needed: {d['brief_summary']}"
        elif total > 0 and issues > 0:
            d["display_summary"] = f"Inspection complete: {issues} issues identified across {total} items."
        elif total > 0 and issues == 0:
            d["display_summary"] = f"Perfect inspection! {total} items checked, 0 issues found. Setup is running flawlessly."
        else:
            d["display_summary"] = "Routine inspection completed. No findings reported."
            
        results.append(d)
        
    return results


def get_audit_log(session_id: str) -> List[Dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM agent_logs WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---- OFFLINE QUEUE ----
def queue_offline_request(endpoint: str, payload: str, timestamp: str, session_id: Optional[str] = None):
    conn = get_connection()
    event_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO offline_queue (event_id, session_id, endpoint, payload, queued_at) VALUES (?, ?, ?, ?, ?)",
        (event_id, session_id, endpoint, payload, timestamp),
    )
    conn.commit()
    conn.close()


def get_unsynced_queue() -> List[Dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM offline_queue WHERE synced = 0 ORDER BY queued_at ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_queue_item_synced(event_id: str, timestamp: str):
    conn = get_connection()
    conn.execute(
        "UPDATE offline_queue SET synced = 1, synced_at = ? WHERE event_id = ?",
        (timestamp, event_id),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()