# Getting Started

## Requirements

- C++20 compiler
- CMake >= 3.16
- Optional: OpenMP for parallel threshold runs
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

Run deterministic smoke test:

```bash
./build/lidmas --smoke
```

## Pauli threshold sweep

```bash
./build/lidmas --surface_threshold \
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
./build/lidmas --surface_threshold \
  --mode=hybrid \
  --decoder=mwpm \
  --d=3,5,7 \
  --sigma_start=0.05 --sigma_end=0.60 --sigma_step=0.05 \
  --trials=2000 \
  --seed=1337 \
  --out=surface_threshold.csv
```

Neural decoder note:

- `--decoder=neural_mwpm` requires `--neural_model=<path>`.

## Output schema

Threshold CSV columns:

`mode,distance,sigma,pauli_p,trials,ler,ci_low,ci_high,defect_mean,weight_mean,decoder_fail_rate,mwpm_weight_scale,mwpm_graph,timestamp`

