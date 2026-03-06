/**
 * PMAdapt - Supervisor Dashboard Logic
 */

const BASE_URL = `http://${window.location.hostname || 'localhost'}:8000`;
const MOCK_MODE = false;

const state = {
    token: null,
    role: null,
    escalations: [],
    selectedEscalationId: null,
    auditLogCache: {}
};

// --- MOCK API ---
async function apiFetch(endpoint, options = {}) {
    const method = options.method || 'GET';
    const body = options.body ? JSON.stringify(options.body) : null;

    if (MOCK_MODE) {
        console.log(`[MOCK API] ${method} ${endpoint}`, options.body || '');
        return new Promise((resolve) => setTimeout(() => resolve(getMockResponse(method, endpoint, options.body)), 500));
    }

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${state.token}`
    };

    try {
        const response = await fetch(`${BASE_URL}${endpoint}`, { method, headers, body });
        if (response.status === 401) {
            handleLogout("Session expired");
            throw new Error("Unauthorized");
        }
        if (!response.ok) throw new Error(`API Error`);
        return await response.json();
    } catch (error) {
        showToast("Error", "API Communication Failed", "danger");
        throw error;
    }
}

function getMockResponse(method, endpoint, body) {
    if (endpoint === '/escalations/pending') {
        // Generate some fake pending items
        if (Math.random() > 0.8 && state.escalations.length === 0) return []; // Sometimes returning empty for demo

        return [
            {
                session_id: "SESS-8492",
                asset_id: "GEN013",
                site_type: "Hospital Backup",
                tech_id: "T0001",
                brief: "Severe battery terminal corrosion with significant voltage drop observed during routine PM.",
                urgency: "high",
                operational_risk_index: 78,
                recommended_decision: "Lockout Asset",
                timestamp: new Date(Date.now() - 15 * 60000).toISOString() // 15 mins ago
            },
            {
                session_id: "SESS-3312",
                asset_id: "PUMP-X22",
                site_type: "Water Treatment",
                tech_id: "T0045",
                brief: "Minor fuel leak detected on secondary line. Flow rate unaffected.",
                urgency: "medium",
                operational_risk_index: 45,
                recommended_decision: "Monitor closely",
                timestamp: new Date(Date.now() - 42 * 60000).toISOString()
            },
            {
                session_id: "SESS-7109",
                asset_id: "COMP-A1",
                site_type: "Manufacturing Unit B",
                tech_id: "T0012",
                brief: "Vibration analysis shows mounting bolts missing on casing.",
                urgency: "high",
                operational_risk_index: 82,
                recommended_decision: "Immediate repair",
                timestamp: new Date(Date.now() - 120 * 60000).toISOString()
            }
        ];
    }

    if (endpoint.includes('/approve')) {
        return {
            approval_id: "APP-" + Math.floor(Math.random() * 1000),
            logged: true,
            timestamp: new Date().toISOString()
        };
    }

    if (endpoint.includes('/audit-log')) {
        return [
            { timestamp: new Date(Date.now() - 30 * 60000).toISOString(), actor: "System", action: "Session auto-started on tag scan", confidence: 1.0, summary: "Initial entry" },
            { timestamp: new Date(Date.now() - 25 * 60000).toISOString(), actor: "T0001", action: "Observation logged: Air Filter", confidence: 0.99, summary: "Normal condition." },
            { timestamp: new Date(Date.now() - 20 * 60000).toISOString(), actor: "T0001", action: "Observation logged: Battery", confidence: 0.95, summary: "Abnormal. Severe corrosion found." },
            { timestamp: new Date(Date.now() - 19 * 60000).toISOString(), actor: "System", action: "Risk calculated: 78", confidence: 0.95, summary: "Red safety level triggered." },
            { timestamp: new Date(Date.now() - 15 * 60000).toISOString(), actor: "T0001", action: "Escalation requested", confidence: 1.0, summary: "Senior override required to proceed." },
        ];
    }

    return {};
}

// --- Init & UI ---

function initDashboard() {
    document.getElementById('loadingOverlay').classList.add('active');

    // SW
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js');

    // Verify token
    const token = localStorage.getItem('pm_token');
    const role = localStorage.getItem('pm_role');

    if (!token || role !== 'supervisor') {
        handleLogout();
        return;
    }

    state.token = token;
    state.role = role;

    setupEventListeners();
    loadPendingEscalations();

    // Auto-refresh dashboard explicitly requested by user (1.5s for instant feel)
    setInterval(loadPendingEscalations, 1500);
}

function handleLogout() {
    localStorage.clear();
    window.location.href = 'index.html?v=' + new Date().getTime();
}

function showToast(title, message, color = "primary") {
    const container = document.querySelector('.toast-container');
    const id = 'toast-' + Date.now();
    const html = `
    <div id="${id}" class="toast align-items-center text-bg-${color} border-0 mb-2" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body fw-medium"><strong>${title}</strong><br>${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>`;
    container.insertAdjacentHTML('beforeend', html);
    new bootstrap.Toast(document.getElementById(id), { delay: 4000 }).show();
}

