/**
 * PMAdapt - Tech Field App Logic
 */

const BASE_URL = `http://${window.location.hostname || 'localhost'}:8000`;
const MOCK_MODE = false; // Set to true to use mock backend

// Single Global State
const state = {
    token: null,
    role: null,
    tech_id: null,
    session_id: null,
    agenda: [],
    currentCategoryIndex: 0,
    stepIndex: 0,
    stepCount: 0,
    observations: [],
    lastChecklist: null,
    escalationTimer: null,
};

// --- API Helper & Mock Data ---

async function apiFetch(endpoint, options = {}) {
    const method = options.method || "GET";
    const isAuth = options.auth !== false; // Default true

    // Mock Mode Intercept
    if (MOCK_MODE) {
        console.log(`[MOCK API] ${method} ${endpoint}`, options.body || "");
        return new Promise((resolve) => {
            setTimeout(() => resolve(getMockResponse(method, endpoint, options.body)), 600);
        });
    }

    const headers = { "Content-Type": "application/json" };
    if (isAuth && state.token) {
        headers["Authorization"] = `Bearer ${state.token}`;
    }

    const fetchOptions = { method, headers };

    if (options.body !== undefined) {
        fetchOptions.body = JSON.stringify(options.body);
    }

    try {
        const response = await fetch(`${BASE_URL}${endpoint}`, fetchOptions);

        const contentType = response.headers.get("content-type") || "";
        const isJson = contentType.includes("application/json");

        // 401: force logout and show real backend message if available
        if (response.status === 401) {
            let msg = "Session expired. Please sign in again.";
            if (isJson) {
                try {
                    const errJson = await response.json();
                    msg = errJson?.detail || errJson?.message || msg;
                } catch (_) { }
            } else {
                try {
                    const txt = await response.text();
                    if (txt) msg = txt;
                } catch (_) { }
            }

            handleLogout(msg);
            throw new Error(msg);
        }

        // Non-OK: extract backend message
        if (!response.ok) {
            let msg = `API Error: ${response.status}`;

            if (isJson) {
                try {
                    const errJson = await response.json();
                    msg = errJson?.detail || errJson?.message || msg;
                } catch (_) { }
            } else {
                try {
                    const txt = await response.text();
                    if (txt) msg = txt;
                } catch (_) { }
            }

            throw new Error(msg);
        }

        // Success
        return isJson ? await response.json() : await response.text();
    } catch (error) {
        console.error("Fetch error:", error);

        // offline interception
        if (!navigator.onLine) {
            showToast("Offline Mode", "Saved securely to local sync queue.", "warning");

            // Queue state-mutating requests
            if (method !== "GET") {
                const queue = JSON.parse(localStorage.getItem("pm_sync_queue") || "[]");
                queue.push({ endpoint, options, timestamp: Date.now() });
                localStorage.setItem("pm_sync_queue", JSON.stringify(queue));
            }

            // Return mock structural data so UI flow can proceed perfectly
            return getMockResponse(method, endpoint, options.body);
        }
        // backend down/unreachable
        else if (error?.name === "TypeError") {
            showToast(
                "Server Unreachable",
                "Backend not reachable. Is FastAPI running on http://localhost:8000?",
                "danger"
            );
        }
        // real error
        else {
            showToast("Request Failed", error.message || "Something went wrong.", "danger");
        }

        throw error;
    }
}

// Background Sync Function
async function syncQueue() {
    const queue = JSON.parse(localStorage.getItem("pm_sync_queue") || "[]");
    if (queue.length === 0) return;

    showToast("Back Online", "Syncing offline data...", "info");
    const failedQueue = [];

    for (const req of queue) {
        try {
            await apiFetch(req.endpoint, req.options);
        } catch (e) {
            console.error("Failed to sync offine request:", req, e);
            failedQueue.push(req);
        }
    }

    localStorage.setItem("pm_sync_queue", JSON.stringify(failedQueue));
    if (failedQueue.length === 0) {
        showToast("Sync Complete", "All offline data sent securely.", "success");
    } else {
        showToast("Sync Partial", "Some offline tasks failed. Will retry later.", "warning");
    }
}

window.addEventListener('online', syncQueue);

// Network Status UI Updates
function updateNetworkIndicator() {
    const badge = document.getElementById('navNetworkBadge');
    const icon = document.getElementById('navNetworkIcon');
    const text = document.getElementById('navNetworkText');
    const offlineAlert = document.getElementById('offlineBadge');

    if (!badge || !icon || !text) return;

    if (navigator.onLine) {
        badge.classList.remove('bg-danger');
        badge.classList.add('bg-success');
        icon.className = icon.className.replace('bi-wifi-off', 'bi-wifi');
        text.textContent = 'Online';
        if (offlineAlert) offlineAlert.style.display = 'none';

        // Minor pulse effect
        badge.style.boxShadow = '0 0 15px rgba(25, 135, 84, 0.5)';
        setTimeout(() => badge.style.boxShadow = '', 2000);
    } else {
        badge.classList.remove('bg-success');
        badge.classList.add('bg-danger');
        icon.className = icon.className.replace('bi-wifi', 'bi-wifi-off');
        text.textContent = 'Offline';
        if (offlineAlert) offlineAlert.style.display = 'block';

        badge.style.boxShadow = '0 0 15px rgba(220, 53, 69, 0.5)';
    }
}

window.addEventListener('online', updateNetworkIndicator);
window.addEventListener('offline', updateNetworkIndicator);

