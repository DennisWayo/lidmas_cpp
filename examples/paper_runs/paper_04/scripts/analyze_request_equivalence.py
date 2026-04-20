#!/usr/bin/env python3
"""Compute pre-decoder request equivalence metrics across paper_04 source datasets."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests-dir", required=True, help="Directory with decoder_requests*.ndjson.")
    parser.add_argument("--out-csv", required=True, help="Output CSV path.")
    parser.add_argument("--out-md", required=True, help="Output markdown path.")
    parser.add_argument("--out-prefix", required=True, help="Figure prefix (without extension).")
    parser.add_argument("--reference-dataset", default="lidmas_reference", help="Reference dataset label.")
    return parser.parse_args()


def dataset_label_from_request(path: Path) -> str:
    stem = path.stem
    if not stem.startswith("decoder_requests"):
        return stem
    suffix = stem[len("decoder_requests") :]
    if not suffix:
        return "job"
    return suffix.lstrip("_")


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values)) / float(len(values))


def _pmf(values: list[int]) -> dict[int, float]:
    if not values:
        return {}
    c = Counter(values)
    n = float(len(values))
    return {k: float(v) / n for k, v in c.items()}


def _tv_distance(p: dict[int, float], q: dict[int, float]) -> float:
    keys = set(p.keys()) | set(q.keys())
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys)


def _js_divergence(p: dict[int, float], q: dict[int, float]) -> float:
    keys = set(p.keys()) | set(q.keys())
    if not keys:
        return 0.0
    m = {k: 0.5 * (p.get(k, 0.0) + q.get(k, 0.0)) for k in keys}

    def kl(a: dict[int, float], b: dict[int, float]) -> float:
        out = 0.0
        for k in keys:
            av = a.get(k, 0.0)
            bv = b.get(k, 0.0)
            if av <= 0.0 or bv <= 0.0:
                continue
            out += av * math.log(av / bv)
        return out

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def _read_request_metrics(path: Path) -> dict[str, Any]:
    event_counts: list[int] = []
    x_counts: list[int] = []
    z_counts: list[int] = []
    nonempty_flags: list[int] = []
    parse_errors = 0

    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            events = obj.get("events", [])
            if not isinstance(events, list):
                events = []
            event_count = len(events)
            x_count = 0
            z_count = 0
            for ev in events:
                if not isinstance(ev, dict):
                    continue
                ev_type = str(ev.get("type", "")).upper()
                if ev_type == "X":
                    x_count += 1
                elif ev_type == "Z":
                    z_count += 1
            event_counts.append(event_count)
            x_counts.append(x_count)
            z_counts.append(z_count)
            nonempty_flags.append(1 if event_count > 0 else 0)

    return {
        "line_count": len(event_counts),
        "parse_errors": parse_errors,
        "event_counts": event_counts,
        "x_counts": x_counts,
        "z_counts": z_counts,
        "nonempty_flags": nonempty_flags,
        "mean_events": _mean([float(v) for v in event_counts]),
        "mean_x_events": _mean([float(v) for v in x_counts]),
        "mean_z_events": _mean([float(v) for v in z_counts]),
        "nonempty_rate": _mean([float(v) for v in nonempty_flags]),
    }


def _write_csv(rows: list[dict[str, Any]], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_dataset",
        "reference_dataset",
        "status",
        "n_source",
        "n_reference",
        "source_parse_errors",
        "reference_parse_errors",
        "mean_events_source",
        "mean_events_reference",
        "delta_mean_events",
        "mean_x_events_source",
        "mean_x_events_reference",
        "delta_mean_x_events",
        "mean_z_events_source",
        "mean_z_events_reference",
        "delta_mean_z_events",
        "nonempty_rate_source",
        "nonempty_rate_reference",
        "delta_nonempty_rate",
        "tv_event_count",
        "js_event_count",
        "tv_x_count",
        "js_x_count",
        "tv_z_count",
        "js_z_count",
    ]
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            for key in fieldnames:
                if key.startswith("mean_") or key.startswith("delta_") or key.startswith("tv_") or key.startswith("js_") or key.endswith("_rate"):
                    if key in out:
                        out[key] = f"{float(out[key]):.6f}"
            writer.writerow(out)


def _write_md(rows: list[dict[str, Any]], out_md: Path) -> None:
    headers = [
        "source_dataset",
        "status",
        "delta_mean_events",
        "delta_nonempty_rate",
        "tv_event_count",
        "js_event_count",
        "tv_z_count",
        "js_z_count",
    ]
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_md.open("w", encoding="utf-8") as f:
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("|" + "|".join(["---"] * len(headers)) + "|\n")
        for row in rows:
            vals: list[str] = []
            for h in headers:
                v = row.get(h, "")
                if h in {"source_dataset", "status"}:
                    vals.append(str(v))
                else:
                    vals.append(f"{float(v):.6f}")
            f.write("| " + " | ".join(vals) + " |\n")


def _plot(rows: list[dict[str, Any]], out_prefix: Path) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        print(f"Warning: matplotlib unavailable; skipping equivalence figure export ({exc}).")
        return

    if not rows:
        return

    metrics = [
        ("tv_event_count", "TV(events)"),
        ("js_event_count", "JS(events)"),
        ("tv_z_count", "TV(Z count)"),
        ("js_z_count", "JS(Z count)"),
        ("delta_mean_events_abs", "|Δ mean events|"),
        ("delta_nonempty_rate_abs", "|Δ nonempty|"),
    ]
    labels = [str(r["source_dataset"]) for r in rows]
    matrix: list[list[float]] = []
    for row in rows:
        matrix.append(
            [
                float(row.get("tv_event_count", 0.0)),
                float(row.get("js_event_count", 0.0)),
                float(row.get("tv_z_count", 0.0)),
                float(row.get("js_z_count", 0.0)),
                abs(float(row.get("delta_mean_events", 0.0))),
                abs(float(row.get("delta_nonempty_rate", 0.0))),
            ]
        )

    fig, ax = plt.subplots(figsize=(9.2, 3.8), dpi=320, constrained_layout=True)
    im = ax.imshow(matrix, aspect="auto", cmap="YlGnBu")
    ax.set_yticks(list(range(len(labels))))
    ax.set_yticklabels(labels)
    ax.set_xticks(list(range(len(metrics))))
    ax.set_xticklabels([m[1] for m in metrics], rotation=20, ha="right")
    ax.set_title("Pre-Decoder Request Equivalence Audit")
    cbar = fig.colorbar(im, ax=ax, shrink=0.95)
    cbar.set_label("distance / divergence")

    for i in range(len(labels)):
        for j in range(len(metrics)):
            ax.text(j, i, f"{matrix[i][j]:.3f}", ha="center", va="center", fontsize=8, color="black")

    for ext in (".png", ".pdf"):
        fig.savefig(out_prefix.with_suffix(ext), bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    requests_dir = Path(args.requests_dir)
    request_files = sorted(requests_dir.glob("decoder_requests*.ndjson"))
    if not request_files:
        raise SystemExit(f"Error: no decoder request files found in {requests_dir}")

    dataset_metrics: dict[str, dict[str, Any]] = {}
    for req in request_files:
        dataset = dataset_label_from_request(req)
        dataset_metrics[dataset] = _read_request_metrics(req)

    ref = args.reference_dataset
    if ref not in dataset_metrics:
        raise SystemExit(f"Error: reference dataset '{ref}' not found in request files.")
    ref_m = dataset_metrics[ref]

    rows: list[dict[str, Any]] = []
    for dataset in sorted(dataset_metrics.keys()):
        if dataset == ref:
            continue
        src = dataset_metrics[dataset]
        status = "ok"
        if src["line_count"] == 0 or ref_m["line_count"] == 0:
            status = "empty_requests"

        src_event_pmf = _pmf(src["event_counts"])
        ref_event_pmf = _pmf(ref_m["event_counts"])
        src_x_pmf = _pmf(src["x_counts"])
        ref_x_pmf = _pmf(ref_m["x_counts"])
        src_z_pmf = _pmf(src["z_counts"])
        ref_z_pmf = _pmf(ref_m["z_counts"])

        rows.append(
            {
                "source_dataset": dataset,
                "reference_dataset": ref,
                "status": status,
                "n_source": src["line_count"],
                "n_reference": ref_m["line_count"],
                "source_parse_errors": src["parse_errors"],
                "reference_parse_errors": ref_m["parse_errors"],
                "mean_events_source": src["mean_events"],
                "mean_events_reference": ref_m["mean_events"],
                "delta_mean_events": src["mean_events"] - ref_m["mean_events"],
                "mean_x_events_source": src["mean_x_events"],
                "mean_x_events_reference": ref_m["mean_x_events"],
                "delta_mean_x_events": src["mean_x_events"] - ref_m["mean_x_events"],
                "mean_z_events_source": src["mean_z_events"],
                "mean_z_events_reference": ref_m["mean_z_events"],
                "delta_mean_z_events": src["mean_z_events"] - ref_m["mean_z_events"],
                "nonempty_rate_source": src["nonempty_rate"],
                "nonempty_rate_reference": ref_m["nonempty_rate"],
                "delta_nonempty_rate": src["nonempty_rate"] - ref_m["nonempty_rate"],
                "tv_event_count": _tv_distance(src_event_pmf, ref_event_pmf),
                "js_event_count": _js_divergence(src_event_pmf, ref_event_pmf),
                "tv_x_count": _tv_distance(src_x_pmf, ref_x_pmf),
                "js_x_count": _js_divergence(src_x_pmf, ref_x_pmf),
                "tv_z_count": _tv_distance(src_z_pmf, ref_z_pmf),
                "js_z_count": _js_divergence(src_z_pmf, ref_z_pmf),
            }
        )

    out_csv = Path(args.out_csv)
    out_md = Path(args.out_md)
    out_prefix = Path(args.out_prefix)
    _write_csv(rows, out_csv)
    _write_md(rows, out_md)
    _plot(rows, out_prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
