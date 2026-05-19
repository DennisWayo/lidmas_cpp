# IBM Superconducting Hardware Integration

IBM Quantum live-data adapter for LiDMaS+ superconducting workflows.

- `ibm_live_noise_stream.py`: poll IBM Quantum backend properties and emit live normalized frames.
- `run_ibm_live_stream.sh`: wrapper that handles optional dependency install and output path setup.

The adapter can optionally push rolling telemetry snapshots to LiDMaS+ backend:

- `POST /api/v1/runs/{run_id}/telemetry`

## Quick Start

Start IBM live polling adapter:

```bash
export IBM_QUANTUM_API_KEY="<api-key>"
bash hardware_integration/ibm/superconducting/run_ibm_live_stream.sh \
  --backend-name ibm_kingston \
  --poll-interval 30
```

## Dependency Notes

IBM live polling needs `qiskit-ibm-runtime` (and Qiskit dependencies).

Install automatically from wrapper:

```bash
bash hardware_integration/ibm/superconducting/run_ibm_live_stream.sh --install-deps --backend-name ...
```

All generated files are written under:

- `examples/results/hardware_integration/ibm/superconducting/`