// Call once on load
document.addEventListener("DOMContentLoaded", () => {
    updateNetworkIndicator();
});

function getMockResponse(method, endpoint, body) {
    // body is already an object in MOCK_MODE
    if (endpoint === "/auth/login") {
        return {
            access_token: "mock_jwt_token_123",
            token_type: "bearer",
            tech_id: body.tech_id,
            role: body.tech_id === "supervisor" ? "supervisor" : "tech",
        };
    }

    if (endpoint.startsWith("/sessions/start")) {
        return {
            session_id: "SESS-" + Math.floor(Math.random() * 10000),
            asset_summary: "Cummins QSK60 Series Generator. Primary backup for Sector 4.",
            pre_visit_summary:
                "Last PM was generic visual inspection. Historical alerts show slight voltage drop.",
            hours_overdue: 142,
            priority_agenda: [
                { rank: 1, category: "battery", reason: "Voltage decay trend", confidence: 0.92 },
                { rank: 2, category: "cooling", reason: "Standard interval", confidence: 0.85 },
                { rank: 3, category: "fuel", reason: "Low priority check", confidence: 0.6 },
            ],
        };
    }

    if (endpoint.match(/\/checklist\/(.*?)\/step\/(\d+)/)) {
        const match = endpoint.match(/\/checklist\/(.*?)\/step\/(\d+)/);
        const category = match[1];
        const stepIdx = parseInt(match[2], 10);

        const counts = { battery: 3, cooling: 2, fuel: 1 };
        const count = counts[category] || 2;

        const tasks = {
            battery: [
                {
                    task: "Check battery terminals for corrosion.",
                    norm: "Clean, tight, >12.4V",
                    abn: "White powder, loose, <12.4V",
                },
                { task: "Measure resting voltage.", norm: ">= 12.4V", abn: "< 12.4V" },
                {
                    task: "Inspect casing for bulging.",
                    norm: "Smooth, normal shape",
                    abn: "Swollen, cracked, leaking",
                },
            ],
        };

        const taskData = tasks[category]
            ? tasks[category][stepIdx]
            : { task: `General inspect ${category} part ${stepIdx + 1}`, norm: "Looks good", abn: "Looks bad" };

        return {
            task: taskData.task,
            normal_hint: taskData.norm,
            abnormal_hint: taskData.abn,
            step_index: stepIdx,
            step_count: count,
        };
    }

    if (endpoint.includes("/next-step")) {
        const obsText = (body?.tech_observation || "").toLowerCase();

        if (obsText.includes("powder") || obsText.includes("corrosion") || obsText.includes("abnormal")) {
            return {
                follow_up_required: true,
                next_step:
                    "1. Photograph corrosion\n2. Disconnect negative terminal first\n3. Clean with baking soda or wire brush",
                instruction: "Safety Risk Identified. Mandatory cleaning required before proceeding.",
                safety_level: "red",
                confidence: 0.95,
            };
        }

        return {
            follow_up_required: false,
            next_step: "Proceed to next checklist item.",
            instruction: "Observation logged. Within normal parameters.",
            safety_level: "green",
            confidence: 0.88,
        };
    }

    if (endpoint.includes("/findings")) {
        const findings = body?.findings || [];
        const hasRed = findings.some((f) => f.safety_level === "red");

        return {
            operational_risk_index: hasRed ? 78 : 12,
            status: hasRed ? "NOT_READY" : "READY",
            clearance_decision: hasRed ? "DO_NOT_RELEASE" : "CLEARED",
            escalation_required: hasRed,
            escalation_reason: hasRed
                ? "High operational risk detected via critical safety level findings."
                : null,
            approver: "Sarah Jenkins (Senior Foreman)",
            risk_breakdown: [
                { factor: "Battery Integrity", contribution: hasRed ? "+45" : "+2" },
                { factor: "Maintenance Delay", contribution: "+10" },
                { factor: "Usage Profile", contribution: "+23" },
            ],
            action_plan: hasRed
                ? [
                    {
                        issue: "Battery Terminal Corrosion",
                        urgency: "high",
                        recommended_action: "Deep clean and test charging system. Replace if failing.",
                        parts_needed: "main_battery_12V",
                        stock_status: "in-stock",
                    },
                ]
                : [
                    {
                        issue: "Routine Wear",
                        urgency: "low",
                        recommended_action: "Monitor.",
                        parts_needed: "none",
                        stock_status: "n/a",
                    },
                ],
        };
    }

    if (endpoint.includes("/status")) {
        return {
            status: Math.random() > 0.7 ? "approved" : "pending",
            instruction:
                "Replace main_battery_12V immediately, run 5-min load test, then clear to operate.",
        };
    }

    return {};
}

// --- DOM Utilities & State ---

function showScreen(screenId) {
    document.querySelectorAll(".app-screen").forEach((el) => el.classList.remove("active"));
    document.getElementById(screenId).classList.add("active");
    window.scrollTo(0, 0);
}

function showLoader(title = "Loading...", subtitle = "") {
    document.getElementById("loadingOverlay").classList.add("active");
    const titleEl = document.getElementById("loadingOverlay").querySelector(".loader-title");
    const subtitleEl = document.getElementById("loadingOverlay").querySelector(".loader-subtitle");

    // Clear any existing interval
    if (state.loaderInterval) {
        clearInterval(state.loaderInterval);
        state.loaderInterval = null;
    }

    if (Array.isArray(title)) {
        if (titleEl) titleEl.textContent = title[0];
        let i = 1;
        state.loaderInterval = setInterval(() => {
            if (titleEl) {
                // Add a small fade effect by toggling a fast CSS class if possible, or just swap text
                titleEl.textContent = title[i % title.length];
            }
            i++;
        }, 3500);
    } else {
        if (titleEl) titleEl.textContent = title;
    }

    if (subtitleEl) {
        if (subtitle) {
            subtitleEl.textContent = subtitle;
            subtitleEl.classList.remove("d-none");
        } else {
            subtitleEl.classList.add("d-none");
        }
    }
}

