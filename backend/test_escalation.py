import urllib.request, json, sys

BASE = "http://localhost:8000"

def api(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode())
    except Exception as e:
        return getattr(e, 'code', 0), str(e)

# 1. Login as tech
print("=== STEP 1: Login tech ===")
s, r = api("POST", "/auth/login", {"tech_id": "T0001", "password": "cummins123"})
print(f"Status: {s}")
if s == 200:
    token = r["access_token"]
    print("Token acquired")
else:
    print("LOGIN FAILED:", r)
    sys.exit(1)

# 2. Start session
print("\n=== STEP 2: Start session GEN013 ===")
s, r = api("POST", "/sessions/start", {"asset_id": "GEN013"}, token)
print(f"Status: {s}")
if s == 200:
    session_id = r["session_id"]
    print("Session ID:", session_id)
    print("Priority agenda items:", len(r.get("priority_agenda", [])))
else:
    print("SESSION START FAILED:", r)
    sys.exit(1)

# 3. Submit ONE finding with a RED safety level to trigger escalation
print("\n=== STEP 3: Submit findings (RED) ===")
findings = [
    {"item": "battery", "observation": "Battery voltage 11.2V, white powder on terminals, clicked load test", "safety_level": "red"},
    {"item": "cooling", "observation": "Coolant looks low", "safety_level": "yellow"},
    {"item": "air_intake", "observation": "Air filter slightly dirty", "safety_level": "green"},
]
s, r = api("POST", f"/sessions/{session_id}/findings", {"findings": findings}, token)
print(f"Status: {s}")
if s == 200:
    print("ORI:", r.get("operational_risk_index"))
    print("Status:", r.get("operational_status"))
    print("Clearance:", r.get("site_clearance"))
    print("Escalation required:", r.get("escalation_required"))
    print("Escalation reason:", r.get("escalation_reason"))
    print("Escalation details:", r.get("escalation_details"))
else:
    print("FINDINGS FAILED:", r)
    sys.exit(1)

# 4. Check escalation status (tech side)
print("\n=== STEP 4: Check escalation status ===")
s, r = api("GET", f"/escalations/{session_id}/status", token=token)
print(f"Status: {s}")
print("Response:", json.dumps(r, indent=2))

# 5. Login as supervisor
print("\n=== STEP 5: Login supervisor ===")
s, r = api("POST", "/auth/login", {"tech_id": "supervisor", "password": "admin123"})
print(f"Status: {s}")
if s == 200:
    sup_token = r["access_token"]
    print("Supervisor token acquired. Role:", r.get("role"))
else:
    print("SUPERVISOR LOGIN FAILED:", r)
    sys.exit(1)

# 6. Get pending escalations
print("\n=== STEP 6: Get pending escalations ===")
s, r = api("GET", "/escalations/pending", token=sup_token)
print(f"Status: {s}")
print("Response:", json.dumps(r, indent=2))
