import requests
import json

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.1:8b"

def call_llm(prompt: str) -> dict:
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    })
    
 
    raw = response.json()
    
    # handle both response formats Ollama might return
    if "message" in raw:
        content = raw["message"]["content"]
    elif "response" in raw:
        content = raw["response"]
    else:
        print(f"Unexpected response format: {raw}")
        return {"error": "unexpected_response_format", "raw": raw}
    
    content = content.replace("```json", "").replace("```", "").strip()
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": "parsing_failed", "raw": content}