function hideLoader() {
    if (state.loaderInterval) {
        clearInterval(state.loaderInterval);
        state.loaderInterval = null;
    }
    document.getElementById("loadingOverlay").classList.remove("active");
}

function showToast(title, message, color = "primary") {
    const toastContainer = document.querySelector(".toast-container");
    if (!toastContainer) {
        // fallback if container missing
        alert(`${title}\n\n${message}`);
        return;
    }

    const id = "toast-" + Date.now();
    const html = `
    <div id="${id}" class="toast align-items-center text-bg-${color} border-0 mb-2" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body fw-medium">
          <strong>${title}</strong><br>${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>
  `;
    toastContainer.insertAdjacentHTML("beforeend", html);

    const toastEl = document.getElementById(id);
    const bsToast = new bootstrap.Toast(toastEl, { delay: 4500 });
    bsToast.show();

    toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
}

// --- App Flow Implementation ---

async function loadHistory() {
    const listEl = document.getElementById("historyList");
    try {
        const res = await apiFetch("/sessions/history/me", { auth: true });
        const sessions = res.sessions || [];

        if (sessions.length === 0) {
            listEl.innerHTML = `
                <div class="text-center p-5 text-muted opacity-50">
                    <i class="bi bi-journal-text fs-1 mb-3"></i>
                    <p>No past inspections found.</p>
                </div>`;
            return;
        }

        listEl.innerHTML = sessions.map(s => {
            const date = new Date(s.created_at).toLocaleDateString();
            const time = new Date(s.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            let badgeClass = "bg-secondary";
            let statusText = "Completed";
            let icon = `<i class="bi bi-check-circle"></i>`;

            if (s.display_status === "approved") {
                badgeClass = "bg-success";
                statusText = "Approved";
                icon = `<i class="bi bi-shield-check"></i>`;
            } else if (s.display_status === "pending") {
                badgeClass = "bg-warning";
                statusText = "Pending Review";
                icon = `<i class="bi bi-hourglass-split"></i>`;
            } else if (s.display_status === "not_ready") {
                badgeClass = "bg-danger";
                statusText = "Not Ready";
                icon = `<i class="bi bi-x-circle-fill"></i>`;
            }

            return `
              <div class="card mb-3 history-card glass-card p-3" onclick="toggleHistoryDetail('${s.session_id}')">
                <div class="d-flex justify-content-between align-items-center mb-2">
                  <span class="fw-bold fs-5 text-light tracking-tight">${s.asset_id} <i id="icon-${s.session_id}" class="bi bi-chevron-down ms-1 fs-6 text-muted"></i></span>
                  <span class="badge w-25 ${badgeClass} bg-opacity-10 text-${badgeClass.replace('bg-', '')} border border-${badgeClass.replace('bg-', '')} border-opacity-25 px-3 py-2 rounded-pill d-flex align-items-center justify-content-center gap-1">${icon} ${statusText}</span>
                </div>
                <div class="d-flex justify-content-between text-muted small mt-2">
                  <span><i class="bi bi-calendar3 me-1 text-primary"></i> ${date} · ${time}</span>
                  <span><i class="bi bi-shield-exclamation me-1 text-primary"></i> Risk: <strong class="${s.operational_risk_index > 50 ? 'text-danger' : s.operational_risk_index > 20 ? 'text-warning' : 'text-success'}">${s.operational_risk_index || 0}</strong></span>
                </div>
                <div id="hist-${s.session_id}" class="d-none mt-3 pt-3 border-top border-secondary">
                  <p class="small text-light mb-1"><strong class="text-primary tracking-wide text-uppercase" style="font-size:0.75rem;"><i class="bi bi-robot me-1"></i>AI Summary:</strong></p>
                  <p class="small text-muted mb-3" style="line-height:1.5;">${s.display_summary || 'Routine inspection completed. No escalation required.'}</p>
                  
                  <p class="small text-light mb-1"><strong class="text-primary tracking-wide text-uppercase" style="font-size:0.75rem;"><i class="bi bi-chat-left-text me-1"></i>Supervisor Notes:</strong></p>
                  <p class="small text-muted mb-0" style="line-height:1.5;">${s.instruction ? formatBulletList(s.instruction) : 'No special instructions provided.'}</p>
                </div>
              </div>
            `;
        }).join("");

    } catch (err) {
        console.error("History fetch failed:", err);
        listEl.innerHTML = `< div class="alert alert-danger mx-3" > Failed to load history: ${err.message}</div > `;
    }
}

window.toggleHistoryDetail = (sessionId) => {
    const detail = document.getElementById(`hist-${sessionId}`);
    const icon = document.getElementById(`icon-${sessionId}`);
    if (!detail) return;

    if (detail.classList.contains("d-none")) {
        detail.classList.remove("d-none");
        if (icon) icon.classList.replace("bi-chevron-down", "bi-chevron-up");
    } else {
        detail.classList.add("d-none");
        if (icon) icon.classList.replace("bi-chevron-up", "bi-chevron-down");
    }
};

async function initApp() {
    window.addEventListener("online", () => document.body.classList.remove("offline"));
    window.addEventListener("offline", () => document.body.classList.add("offline"));
    if (!navigator.onLine) document.body.classList.add("offline");

    // Register SW
    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("./sw.js").catch((err) => console.log("SW registration failed:", err));
    }

    // Check auth — also validate the token is still accepted by backend
    const savedToken = localStorage.getItem("pm_token");
    const savedRole = localStorage.getItem("pm_role");

    if (savedToken) {
        // Client-side JWT expiry check — no network call needed
        try {
            const payload = JSON.parse(atob(savedToken.split('.')[1]));
            const isExpired = payload.exp && (Date.now() / 1000) > payload.exp;
            if (isExpired) {
                console.warn("[AUTH] Stored token is expired. Forcing re-login.");
                localStorage.clear();
                showScreen("screen-login");
                showToast("Session Expired", "Your session expired. Please log in again.", "warning");
                setupEventListeners();
                return;
            }
        } catch (_) {
            console.warn("[AUTH] Could not decode token. Clearing and forcing re-login.");
            localStorage.clear();
            showScreen("screen-login");
            setupEventListeners();
            return;
        }

        state.token = savedToken;
        state.role = savedRole;
        state.tech_id = localStorage.getItem("pm_tech_id");

        if (state.role === "supervisor") {
            window.location.href = "dashboard.html";
            return;
        }

        document.getElementById("mainNav").classList.remove("d-none");
        showScreen("screen-asset");
        startTechNotificationPoller();
    } else {
        showScreen("screen-login");
    }

    setupEventListeners();
}

