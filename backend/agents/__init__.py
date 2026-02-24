import requests
import json

def call_llm(prompt):
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "llama3.1:8b",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
    )
    content = response.json()["message"]["content"]
    content = content.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": "parsing_failed", "raw": content}