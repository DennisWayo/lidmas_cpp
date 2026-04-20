#!/usr/bin/env python3
"""Summarize and plot paper_04 source-vs-reference decoder comparison metrics."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-csv", required=True, help="Input replay matrix CSV.")
    parser.add_argument("--out-csv", required=True, help="Output comparison CSV.")
    parser.add_argument("--out-md", required=True, help="Output comparison markdown table.")
    parser.add_argument("--out-prefix", required=True, help="Figure output prefix without extension.")
    parser.add_argument(
        "--reference-dataset",
        default="lidmas_reference",
        help="Reference dataset label used for delta computation.",
    )
    return parser.parse_args()


def _f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt(v: float) -> str:
    return f"{v:.6f}"


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _index_by_decoder_dataset(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        decoder = (row.get("decoder") or "").strip()
        dataset = (row.get("dataset") or "").strip()
        if not decoder or not dataset:
            continue
        out[(decoder, dataset)] = row
    return out


def _discover_sources(rows: list[dict[str, str]], reference_dataset: str) -> tuple[list[str], list[str]]:
    decoders = sorted({(row.get("decoder") or "").strip() for row in rows if (row.get("decoder") or "").strip()})
    datasets = sorted({(row.get("dataset") or "").strip() for row in rows if (row.get("dataset") or "").strip()})
    sources = [d for d in datasets if d and d != reference_dataset]
    return decoders, sources


def _build_comparison(
    rows: list[dict[str, str]], *, reference_dataset: str
) -> tuple[list[dict[str, Any]], list[str], list[str], dict[tuple[str, str], dict[str, str]]]:
    idx = _index_by_decoder_dataset(rows)
    decoders, sources = _discover_sources(rows, reference_dataset)
    out: list[dict[str, Any]] = []

    for decoder in decoders:
        ref_row = idx.get((decoder, reference_dataset))
        for source in sources:
            src_row = idx.get((decoder, source))

            status = "ok"
            if src_row is None and ref_row is None:
                status = "missing_source_and_reference"
            elif src_row is None:
                status = f"missing_{source}"
            elif ref_row is None:
                status = f"missing_{reference_dataset}"

            s_flip = _f((src_row or {}).get("avg_flip_count"))
            r_flip = _f((ref_row or {}).get("avg_flip_count"))
            s_warn = _f((src_row or {}).get("warning_no_syndrome_rate"))
            r_warn = _f((ref_row or {}).get("warning_no_syndrome_rate"))
            s_event = _f((src_row or {}).get("nonempty_request_event_rate"))
            r_event = _f((ref_row or {}).get("nonempty_request_event_rate"))

            out.append(
                {
                    "decoder": decoder,
                    "source_dataset": source,
                    "reference_dataset": reference_dataset,
                    "status": status,
                    "avg_flip_count_source": s_flip,
                    "avg_flip_count_reference": r_flip,
                    "delta_avg_flip_count_source_minus_reference": s_flip - r_flip,
                    "warning_rate_source": s_warn,
                    "warning_rate_reference": r_warn,
                    "delta_warning_rate_source_minus_reference": s_warn - r_warn,
                    "nonempty_event_rate_source": s_event,
                    "nonempty_event_rate_reference": r_event,
                    "delta_nonempty_event_rate_source_minus_reference": s_event - r_event,
                }
            )
    return out, decoders, sources, idx


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "decoder",
        "source_dataset",
        "reference_dataset",
        "status",
        "avg_flip_count_source",
        "avg_flip_count_reference",
        "delta_avg_flip_count_source_minus_reference",
        "warning_rate_source",
        "warning_rate_reference",
        "delta_warning_rate_source_minus_reference",
        "nonempty_event_rate_source",
        "nonempty_event_rate_reference",
        "delta_nonempty_event_rate_source_minus_reference",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            for key in fieldnames:
                if key.startswith("avg_") or key.startswith("warning_") or key.startswith("nonempty_") or key.startswith("delta_"):
                    if key in out:
                        out[key] = _fmt(_f(out[key]))
            writer.writerow(out)


def _write_md(rows: list[dict[str, Any]], path: Path) -> None:
    headers = [
        "decoder",
        "source_dataset",
        "status",
        "avg_flip_count_source",
        "avg_flip_count_reference",
        "delta_avg_flip_count_source_minus_reference",
        "warning_rate_source",
        "warning_rate_reference",
        "delta_warning_rate_source_minus_reference",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("|" + "|".join(["---"] * len(headers)) + "|\n")
        for row in rows:
            vals: list[str] = []
            for h in headers:
                v = row.get(h, "")
                if h in {"decoder", "source_dataset", "status"}:
                    vals.append(str(v))
                else:
                    vals.append(_fmt(_f(v)))
            f.write("| " + " | ".join(vals) + " |\n")


def _plot(
    idx: dict[tuple[str, str], dict[str, str]],
    *,
    decoders: list[str],
    sources: list[str],
    reference_dataset: str,
    out_prefix: Path,
) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping figure export ({exc}).")
        return

    if not decoders:
        return

    datasets = [reference_dataset] + sources
    base_x = list(range(len(decoders)))
    width = min(0.18, 0.78 / max(1, len(datasets)))
    offsets = [((i - (len(datasets) - 1) / 2.0) * width) for i in range(len(datasets))]

    palette = {
        reference_dataset: "#ff7f0e",
        "pennylane": "#1f77b4",
        "qiskit": "#2ca02c",
    }

    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.6), dpi=320, constrained_layout=True)

    for dataset, offset in zip(datasets, offsets):
        x = [v + offset for v in base_x]
        flip_vals = [_f((idx.get((decoder, dataset)) or {}).get("avg_flip_count")) for decoder in decoders]
        warn_vals = [_f((idx.get((decoder, dataset)) or {}).get("warning_no_syndrome_rate")) for decoder in decoders]
        color = palette.get(dataset, None)
        label = "LiDMaS+ reference" if dataset == reference_dataset else f"{dataset} source"

        axes[0].bar(x, flip_vals, width=width, color=color, label=label)
        axes[1].bar(x, warn_vals, width=width, color=color, label=label)

    axes[0].set_title("Average Flip Count by Source")
    axes[0].set_xlabel("Decoder")
    axes[0].set_ylabel("Mean flips/request")
    axes[0].set_xticks(base_x)
    axes[0].set_xticklabels(decoders, rotation=0)
    axes[0].grid(axis="y", alpha=0.25)

    axes[1].set_title("No-Syndrome Warning Rate by Source")
    axes[1].set_xlabel("Decoder")
    axes[1].set_ylabel("Rate")
    axes[1].set_xticks(base_x)
    axes[1].set_xticklabels(decoders, rotation=0)
    axes[1].grid(axis="y", alpha=0.25)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=min(4, len(labels)), frameon=False, bbox_to_anchor=(0.5, 1.03))

    for ext in (".png", ".pdf"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    matrix_rows = _load_rows(Path(args.matrix_csv))
    comparison_rows, decoders, sources, idx = _build_comparison(
        matrix_rows,
        reference_dataset=args.reference_dataset,
    )

    _write_csv(comparison_rows, Path(args.out_csv))
    _write_md(comparison_rows, Path(args.out_md))
    _plot(
        idx,
        decoders=decoders,
        sources=sources,
        reference_dataset=args.reference_dataset,
        out_prefix=Path(args.out_prefix),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
