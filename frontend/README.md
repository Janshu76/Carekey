# CareLink PWA

CareLink is the React + Vite progressive web app for the Emergency Bridge demo. It calls the FastAPI backend directly and uses synthetic patient information only.

## Run the integrated demo

From the repository root in PowerShell, start the backend:

```powershell
.\.venv\Scripts\python -m uvicorn backend.app.main:app --reload
```

In another terminal, start the PWA:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://localhost:5173`). The backend uses `http://127.0.0.1:8000` by default. To use a different API base URL, set `VITE_API_BASE_URL` before starting Vite.

## Demo walkthrough

### Family guardian

1. Choose **Family guardian** and enter the seeded phone number `+91 98990 11223`.
2. Use the demo OTP shown in the app.
3. Explore the dashboard and **Health record**. Select a marker on the interactive 2D body map to inspect a condition or past injury.
4. Under **Consent & access**, change share permissions and save; this creates a consent receipt. Create an emergency QR code to display or print the wallet card.
5. Add a condition or injury to attach a body location and show it on the map. Admission actions use current consent and update the activity timeline.

### Responder

1. Log out and choose **Responder**.
2. Enter a demo responder name and organization.
3. In the guardian session, create an emergency QR code, then paste its one-time secret into the responder console, or use a seeded test code such as `carelink-1-demo-token`.
4. The scan returns only consented fields, source labels, dose conflicts, an audit entry, and a family notification. Break-glass scans require a reason and are labeled in the audit.

The simulated responder login and OTP delivery are for demonstration, not production authentication.

## PWA

The app includes a web manifest, icon, and a service worker that caches the app shell. Patient, auth, and scan API responses are deliberately never cached. Camera QR scanning requires browser camera permission and a secure context (HTTPS or localhost).

Production builds are created with `npm run build`.