function startTechNotificationPoller() {
    if (state.notificationPoller) clearInterval(state.notificationPoller);

    state.notificationPoller = setInterval(async () => {
        try {
            const res = await apiFetch("/sessions/history/me", { auth: true });
            const sessions = res.sessions || [];
            const approvedSessions = sessions.filter(s => s.display_status === "approved");

            if (state.knownApprovedCounts === undefined) {
                // Initial load baseline - do not notify
                state.knownApprovedCounts = approvedSessions.length;
                return;
            }

            if (approvedSessions.length > state.knownApprovedCounts) {
                // New approval detected!
                const newUpdates = approvedSessions.length - state.knownApprovedCounts;
                state.knownApprovedCounts = approvedSessions.length;

                const btnHistory = document.getElementById("btnHistory");
                const existingBadge = btnHistory.querySelector('.badge-notification');
                if (existingBadge) {
                    existingBadge.textContent = parseInt(existingBadge.textContent || 0) + newUpdates;
                } else {
                    btnHistory.innerHTML += `<span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger border border-light badge-notification" style="font-size: 0.65rem;">${newUpdates}</span>`;
                    btnHistory.classList.add('position-relative');
                }
                showToast("Supervisor Update", "A pending escalation has just been approved!", "success");
            }
        } catch (e) {
            console.warn("Notification poll failed:", e);
        }
    }, 5000);
}

