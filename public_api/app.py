from __future__ import annotations

import math
import os
import re
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


API_PREFIX = "/api/v1"
STARTED_AT = datetime.now(timezone.utc)
ISO_BASE = "2026-04-20T10:00:00Z"
DEFAULT_RUN_ID = "7f08982d-6bfb-4c64-bec8-feb4e8b2665f"
DECODERS = ["bp_osd", "mwpm_gkp", "union_find"]


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_cors_origins() -> list[str]:
    raw = os.getenv(
        "CORS_ORIGINS",
        "https://gottesman-software.github.io,http://127.0.0.1:5173,http://localhost:5173",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def public_error(message: str, status_code: int = 403) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


def provider_fixture() -> list[dict[str, Any]]:
    providers = [
        ("2fb9d977-b44f-4907-8826-82f7953ac26a", "PennyLane circuit simulator", "simulated", "ready"),
        ("93a9edc8-1e87-4af0-9f70-3bcf56261379", "Qiskit Aer noise simulator", "simulated", "ready"),
        ("e7fe27f7-4f0e-4992-95dc-a2f33cd9705f", "Cirq syndrome simulator", "simulated", "ready"),
        ("4afcd5b2-f17c-49c4-9f3e-a68e7c6cf75b", "SchroSIM photonic CV simulator", "simulated", "ready"),
    ]
    return [
        {
            "id": provider_id,
            "name": name,
            "status": status,
            "kind": kind,
            "hardware_kind": kind,
            "contact_email": None,
            "supported_formats": ["jsonl", "csv", "json"],
            "supports_scientific": True,
            "supports_benchmark": True,
            "supports_replay": True,
            "supports_live": False,
            "last_seen": utcnow(),
            "readiness_note": "Public simulator fixture. No credentials or hardware access.",
            "notes": "Construct circuit, inject noise, extract syndrome data, and run a decoder policy.",
            "created_at": ISO_BASE,
            "updated_at": utcnow(),
        }
        for provider_id, name, kind, status in providers
    ]


def job_fixture(providers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = [
        ("pennylane_circuit_noise_syndrome", "running", 0),
        ("qiskit_aer_noise_policy", "completed", 1),
        ("cirq_syndrome_extraction_policy", "completed", 2),
        ("schrosim_cv_decoder_policy", "queued", 3),
    ]
    jobs: list[dict[str, Any]] = []
    for index, (label, status, provider_index) in enumerate(labels):
        created_at = f"2026-04-20T14:{(6 + index):02d}:00Z"
        jobs.append(
            {
                "id": f"a338f7a2-31fd-4fcd-b17a-7adf2f9a{100 + index}",
                "provider_id": providers[provider_index % len(providers)]["id"],
                "dataset_label": label,
                "decoders": DECODERS,
                "priority": 5,
                "status": status,
                "message": "Public simulator pipeline: circuit construction, noise injection, syndrome extraction, decoder policy.",
                "created_at": created_at,
                "updated_at": created_at,
                "started_at": None if status == "queued" else created_at,
                "completed_at": "2026-04-20T14:30:00Z" if status == "completed" else None,
            }
        )
    return jobs


def telemetry_for_run(run_id: str, scale: float = 1.0) -> dict[str, Any]:
    rounds = 24
    stabilizers = 12
    noise_samples = [
        {
            "index": index,
            "physical_error_rate": round(0.006 + (math.sin(index / 4) + 1) * 0.0045 * scale, 6),
            "displacement_sigma": round(0.12 + (math.cos(index / 5) + 1) * 0.09 * scale, 6),
            "photon_loss_rate": round(0.009 + (math.sin(index / 6) + 1) * 0.003 * scale, 6),
        }
        for index in range(30)
    ]
    syndrome_samples = []
    for index in range(rounds * stabilizers):
        round_index = index // stabilizers
        stabilizer_index = index % stabilizers
        wave = math.sin((round_index + 1) * (stabilizer_index + 2) * 0.21)
        triggered = abs(wave) > 0.62
        syndrome_samples.append(
            {
                "round": round_index,
                "stabilizer": f"S{stabilizer_index + 1:02d}",
                "value": 1 if triggered and wave >= 0 else -1 if triggered else 0,
                "is_triggered": triggered,
            }
        )
    decoder_interventions = [
        {
            "decoder": decoder,
            "round": round_index,
            "flips": max(1, round((2.4 + decoder_index * 0.9) * (1 + math.sin(round_index * 0.31) * 0.18))),
            "residual_weight": max(
                1,
                round((1.6 + decoder_index * 0.55) * (1 + math.cos(round_index * 0.37) * 0.2)),
            ),
        }
        for decoder_index, decoder in enumerate(DECODERS)
        for round_index in range(rounds)
    ]
    oscillator_states = [
        {
            "round": index // 8,
            "mode": f"M{(index % 8) + 1:02d}",
            "q": round(math.cos(index * 0.37) * 0.72, 4),
            "p": round(math.sin(index * 0.41) * 0.72, 4),
            "variance": round(0.04 + abs(math.sin(index * 0.19)) * 0.08, 4),
            "energy": round(0.18 + abs(math.cos(index * 0.23)) * 0.24, 4),
            "flagged": abs(math.sin(index * 0.19)) > 0.78,
        }
        for index in range(rounds * 8)
    ]
    logical_trials = 2400
    logical_failures = max(1, round(41 * scale))
    return {
        "run_id": run_id,
        "request_count": logical_trials,
        "request_line_count": logical_trials,
        "response_line_count": logical_trials,
        "response_ratio": 1.0,
        "expanded_shot_count": logical_trials,
        "rounds": rounds,
        "stabilizer_count": stabilizers,
        "syndrome_opportunities": rounds * stabilizers,
        "decoder_name": "mwpm_gkp",
        "logical_failures": logical_failures,
        "logical_trials": logical_trials,
        "logical_error_rate": round(logical_failures / logical_trials, 6),
        "physical_error_events": 31,
        "physical_error_opportunities": 2880,
        "physical_error_rate": 0.010764,
        "residual_syndrome_events": 55,
        "residual_syndrome_rate": round(55 / (rounds * stabilizers), 6),
        "warning_rate": round(0.17 * scale, 6),
        "noise_samples": noise_samples,
        "syndrome_samples": syndrome_samples,
        "decoder_exact_metrics": [
            {"decoder": "bp_osd", "trials": logical_trials, "logical_failures": 47, "encoder_state": "gkp"},
            {"decoder": "mwpm_gkp", "trials": logical_trials, "logical_failures": logical_failures, "encoder_state": "gkp"},
            {"decoder": "union_find", "trials": logical_trials, "logical_failures": 63, "encoder_state": "gkp"},
        ],
        "gkp_oscillator_states": oscillator_states,
        "decoder_interventions": decoder_interventions,
        "updated_at": utcnow(),
    }


def run_fixture(providers: list[dict[str, Any]], jobs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    runs = [
        {
            "id": DEFAULT_RUN_ID,
            "job_id": jobs[0]["id"],
            "workflow_id": "pennylane-surface-code-policy",
            "provider_id": providers[0]["id"],
            "dataset_label": "pennylane_surface_d5_depolarizing_syndromes",
            "decoders": DECODERS,
            "status": "running",
            "message": "PennyLane surface-code circuit with depolarizing noise, extracted syndromes, and MWPM decoder policy.",
            "artifacts": [
                {
                    "name": "constructed_circuit",
                    "kind": "json",
                    "path": "public://runs/pennylane/constructed_circuit.json",
                    "sha256": None,
                    "created_at": "2026-04-20T14:09:00Z",
                },
                {
                    "name": "noise_injection",
                    "kind": "json",
                    "path": "public://runs/pennylane/noise_injection.json",
                    "sha256": None,
                    "created_at": "2026-04-20T14:09:30Z",
                },
                {
                    "name": "syndrome_trace",
                    "kind": "jsonl",
                    "path": "public://runs/pennylane/syndrome_trace.jsonl",
                    "sha256": None,
                    "created_at": "2026-04-20T14:10:00Z",
                },
                {
                    "name": "decoder_policy_metrics",
                    "kind": "csv",
                    "path": "public://runs/pennylane/decoder_policy_metrics.csv",
                    "sha256": None,
                    "created_at": "2026-04-20T14:11:30Z",
                },
            ],
            "metrics": {
                "avg_flip_count": 3.2,
                "nonempty_flip_rate": 0.34,
                "syndrome_satisfaction_rate": 0.92,
                "residual_nonzero_rate": 0.19,
                "warning_rate": 0.17,
                "logical_error_rate": 0.017083,
                "logical_failures": 41,
                "logical_trials": 2400,
                "best_decoder": "mwpm_gkp",
                "scientific_validation_ready": True,
            },
            "created_at": "2026-04-20T14:08:00Z",
            "updated_at": utcnow(),
        }
    ]
    dataset_labels = [
        "qiskit_aer_surface_d5_phase_flip_syndromes",
        "cirq_repetition_code_bitflip_syndromes",
        "schrosim_cv_gkp_loss_syndromes",
    ]
    workflow_ids = [
        "qiskit-aer-noise-policy",
        "cirq-syndrome-policy",
        "schrosim-cv-decoder-policy",
    ]
    messages = [
        "Qiskit Aer circuit with phase-flip noise, syndrome extraction, and decoder-policy replay.",
        "Cirq stabilizer circuit with bit-flip injection, syndrome extraction, and decoder-policy replay.",
        "SchroSIM CV photonic circuit with loss-style noise, syndrome extraction, and decoder-policy replay.",
    ]
    for index in range(1, 4):
        run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"lidmas-public-run-{index}"))
        runs.append(
            {
                "id": run_id,
                "job_id": jobs[index % len(jobs)]["id"],
                "workflow_id": workflow_ids[index - 1],
                "provider_id": providers[index % len(providers)]["id"],
                "dataset_label": dataset_labels[index - 1],
                "decoders": DECODERS,
                "status": "finished",
                "message": messages[index - 1],
                "artifacts": [],
                "metrics": {
                    "warning_rate": round(0.11 + index * 0.015, 6),
                    "logical_error_rate": round(0.012 + index * 0.003, 6),
                    "logical_failures": 29 + index * 6,
                    "logical_trials": 2400,
                    "best_decoder": DECODERS[index % len(DECODERS)],
                    "scientific_validation_ready": True,
                },
                "created_at": f"2026-04-20T14:{10 + index:02d}:00Z",
                "updated_at": utcnow(),
            }
        )
    telemetry = {run["id"]: telemetry_for_run(run["id"], 1.0 + index * 0.08) for index, run in enumerate(runs)}
    return runs, telemetry


PROVIDERS = provider_fixture()
JOBS = job_fixture(PROVIDERS)
RUNS, RUN_TELEMETRY = run_fixture(PROVIDERS, JOBS)
INTEGRATION_SESSIONS: list[dict[str, Any]] = []
HARDWARE_SESSIONS: list[dict[str, Any]] = []


app = FastAPI(
    title="LiDMaS+ Public API",
    version="1.2.2-public-demo",
    description="Public, fixture-backed LiDMaS+ API for Gottesman Studio.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["authorization", "content-type"],
)


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "LiDMaS+ Public API",
        "mode": "public-demo",
        "api": API_PREFIX,
        "docs": "/docs",
    }


