# LiDMaS+ Public API

This is the Render-facing public demo API for Gottesman Studio.

It is intentionally stateless and fixture-backed. It exposes public decoder examples, run metadata, benchmark-style telemetry, validation checks, and read-only provider data.

It does not accept IBM credentials, start real hardware sessions, control lab equipment, persist uploaded private files, or run long paper workflows.

## Local Run

```bash
pip install -r public_api/requirements.txt
uvicorn public_api.app:app --host 127.0.0.1 --port 8080
```

Open:

```text
http://127.0.0.1:8080/api/v1/health
```

## Render

Use the repository-level `render.yaml` blueprint, or create a Render Web Service manually:

- Build command: `pip install -r public_api/requirements.txt`
- Start command: `uvicorn public_api.app:app --host 0.0.0.0 --port $PORT`
- Health check path: `/api/v1/health`

Set `CORS_ORIGINS` to the Gottesman Studio origin and any local development origins that should be allowed.
