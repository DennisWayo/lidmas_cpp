# Getting Started

## Requirements

- C++20 compiler
- CMake >= 3.16
- Optional: OpenMP for parallel threshold runs
- Optional: CUDA toolkit (for GPU-accelerated Pauli surface_threshold sampling)
- Optional: Python 3 with `matplotlib` and `pandas` for plots

## Build

```bash
cmake -S . -B build
cmake --build build -j
```

Primary executable:

- `build/lidmas`

## First commands

Show CLI help:

```bash
./build/lidmas --help
```

Engine switch examples:

```bash
./build/lidmas --engine=surface
./build/lidmas --engine=css \
  --css_spec=examples/css_codes/steane/spec.yaml
./build/lidmas --engine=css \
  --css_repetition=7
./build/lidmas --engine=css \
  --css_shor
./build/lidmas --engine=ldpc
```

Run deterministic smoke test:

```bash
./build/lidmas --smoke
```

## Pauli threshold sweep

```bash
./build/lidmas --engine=surface --surface_threshold \
  --mode=pauli \
  --decoder=mwpm \
  --d=3,5,7 \
  --p_start=0.01 --p_end=0.15 --p_step=0.01 \
  --trials=2000 \
  --seed=1337 \
  --out=surface_threshold.csv
```

## Hybrid CV sweep

```bash
./build/lidmas --engine=surface --surface_threshold \
  --mode=hybrid \
  --decoder=mwpm \
  --d=3,5,7 \
  --sigma_start=0.05 --sigma_end=0.60 --sigma_step=0.05 \
  --trials=2000 \
  --seed=1337 \
  --out=surface_threshold.csv
```

## GKP sweep (native lattice)

```bash
./build/lidmas --engine=surface --surface_threshold \
  --mode=gkp \
  --decoder=mwpm \
  --d=3,5,7 \
  --sigma_start=0.05 --sigma_end=0.60 --sigma_step=0.05 \
  --gkp_gate=0.0005 --gkp_meas=0.0005 --gkp_idle=0.0002 \
  --gkp_loss=0.001 \
  --trials=2000 \
  --seed=1337 \
  --out=gkp_surface_threshold.csv
```

Neural decoder note:

- `--decoder=neural_mwpm` requires `--neural_model=<path>`.
- Trained reference model: `examples/decoder_comparison/trained_model.json`.
- Retrain/update: `python3 examples/decoder_comparison/train_neural_model.py`.

## CSS threshold sweep (experimental)

```bash
./build/lidmas --engine=css --css_threshold \
  --mode=pauli \
  --decoder=bp_sum \
  --css_spec=examples/css_codes/steane/spec.yaml \
  --trials=2000 \
  --seed=7300000 \
  --out=css_threshold.csv
```

CSS matrix files are dense 0/1 text (space or comma separated). Logical files can include multiple rows.

`--css_repetition=<n>` builds a bit-flip repetition code automatically (Hx empty, Hz chain).
`--css_shor` builds the Shor [[9,1,3]] code automatically.

## Output schema

Threshold CSV columns:

`mode,distance,sigma,pauli_p,trials,ler,ci_low,ci_high,defect_mean,weight_mean,decoder_fail_rate,mwpm_weight_scale,mwpm_graph,timestamp`