@app.get("/health")
@app.get(f"{API_PREFIX}/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "1.2.2-public-demo",
        "started_at": STARTED_AT.isoformat().replace("+00:00", "Z"),
        "uptime_seconds": int(time.time() - STARTED_AT.timestamp()),
    }


@app.get(f"{API_PREFIX}/providers")
def list_providers() -> list[dict[str, Any]]:
    return deepcopy(PROVIDERS)


@app.post(f"{API_PREFIX}/providers")
async def create_provider_public() -> JSONResponse:
    return public_error("Provider creation is disabled in the public LiDMaS+ API.")


@app.get(f"{API_PREFIX}/jobs")
def list_jobs() -> list[dict[str, Any]]:
    return deepcopy(JOBS)


@app.post(f"{API_PREFIX}/jobs")
async def create_job(request: Request) -> dict[str, Any]:
    payload = await request.json()
    provider_id = payload.get("provider_id") or PROVIDERS[0]["id"]
    if not any(provider["id"] == provider_id for provider in PROVIDERS):
        raise HTTPException(status_code=404, detail="Provider not found")
    now = utcnow()
    job = {
        "id": str(uuid.uuid4()),
        "provider_id": provider_id,
        "dataset_label": str(payload.get("dataset_label") or "public_demo_job"),
        "decoders": payload.get("decoders") or DECODERS,
        "priority": int(payload.get("priority") or 5),
        "status": "queued",
        "message": "Created as an in-memory public demo job. It will reset when the service sleeps.",
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
    }
    JOBS.insert(0, job)
    return deepcopy(job)


