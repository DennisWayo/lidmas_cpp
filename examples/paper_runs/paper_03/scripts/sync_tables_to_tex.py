#!/usr/bin/env python3
"""Sync paper_03 LaTeX table rows from generated CSV summaries."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


LABEL_FIXTURE = r"\label{tab:decoder_matrix_fixture}"
LABEL_REAL = r"\label{tab:decoder_matrix_real}"
LABEL_REQUEST = r"\label{tab:request_manifest_fixture}"

DECODER_ORDER = {
    "mwpm": 0,
    "uf": 1,
    "bp": 2,
    "neural_mwpm": 3,
    "stub": 4,
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tex", required=True, help="Target LaTeX file (paper_03.tex)")
    p.add_argument("--request-csv", required=True, help="Request manifest CSV")
    p.add_argument("--fixture-csv", required=True, help="Fixture summary CSV")
    p.add_argument("--real-csv", required=True, help="Real-data summary CSV")
    return p.parse_args()


def latex_escape(s: str) -> str:
    return s.replace("_", "\\_")


def _sort_key(row: dict[str, str], dataset_order: dict[str, int]) -> tuple[int, int, str]:
    dataset = row.get("dataset", "")
    decoder = row.get("decoder", "")
    return (
        dataset_order.get(dataset, 9999),
        DECODER_ORDER.get(decoder, 9999),
        decoder,
    )


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def make_table_rows(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["        not\\_run & -- & -- & -- & -- & -- \\\\"]

    dataset_order: dict[str, int] = {}
    next_index = 0
    for row in rows:
        ds = row.get("dataset", "")
        if ds not in dataset_order:
            dataset_order[ds] = next_index
            next_index += 1

    rows_sorted = sorted(rows, key=lambda r: _sort_key(r, dataset_order))
    out: list[str] = []
    for row in rows_sorted:
        dataset = latex_escape(row.get("dataset", ""))
        decoder = latex_escape(row.get("decoder", ""))
        request_lines = row.get("request_lines", "--")
        response_lines = row.get("response_lines", "--")
        warning_rate = row.get("warning_no_syndrome_rate", "0")
        avg_flip = row.get("avg_flip_count", "0")

        try:
            warning_rate_fmt = f"{float(warning_rate):.3f}"
        except ValueError:
            warning_rate_fmt = "--"
        try:
            avg_flip_fmt = f"{float(avg_flip):.3f}"
        except ValueError:
            avg_flip_fmt = "--"

        out.append(
            f"        {dataset} & {decoder} & {request_lines} & {response_lines} & {warning_rate_fmt} & {avg_flip_fmt} \\\\"
        )
    return out


def make_request_rows(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["        not\\_run & -- & -- \\\\"]

    out: list[str] = []
    for row in rows:
        dataset = latex_escape(row.get("dataset", ""))
        request_file = latex_escape(row.get("request_file", ""))
        request_lines = row.get("request_lines", "--")
        out.append(f"        {dataset} & {request_file} & {request_lines} \\\\")
    return out


def replace_table_rows_by_label(lines: list[str], label: str, generated_rows: list[str]) -> list[str]:
    label_idx = -1
    for i, line in enumerate(lines):
        if label in line:
            label_idx = i
            break
    if label_idx < 0:
        raise RuntimeError(f"Label not found in LaTeX file: {label}")

    mid_idx = -1
    for i in range(label_idx, len(lines)):
        if "\\midrule" in lines[i]:
            mid_idx = i
            break
    if mid_idx < 0:
        raise RuntimeError(f"Could not find \\midrule after label: {label}")

    bottom_idx = -1
    for i in range(mid_idx + 1, len(lines)):
        if "\\bottomrule" in lines[i]:
            bottom_idx = i
            break
    if bottom_idx < 0:
        raise RuntimeError(f"Could not find \\bottomrule after label: {label}")

    indent = lines[mid_idx].split("\\")[0]
    generated_comment = indent + "% Auto-generated from workflow CSV; do not edit manually."
    new_block = [generated_comment] + generated_rows
    return lines[: mid_idx + 1] + new_block + lines[bottom_idx:]


def main() -> int:
    args = parse_args()
    tex_path = Path(args.tex)
    request_csv = Path(args.request_csv)
    fixture_csv = Path(args.fixture_csv)
    real_csv = Path(args.real_csv)

    lines = tex_path.read_text(encoding="utf-8").splitlines()
    request_rows = make_request_rows(load_rows(request_csv))
    fixture_rows = make_table_rows(load_rows(fixture_csv))
    real_rows = make_table_rows(load_rows(real_csv))

    lines = replace_table_rows_by_label(lines, LABEL_REQUEST, request_rows)
    lines = replace_table_rows_by_label(lines, LABEL_FIXTURE, fixture_rows)
    lines = replace_table_rows_by_label(lines, LABEL_REAL, real_rows)

    tex_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
