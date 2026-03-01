# backend/audit_log.py
import json
from datetime import datetime, timezone
from database import log_agent_action

def audit(agent_id: str):
    """
    Decorator that logs every agent action to SQLite (offline-first).
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            timestamp = datetime.now(timezone.utc).isoformat()
            session_id = args[0] if args else kwargs.get("session_id", "unknown")

            input_parts = []
            if len(args) > 1:
                for arg in args[1:]:
                    if isinstance(arg, dict):
                        input_parts.append(str(arg)[:200])
                    elif isinstance(arg, list):
                        input_parts.append(f"list[{len(arg)}]")
                    else:
                        input_parts.append(str(arg)[:100])
            input_summary = " | ".join(input_parts) if input_parts else "no input"

            result = func(*args, **kwargs)

            confidence = None
            if isinstance(result, dict):
                confidence = result.get("confidence")
                if confidence is None and "priorities" in result and result["priorities"]:
                    confidence = result["priorities"][0].get("confidence")

            try:
                log_agent_action(
                    session_id=str(session_id),
                    agent_id=agent_id,
                    timestamp=timestamp,
                    input_summary=input_summary,
                    output_json=json.dumps(result),
                    confidence=confidence,
                )
            except Exception as e:
                print(f"Warning: audit log failed for {agent_id}: {e}")

            return result
        return wrapper
    return decorator