function setupEventListeners() {
    document.getElementById('btnLogout').addEventListener('click', handleLogout);
    document.getElementById('btnRefresh').addEventListener('click', () => {
        loadPendingEscalations();
    });

    document.getElementById('btnApproveAction').addEventListener('click', () => {
        try {
            if (!state.selectedEscalationId) {
                showToast("No Case Selected", "Please select an escalation from the list first.", "warning");
                return;
            }
            const esc = state.escalations.find(e => e.session_id === state.selectedEscalationId);
            if (!esc) return;

            document.getElementById('modalAssetId').textContent = esc.asset_id;
            document.getElementById('approveInstruction').value = '';

            // Use getOrCreateInstance to avoid double-init errors
            bootstrap.Modal.getOrCreateInstance(document.getElementById('approveModal')).show();
        } catch (err) {
            console.error('[APPROVE BTN]', err);
            showToast('Error', 'Could not open approval dialog: ' + err.message, 'danger');
        }
    });

    document.getElementById('btnConfirmApprove').addEventListener('click', submitApproval);

    document.getElementById('btnOpenAuditLog').addEventListener('click', () => {
        try {
            if (!state.selectedEscalationId) {
                showToast("No Case Selected", "Please select an escalation from the list first.", "warning");
                return;
            }
            loadAuditLog();
        } catch (err) {
            console.error('[AUDIT LOG BTN]', err);
            showToast('Error', 'Could not open audit log: ' + err.message, 'danger');
        }
    });
}

// --- Core Flows ---

async function loadPendingEscalations() {
    try {
        const data = await apiFetch('/escalations/pending');
        // Backend returns { escalations: [...] }
        state.escalations = data.escalations || data || [];
        renderList();

        if (state.selectedEscalationId) {
            const stillExists = state.escalations.find(e => e.session_id === state.selectedEscalationId);
            if (!stillExists) {
                state.selectedEscalationId = null;
                hideDetailView();
            }
        }
    } catch (e) {
        console.error('Failed to load escalations:', e);
    } finally {
        document.getElementById('loadingOverlay').classList.remove('active');
    }
}

function renderList() {
    const listEl = document.getElementById('escalationList');
    const badge = document.getElementById('pendingCountBadge');

    badge.textContent = state.escalations.length;

    if (state.escalations.length === 0) {
        listEl.innerHTML = `
            <div id="emptyEscalationState" class="text-center p-5 mt-5 text-muted">
                <i class="bi bi-check-circle fs-1 mb-3 d-block text-success opacity-50"></i>
                <h5>All Caught Up</h5>
                <p class="small">No pending escalations require your attention.</p>
            </div>
        `;
        return;
    }

    let html = '';

    state.escalations.forEach(esc => {
        const isActive = esc.session_id === state.selectedEscalationId;
        const timeAgo = Math.floor((new Date() - new Date(esc.created_at)) / 60000);
        // DB field: urgency_level
        const urgency = (esc.urgency_level || 'high').toLowerCase();
        const urgColor = urgency === 'high' ? 'danger' : 'warning';

        html += `
      <div class="card mb-3 list-item-card ${isActive ? 'list-item-active' : 'glass-card'}" 
           style="cursor: pointer;"
           onclick="selectEscalation('${esc.session_id}')">
        <div class="card-body p-3">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <span class="fw-bold text-light fs-5 tracking-tight">${esc.asset_id}</span>
            <span class="small text-muted border border-secondary px-2 rounded-pill"><i class="bi bi-clock me-1"></i>${timeAgo}m</span>
          </div>
          <div class="d-flex justify-content-between align-items-center">
            <span class="badge bg-${urgColor} bg-opacity-10 text-${urgColor} border border-${urgColor} border-opacity-25 px-2 py-1"><i class="bi bi-exclamation-triangle-fill me-1"></i>${urgency.toUpperCase()}</span>
            <span class="text-muted small"><i class="bi bi-person-fill text-primary me-1"></i>${esc.tech_id}</span>
          </div>
        </div>
      </div>
    `;
    });

    listEl.innerHTML = html;
}

