# Xanadu Hardware Integration

Xanadu public-data integration for LiDMaS+ (Aurora, QCA, GKP, and legacy job JSON).

## Quick Start

```bash
bash hardware_integration/xanadu/run.sh
bash hardware_integration/xanadu/run_public_datasets.sh
bash hardware_integration/xanadu/xandau_hardware_data.sh --install-deps
```

Replay converted requests through the C++ decoder adapter:

```bash
bash hardware_integration/xanadu/replay.sh
```

All generated requests/responses are written to:

- `examples/results/hardware_integration/`
