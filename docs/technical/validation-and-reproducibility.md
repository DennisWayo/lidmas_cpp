# Validation and Reproducibility

## Reproducibility Protocol

1. Build from a clean checkout.
2. Run smoke checks.
3. Run `paper_04` with fixed seeds and explicit decoders.
4. Verify generated tables and manifests.
5. Cross-check App results against CLI artifacts.

## Baseline Commands

```bash
lidmas --smoke
./examples/paper_runs/paper_04/run_all.sh
```

Optional controlled run:

```bash
LIDMAS_P4_SHOTS=300 \
LIDMAS_P4_ROUNDS=3 \
LIDMAS_DECODERS=mwpm,uf,bp \
LIDMAS_P4_SEED=20260409 \
./examples/paper_runs/paper_04/run_all.sh
```

## Required Audit Artifacts

- `examples/paper_runs/paper_04/results/03_analysis/table_replay_matrix.csv`
- `examples/paper_runs/paper_04/results/03_analysis/table_source_vs_lidmas.csv`
- `examples/paper_runs/paper_04/results/04_extended_analysis/table_request_equivalence.csv`
- `examples/paper_runs/paper_04/results/04_extended_analysis/table_bootstrap_metrics.csv`
- `examples/paper_runs/paper_04/results/04_extended_analysis/table_bootstrap_source_vs_reference.csv`

## CLI vs App Parity Checklist

1. Capture CLI manifest/hash for `paper_04`.
2. Run `paper_04` from LiDMaS+ App with same config.
3. Compare:
   - manifest hash,
   - run status,
   - artifact counts,
   - key summary tables.
4. Investigate any mismatch before reporting results.

## Citation and Provenance

Use [Reproducibility & Citation](../reproducibility-citation.md) for publication citation guidance and version capture.