function setupEventListeners() {
    // SCREEN 1: Login
    document.getElementById("loginForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const pid = document.getElementById("loginTechId").value.trim();
        const pwd = document.getElementById("loginPassword").value;

        showLoader();
        try {
            const res = await apiFetch("/auth/login", {
                method: "POST",
                auth: false,
                body: { tech_id: pid, password: pwd },
            });

            localStorage.setItem("pm_token", res.access_token);
            localStorage.setItem("pm_role", res.role);
            localStorage.setItem("pm_tech_id", res.tech_id);

            state.token = res.access_token;
            state.role = res.role;
            state.tech_id = res.tech_id;

            if (res.role === "supervisor") {
                window.location.href = "dashboard.html?v=" + new Date().getTime();
            } else {
                document.getElementById("mainNav").classList.remove("d-none");
                showScreen("screen-asset");
            }
        } catch (err) {
            showToast("Login Failed", err.message || "Login failed.", "danger");
        } finally {
            hideLoader();
        }
    });

    // Role Switcher & Demo Fill Logic
    const roleTech = document.getElementById("roleTech");
    const roleSuper = document.getElementById("roleSuper");
    const loginIdLabel = document.getElementById("loginIdLabel");
    const loginTechId = document.getElementById("loginTechId");
    const loginPassword = document.getElementById("loginPassword");
    const userIcon = document.getElementById("loginUserIcon");

    function updateRoleUI() {
        if (!roleTech || !roleSuper) return;

        if (roleSuper.checked) {
            loginIdLabel.textContent = "SUPERVISOR ID";
            loginIdLabel.classList.add("text-primary");
            loginTechId.placeholder = "e.g. supervisor";
            userIcon.classList.replace("bi-person", "bi-shield-lock");

            // Fast fill testing credentials
            loginTechId.value = "supervisor";
            loginPassword.value = "admin123";

            document.querySelector('[for="roleTech"]').classList.add("text-muted");
            document.querySelector('[for="roleSuper"]').classList.remove("text-muted");
        } else {
            loginIdLabel.textContent = "TECHNICIAN ID";
            loginIdLabel.classList.remove("text-primary");
            loginTechId.placeholder = "e.g. T0001";
            userIcon.classList.replace("bi-shield-lock", "bi-person");

            // Fast fill testing credentials
            loginTechId.value = "T0001";
            loginPassword.value = "cummins123";

            document.querySelector('[for="roleSuper"]').classList.add("text-muted");
            document.querySelector('[for="roleTech"]').classList.remove("text-muted");
        }
    }

    if (roleTech && roleSuper) {
        roleTech.addEventListener("change", updateRoleUI);
        roleSuper.addEventListener("change", updateRoleUI);
        updateRoleUI(); // Initialize on load
    }

    // Navbar
    document.getElementById("btnLogout").addEventListener("click", () => {
        localStorage.clear();
        window.location.href = "index.html?v=" + new Date().getTime();
    });

    document.getElementById("btnHistory").addEventListener("click", () => {
        const btnHistory = document.getElementById("btnHistory");
        const badge = btnHistory.querySelector('.badge-notification');
        if (badge) badge.remove();
        btnHistory.classList.remove('position-relative');

        loadHistory();
        showScreen("screen-history");
    });

    document.getElementById("btnBackFromHistory").addEventListener("click", () => {
        showScreen("screen-asset");
    });

    // SCREEN 2: Asset Entry
    document.getElementById("assetForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const aid = document.getElementById("assetId").value.trim();
        console.log("[LOOKUP] Triggered for asset:", aid);
        console.log("[LOOKUP] Token present:", !!state.token, "| Token prefix:", state.token ? state.token.substring(0, 20) + '...' : 'NONE');

        if (!aid) {
            showToast("Missing Asset ID", "Please enter an asset ID.", "warning");
            return;
        }
        if (!state.token) {
            showToast("Not logged in", "Your session may have expired. Please log out and log back in.", "danger");
            return;
        }

        showLoader("Running AI Risk Assessment...", "This may take up to 1-2 minutes.");
        try {
            console.log("[LOOKUP] Calling /sessions/start ...");
            const res = await apiFetch("/sessions/start", {
                method: "POST",
                body: { asset_id: aid },
            });
            console.log("[LOOKUP] Response received:", res);

            state.session_id = res.session_id;
            state.agenda = res.priority_agenda || [];
            state.currentCategoryIndex = 0;
            state.observations = [];

            document.getElementById("assetHoursOverdue").textContent = res.hours_overdue ?? "-";
            document.getElementById("assetSummary").textContent = `${res.asset_summary || ""} ${res.pre_visit_summary || ""} `.trim();

            const agendaEl = document.getElementById("priorityAgendaList");
            agendaEl.innerHTML = "";
            (res.priority_agenda || []).forEach((cat, idx) => {
                agendaEl.innerHTML += `
                <div class="card bg-dark border-secondary mb-3 list-item-card glass-card shadow-sm">
                    <div class="card-body p-3">
                        <!-- Header -->
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <div>
                                <span class="badge bg-secondary me-2 rounded-pill px-2 py-1">${idx + 1}</span>
                                <span class="text-light fw-bold text-capitalize fs-6">${String(cat.category || "").replace("_", " ")}</span>
                            </div>
                            <div class="text-end">
                                <span class="text-danger small fw-bold d-block mb-1">${((cat.confidence || 0) * 100).toFixed(0)}% AI Confidence</span>
                            </div>
                        </div>
                        
                        <!-- Progress Bar -->
                        <div class="progress mb-3" style="height: 6px; background-color: var(--pm-border);">
                            <div class="progress-bar bg-danger progress-bar-striped progress-bar-animated" role="progressbar" style="width: ${((cat.confidence || 0) * 100).toFixed(0)}%; opacity: 0.9;" aria-valuenow="${((cat.confidence || 0) * 100).toFixed(0)}" aria-valuemin="0" aria-valuemax="100"></div>
                        </div>

                        <!-- AI Reason Insight Box -->
                        <div class="d-flex align-items-start bg-danger bg-opacity-10 rounded p-2 border border-danger border-opacity-25 mt-2">
                            <i class="bi bi-robot text-danger me-2 mt-1 fs-6"></i>
                            <p class="text-light small mb-0 fw-medium" style="line-height: 1.4; opacity: 0.9;">
                                ${cat.reason || "AI detected anomalies requiring inspection."}
                            </p>
                        </div>
                    </div>
                </div>
                `;
            });

            document.getElementById("preVisitSection").classList.remove("d-none");
            console.log("[LOOKUP] Pre-visit section shown.");
        } catch (err) {
            console.error("[LOOKUP] Session start failed:", err);
            document.getElementById("preVisitSection").classList.add("d-none");
            showToast("Session Start Failed", err.message || "Could not start session.", "danger");
        } finally {
            hideLoader();
        }
    });

    document.getElementById("btnBeginInspection").addEventListener("click", () => {
        if (!state.agenda || state.agenda.length === 0) {
            showToast("No Agenda", "Start a session first to generate inspection priorities.", "warning");
            return;
        }
        loadChecklistStep(0, 0);
    });

    // SCREEN 3: Quick Actions & Forms
    document.getElementById("btnFlagIssue").addEventListener("click", () => {
        document.getElementById("quickActions").classList.add("d-none");
        document.getElementById("observationForm").classList.remove("d-none");
        document.getElementById("observationInput").focus();
    });

    document.getElementById("btnGoodPass").addEventListener("click", async () => {
        const btn = document.getElementById("btnGoodPass");
        const currentCat = state.agenda[state.currentCategoryIndex].category;
        const defaultObs = "Visual inspection passed. Equipment in good condition.";

        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Saving...';

        try {
            const res = await apiFetch(`/sessions/${state.session_id}/next-step`, {
                method: "POST",
                body: { current_item: currentCat, tech_observation: defaultObs },
            });

            state.observations.push({
                item: currentCat,
                observation: defaultObs,
                safety_level: res.safety_level || "green",
            });

            localStorage.setItem("pm_obs", JSON.stringify(state.observations));

            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-check-circle-fill fs-5 me-2"></i> Pass / Good Condition';

            // Auto skip the guidance panel for faster "Pass"
            handleNextStep();
        } catch (err) {
            showToast("Passing Failed", err.message || "Could not pass observation.", "danger");
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-check-circle-fill fs-5 me-2"></i> Pass / Good Condition';
        }
    });

    document.getElementById("observationForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = document.getElementById("btnSubmitObservation");
        const obs = document.getElementById("observationInput").value;
        const currentCat = state.agenda[state.currentCategoryIndex].category;

        btn.disabled = true;
        btn.innerHTML =
            '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Analyzing...';

        try {
            const res = await apiFetch(`/sessions/${state.session_id}/next-step`, {
                method: "POST",
                body: { current_item: currentCat, tech_observation: obs },
            });

            state.observations.push({
                item: currentCat,
                observation: obs,
                // safety_level: use the response value, or infer from follow_up_required
                safety_level: res.safety_level || (res.follow_up_required ? "yellow" : "green"),
            });

            localStorage.setItem("pm_obs", JSON.stringify(state.observations));

            document.getElementById("observationForm").classList.add("d-none");

            if (res.follow_up_required) {
                document.getElementById("abnormalBanner").classList.remove("d-none");
                document.getElementById("abnormalBanner").classList.add("d-flex");

                const badge = document.getElementById("safetyLevelBadge");
                badge.className = "badge mt-1";
                if (res.safety_level === "red") badge.classList.add("bg-danger");
                else if (res.safety_level === "yellow") badge.classList.add("bg-warning", "text-dark");
                else badge.classList.add("bg-success");
                badge.textContent = `RISK: ${String(res.safety_level || "").toUpperCase()}`;

                document.getElementById("followupPanel").classList.remove("d-none");
                document.getElementById("followupInstruction").textContent = res.instruction || "";
                document.getElementById("followupNextStepList").innerHTML = formatBulletList(res.next_step);
            } else {
                document.getElementById("guidancePanel").classList.remove("d-none");
                document.getElementById("guidanceInstruction").textContent = res.instruction || "";
                document.getElementById("guidanceNextStepList").innerHTML = formatBulletList(res.next_step);
            }
        } catch (err) {
            showToast("Observation Failed", err.message || "Could not submit observation.", "danger");
            btn.disabled = false;
            btn.innerHTML = 'Submit Observation <i class="bi bi-arrow-up-circle ms-2"></i>';
        }
    });

    document.getElementById("btnGuidanceContinue").addEventListener("click", handleNextStep);
    document.getElementById("btnFollowupConfirm").addEventListener("click", handleNextStep);

    // SCREEN 6: Summaries
    document.getElementById("btnCloseVisit").addEventListener("click", closeCleanVisit);
    document.getElementById("btnSubmitEscalation").addEventListener("click", submitEscalation);

    // VOICE
    document.getElementById("btnMic").addEventListener("click", handleVoiceInput);

    // Finish button
    const finishBtn = document.getElementById("btnFinish");
    if (finishBtn) {
        finishBtn.addEventListener("click", () => {
            localStorage.removeItem("pm_obs");
            state.session_id = null;
            state.agenda = [];
            showScreen("screen-asset");
            document.getElementById("assetId").value = "";
            document.getElementById("preVisitSection").classList.add("d-none");
        });
    }
}

