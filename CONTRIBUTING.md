# Contributing

Thanks for contributing to LiDMaS+.

## Scope

This public repository is CLI-first and open-source focused:

- core simulation/decoder engine
- reproducible workflows in `examples/`
- hardware integration adapters and replay tooling
- public documentation in `docs/`

Enterprise UI/API code is maintained in a separate private track.

## Development Setup

1. Build:

```bash
cmake -S . -B build
cmake --build build -j
```

2. Sanity checks:

```bash
./build/lidmas --help
./build/lidmas --selftest
./build/lidmas --smoke
```

3. Docs check (if docs changed):

```bash
./.venv_docs/bin/mkdocs build --strict
```

## Pull Requests

Please include:

- clear problem statement
- concise change summary
- reproducible validation steps
- expected vs observed behavior for bug fixes

Keep PRs scoped. Avoid unrelated refactors in the same change.

## Coding Guidance

- Follow existing patterns and naming in nearby code.
- Keep changes narrowly scoped to the requested behavior.
- Prefer deterministic and reproducible defaults for experiments.
- Update docs when flags, workflows, or output contracts change.

## Security

Do not disclose vulnerabilities publicly in issues before coordination.
See `SECURITY.md` for responsible disclosure guidance.
