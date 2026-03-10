# Decoder Comparison Example

This example benchmarks three surface-code decoders at fixed distance (`d=5`) over a Pauli noise sweep:

- `mwpm`: minimum-weight perfect matching baseline (high-accuracy reference).
- `uf`: Union-Find decoder (faster approximate decoder).
- `neural_mwpm`: MWPM with learned edge weighting using `trained_model.json`.

## Expected Behavior

- `UF` is typically worse than `MWPM` at the same physical error rate.
- `Neural MWPM` uses a lightweight linear model trained from LiDMaS simulator feedback.

## Run

From this directory:

```bash
./run.sh
```

The script builds the project, runs all three decoders, merges outputs, and generates figures.

## Model Training

To retrain/update the neural model:

```bash
python3 train_neural_model.py
```

This writes:

- `examples/decoder_comparison/trained_model.json`

You can also point `run.sh` to a custom model:

```bash
LIDMAS_NEURAL_MODEL=/path/to/model.json ./run.sh
```

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
