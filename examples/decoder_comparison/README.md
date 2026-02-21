# Decoder Comparison Example

This example benchmarks three surface-code decoders at fixed distance (`d=5`) over a Pauli noise sweep:

- `mwpm`: minimum-weight perfect matching baseline (high-accuracy reference).
- `uf`: Union-Find decoder (faster approximate decoder).
- `neural_mwpm`: MWPM with learned edge weighting. This example uses a deterministic dummy model (`dummy_model.json`) for reproducibility.

## Expected Behavior

- `UF` is typically worse than `MWPM` at the same physical error rate.
- `Neural MWPM` should be close to `MWPM` here because the dummy model is a simple linear demonstration model.

## Run

From this directory:

```bash
./run.sh
```

The script builds the project, runs all three decoders, merges outputs, and generates figures.

## Outputs

All outputs are saved to:

`examples/results/decoder_comparison/`

Files:

- `results_mwpm.csv`
- `results_uf.csv`
- `results_neural.csv`
- `decoder_comparison_combined.csv`
- `figure_decoder_comparison.png`
- `figure_decoder_comparison.pdf`
- `figure_decoder_comparison.svg`
