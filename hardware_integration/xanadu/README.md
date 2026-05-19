# Xanadu Hardware Integration

Xanadu public-data integration for LiDMaS+ (Aurora, QCA, GKP, and legacy job JSON).

## Quick Start

```bash
bash hardware_integration/xanadu/run.sh
bash hardware_integration/xanadu/run_public_datasets.sh
bash hardware_integration/xanadu/xandau_hardware_data.sh --install-deps
bash hardware_integration/xanadu/run_gkp_remote_ssh.sh --remote-input-root /Volumes/quantum/xanadu_gkp_33gb
```

Replay converted requests through the C++ decoder adapter:

```bash
bash hardware_integration/xanadu/replay.sh
```

Remote-first GKP workflow (compute on remote host, copy NDJSON locally, then replay):

```bash
bash hardware_integration/xanadu/run_gkp_remote_ssh.sh \
  --remote dela@macstudio \
  --remote-input-root /Volumes/quantum/xanadu_gkp_33gb
```

All generated requests/responses are written to:

- `examples/results/hardware_integration/`