@app.get(f"{API_PREFIX}/runs")
def list_runs() -> list[dict[str, Any]]:
    return deepcopy(RUNS)


@app.post(f"{API_PREFIX}/runs")
async def create_run(request: Request) -> dict[str, Any]:
    payload = await request.json()
    provider_id = payload.get("provider_id") or PROVIDERS[0]["id"]
    if not any(provider["id"] == provider_id for provider in PROVIDERS):
        raise HTTPException(status_code=404, detail="Provider not found")
    now = utcnow()
    run_id = str(uuid.uuid4())
    run = {
        "id": run_id,
        "job_id": payload.get("job_id"),
        "workflow_id": payload.get("workflow_id") or "public-demo-created-run",
        "provider_id": provider_id,
        "dataset_label": payload.get("dataset_label") or "public_created_replay",
        "decoders": payload.get("decoders") or DECODERS,
        "status": "finished",
        "message": "Created as a provider-safe public replay result.",
        "artifacts": [],
        "metrics": {
            "warning_rate": 0.12,
            "logical_error_rate": 0.014583,
            "logical_failures": 35,
            "logical_trials": 2400,
            "best_decoder": "mwpm_gkp",
            "scientific_validation_ready": True,
        },
        "created_at": now,
        "updated_at": now,
    }
    RUNS.insert(0, run)
    RUN_TELEMETRY[run_id] = telemetry_for_run(run_id, 0.9)
    return deepcopy(run)


