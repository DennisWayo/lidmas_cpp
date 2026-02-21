# Pauli Threshold Example

This run performs the baseline **Pauli noise threshold sweep**:

- Surface-code distances: `d=3,5,7`
- Noise mode: `pauli`
- Decoder: MWPM
- Pauli error range: `p=0.01` to `0.15` in steps of `0.01`

## Run

From any directory:

```bash
./examples/pauli_threshold/run.sh
```

Optional quick run:

```bash
LIDMAS_TRIALS=200 ./examples/pauli_threshold/run.sh
```

## Outputs

- `examples/results/pauli_threshold/surface_threshold.csv`
- `examples/results/pauli_threshold/figure_pauli_threshold.png` (600 dpi)
- `examples/results/pauli_threshold/figure_pauli_threshold.pdf`
- `examples/results/pauli_threshold/figure_pauli_threshold.svg`

This produces the standard logical error rate (LER) vs `p` curve and does **not** use CV/GKP digitization. It is intended as the baseline comparison against hybrid mode.
