# Getting Started

## Installation paths

### 1) PyPI install (recommended)

```bash
python -m pip install --upgrade lidmas
lidmas --help
```

### 2) Source build

```bash
cmake -S . -B build
cmake --build build -j
./build/lidmas --help
```

If you built from source and did not install from PyPI, replace `lidmas` below with `./build/lidmas`.

## Requirements

- C++20 compiler
- CMake >= 3.16
- Optional: OpenMP for parallel threshold runs
- Optional: CUDA toolkit (for GPU-accelerated Pauli surface_threshold sampling)
- Optional: Python 3 with `matplotlib` and `pandas` for plots (example plotting)

## First commands

Show CLI help:

```bash
lidmas --help
```

Engine switch examples:

```bash
lidmas --engine=surface
lidmas --engine=css \
  --css_spec=examples/css_codes/steane/spec.yaml
lidmas --engine=css \
  --css_repetition=7
lidmas --engine=css \
  --css_shor
lidmas --engine=ldpc
```

Run deterministic smoke test:

```bash
lidmas --smoke
```

## Pauli threshold sweep

```bash
lidmas --engine=surface --surface_threshold \
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
lidmas --engine=surface --surface_threshold \
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
lidmas --engine=surface --surface_threshold \
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
lidmas --engine=css --css_threshold \
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