@app.get(f"{API_PREFIX}/runs/{{run_id}}/telemetry")
def get_run_telemetry(run_id: str, scientific: bool = False) -> dict[str, Any]:
    telemetry = RUN_TELEMETRY.get(run_id)
    if telemetry is None:
        raise HTTPException(status_code=404, detail="Run telemetry not found")
    response = deepcopy(telemetry)
    if scientific:
        response["scientific_mode"] = True
    return response


@app.post(f"{API_PREFIX}/runs/{{run_id}}/telemetry")
async def upsert_run_telemetry(run_id: str, request: Request) -> dict[str, Any]:
    if not any(run["id"] == run_id for run in RUNS):
        raise HTTPException(status_code=404, detail="Run not found")
    payload = await request.json()
    telemetry = telemetry_for_run(run_id, 1.0)
    telemetry.update(payload)
    telemetry["run_id"] = run_id
    telemetry["updated_at"] = utcnow()
    RUN_TELEMETRY[run_id] = telemetry
    return deepcopy(telemetry)


@app.post(f"{API_PREFIX}/providers/{{provider_id}}/validate")
async def validate_provider(provider_id: str, request: Request) -> dict[str, Any]:
    if not any(provider["id"] == provider_id for provider in PROVIDERS):
        raise HTTPException(status_code=404, detail="Provider not found")
    payload = await request.json()
    request_lines = int(payload.get("request_lines") or 0)
    response_lines = int(payload.get("response_lines") or 0)
    request_errors = int(payload.get("request_parse_errors") or 0)
    response_errors = int(payload.get("response_parse_errors") or 0)
    decoder_mismatches = int(payload.get("decoder_name_mismatch_count") or 0)
    line_coverage_ok = request_lines > 0 and response_lines >= max(1, int(request_lines * 0.95))
    parse_integrity_ok = request_errors == 0 and response_errors == 0
    decoder_name_integrity_ok = decoder_mismatches == 0
    checks = [
        "Request and response line coverage inspected.",
        "JSON parse error counters inspected.",
        "Decoder naming consistency inspected.",
        "Public validation only; no private records or hardware sessions were accessed.",
    ]
    return {
        "provider_id": provider_id,
        "dataset_label": payload.get("dataset_label") or "public_validation",
        "line_coverage_ok": line_coverage_ok,
        "parse_integrity_ok": parse_integrity_ok,
        "decoder_name_integrity_ok": decoder_name_integrity_ok,
        "warning_rate": payload.get("warning_no_syndrome_count", 0) / max(1, response_lines),
        "overall_ok": line_coverage_ok and parse_integrity_ok and decoder_name_integrity_ok,
        "checks": checks,
        "checked_at": utcnow(),
    }


