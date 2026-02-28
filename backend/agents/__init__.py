import json
import time
from typing import Any, Dict, Optional

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.1:8b"


def call_llm(
    prompt: str,
    timeout_s: int = 30,
    retries: int = 0,
) -> Dict[str, Any]:
    """
    Calls Ollama /api/chat and expects JSON in the assistant content.
    Adds timeout + retries to prevent demo crashes.
    """
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    last_err: Optional[str] = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout_s)
            resp.raise_for_status()
            raw = resp.json()

            # handle both response formats Ollama might return
            if "message" in raw and raw["message"] and "content" in raw["message"]:
                content = raw["message"]["content"]
            elif "response" in raw:
                content = raw["response"]
            else:
                return {"error": "unexpected_response_format", "raw": raw}

            # strip codefence
            content = content.replace("```json", "").replace("```", "").strip()

            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"error": "parsing_failed", "raw": content}

        except requests.exceptions.RequestException as e:
            last_err = str(e)
            if attempt < retries:
                time.sleep(0.5)
                continue
            return {"error": "request_failed", "detail": last_err}

    return {"error": "request_failed", "detail": last_err or "unknown"}