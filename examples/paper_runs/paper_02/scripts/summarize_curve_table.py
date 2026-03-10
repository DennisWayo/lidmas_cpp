#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def trapezoid_area(xs, ys):
    if len(xs) < 2:
        return 0.0
    area = 0.0
    for i in range(len(xs) - 1):
        dx = xs[i + 1] - xs[i]
        area += 0.5 * dx * (ys[i] + ys[i + 1])
    return area


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize LiDMaS curve CSVs into markdown and CSV tables.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--x-col", required=True)
    parser.add_argument("--group-cols", default="decoder")
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-csv", required=True)
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        raise FileNotFoundError(f"missing input CSV: {in_path}")

    group_cols = [c.strip() for c in args.group_cols.split(",") if c.strip()]
    with in_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        raise RuntimeError("no rows found in input CSV")

    grouped = {}
    for row in rows:
        key = tuple(row.get(col, "") for col in group_cols)
        grouped.setdefault(key, []).append(row)

    summary_rows = []
    for key, grows in grouped.items():
        pairs = []
        for row in grows:
            try:
                x = float(row[args.x_col])
                ler = float(row["ler"])
            except (KeyError, ValueError):
                continue
            pairs.append((x, ler))
        pairs.sort(key=lambda t: t[0])
        if not pairs:
            continue
        xs = [x for x, _ in pairs]
        ys = [y for _, y in pairs]
        summary = {col: key[idx] for idx, col in enumerate(group_cols)}
        summary.update(
            {
                "points": str(len(pairs)),
                "x_min": f"{xs[0]:.6g}",
                "x_max": f"{xs[-1]:.6g}",
                "ler_min": f"{min(ys):.6g}",
                "ler_max": f"{max(ys):.6g}",
                "ler_mean": f"{(sum(ys) / len(ys)):.6g}",
                "auc_ler": f"{trapezoid_area(xs, ys):.6g}",
            }
        )
        summary_rows.append(summary)

    fieldnames = group_cols + ["points", "x_min", "x_max", "ler_min", "ler_max", "ler_mean", "auc_ler"]
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_md.open("w", encoding="utf-8") as f:
        f.write("# Curve Summary\n\n")
        f.write("| " + " | ".join(fieldnames) + " |\n")
        f.write("|" + "|".join(["---"] * len(fieldnames)) + "|\n")
        for row in summary_rows:
            f.write("| " + " | ".join(row.get(field, "") for field in fieldnames) + " |\n")

    print(f"Wrote {out_csv}")
    print(f"Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