@app.get(f"{API_PREFIX}/hardware/schema")
def hardware_schema() -> dict[str, Any]:
    return {
        "schema_version": "public-demo-1",
        "frame_format": "disabled-public-demo",
        "notes": [
            "Hardware control is disabled in the public API.",
            "Use this page only to understand the future fixture and loopback data contract.",
            "Real instruments, credentials, sessions, and lab hardware remain private.",
        ],
        "create_session_request_example": {
            "provider_id": PROVIDERS[-1]["id"],
            "dataset_label": "loopback_timing_fixture",
            "decoders": DECODERS,
            "source_name": "public_loopback_fixture",
            "source_mode": "replay",
        },
        "frame_request_example": {
            "frames": [
                {
                    "frame_index": 0,
                    "source": "public_loopback_fixture",
                    "noise_sample": {
                        "physical_error_rate": 0.01,
                        "displacement_sigma": 0.2,
                        "photon_loss_rate": 0.012,
                    },
                    "syndrome_samples": [],
                    "decoder_interventions": [],
                }
            ]
        },
    }


@app.get(f"{API_PREFIX}/hardware/sessions")
def list_hardware_sessions() -> list[dict[str, Any]]:
    return deepcopy(HARDWARE_SESSIONS)


@app.post(f"{API_PREFIX}/hardware/sessions")
async def create_hardware_session_public() -> JSONResponse:
    return public_error("Hardware sessions are disabled in the public LiDMaS+ API.")


@app.post(f"{API_PREFIX}/hardware/sessions/{{session_id}}/frames")
async def ingest_hardware_frames_public(session_id: str) -> JSONResponse:
    return public_error(f"Hardware frame ingest is disabled for public session {session_id}.")


@app.post(f"{API_PREFIX}/hardware/sessions/{{session_id}}/complete")
async def complete_hardware_session_public(session_id: str) -> JSONResponse:
    return public_error(f"Hardware session completion is disabled for public session {session_id}.")


@app.post(f"{API_PREFIX}/system/credentials/ibm")
async def set_ibm_api_key_public() -> JSONResponse:
    return public_error("IBM credentials are not accepted or stored by the public LiDMaS+ API.")


@app.get(f"{API_PREFIX}/system/calibrations")
def vendor_calibrations() -> dict[str, Any]:
    return {
        "schema_version": "public-demo-1",
        "generated_at": utcnow(),
        "refresh_mode": "static-public-fixture",
        "snapshots": [
            {
                "id": "public-pennylane-surface-fixture",
                "label": "PennyLane surface-code depolarizing model",
                "vendor": "pennylane",
                "hardware_target": "simulated",
                "backend": "pennylane_default_qubit",
                "captured_at": "2026-04-20T14:00:00Z",
                "source": "public_simulator_fixture",
                "metrics": {"physical_error_rate": 0.0112, "syndrome_trigger_rate": 0.21, "logical_error_rate": 0.017083},
            },
            {
                "id": "public-qiskit-aer-fixture",
                "label": "Qiskit Aer phase-flip noise model",
                "vendor": "qiskit",
                "hardware_target": "simulated",
                "backend": "qiskit_aer",
                "captured_at": "2026-04-20T14:05:00Z",
                "source": "public_simulator_fixture",
                "metrics": {"phase_flip_rate": 0.014, "syndrome_trigger_rate": 0.18, "logical_error_rate": 0.015},
            },
            {
                "id": "public-cirq-fixture",
                "label": "Cirq repetition-code bit-flip model",
                "vendor": "cirq",
                "hardware_target": "simulated",
                "backend": "cirq_simulator",
                "captured_at": "2026-04-20T14:06:00Z",
                "source": "public_simulator_fixture",
                "metrics": {"bit_flip_rate": 0.0125, "syndrome_trigger_rate": 0.16, "logical_error_rate": 0.018},
            },
            {
                "id": "public-schrosim-fixture",
                "label": "SchroSIM CV photonic loss model",
                "vendor": "schrosim",
                "hardware_target": "simulated",
                "backend": "schrosim_cv",
                "captured_at": "2026-04-20T14:07:00Z",
                "source": "public_simulator_fixture",
                "metrics": {"photon_loss_rate": 0.021, "displacement_sigma": 0.16, "logical_error_rate": 0.021},
            },
        ],
        "notes": ["Static public simulator catalog. No live vendor credentials, hardware data, or private calibrations are loaded."],
    }


