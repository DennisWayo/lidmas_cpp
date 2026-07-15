# LiDMaS+ Open-Source UI

Version target: `v1.2.2`

This folder contains the open-source web UI for LiDMaS+. The UI is built against a backend service contract for decoder studies, replay workflows, validation views, provider metadata, and lab-facing integration sessions.

## Scope

- Provider registry and metadata (`/providers`)
- Job orchestration metadata (`/jobs`)
- Run tracking and artifact lineage (`/runs`)
- Adapter session orchestration for hardware/replay flows (`/integrations/sessions`)
- Provider-output integrity validation (`/providers/{id}/validate`)
- Research system log scanning (`/system/logscan`)
- Health and uptime (`/health`)

Storage and runtime policy are owned by the backend service. The frontend can run against a local or hosted `VITE_API_BASE_URL`.

## Frontend

A React + TypeScript GUI scaffold is available in:

`lidmas+/frontend`

Run it with:

```bash
cd "lidmas+/frontend"
npm install
npm run dev
```

## Backend Target

```bash
VITE_API_BASE_URL=http://127.0.0.1:8080/api/v1 npm run dev
```

Default frontend URL: `http://127.0.0.1:5173`
Default backend target: `http://127.0.0.1:8080/api/v1`

## API Root

- `GET /api/v1/health`

## paper_04 App Parity Endpoints

LiDMaS+ now exposes app-driven `paper_04` execution and manifest parity checks against the canonical CLI workflow (`./examples/paper_runs/paper_04/run_all.sh`).

- `GET /api/v1/system/paper_04/manifest`
- `POST /api/v1/system/paper_04/run`

`POST /run` executes the same `paper_04` runner script and returns:

- execution status (`succeeded`, `failed`, `timeout`, or `parity_mismatch`)
- stdout/stderr tails
- deterministic artifact manifest hash over key `paper_04/results` outputs
- optional parity comparison (`compare_with_manifest_hash`)

## Authentication

Most `/api/v1/*` endpoints now require bearer authentication.

Public auth endpoints:

- `POST /api/v1/auth/signup`
- `POST /api/v1/auth/signin`

Protected auth endpoints:

- `GET /api/v1/auth/me`
- `POST /api/v1/auth/signout`

Example sign-in:

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/auth/signin \
  -H "content-type: application/json" \
  -d '{"email":"you@example.org","password":"your-password"}'
```

Use returned `token` as:

```bash
-H "authorization: Bearer <TOKEN>"
```

`POST /api/v1/runs/{run_id}/telemetry` remains open for adapter push workflows.

## Example Flow

1. Register provider:

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/providers \
  -H "content-type: application/json" \
  -d '{
    "name":"Xanadu",
    "kind":"photonic",
    "supported_formats":["aurora_switch_dir","shot_matrix","count_table_json"],
    "contact_email":"integration@example.org",
    "notes":"provider integration test"
  }'
```

2. Create job:

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/jobs \
  -H "content-type: application/json" \
  -d '{
    "provider_id":"<PROVIDER_UUID>",
    "dataset_label":"aurora_batch0_qpu5",
    "decoders":["mwpm","uf","bp","neural_mwpm"],
    "priority":5
  }'
```

3. Validate provider result integrity:

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/providers/<PROVIDER_UUID>/validate \
  -H "content-type: application/json" \
  -d '{
    "dataset_label":"aurora_batch0_qpu5",
    "request_lines":500,
    "response_lines":500,
    "request_parse_errors":0,
    "response_parse_errors":0,
    "decoder_name_mismatch_count":0,
    "warning_no_syndrome_count":346
  }'
```

4. Create run:

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/runs \
  -H "content-type: application/json" \
  -d '{
    "provider_id":"<PROVIDER_UUID>",
    "dataset_label":"aurora_batch0_qpu5",
    "decoders":["mwpm","uf","bp","neural_mwpm"]
  }'
```

5. Attach artifact:

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/runs/<RUN_UUID>/artifacts \
  -H "content-type: application/json" \
  -d '{
    "name":"figure_A_decoder_tradeoff_scatter",
    "kind":"figure_pdf",
    "path":"examples/paper_runs/paper_03/results/08_extended_analysis/figures/figure_A_decoder_tradeoff_scatter.pdf",
    "sha256":"<optional_sha256>"
  }'
```

6. Run research log scan:

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/system/logscan \
  -H "content-type: application/json" \
  -d '{
    "logs":[
      {
        "timestamp":"2026-04-20 15:28:02.341",
        "level":"ERROR",
        "message":"Provider-03 returned timeout during parity check replay",
        "source":"providers/health.rs:156"
      }
    ],
    "max_findings":50
  }'
```

7. Start integration session (IBM live example):

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/integrations/sessions \
  -H "content-type: application/json" \
  -d '{
    "run_id":"<RUN_UUID>",
    "adapter_id":"ibm_superconducting_live",
    "config":{
      "backend_name":"ibm_kingston",
      "poll_interval":30
    }
  }'
```

8. Tail integration session logs:

```bash
curl -s "http://127.0.0.1:8080/api/v1/integrations/sessions/<SESSION_UUID>/logs?tail=100"
```

## Adapter Session Endpoints

- `GET /api/v1/integrations/sessions`
- `POST /api/v1/integrations/sessions`
- `GET /api/v1/integrations/sessions/{session_id}`
- `POST /api/v1/integrations/sessions/{session_id}/stop`
- `GET /api/v1/integrations/sessions/{session_id}/logs?tail=200`
- `POST /api/v1/system/credentials/ibm` (store IBM API key in runtime memory)

Supported adapter ids:

- `ibm_superconducting_live`
- `ankaa_superconducting_replay`
- `xanadu_gkp_remote_replay`

IBM auth note:

- Adapter session payloads do not carry API keys.
- The frontend may submit an IBM key to `/system/credentials/ibm`, where the backend stores it in runtime memory for the current service session.
- If no runtime key is provided, the backend may use `IBM_QUANTUM_API_KEY` or a saved `qiskit-ibm-runtime` account.

## Troubleshooting

If frontend shows `Backend missing /integrations/sessions (old server)`, your UI is connected to an older backend build.
Restart the backend service and verify:

```bash
curl -i http://127.0.0.1:8080/api/v1/integrations/sessions
```

Expected status is `200` (not `404`).

## Next Steps

- Persist state to PostgreSQL (providers/jobs/runs/artifacts tables)
- Add auth/roles for provider portal vs researcher views
- Add async worker queue for real run execution
- Add run logs/streaming endpoint for GUI live monitor
- Add schema versioning + provider plugin registry contract
