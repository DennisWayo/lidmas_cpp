# Developer Guide

This guide covers the open-source LiDMaS+ developer workflow centered on the `lidmas` CLI.

## Distribution Boundary

LiDMaS+ is split into two tracks:

- Open source: CLI engine, simulation/decoder code, schemas, and reproducible workflows.
- Enterprise: internal app UI/API stack managed outside public release artifacts.

Public documentation and PyPI releases in this repository are intentionally CLI-first.

## OSS Scope

In scope for this repository:

- `src/`, `include/`, `schemas/`
- `examples/` reproducibility workflows
- `hardware_integration/` adapters and replay tooling
- `docs/` for open-source usage and methods

Out of scope for public release:

- Enterprise UI/API source and deployment details
- Enterprise authentication, tenancy, and operations workflows

## Local Development Setup (CLI)

### 1) Build CLI

```bash
cmake -S . -B build
cmake --build build -j
./build/lidmas --help
```

### 2) Run sanity checks

```bash
./build/lidmas --smoke
```

### 3) Run a reproducible workflow

```bash
bash examples/quick_smoke/run.sh
```

## Public Release Guardrails

The repository enforces guardrails to keep enterprise sources out of public docs and packages.

Guardrail script:

```bash
bash scripts/check_oss_release_boundary.sh
```

Artifact-level validation (sdist/wheel):

```bash
bash scripts/check_oss_release_boundary.sh dist/*.tar.gz dist/*.whl
```

## Publish Checklist (OSS)

1. Build + help:
   - `./build/lidmas --help`
2. Smoke:
   - `./build/lidmas --smoke`
3. Docs:
   - `mkdocs build --strict`
4. Boundary checks:
   - `bash scripts/check_oss_release_boundary.sh`
5. Artifacts:
   - sdist/wheel checks show no enterprise paths

## Documentation Ownership

When CLI flags or workflow scripts change, update at minimum:

- `docs/cli-reference.md`
- `docs/getting-started.md`
- `docs/examples-workflows.md`
- `docs/developer-guide.md`
- `mkdocs.yml` nav (if page names/locations change)
