# CLI Reference

This page summarizes the main `lidmas` command-line entry points.

## Main entry points

- `./lidmas`
  - Runs the classical LDPC BSC sweep (default mode).
- `./lidmas --qec=css_demo`
  - Runs CSS demo using BP decoder core.
- `./lidmas --surface_demo=stub|mwpm|uf|neural_mwpm`
  - Runs surface pipeline demo.
- `./lidmas --surface_threshold ...`
  - Runs threshold sweeps over `pauli` or `hybrid` mode.
- `./lidmas --smoke`
  - Runs lightweight surface smoke checks.

## Threshold command pattern

```bash
./lidmas --surface_threshold \
  --decoder=<mwpm|uf|neural_mwpm> \
  --d=3,5,7 \
  --mode=<pauli|hybrid> \
  --trials=2000 \
  --seed=12345 \
  --out=surface_threshold.csv
```

Mode-specific sweep parameters:

- Pauli: `--p_start --p_end --p_step`
- Hybrid: `--sigma_start --sigma_end --sigma_step`

## Key options

### Decoder and weighting

- `--decoder=<name>`
- `--neural_model=<path>`
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
- `--quiet-iter-log`
- `--help` / `-h`

## BP options

- `--bp=sum-product`
- `--bp=nms`
- `--alpha=<value>`

