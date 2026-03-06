# PMAdapt: Predictive Maintenance Field Operations & Central Command

**PMAdapt** is a dual-interface, AI-driven Predictive Maintenance platform built for industrial field technicians and facility supervisors. It analyzes sensory observations in real-time to generate operational risk indexes, adapt physical inspection checklists on the fly, and automate safety escalation workflows for heavy machinery (like Cummins QSK60 series generators).

## Key Features
*   **Dual Platforms**: 
    *   **Field Technician App (Mobile-First):** Guides field engineers step-by-step through machine diagnostics using an AI-assisted dynamic checklist.
    *   **Supervisor Dashboard (Central Command):** A tablet/desktop control center providing live telemetry of operational risks, active field escalations, and total audit trails.
*   **Local AI Inference Architecture**: Operates 100% locally on secure hardware using Ollama (`mistral-large-3:675b-cloud` / equivalent) for interpreting fuzzy technician notes without exposing proprietary data to public clouds.
*   **"Dead Zone" Offline Synchronization**: A Service Worker and Local Storage queue allow technicians to continue running inspections deep inside shielded generator rooms where cellular networks drop out. It automatically flushes the local payload to the backend the moment internet is reacquired.
*   **Lightning Demo Mode**: A persistent MD5 hash-cache layer built into the LLM adapter guarantees milliseconds-fast AI responses during rehearsed presentations, bypassing local hardware inference latency while maintaining functional validity.

## Technical Architecture

### 1. The Backend (`/backend`)
A high-performance Python **FastAPI** application handling routing, token authentication, SQLite database operations, and the core Multi-Agent AI orchestration.
*   **Database**: SQLite (`pm_database.db`) storing assets, sessions, tech credentials, findings, and time-stamped audit logs.
*   **Orchestration Agents (`/backend/agents`)**:
    *   `adaptive_checklist.py`: Generates the next best inspection procedure based on the technician's last observation.
    *   `findings_analysis.py`: Computes the Operational Risk Index (0-100) and formulates parts-action plans.
    *   `risk_assessment.py`: Scrapes historical data at the start of a session to build a "Priority Agenda".
    *   `escalation.py`: Triggers human-in-the-loop workflows if a safety threshold is breached (e.g. Red Risk).

### 2. The Frontend (`/frontend`)
A bespoke, dependency-light **Vanilla JavaScript** SPA utilizing Bootstrap 5 for rapid styling but relying completely on raw ES6 DOM manipulation for absolute performance.
*   **Design Language**: Custom CSS Glassmorphism, animated glowing orbs, and distinct Cummins-inspired red accents.
*   **App Logic (`app.js`)**: Core PWA logic, fetching, local caching, and UI routing.
*   **Server**: Hosted locally via a static Python HTTP server proxy.

---

## How to Run Locally

Because PMAdapt utilizes local LLM models and strict static routing, please boot the components in this exact order:

### Prerequisites:
1. Python 3.9+
2. Node/NPM (optional, for tooling)
3. Ollama installed locally with an active model (e.g. `mistral` or `llama3`).

### Step 1: Start the AI Engine
Ensure your local Ollama instance is running in the background. If you need to map it to a specific model name, ensure the `MODEL` variable in `backend/agents/__init__.py` aligns with what you have pulled.

### Step 2: Boot the FastAPI Backend
Open a terminal in the root directory.
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
*Note: The SQLite database `pm_database.db` will automatically seed itself if it does not exist.*

### Step 3: Boot the Frontend Application
Open a **new** terminal window in the root directory.
```bash
cd frontend
python -m http.server 8080
```

### Step 4: Access the Apps
**Technician View:** Open your browser to `http://localhost:8080/index.html`
*   *Default Tech ID:* `T0001`
*   *Default Password:* `cummins123`
*   *Asset ID to Lookup:* `GEN013`

**Supervisor Dashboard:** Click the "Supervisor" toggle on the login screen, or browse to `http://localhost:8080/dashboard.html`
*   *Default Super ID:* `supervisor`
*   *Default Password:* `admin123`

---

## License & Acknowledgements
Built for the Xtern Challenge 2026.
