import json
import time
from typing import Any, Dict, Optional

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.1:8b"

def call_llm(prompt: str, timeout_s: int = 30, retries: int = 0) -> Dict[str, Any]:
    """
    Calls Ollama chat endpoint and expects JSON-only output from the model.
    Adds:
      - timeout control
      - retries
      - consistent error payload on failure
    """
    last_err: Optional[str] = None

    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
                timeout=timeout_s,
            )
            resp.raise_for_status()
            raw = resp.json()

            # handle both response formats Ollama might return
            if "message" in raw and isinstance(raw["message"], dict):
                content = raw["message"].get("content", "")
            elif "response" in raw:
                content = raw.get("response", "")
            else:
                return {"error": "unexpected_response_format", "raw": raw}

            content = (content or "").replace("```json", "").replace("```", "").strip()

            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    return parsed
                return {"error": "non_object_json", "raw": parsed}
            except json.JSONDecodeError:
                return {"error": "parsing_failed", "raw": content}

        except Exception as e:
            last_err = str(e)
            if attempt < retries:
                time.sleep(0.4)
                continue

    return {"error": "request_failed", "detail": last_err or "unknown_error"}