@app.post(f"{API_PREFIX}/system/calibrations/refresh")
async def refresh_vendor_calibrations_public() -> dict[str, Any]:
    return {
        "ok": True,
        "command": "public-demo:no-op",
        "duration_ms": 0,
        "exit_code": 0,
        "stdout_tail": ["Public demo uses a static calibration catalog."],
        "stderr_tail": [],
        "catalog_path": "public://calibrations/catalog.json",
        "refreshed_at": utcnow(),
        "catalog": vendor_calibrations(),
    }


@app.get(f"{API_PREFIX}/system/paper_04/manifest")
def paper_04_manifest() -> dict[str, Any]:
    return {
        "generated_at": utcnow(),
        "results_root": "public://paper_04",
        "artifact_count": 3,
        "manifest_hash": "public-demo-paper-04",
        "artifacts": [
            {"path": "comparison_summary.json", "exists": True, "size_bytes": 1412, "sha256": None},
            {"path": "decoder_table.csv", "exists": True, "size_bytes": 820, "sha256": None},
            {"path": "readme.txt", "exists": True, "size_bytes": 340, "sha256": None},
        ],
    }


@app.post(f"{API_PREFIX}/system/paper_04/run")
async def run_paper_04_public() -> JSONResponse:
    return public_error("Long paper-run execution is disabled in the public LiDMaS+ API.")


@app.get(f"{API_PREFIX}/integrations/sessions")
def list_integration_sessions() -> list[dict[str, Any]]:
    return deepcopy(INTEGRATION_SESSIONS)


@app.post(f"{API_PREFIX}/integrations/sessions")
async def create_integration_session_public(request: Request) -> dict[str, Any]:
    payload = await request.json()
    run_id = str(payload.get("run_id") or DEFAULT_RUN_ID)
    if not any(run["id"] == run_id for run in RUNS):
        run_id = DEFAULT_RUN_ID
    adapter_id = str(payload.get("adapter_id") or "pennylane_surface_replay")
    if "ibm" in adapter_id.lower() or str((payload.get("config") or {}).get("ibm_live_source_mode") or "").lower() == "qpu":
        return public_error("Live provider sessions are disabled in the public LiDMaS+ API.")
    provider = "pennylane"
    if "schrosim" in adapter_id:
        provider = "schrosim"
    elif "qiskit" in adapter_id:
        provider = "qiskit"
    elif "cirq" in adapter_id:
        provider = "cirq"
    elif "pennylane" in adapter_id:
        provider = "pennylane"
    elif "ankaa" in adapter_id:
        provider = "ankaa"
    now = utcnow()
    session = {
        "id": str(uuid.uuid4()),
        "run_id": run_id,
        "provider": provider,
        "mode": "replay_static",
        "adapter_id": adapter_id,
        "status": "finished",
        "config": payload.get("config") or {},
        "started_at": now,
        "updated_at": now,
        "ended_at": now,
        "exit_code": 0,
        "last_error": None,
    }
    INTEGRATION_SESSIONS.insert(0, session)
    return deepcopy(session)


