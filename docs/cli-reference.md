# CLI Reference

This page summarizes the main `lidmas` command-line entry points.

## Main entry points

- `./lidmas`
  - Runs the classical LDPC BSC sweep (default mode).
- `./lidmas --engine=surface`
  - Selects surface-code engine routing.
- `./lidmas --engine=css`
  - Selects CSS engine routing (requires `--css_spec` or `--css_hx/--css_hz/--css_lx/--css_lz`).
- `./lidmas --engine=ldpc`
  - Selects LDPC engine routing (same behavior as default).
- `./lidmas --qec=css_demo`
  - Runs CSS demo using BP decoder core (requires `--css_spec` or `--css_hx/--css_hz/--css_lx/--css_lz`).
- `./lidmas --surface_demo=stub|mwpm|uf|neural_mwpm|bp` (use `--mode=gkp` for a sigma sweep)
- `--demo_sigma_start/--demo_sigma_end/--demo_sigma_step` (surface demo sigma sweep)
- `--demo_sigma_values=0.10,0.15,0.20` (explicit surface demo sigma values)
- `--demo_d=5` (surface demo distance)
- `--demo_trials=500` (surface demo trials per point)
- `--demo_seed=8400000` (surface demo seed base)
- `--demo_distance_list=3,5,7` (surface demo distances list)
- `--demo_seed_per_distance` (salt seed by distance)
- `--demo_sigma_by_d=3:0.10,0.12;5:0.14,0.16` (per-distance sigma overrides)
- `--demo_p_by_d=3:0.01,0.02;5:0.015` (per-distance p overrides)
  - Runs surface pipeline demo.
- `./lidmas --surface_threshold ...`
  - Runs threshold sweeps over `pauli` or `hybrid` mode.
- `./lidmas --css_threshold ...`
  - Runs CSS threshold sweeps over `pauli` or `hybrid` mode.
- `./lidmas --smoke`
  - Runs lightweight surface smoke checks.

## Threshold command pattern

```bash
./lidmas --engine=surface --surface_threshold \
  --decoder=<mwpm|uf|neural_mwpm|bp> \
  --d=3,5,7 \
  --mode=<pauli|hybrid|gkp> \
  --trials=2000 \
  --seed=12345 \
  --out=surface_threshold.csv
```

Mode-specific sweep parameters:

- Pauli: `--p_start --p_end --p_step`
- Hybrid: `--sigma_start --sigma_end --sigma_step`
- GKP: `--sigma_start --sigma_end --sigma_step` (plus GKP noise flags)

## CSS threshold command pattern

```bash
./lidmas --engine=css --css_threshold \
  --decoder=<bp|bp_sum|bp_nms> \
  --css_spec=<path> \
  # or: --css_hx=<path> --css_hz=<path> --css_lx=<path> --css_lz=<path> \
  --mode=<pauli|hybrid> \
  --trials=2000 \
  --seed=7300000 \
  --out=css_threshold.csv
```

CSS matrix files are dense 0/1 text (space or comma separated). Logical files can include multiple rows.

CSS spec files must define string paths for `hx`, `hz`, `lx`, and `lz` (JSON or YAML key/value).

## Key options

### Engine routing

- `--engine=<surface|css|ldpc>`

### Decoder and weighting

- `--decoder=<name>`
- `--css_spec=<path>`
- `--css_repetition=<n>`
- `--css_shor`
- `--css_hx=<path>`
- `--css_hz=<path>`
- `--css_lx=<path>`
- `--css_lz=<path>`
- `--neural_model=<path>`
  - Recommended starter path: `examples/decoder_comparison/trained_model.json`
- `--weight_mode=<uniform|neural|llr>`
- `--mwpm_weight_scale=<x>`
- `--mwpm_graph=<full|simple>`
- `--uf_weighted`
- `--neural_weights=<path>`

### LLR controls

- `--llr_p_data=<x>`
- `--llr_p_meas=<x>`
- `--llr_p_idle=<x>`
- `--llr_clamp_min=<x>`
- `--llr_clamp_max=<x>`

### Adaptive CI and scaling

- `--min_trials=<N>`
- `--max_trials=<N>`
- `--batch_trials=<N>`
- `--target_ci_halfwidth=<x>`
- `--target_rel_ci=<x>`
- `--auto_threshold`
- `--estimate_threshold`
- `--scaling_fit`
- `--scaling_bootstrap=<N>`
- `--scaling_seed=<uint>`
- `--pc_min=<x> --pc_max=<x>`
- `--nu_min=<x> --nu_max=<x>`
- `--grid_pc=<N> --grid_nu=<N>`
- `--ler_smooth_eps=<x>`
- `--scaling_report=<path>`
- `--scaling_json=<path>`

### Runtime

- `--threads=<N>`
- `--gpu` (CUDA backend for pauli surface_threshold sampling)
- `--gpu_bench` (CPU vs GPU sampling benchmark)
- `--gpu_bench_quick`
- `--gpu_bench_full`
- `--gpu_bench_d=<odd>`
- `--gpu_bench_trials=<N>`
- `--gpu_bench_batch=<N>`
- `--gpu_bench_p=<x>`
- `--gpu_bench_seed=<uint>`
- `--quiet-iter-log`
- `--help` / `-h`

### GKP controls (mode=gkp)

- `--gkp_gate=<x>`
- `--gkp_meas=<x>`
- `--gkp_idle=<x>`
- `--gkp_loss=<x>`
- `--gkp_loss_map=<path>`

## BP options

- `--bp=sum-product`
- `--bp=nms`
- `--alpha=<value>`

These options apply to LDPC, CSS, and surface `--decoder=bp`.

`--css_repetition` and `--css_shor` are mutually exclusive with `--css_spec` and `--css_hx/--css_hz/--css_lx/--css_lz`.
