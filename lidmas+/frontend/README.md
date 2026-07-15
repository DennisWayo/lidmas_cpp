# LiDMaS+ Frontend (React + TypeScript)

This frontend is an open-source research UI scaffold for the LiDMaS+ control plane.

## Features in scaffold

- App shell with top mode chips + persistent sidebar navigation
- Auth gate overlay (Sign In / Sign Up) before workspace access
- Post-login IBM onboarding popup for optional live-noise key setup
- Routed modules:
  - Dashboard
  - Providers
  - Jobs Queue
  - Runs & Logs
  - Analysis
  - Artifacts
  - Conformance
  - Settings
- API integration against Rust backend `/api/v1` endpoints
- React Query data fetching + mutations
- Structured components ready for research-workspace expansion
- Jobs page Adapter Sessions panel:
  - provider-family launcher (`IBM`, `Ankaa`, `Xanadu`)
  - automatic adapter selection
  - optional auto-create run/provider when no run is selected
  - stop and log-tail actions for active sessions

## Run

```bash
cd "lidmas+/frontend"
npm install
npm run dev
```

Default frontend URL: `http://127.0.0.1:5173`
Default backend target: `http://127.0.0.1:8080/api/v1`

To use a different backend:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8080/api/v1 npm run dev
```

## Adapter Session Flow

1. Set data mode to `Live API`.
2. Open `Jobs & Runs`.
3. Click `+ Start Adapter Session`.
4. Pick provider family (`IBM`, `Ankaa`, or `Xanadu`) and fill provider-specific fields.
5. Start session and monitor from `Adapter Sessions` table (status/logs/stop).

Provider-to-adapter mapping is automatic:

- `IBM` -> `ibm_superconducting_live`
- `Ankaa` -> `ankaa_superconducting_replay`
- `Xanadu` -> `xanadu_gkp_remote_replay`

IBM authentication behavior:

- After login, frontend can collect IBM API key and submit it to backend runtime memory (`POST /api/v1/system/credentials/ibm`).
- Backend injects stored key into IBM adapter session process env (`IBM_QUANTUM_API_KEY`).
- If no key is provided, backend falls back to existing runtime env/saved Qiskit credentials.
- Missing credentials surface as adapter session failure logs.

Backend auth behavior:

- Frontend sign-in/sign-up is now backed by backend auth endpoints (`/api/v1/auth/*`).
- API requests include bearer token automatically after successful login.

## paper_04 CLI/IDE Parity Flow

From `Runs` page:

1. Click `Capture CLI Baseline` after generating `paper_04` from CLI (or existing artifacts).
2. Click `Run paper_04 In LiDMaS+` to execute the same workflow through backend.
3. Compare returned manifest parity (`MATCH` / `MISMATCH`).

Backend endpoints used:

- `GET /api/v1/system/paper_04/manifest`
- `POST /api/v1/system/paper_04/run`

## Troubleshooting

If Adapter Sessions shows:

- `Backend missing /integrations/sessions (old server)`

your frontend is pointed to an older backend binary. Restart backend from latest source and verify:

```bash
curl -i http://127.0.0.1:8080/api/v1/integrations/sessions
```

Expected response: `200` with JSON array.

## Next recommended additions

1. Auth (OIDC/JWT) and route guards by role.
2. Real-time logs/telemetry via SSE or WebSocket.
3. Rich tables and charting for figure/table previews.
4. Provider mapping editor with schema-diff preview.
