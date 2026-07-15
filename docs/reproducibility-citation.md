# Reproducibility and Citation

## Reproducibility

LiDMaS+ is designed for deterministic reruns:

- explicit seed control in CLI,
- deterministic per-trial seed mixing,
- scripted workflows under `examples/`,
- centralized artifact outputs in `examples/results/`.

For quick CI/local validation:

```bash
lidmas --smoke
```

If installed from source only, use `./build/lidmas --smoke`.

## Validation checklist

1. Build from a clean checkout.
2. Run `--smoke`.
3. Run one full sweep (`pauli` or `hybrid`) with fixed `--seed`.
4. Confirm CSV schema and CI fields are present.
5. (Optional) run matching example script and compare generated figure + CSV paths.

## Citation

If you use LiDMaS+ in academic work, cite the software release used for experiments (tag + commit hash). If a JOSS/arXiv record exists for your version, cite that record directly.

## PyPI package

- Package name: `lidmas`
- Install: `python -m pip install --upgrade lidmas`
- Check installed version:

```bash
python -c "import importlib.metadata as m; print(m.version('lidmas'))"
```

Suggested software citation:

```text
Wayo, D. (Year). LiDMaS+ (Version X.Y.Z) [Computer software].
https://github.com/Gottesman-Software/lidmas_cpp
```

## License

LiDMaS+ is released under the MIT License. See `LICENSE`.