function handleLogout(msg) {
    localStorage.clear();
    state.token = null;
    state.role = null;
    state.tech_id = null;
    state.session_id = null;
    state.agenda = [];
    state.observations = [];

    document.getElementById("mainNav").classList.add("d-none");
    showScreen("screen-login");
    if (msg) showToast("Logged Out", msg, "info");
}

async function loadChecklistStep(catIdx, stepIdx) {
    state.currentCategoryIndex = catIdx;
    state.stepIndex = stepIdx;

    const currentCat = state.agenda[catIdx].category;

    showLoader();
    try {
        const data = await apiFetch(`/checklist/${currentCat}/step/${stepIdx}`);
        state.lastChecklist = data;
        state.stepCount = data.step_count;

        // Reset UI
        document.getElementById("quickActions").classList.remove("d-none");
        document.getElementById("observationForm").classList.add("d-none");
        document.getElementById("observationInput").value = "";
        document.getElementById("btnSubmitObservation").disabled = false;
        document.getElementById("btnSubmitObservation").innerHTML =
            'Submit Observation <i class="bi bi-arrow-up-circle ms-2"></i>';

        document.getElementById("abnormalBanner").classList.add("d-none");
        document.getElementById("abnormalBanner").classList.remove("d-flex");
        document.getElementById("guidancePanel").classList.add("d-none");
        document.getElementById("followupPanel").classList.add("d-none");

        // Populate
        document.getElementById("currentCategoryTitle").innerHTML =
            `<i class="bi bi-tools me-2 text-primary"></i>${String(currentCat).replace("_", " ")}`;
        document.getElementById("stepProgress").textContent = `Step ${stepIdx + 1} of ${data.step_count}`;
        document.getElementById("taskText").textContent = data.task || "";
        document.getElementById("normalHint").textContent = data.normal_hint || "";
        document.getElementById("abnormalHint").textContent = data.abnormal_hint || "";

        renderStepper(data.step_count, stepIdx);

        showScreen("screen-checklist");
    } catch (e) {
        showToast("Checklist Load Failed", e.message || "Could not load checklist step.", "danger");
    } finally {
        hideLoader();
    }
}

