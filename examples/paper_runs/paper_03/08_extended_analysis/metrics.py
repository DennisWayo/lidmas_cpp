#!/usr/bin/env python3
"""Derived metric computation and dataframe harmonization for paper_03 extended analysis."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

DECODER_ORDER = ["mwpm", "uf", "bp", "neural_mwpm", "stub"]
DECODER_LABELS = {
    "mwpm": "MWPM",
    "uf": "UF",
    "bp": "BP",
    "neural_mwpm": "Neural-MWPM",
    "stub": "Stub",
}
SCOPE_ORDER = ["fixture", "real_slice", "synthetic_holdout", "real_full_hpc"]
SCOPE_LABELS = {
    "fixture": "Fixture",
    "real_slice": "Real slice",
    "synthetic_holdout": "Synthetic heldout",
    "real_full_hpc": "Real full HPC",
}


def decoder_label(decoder: str) -> str:
    return DECODER_LABELS.get(decoder, decoder.upper())


def scope_label(scope: str) -> str:
    return SCOPE_LABELS.get(scope, scope.replace("_", " ").title())


def infer_provider(dataset: str) -> str:
    s = str(dataset).strip().lower()
    if s.startswith("synth_"):
        s = s[len("synth_") :]
    if "aurora" in s:
        return "Aurora"
    if "qca" in s:
        return "QCA"
    if "quandela" in s:
        return "Quandela"
    if "google" in s:
        return "Google"
    if "gkp" in s:
        return "GKP"
    if s == "job":
        return "FixtureJob"
    prefix = s.split("_", 1)[0] if "_" in s else s
    if not prefix:
        return "Unknown"
    return prefix.capitalize()


def pretty_dataset(dataset: str) -> str:
    s = str(dataset).strip()
    mapping = {
        "job": "job",
        "aurora": "aurora",
        "gkp": "gkp",
        "qca": "qca",
        "aurora_batch0_qpu5": "aurora_batch0_qpu5",
        "qca_fig3b": "qca_fig3b",
        "synth_aurora_batch0_qpu5_heldout": "synth_aurora_heldout",
        "synth_qca_fig3b_heldout": "synth_qca_heldout",
    }
    return mapping.get(s, s)


def _safe_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def build_merged_metrics(matrix_df: pd.DataFrame, quality_df: pd.DataFrame) -> pd.DataFrame:
    matrix_cols_numeric = [
        "request_lines",
        "request_parse_errors",
        "response_lines",
        "response_parse_errors",
        "response_ratio",
        "avg_request_events",
        "nonempty_request_event_rate",
        "warning_no_syndrome_count",
        "warning_no_syndrome_rate",
        "error_count",
        "avg_sx_count",
        "avg_sz_count",
        "avg_flip_count",
        "nonempty_flip_rate",
        "unique_flip_qubits",
        "decoder_name_mismatch_count",
    ]
    quality_cols_numeric = [
        "response_ratio",
        "syndrome_eval_lines",
        "syndrome_satisfied_count",
        "syndrome_satisfied_rate",
        "residual_nonzero_count",
        "residual_nonzero_rate",
        "avg_residual_sx_count",
        "avg_residual_sz_count",
        "logical_eval_lines",
        "logical_x_fail_count",
        "logical_x_fail_rate",
        "logical_z_fail_count",
        "logical_z_fail_rate",
        "logical_fail_count",
        "logical_fail_rate",
    ]

    mdf = _safe_numeric(matrix_df, matrix_cols_numeric)
    qdf = _safe_numeric(quality_df, quality_cols_numeric)

    key_cols = ["scope", "dataset", "decoder"]
    if qdf.empty:
        merged = mdf.copy()
    else:
        q_keep = [c for c in qdf.columns if c in key_cols + quality_cols_numeric + ["status"]]
        q_keep_renamed = qdf[q_keep].rename(columns={"status": "quality_status"})
        merged = mdf.merge(q_keep_renamed, on=key_cols, how="left")

    merged["provider"] = merged["dataset"].astype(str).map(infer_provider)
    merged["dataset_pretty"] = merged["dataset"].astype(str).map(pretty_dataset)
    merged["decoder_label"] = merged["decoder"].astype(str).map(decoder_label)
    merged["scope_label"] = merged["scope"].astype(str).map(scope_label)
    merged["is_synthetic"] = merged["scope"].astype(str).eq("synthetic_holdout")
    merged = add_derived_metrics(merged)
    merged = add_decoder_stability(merged)

    def _decoder_key(decoder: Any) -> tuple[int, str]:
        s = str(decoder)
        try:
            idx = DECODER_ORDER.index(s)
        except ValueError:
            idx = 999
        return (idx, s)

    merged = merged.sort_values(
        by=["scope", "dataset", "decoder"],
        key=lambda c: c.map(lambda v: _decoder_key(v)[0]) if c.name == "decoder" else c,
    ).reset_index(drop=True)
    return merged


def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    eps = 1e-9
    out["syndrome_satisfied_rate"] = pd.to_numeric(out.get("syndrome_satisfied_rate"), errors="coerce")
    out["residual_nonzero_rate"] = pd.to_numeric(out.get("residual_nonzero_rate"), errors="coerce")
    out["avg_flip_count"] = pd.to_numeric(out.get("avg_flip_count"), errors="coerce")
    out["warning_no_syndrome_rate"] = pd.to_numeric(out.get("warning_no_syndrome_rate"), errors="coerce")
    out["nonempty_request_event_rate"] = pd.to_numeric(out.get("nonempty_request_event_rate"), errors="coerce")

    out["correction_efficiency_index"] = out["syndrome_satisfied_rate"] / (out["avg_flip_count"] + eps)
    out["intervention_to_clearance_ratio"] = out["avg_flip_count"] / (out["syndrome_satisfied_rate"] + eps)
    out["dataset_sparsity_index"] = 1.0 - out["nonempty_request_event_rate"]

    warning_mean = out.groupby(["scope", "dataset"])["warning_no_syndrome_rate"].transform("mean")
    warning_gap = (out["warning_no_syndrome_rate"] - warning_mean).abs()
    max_gap = float(warning_gap.max()) if warning_gap.notna().any() else 0.0
    denom = max(max_gap, eps)
    out["warning_invariance_gap"] = warning_gap
    out["warning_invariance_score"] = 1.0 - (warning_gap / denom)

    return out


def _cv(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    mean = float(np.mean(values))
    if abs(mean) < 1e-12:
        return 0.0
    std = float(np.std(values))
    return std / abs(mean)


def add_decoder_stability(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rows: list[dict[str, Any]] = []
    for decoder, group in out.groupby("decoder"):
        flip_vals = pd.to_numeric(group.get("avg_flip_count"), errors="coerce").dropna().to_numpy()
        sat_vals = pd.to_numeric(group.get("syndrome_satisfied_rate"), errors="coerce").dropna().to_numpy()
        residual_vals = pd.to_numeric(group.get("residual_nonzero_rate"), errors="coerce").dropna().to_numpy()
        cv_flip = _cv(flip_vals)
        cv_sat = _cv(sat_vals)
        cv_residual = _cv(residual_vals)
        stability = 1.0 / (1.0 + cv_flip + cv_sat + cv_residual)
        rows.append(
            {
                "decoder": decoder,
                "decoder_stability_score": stability,
                "decoder_cv_avg_flip": cv_flip,
                "decoder_cv_satisfaction": cv_sat,
                "decoder_cv_residual": cv_residual,
            }
        )
    stab_df = pd.DataFrame(rows)
    return out.merge(stab_df, on="decoder", how="left")


def decoder_stability_table(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "decoder",
        "decoder_stability_score",
        "decoder_cv_avg_flip",
        "decoder_cv_satisfaction",
        "decoder_cv_residual",
    ]
    if not all(c in df.columns for c in cols):
        return pd.DataFrame(columns=cols)
    out = df[cols].drop_duplicates().copy()
    out["decoder_label"] = out["decoder"].astype(str).map(decoder_label)
    out = out.sort_values("decoder_stability_score", ascending=False).reset_index(drop=True)
    return out
