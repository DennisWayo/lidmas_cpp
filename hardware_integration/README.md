# Hardware Integration

Provider-oriented hardware integration entry point for LiDMaS+.

## Providers

- `ankaa/`: replay adapters for superconducting QEC data workflows.
- `ibm/`: live polling adapters for IBM superconducting backends.
- `xanadu/`: converters, mappings, demos, and real-data download/replay scripts for Aurora/QCA/GKP workflows.
- `calibration/`: periodic vendor calibration snapshot refresh pipeline.

## Quick Start

```bash
bash hardware_integration/xanadu/run.sh
bash hardware_integration/xanadu/run_public_datasets.sh
bash hardware_integration/xanadu/xandau_hardware_data.sh --install-deps
bash hardware_integration/ankaa/superconducting/run_ankaa_stream.sh --input hardware_integration/ankaa/superconducting/ankaa_fixture_example.json
bash hardware_integration/ibm/superconducting/run_ibm_live_stream.sh --backend-name ibm_kingston --poll-interval 30
python3 hardware_integration/calibration/refresh_vendor_calibrations.py --workspace-root .
```

Outputs stay centralized in:

- `examples/results/hardware_integration/`

Calibration snapshot catalog output:

- `hardware_integration/calibration/vendor_calibrations.live.json`

## Periodic Calibration Refresh

The backend now runs a periodic calibration refresh loop in-process and writes:

- `hardware_integration/calibration/vendor_calibrations.live.json`

Environment controls:

- `LIDMAS_CALIBRATION_REFRESH_ENABLED` (`1|0`, default `1`)
- `LIDMAS_CALIBRATION_REFRESH_INTERVAL_SECONDS` (default `900`)
- `LIDMAS_CALIBRATION_REFRESH_TIMEOUT_SECONDS` (default `120`)

IBM live calibration ingestion uses:

- `IBM_QUANTUM_API_KEY` (optional; without this, IBM defaults are retained)

Manual API endpoints:

- `GET /api/v1/system/calibrations`
- `POST /api/v1/system/calibrations/refresh`
