#!/usr/bin/env python3
"""Submit paper_05 repetition-code syndrome circuits to IBM Runtime Sampler."""

from __future__ import annotations

import argparse
import collections
import json
import os
from pathlib import Path
from typing import Any

from repetition_syndrome import build_qiskit_circuit, circuit_metadata, experiment_specs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--n-data", type=int, default=5)
    parser.add_argument("--targets", default="all")
    parser.add_argument("--shots", type=int, default=256)
    parser.add_argument("--backend", default="", help="IBM backend name. If omitted, least-busy hardware is selected.")
    parser.add_argument("--instance", default="", help="Optional IBM Quantum instance/hub/group/project.")
    parser.add_argument(
        "--credentials-file",
        default="",
        help="Optional local JSON file with token, instance, and backend. Defaults to paper_05/ibm_credentials.local.json if present.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Submit the Runtime job and write job metadata without waiting for results.",
    )
    parser.add_argument(
        "--result-timeout",
        type=float,
        default=900.0,
        help="Maximum seconds to wait for Runtime results when waiting is enabled.",
    )
    parser.add_argument("--optimization-level", type=int, default=1)
    return parser.parse_args()


def default_credentials_path() -> Path:
    return Path(__file__).resolve().parents[1] / "ibm_credentials.local.json"


def load_credentials(path_arg: str) -> dict[str, str]:
    path = Path(path_arg).expanduser() if path_arg else default_credentials_path()
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return {str(k): str(v) for k, v in raw.items() if v is not None and str(v).strip()}


def load_service(instance: str, token: str, channel: str) -> Any:
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService  # type: ignore
    except Exception as exc:
        raise SystemExit(
            "qiskit-ibm-runtime is required for hardware submission. "
            "Install it in the active Python environment."
        ) from exc

    kwargs: dict[str, Any] = {}
    if instance:
        kwargs["instance"] = instance
    if token:
        kwargs["channel"] = channel
        kwargs["token"] = token
    try:
        return QiskitRuntimeService(**kwargs)
    except Exception as exc:
        raise SystemExit(
            "Could not initialize QiskitRuntimeService. Configure credentials with a saved "
            "Qiskit IBM Runtime account, set IBM_QUANTUM_TOKEN, or create "
            "examples/paper_runs/paper_05/ibm_credentials.local.json. If your account "
            "requires an instance, include instance=hub/group/project."
        ) from exc


def choose_backend(service: Any, backend_name: str, min_qubits: int) -> Any:
    if backend_name:
        return service.backend(backend_name)
    try:
        return service.least_busy(operational=True, simulator=False, min_num_qubits=min_qubits)
    except TypeError:
        candidates = [
            backend
            for backend in service.backends(simulator=False, operational=True)
            if getattr(backend, "num_qubits", 0) >= min_qubits
        ]
        if not candidates:
            raise SystemExit(f"No operational IBM hardware backend with at least {min_qubits} qubits was found.")
        return sorted(candidates, key=lambda b: getattr(getattr(b, "status", lambda: None)(), "pending_jobs", 10**9))[0]


def transpile_for_backend(circuits: list[Any], backend: Any, optimization_level: int) -> list[Any]:
    try:
        from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager  # type: ignore

        pm = generate_preset_pass_manager(backend=backend, optimization_level=optimization_level)
        return list(pm.run(circuits))
    except Exception:
        from qiskit import transpile  # type: ignore

        return list(transpile(circuits, backend=backend, optimization_level=optimization_level))


def sampler_class() -> Any:
    try:
        from qiskit_ibm_runtime import SamplerV2 as Sampler  # type: ignore

        return Sampler
    except Exception:
        from qiskit_ibm_runtime import Sampler  # type: ignore

        return Sampler


