# Formal Problem Definition

## Inputs

For each experiment point:

- code family/configuration (distance, rounds, supports),
- noise parameters (`p`, `sigma`, or hybrid parameters),
- decoder choice,
- RNG seed and trial count,
- request/response datasets in NDJSON form (for replay workflows).

## State Variables

- physical error vectors (`e_X`, `e_Z`),
- syndromes (`s_X`, `s_Z`),
- decoder corrections (`c_X`, `c_Z`),
- residual logical predicates.

## Output Variables

- per-run decoder metrics (flip count, warning rates, event rates),
- logical error estimates,
- confidence intervals,
- threshold/scaling summaries,
- reproducible tables/figures/manifests.

## Primary Objective

Estimate logical failure behavior under controlled noise and decoding choices, then compare:

1. across decoders,
2. across software stacks (PennyLane/Qiskit/Cirq vs LiDMaS+ reference),
3. across code families (`surface`, `gkp`),
4. across execution surfaces (CLI vs App).

## Constraint Set

- deterministic seeds for comparable reruns,
- stable dataset schema for replay compatibility,
- per-step artifact outputs required for auditability,
- explicit failure/warning accounting rather than silent omission.