function renderStepper(total, current) {
    const container = document.getElementById("stepperContainer");
    let html = "";
    for (let i = 0; i < total; i++) {
        let classes = "step";
        if (i === current) classes += " active";
        if (i < current) classes += " completed shadow-sm";

        const content = i < current ? '<i class="bi bi-check"></i>' : i + 1;
        html += `<div class="${classes}">${content}</div>`;
    }
    container.innerHTML = html;
}

function handleNextStep() {
    const nextIdx = state.stepIndex + 1;
    if (nextIdx < state.stepCount) {
        loadChecklistStep(state.currentCategoryIndex, nextIdx);
    } else {
        const nextCat = state.currentCategoryIndex + 1;
        if (nextCat < state.agenda.length) {
            loadChecklistStep(nextCat, 0);
        } else {
            finishInspection();
        }
    }
}

async function finishInspection() {
    const dynamicProcessingText = [
        "Analyzing field observations...",
        "Cross-referencing safety thresholds...",
        "Calculating Operational Risk Index...",
        "Synthesizing action plan...",
        "Finalizing diagnostic report..."
    ];
    showLoader(dynamicProcessingText, "This may take 1-2 minutes depending on connection.");
    try {
        console.log("[FINDINGS] Submitting observations:", JSON.stringify(state.observations));
        const res = await apiFetch(`/sessions/${state.session_id}/findings`, {
            method: "POST",
            body: { findings: state.observations },
        });
        console.log("[FINDINGS] Response:", JSON.stringify({ ori: res.operational_risk_index, status: res.operational_status, escalation: res.escalation_required }));

        const oriEl = document.getElementById("oriValue");
        const oriProg = document.getElementById("oriProgress");

        animateValue(oriEl, 0, res.operational_risk_index, 1000);
        setTimeout(() => {
            oriProg.style.width = res.operational_risk_index + "%";
            oriProg.classList.remove("bg-danger", "bg-warning", "bg-success");
            if (res.operational_risk_index > 60) oriProg.classList.add("bg-danger");
            else if (res.operational_risk_index > 30) oriProg.classList.add("bg-warning");
            else oriProg.classList.add("bg-success");
        }, 100);

        const banner = document.getElementById("statusBanner");
        const icon = document.getElementById("statusIcon");
        const title = document.getElementById("statusText");
        const dec = document.getElementById("clearanceDecision");

        banner.className = "alert d-flex align-items-center shadow-sm mb-4";
        if (res.operational_status === "READY") {
            banner.classList.add("alert-success");
            icon.className = "bi bi-check-circle-fill fs-3 text-success me-3";
            title.textContent = "Ready for Operation";
        } else if (res.operational_status === "CAUTION") {
            banner.classList.add("alert-warning");
            icon.className = "bi bi-exclamation-triangle-fill fs-3 text-warning me-3";
            title.textContent = "Caution Recommended";
        } else {
            banner.classList.add("alert-danger");
            icon.className = "bi bi-x-circle-fill fs-3 text-danger me-3";
            title.textContent = "Not Ready / Unsafe";
        }
        dec.textContent = "Clearance: " + (res.site_clearance || res.clearance_decision || "Unknown");

        const table = document.getElementById("riskBreakdownTable");
        table.innerHTML = "";
        (res.risk_breakdown || []).forEach((rb) => {
            const pts = rb.points != null ? rb.points : rb.contribution;
            const label = String(rb.factor || "").replace(/_/g, " ");
            table.innerHTML += `
        <tr>
          <td class="text-light text-capitalize">${label}</td>
          <td class="text-end fw-bold text-danger">+${pts} pts</td>
        </tr>
      `;
        });

        const actionList = document.getElementById("actionPlanList");
        actionList.innerHTML = "";
        (res.action_plan || []).forEach((ap) => {
            const urgency = (ap.urgency || "monitor").toLowerCase();
            const urgColor = urgency === "immediate" ? "danger" : urgency === "schedule" ? "warning" : "info";
            // parts_needed is an array of {part_name, stock_status} objects
            const parts = Array.isArray(ap.parts_needed) ? ap.parts_needed : [];
            const partsHtml = parts.length
                ? parts.map(p => `<span class="badge bg-secondary me-1">${p.part_name || p}</span>`).join("")
                : "<span class='text-muted small'>No parts required</span>";
            const stockStatus = parts.length ? (parts[0].stock_status || "") : "n/a";
            actionList.innerHTML += `
        <div class="card border-${urgColor} bg-dark shadow-sm">
          <div class="card-body">
            <div class="d-flex justify-content-between mb-2">
              <h6 class="fw-bold mb-0 text-white">${ap.issue || "Issue"}</h6>
              <span class="badge bg-${urgColor}">${String(ap.urgency || "MONITOR").toUpperCase()}</span>
            </div>
            <p class="small text-muted mb-2">${ap.recommended_action || ""}</p>
            <div class="d-flex justify-content-between align-items-center flex-wrap gap-1">
              <div>Parts: ${partsHtml}</div>
              ${stockStatus !== "n/a" && stockStatus ? `<span class="badge rounded-pill bg-secondary text-light px-2"><i class="bi bi-box-seam me-1"></i>${stockStatus}</span>` : ""}
            </div>
          </div>
        </div>
      `;
        });

        document.getElementById("btnCloseVisit").classList.add("d-none");
        document.getElementById("btnSubmitEscalation").classList.add("d-none");

        if (res.escalation_required) {
            // Cache the escalation payload for when the explicit submit button is pressed
            state.pendingEscalation = {
                approver: res.approver || "Duty Supervisor",
                approver_email: res.approver_email || "",
                brief_summary: res.brief_summary || "",
                urgency: res.urgency || "high",
                reason: res.escalation_reason || "Automated trigger.",
                operational_risk_index: res.operational_risk_index || 0
            };

            document.getElementById("btnSubmitEscalation").classList.remove("d-none");
            document.getElementById("escApprover").textContent = state.pendingEscalation.approver;
            document.getElementById("escUrgency").textContent = state.pendingEscalation.urgency.toUpperCase();
            document.getElementById("escUrgency").className = "badge bg-danger";
            document.getElementById("escBrief").textContent = state.pendingEscalation.reason;
        } else {
            state.pendingEscalation = null;
            document.getElementById("btnCloseVisit").classList.remove("d-none");
        }

        showScreen("screen-summary");
    } catch (e) {
        showToast("Findings Failed", e.message || "Could not generate findings.", "danger");
    } finally {
        hideLoader();
    }
}