function selectEscalation(sessionId) {
    state.selectedEscalationId = sessionId;
    renderList(); // Update active state class

    const esc = state.escalations.find(e => e.session_id === sessionId);
    if (!esc) return;

    document.getElementById('emptyDetailState').classList.add('d-none');
    document.getElementById('detailView').classList.remove('d-none');

    // Populate Detail — use DB field names
    document.getElementById('detAssetId').textContent = esc.asset_id;
    document.getElementById('detSiteType').textContent = esc.tech_id || 'N/A';
    document.getElementById('detTechId').textContent = esc.tech_id;
    // ORI now stored on escalations table
    const oriEl = document.getElementById('detOri');
    const ori = esc.operational_risk_index;
    if (ori != null && ori > 0) {
        oriEl.textContent = ori;
        oriEl.className = `fw-bold mb-0 ${ori > 60 ? 'text-danger' : ori > 30 ? 'text-warning' : 'text-success'}`;
    } else {
        const urgency = (esc.urgency_level || 'high').toLowerCase();
        oriEl.textContent = urgency === 'high' ? '⚠ HIGH' : '⚠ MED';
        oriEl.className = `fw-bold mb-0 ${urgency === 'high' ? 'text-danger' : 'text-warning'}`;
    }

    document.getElementById('detBrief').textContent = esc.brief_summary || esc.escalation_reason || 'No summary available';
    document.getElementById('detRecommendedDecision').textContent = esc.escalation_reason || 'Senior review required';

    const urgBadge = document.getElementById('detUrgency');
    urgBadge.className = `badge rounded-pill mb-2 px-3 ${urgency === 'high' ? 'bg-danger' : 'bg-warning text-dark'}`;
    urgBadge.innerHTML = `<i class="bi bi-lightning-charge-fill me-1"></i> ${urgency.toUpperCase()} URGENCY`;
}

function hideDetailView() {
    document.getElementById('emptyDetailState').classList.remove('d-none');
    document.getElementById('detailView').classList.add('d-none');
}

async function submitApproval() {
    const instruction = document.getElementById('approveInstruction').value.trim();
    if (!instruction) {
        showToast("Required", "You must provide an instruction for the technician.", "warning");
        return;
    }

    const btn = document.getElementById('btnConfirmApprove');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';

    try {
        const res = await apiFetch(`/escalations/${state.selectedEscalationId}/approve`, {
            method: 'POST',
            body: { decision: "approve", instruction: instruction }
        });

        // Success
        const modal = bootstrap.Modal.getInstance(document.getElementById('approveModal'));
        modal.hide();

        showToast("Approved", `Successfully logged approval ID: ${res.approval_id}`, "success");

        // Remove from local list
        state.escalations = state.escalations.filter(e => e.session_id !== state.selectedEscalationId);
        state.selectedEscalationId = null;

        hideDetailView();
        renderList();

    } catch (e) { } finally {
        btn.disabled = false;
        btn.innerHTML = 'Confirm Approval <i class="bi bi-check2 me-1"></i>';
    }
}

async function loadAuditLog() {
    if (!state.selectedEscalationId) return;
    // Use getOrCreateInstance to avoid re-init errors
    const offcanvas = bootstrap.Offcanvas.getOrCreateInstance(document.getElementById('auditLogOffcanvas'));
    offcanvas.show();

    const container = document.getElementById('auditLogContent');
    container.innerHTML = `<div class="text-center p-5 text-muted"><div class="spinner-border spinner-border-sm mb-3 text-primary"></div><br>Fetching log entries...</div>`;

    try {
        const data = await apiFetch(`/sessions/${state.selectedEscalationId}/audit-log`);
        // Backend returns { session_id, audit_log: [...] }
        const logs = data.audit_log || data || [];
        let html = '';
        logs.forEach(log => {
            const time = new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            html += `
        <div class="list-group-item bg-black border-secondary border-bottom p-3">
          <div class="d-flex justify-content-between mb-1">
            <span class="small fw-bold text-primary">${log.agent_id || 'System'}</span>
            <span class="small text-muted">${time}</span>
          </div>
          <div class="text-light fw-medium mb-1">${log.input_summary || 'No action summary'}</div>
          <div class="small text-muted"><i class="bi bi-robot me-1 opacity-50"></i>AI Processed <span class="badge bg-secondary opacity-75 ms-2">Conf: ${log.confidence || 'N/A'}</span></div>
        </div>
      `;
        });
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = `<div class="p-4 text-danger"><i class="bi bi-exclamation-triangle-fill me-2"></i>Failed to load logs.</div>`;
    }
}
document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
    updateNetworkIndicator();
});

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