@app.post(f"{API_PREFIX}/integrations/sessions/{{session_id}}/stop")
async def stop_integration_session_public(session_id: str) -> dict[str, Any]:
    return {
        "session": {
            "id": session_id,
            "run_id": DEFAULT_RUN_ID,
            "provider": "pennylane",
            "mode": "replay_static",
            "adapter_id": "pennylane_surface_replay",
            "status": "cancelled",
            "config": {},
            "started_at": utcnow(),
            "updated_at": utcnow(),
            "ended_at": utcnow(),
            "exit_code": 0,
            "last_error": None,
        },
        "stopped": True,
        "message": "No live session was running in public demo mode.",
    }


@app.get(f"{API_PREFIX}/integrations/sessions/{{session_id}}/logs")
def integration_session_logs(session_id: str, tail: int = 100) -> dict[str, Any]:
    lines = [
        {
            "timestamp": utcnow(),
            "stream": "system",
            "line": "Public demo session logs are static; no external provider was contacted.",
        }
    ]
    return {"session_id": session_id, "total_lines": len(lines), "has_more": False, "lines": lines[-tail:]}


@app.post(f"{API_PREFIX}/system/logscan")
async def system_log_scan(request: Request) -> dict[str, Any]:
    payload = await request.json()
    logs = payload.get("logs") or []
    custom_rules = payload.get("custom_rules") or []
    suppressions = payload.get("suppressions") or []
    max_findings = int(payload.get("max_findings") or 50)
    default_rules = [
        {
            "id": "public-secret-token",
            "title": "Potential secret token",
            "pattern": r"(api[_-]?key|token|secret|password)",
            "severity": "high",
            "confidence": 0.85,
            "tags": ["secrets", "public-demo"],
            "recommendation": "Remove secrets before sharing public replay artifacts.",
        },
        {
            "id": "hardware-claim",
            "title": "Hardware claim needs label",
            "pattern": r"(qpu|hardware|instrument|detector|board)",
            "severity": "medium",
            "confidence": 0.7,
            "tags": ["claim-boundary"],
            "recommendation": "Label whether this is simulated, loopback, replayed, or partner-lab evidence.",
        },
    ]
    rules = default_rules + custom_rules
    findings: list[dict[str, Any]] = []
    suppressed = 0
    for line_index, entry in enumerate(logs):
        message = str(entry.get("message") or "")
        lowered = message.lower()
        is_suppressed = any(str(item.get("pattern") or "").lower() in lowered for item in suppressions)
        for rule in rules:
            pattern = str(rule.get("pattern") or "")
            if not pattern:
                continue
            if re.search(pattern, message, re.IGNORECASE):
                if is_suppressed:
                    suppressed += 1
                    continue
                findings.append(
                    {
                        "rule_id": rule.get("id") or "custom-rule",
                        "rule_origin": "custom" if rule in custom_rules else "default",
                        "title": rule.get("title") or "Log finding",
                        "severity": rule.get("severity") or "info",
                        "confidence": float(rule.get("confidence") or 0.5),
                        "line_index": line_index,
                        "timestamp": entry.get("timestamp"),
                        "level": entry.get("level"),
                        "source": entry.get("source"),
                        "message": message,
                        "tags": rule.get("tags") or [],
                        "recommendation": rule.get("recommendation"),
                    }
                )
                if len(findings) >= max_findings:
                    break
        if len(findings) >= max_findings:
            break
    severity_counts = {level: sum(1 for finding in findings if finding["severity"] == level) for level in ["critical", "high", "medium", "low", "info"]}
    verdict = "critical" if severity_counts["critical"] else "warn" if findings else "pass"
    return {
        "scan_id": str(uuid.uuid4()),
        "summary": {
            "scanned_entries": len(logs),
            "matched_entries": len(findings),
            "suppressed_matches": suppressed,
            "critical_count": severity_counts["critical"],
            "high_count": severity_counts["high"],
            "medium_count": severity_counts["medium"],
            "low_count": severity_counts["low"],
            "info_count": severity_counts["info"],
            "risk_score": min(100, severity_counts["critical"] * 40 + severity_counts["high"] * 25 + severity_counts["medium"] * 12),
            "verdict": verdict,
        },
        "findings": findings,
        "top_recommendations": list({finding.get("recommendation") for finding in findings if finding.get("recommendation")})[:5],
        "generated_at": utcnow(),
    }