async function submitEscalation() {
    if (!state.pendingEscalation) return;

    const btn = document.getElementById("btnSubmitEscalation");
    const ogHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Submitting...';

    try {
        await apiFetch(`/sessions/${state.session_id}/escalate`, {
            method: "POST",
            body: state.pendingEscalation
        });

        showScreen("screen-escalation-pending");
        startEscalationPolling();
    } catch (err) {
        showToast("Escalation Failed", err.message || "Failed to submit escalation explicitly.", "danger");
    } finally {
        btn.disabled = false;
        btn.innerHTML = ogHtml;
    }
}

function closeCleanVisit() {
    localStorage.removeItem("pm_obs");
    showToast("Success", "Visit finalized and closed.", "success");
    setTimeout(() => {
        state.session_id = null;
        state.agenda = [];
        showScreen("screen-asset");
        document.getElementById("assetId").value = "";
        document.getElementById("preVisitSection").classList.add("d-none");
    }, 1500);
}

function startEscalationPolling() {
    if (state.escalationTimer) clearInterval(state.escalationTimer);

    state.escalationTimer = setInterval(async () => {
        try {
            const res = await apiFetch(`/escalations/${state.session_id}/status`, { auth: true });
            if (res.status === "approved") {
                clearInterval(state.escalationTimer);
                document.getElementById("approvedInstruction").innerHTML = formatBulletList(res.instruction);
                showScreen("screen-escalation-approved");
            }
        } catch (e) {
            console.warn("Polling error:", e);
        }
    }, 10000);
}

// --- Utils ---

function formatBulletList(text) {
    if (!text) return "";
    if (Array.isArray(text)) {
        return `<ul class="list-unstyled mb-0 ps-2" style="border-left: 2px solid rgba(255,255,255,0.1);">${text
            .map(
                (t) =>
                    `<li class="mb-2 position-relative ps-3"><i class="bi bi-asterisk position-absolute start-0 text-primary" style="font-size:0.5rem; top:6px;"></i>${t}</li>`
            )
            .join("")}</ul>`;
    }

    const lines = String(text)
        .split(/\n|<br>|(?=\d+\.\s)/)
        .filter((l) => l.trim().length > 0);

    if (lines.length > 1) {
        return `<ul class="list-unstyled mb-0 ps-2" style="border-left: 2px solid rgba(255,255,255,0.1);">${lines
            .map(
                (l) =>
                    `<li class="mb-2 position-relative ps-3 text-light"><i class="bi bi-chevron-right position-absolute start-0 text-primary" style="font-size:0.75rem; top:3px;"></i>${l
                        .trim()
                        .replace(/^\d+\.\s*/, "")}</li>`
            )
            .join("")}</ul>`;
    }

    return `<div class="d-flex"><i class="bi bi-arrow-right-short text-primary fs-4 me-1"></i><span class="mt-1">${text}</span></div>`;
}

function handleVoiceInput() {
    if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
        showToast("Not Supported", "Speech recognition not supported in this browser.", "warning");
        return;
    }

    const SpeechR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recog = new SpeechR();
    recog.lang = "en-US";
    recog.interimResults = false;

    const btn = document.getElementById("btnMic");
    btn.classList.add("text-danger");
    showToast("Listening", "Speak your observation now...", "info");

    recog.onresult = (e) => {
        const text = e.results[0][0].transcript;
        const input = document.getElementById("observationInput");
        input.value = input.value ? input.value + " " + text : text;
    };

    recog.onend = () => {
        btn.classList.remove("text-danger");
    };

    recog.onerror = () => {
        btn.classList.remove("text-danger");
        showToast("Error", "Could not capture voice.", "danger");
    };

    recog.start();
}

document.getElementById("btnInspectAnother").addEventListener("click", () => {
    if (state.escalationTimer) clearInterval(state.escalationTimer);
    state.session_id = null;
    state.currentCategoryIndex = 0;
    state.observations = [];
    state.agenda = [];
    showScreen("screen-asset");
    document.getElementById("assetId").value = "";
    document.getElementById("preVisitSection").classList.add("d-none");
});

function animateValue(obj, start, end, duration) {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.innerHTML = Math.floor(progress * (end - start) + start);
        if (progress < 1) window.requestAnimationFrame(step);
    };
    window.requestAnimationFrame(step);
}

// Start App
document.addEventListener("DOMContentLoaded", initApp);