# Read the Docs Setup

This repository includes the files required for automatic Read the Docs builds:

- `.readthedocs.yaml`
- `mkdocs.yml`
- `docs/requirements.txt`
- `docs/` content pages

## Enable on Read the Docs

1. Sign in to Read the Docs.
2. Import `DennisWayo/lidmas_cpp` from GitHub.
3. Confirm the default branch and Python version (configured in `.readthedocs.yaml`).
4. Trigger a build.

## Local docs build

```bash
python3 -m venv .venv-docs
source .venv-docs/bin/activate
pip install -r docs/requirements.txt
mkdocs serve
```

Docs will be available at `http://127.0.0.1:8000`.

## Notes

- Any push that changes docs or config will trigger a new RTD build once the project is connected.
- Keep command examples in docs aligned with `README.md` and `--help` output.

## GitHub Pages (also supported)

This repository also deploys docs with GitHub Pages via `.github/workflows/docs.yml`.

In repository settings:

1. Go to `Settings -> Pages`.
2. Set `Source` to `GitHub Actions`.
3. Push to `main` (or run the `docs` workflow manually).

Published URL:

- `https://denniswayo.github.io/lidmas_cpp/`
