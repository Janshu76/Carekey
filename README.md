# CareLink — Emergency Bridge

CareLink is a progressive web app demo for helping a person share the right health information with emergency responders when they may not be able to explain their medical history. A guardian manages the patient’s record and sharing permissions; a responder can use a time-limited QR credential to request access during an emergency.

The project includes a React PWA, a FastAPI backend, and a SQLite database seeded with synthetic demo records. It is a prototype and is **not intended for real patient data or clinical use**.

## Why CareLink is different

Many health-record apps focus on storing records for patients or clinicians who already have access and time to search. CareLink is designed around the handoff at the point of emergency:

- **No responder app installation:** the patient’s printed QR card can be scanned with a phone camera, or its backup code can be entered through a browser. The PWA can also be installed on a guardian’s home screen.
- **Consent-controlled disclosure:** guardians choose which categories can be shared. The responder view filters information according to those permissions instead of exposing the full record by default.
- **Designed for fragmented records:** the demo combines records from simulated source systems and labels their sources, surfacing conflicting medication information rather than silently choosing one source.
- **Emergency workflow in one place:** temporary QR access, an admission prefill, family notifications, and an access timeline connect the responder handoff to what happens next.
- **Health history is easier to explore:** a selectable 2D body map links conditions and past injuries to their recorded body areas, alongside a chronological record view.
- **Access is accountable:** emergency access is recorded in an audit trail. A distinct break-glass path requires a reason and is marked in the log.

These are prototype design choices, not claims of interoperability certification, clinical validation, or production-grade security. The source records and notification delivery are simulated.

## Features in this demo

### Guardian experience

- Demo OTP sign-in using a seeded guardian phone number.
- Patient overview, health details, and a body map for conditions and injuries.
- Consent settings and consent receipts.
- Temporary emergency QR credential creation and revocation.
- Activity timeline, notifications, and admission prefill/recording.

### Responder experience

- Simulated responder sign-in.
- QR scanning in a supported browser or manual credential entry.
- Consent-filtered emergency record with source labels and conflict indicators.
- Standard or reasoned break-glass access, recorded in the audit history.

## Technology

- **Frontend:** React, Vite, Tailwind CSS, and PWA manifest/service worker; QR generation and browser-based scanning.
- **Backend:** Python, FastAPI, Pydantic, and SQLAlchemy.
- **Demo database:** SQLite, initialized and populated with synthetic data when the backend starts outside production mode.
- **Tests:** Pytest API tests; frontend lint and Vite production build scripts.

## Run locally

You need Python 3.10 or newer, Node.js/npm compatible with the installed Vite version, and two terminals. Run commands from the repository root unless noted.

### 1. Set up and start the API

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
.\.venv\Scripts\python -m uvicorn backend.app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive API documentation is at `http://127.0.0.1:8000/docs`. On first startup it creates the local SQLite database and seeds demo data.

### 2. Set up and start the PWA

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite, normally `http://localhost:5173`. The frontend uses `http://127.0.0.1:8000` as its API by default. To point it at another API, create `frontend/.env.local` with:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### Optional: start the backend with Docker Compose

From the repository root:

```powershell
docker compose up --build
```

This starts only the API on port `8000`; start the frontend separately as described above.

## Try the demo

1. On the PWA sign-in screen, choose **Family guardian** and enter `+91 98990 11223`.
2. Request the OTP. It is generated locally and shown by the demo; no SMS is sent.
3. Explore **Health record** and select body-map markers to inspect the synthetic condition and injury history.
4. Open **Consent & access** to review sharing permissions, then create an emergency QR credential.
5. Log out and choose **Responder**. Sign in with a demo name and organization.
6. Scan the guardian’s QR code, or enter its credential manually. For a quick seeded test, use `carelink-1-demo-token`.
7. Review the consent-filtered record, then check the guardian’s activity timeline for the access event and notification.

Camera scanning requires browser camera permission and a secure context (HTTPS or localhost). The mock sign-in flows and seeded test token are for demonstration only.

## Tests and production build

From the repository root, run backend tests:

```powershell
.\.venv\Scripts\python -m pytest backend\tests -q
```

Run frontend lint and create a production build:

```powershell
cd frontend
npm run lint
npm run build
```

The build output is written to `frontend/dist`.

## Project layout

```text
backend/
  app/                 FastAPI application, models, schemas, seed data, and services
  tests/               Backend API tests
frontend/
  src/                 React application and API client
  public/              PWA manifest, icons, and service worker
docker-compose.yml     Optional local API container
```

## Safety and production readiness

All included patient data is synthetic. OTP delivery and responder identity verification are mocked; notifications are demo behavior. Do not enter real health information or deploy this configuration for patient care. A real deployment would require, among other work, a production identity provider and OTP channel, secure secrets management, HTTPS, privacy and regulatory review, database migrations and backups, operational monitoring, and security testing. The backend disables demo seeding and mock authentication endpoints in production mode, but that alone does not make the application production-ready.

For API details and backend configuration, see [backend/README.md](./backend/README.md). For PWA-specific notes, see [frontend/README.md](./frontend/README.md).
