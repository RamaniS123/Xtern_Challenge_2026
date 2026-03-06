import json
import time
import hashlib
import os
from typing import Any, Dict, Optional

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "mistral-large-3:675b-cloud"
LLM_CACHE_FILE = "llm_cache.json"

def _load_cache() -> Dict[str, Any]:
    if os.path.exists(LLM_CACHE_FILE):
        try:
            with open(LLM_CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def _save_cache(cache_data: Dict[str, Any]):
    try:
        with open(LLM_CACHE_FILE, "w") as f:
            json.dump(cache_data, f)
    except:
        pass

def call_llm(prompt: str, timeout_s: int = 30, retries: int = 0) -> Dict[str, Any]:
    """
    Calls Ollama chat endpoint and expects JSON-only output from the model.
    Adds:
      - persistent caching for instantaneous demo speeds
      - timeout control
      - retries
      - consistent error payload on failure
    """
    # 1. Check persistent cache
    prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()
    cache = _load_cache()
    if prompt_hash in cache:
        print(f"[CACHE HIT] Returning instant AI response for prompt.")
        # Artificial tiny delay just to show a micro-loading state on frontend, rather than jarring 0ms
        time.sleep(0.5) 
        return cache[prompt_hash]

    print(f"[CACHE MISS] Executing real AI inference...")
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
                    # 2. Save structural dict to cache
                    cache[prompt_hash] = parsed
                    _save_cache(cache)
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