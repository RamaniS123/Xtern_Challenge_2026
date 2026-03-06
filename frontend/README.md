# PMAdapt Field App & Central Command (Frontend)

This directory contains the entire frontend architecture for the **PMAdapt** Predictive Maintenance platform, encompassing both the mobile-first Field Technician App and the tablet/desktop Central Command Supervisor Dashboard.

## 🏗️ Architecture & Technologies

The frontend is a completely bespoke, vanilla JavaScript application with a focus on absolute performance, offline capability, and a premium "glassmorphism" design system.

- **Core:** Vanilla JS (ES6+), HTML5, CSS3
- **Styling:** Bootstrap 5 (CSS only), Custom Glassmorphism Theme (`styles.css`), Bootstrap Icons
- **Offline Support:** Service Worker Caching (`sw.js`), Local Storage API Queuing
- **Architecture:** Local state management, direct DOM manipulation, Modular ES-style organization.

## 📁 Project Structure

| File | Purpose |
|------|---------|
| `index.html` | The **Field Technician App** (Mobile-first). Handles login, asset lookup, AI checklists, and offline sync. |
| `dashboard.html`| The **Central Command Supervisor Dashboard**. Handles live escalations, JSON audit logs, and operational risk metrics. |
| `app.js` | Core logic for the Technician App. Includes the `apiFetch` network interceptor and the dynamic sequence engine. |
| `dashboard.js` | Core logic for the AI Supervisor Dashboard. Handles periodic telemetry updates and escalation resolutions. |
| `styles.css` | The global styling engine. Contains the glowing orb animations, custom UI components, and strict font definitions. |
| `sw.js` | Service Worker script responsible for caching the application shell for "Dead-Zone" offline availability. |
| `manifest.json` | PWA manifest allowing the web app to be installed natively on iOS/Android devices. |

## 🚀 How to Run (Development)

The frontend uses absolute module routing and Service Worker installation, so it **must** be served over a local HTTP server rather than opening the files directly in a browser.

1. Ensure the Python FastAPI backend is running on `http://localhost:8000`.
2. Open a terminal in this `frontend` directory.
3. Start a local HTTP server via Python:

```bash
python -m http.server 8080
```

4. Navigate to `http://localhost:8080` in your web browser.

### Bypassing Local AI Latency (Lightning Demo Mode)
If you are running a live demonstration and want to guarantee lightning-fast screen transitions without waiting for local LLM inference, the `MOCK_MODE` constant at the top of both `app.js` and `dashboard.js` can be manually flipped to `true`. This instantly forces the UI to fall back to hardcoded structural payloads in < 500ms.

## 📡 Offline Synchronization Module

This frontend is designed to be fully usable deep underground in generator rooms without cellular reception.

1. **App Shell Caching:** On first load, `sw.js` caches all visual UI assets.
2. **Offline Queue:** If the `navigator.onLine` flag drops, `app.js` intercepts modifying requests (e.g., submitting an inspection protocol), serializes them, and drops them into a `pm_sync_queue` sitting in `localStorage`, smoothly handing a mock fallback to the UI so the user isn't interrupted.
3. **Background Reconsolidation:** A global `window.addEventListener('online')` automatically pushes the queued reports back to the server the moment Wi-Fi or cellular data is restored.
