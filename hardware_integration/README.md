# Hardware Integration

Provider-oriented hardware integration entry point for LiDMaS+.

## Providers

- `xanadu/`: converters, mappings, demos, and real-data download/replay scripts for Aurora/QCA/GKP workflows.

## Quick Start

```bash
bash hardware_integration/xanadu/run.sh
bash hardware_integration/xanadu/run_public_datasets.sh
bash hardware_integration/xanadu/xandau_hardware_data.sh --install-deps
```

Outputs stay centralized in:

- `examples/results/hardware_integration/`