def extract_counts(pub_result: Any) -> dict[str, int]:
    data = getattr(pub_result, "data", pub_result)
    bit_array = getattr(data, "meas", None)
    if bit_array is None:
        for name in dir(data):
            if name.startswith("_"):
                continue
            candidate = getattr(data, name)
            if hasattr(candidate, "get_counts") or hasattr(candidate, "get_bitstrings"):
                bit_array = candidate
                break
    if bit_array is None:
        raise RuntimeError("Could not locate a measured classical register in Sampler result.")

    if hasattr(bit_array, "get_counts"):
        counts = bit_array.get_counts()
        return {str(k): int(v) for k, v in counts.items()}
    if hasattr(bit_array, "get_bitstrings"):
        return dict(collections.Counter(str(b) for b in bit_array.get_bitstrings()))
    raise RuntimeError("Sampler result object does not expose counts or bitstrings.")


def job_id_value(job: Any) -> str:
    value = getattr(job, "job_id", "")
    if callable(value):
        value = value()
    return str(value)


def write_submission(
    path: Path,
    *,
    backend_name: str,
    job_id: str,
    shots: int,
    n_data: int,
    optimization_level: int,
    status: str,
    experiments: list[dict[str, Any]],
) -> None:
    payload = {
        "schema": "paper05_ibm_submission_v1",
        "source": "ibm_runtime",
        "backend": backend_name,
        "job_id": job_id,
        "shots": shots,
        "n_data": n_data,
        "n_checks": n_data - 1,
        "optimization_level": optimization_level,
        "status": status,
        "experiments": experiments,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def main() -> int:
    args = parse_args()
    if args.n_data < 3:
        raise SystemExit("Error: --n-data must be at least 3.")
    if args.shots <= 0:
        raise SystemExit("Error: --shots must be positive.")

    creds = load_credentials(args.credentials_file)
    token = (
        os.environ.get("IBM_QUANTUM_TOKEN")
        or os.environ.get("QISKIT_IBM_TOKEN")
        or creds.get("token", "")
        or creds.get("ibm_quantum_token", "")
    )
    instance = args.instance or os.environ.get("IBM_QUANTUM_INSTANCE", "") or creds.get("instance", "")
    channel = os.environ.get("IBM_QUANTUM_CHANNEL", "") or creds.get("channel", "") or "ibm_quantum_platform"
    backend_name_arg = args.backend or creds.get("backend", "")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    specs = experiment_specs(args.n_data, args.targets)
    circuits = [build_qiskit_circuit(args.n_data, spec) for spec in specs]
    experiment_metadata = [circuit_metadata(args.n_data, spec) for spec in specs]
    service = load_service(instance, token, channel)
    backend = choose_backend(service, backend_name_arg, min_qubits=(2 * args.n_data - 1))
    backend_name = getattr(backend, "name", None)
    if callable(backend_name):
        backend_name = backend_name()
    backend_name = str(backend_name or backend)

    isa_circuits = transpile_for_backend(circuits, backend, args.optimization_level)
    Sampler = sampler_class()
    sampler = Sampler(backend)
    job = sampler.run(isa_circuits, shots=args.shots)
    job_id = job_id_value(job)
    submission_path = out_dir / "ibm_runtime_submission.json"
    write_submission(
        submission_path,
        backend_name=backend_name,
        job_id=job_id,
        shots=args.shots,
        n_data=args.n_data,
        optimization_level=args.optimization_level,
        status="submitted",
        experiments=experiment_metadata,
    )
    print(f"Submitted IBM Runtime job {job_id} on {backend_name}; wrote {submission_path}")

    if args.no_wait:
        print("Not waiting for results because --no-wait was set.")
        return 0

    try:
        result = job.result(timeout=args.result_timeout)
    except TypeError:
        result = job.result()

    experiments: list[dict[str, Any]] = []
    for spec, pub_result in zip(specs, result):
        experiments.append(
            {
                **circuit_metadata(args.n_data, spec),
                "counts": dict(sorted(extract_counts(pub_result).items())),
            }
        )

    payload = {
        "schema": "paper05_repetition_results_v1",
        "source": "ibm_runtime",
        "backend": backend_name,
        "job_id": job_id,
        "shots": args.shots,
        "n_data": args.n_data,
        "n_checks": args.n_data - 1,
        "optimization_level": args.optimization_level,
        "experiments": experiments,
    }
    out_path = out_dir / "ibm_repetition_results.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"Wrote IBM Runtime repetition results to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
