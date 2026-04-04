#!/usr/bin/env python3
"""Run paper_03 extended analysis and generate journal-grade figure pack."""

from __future__ import annotations

import argparse
import hashlib
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from loader import load_quality_data, load_replay_data
from metrics import build_merged_metrics, decoder_stability_table
from plotting import (
    FigureResult,
    configure_matplotlib,
    generate_figure_a,
    generate_figure_b,
    generate_figure_c,
    generate_figure_d,
    generate_figure_f,
    generate_figure_g,
    generate_figure_h,
    generate_figure_i,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    default_paper_root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--paper-root",
        default=str(default_paper_root),
        help="Path to examples/paper_runs/paper_03 root",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Output directory (default: <paper-root>/results/08_extended_analysis)",
    )
    parser.add_argument("--export-svg", action="store_true", help="Also export SVG figure variants.")
    parser.add_argument("--skip-figures", action="store_true", help="Generate tables/logs/summary only.")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR).")
    return parser.parse_args()


def _ensure_dirs(output_dir: Path) -> tuple[Path, Path, Path]:
    figures_dir = output_dir / "figures"
    tables_dir = output_dir / "tables"
    logs_dir = output_dir / "logs"
    for d in (figures_dir, tables_dir, logs_dir):
        d.mkdir(parents=True, exist_ok=True)
    return figures_dir, tables_dir, logs_dir


def _setup_logger(logs_dir: Path, level_name: str) -> logging.Logger:
    logger = logging.getLogger("paper03_extended_analysis")
    logger.setLevel(getattr(logging, level_name.upper(), logging.INFO))
    logger.handlers.clear()
    logger.propagate = False

    file_handler = logging.FileHandler(logs_dir / "run_extended_analysis.log", mode="w", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("[extended-analysis] %(levelname)s: %(message)s"))
    logger.addHandler(stream_handler)
    return logger


def _write_df(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format="%.8f")
    return path


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _write_core_tables(
    tables_dir: Path,
    matrix_df: pd.DataFrame,
    quality_df: pd.DataFrame,
    request_df: pd.DataFrame,
    manifest_df: pd.DataFrame,
    merged_df: pd.DataFrame,
    stability_df: pd.DataFrame,
) -> list[Path]:
    written: list[Path] = []
    if not matrix_df.empty:
        written.append(
            _write_df(
                matrix_df.sort_values(["scope", "dataset", "decoder"]).reset_index(drop=True),
                tables_dir / "table_replay_matrix_extended.csv",
            )
        )
    if not quality_df.empty:
        written.append(
            _write_df(
                quality_df.sort_values(["scope", "dataset", "decoder"]).reset_index(drop=True),
                tables_dir / "table_quality_metrics_extended.csv",
            )
        )
    if not request_df.empty:
        written.append(
            _write_df(
                request_df.sort_values(["scope", "dataset", "decoder", "line_index"]).reset_index(drop=True),
                tables_dir / "table_request_level_records.csv",
            )
        )
    if not manifest_df.empty:
        written.append(
            _write_df(
                manifest_df.sort_values(["scope", "dataset", "decoder"]).reset_index(drop=True),
                tables_dir / "table_replay_manifest_extended.csv",
            )
        )
    if not merged_df.empty:
        written.append(
            _write_df(
                merged_df.sort_values(["scope", "dataset", "decoder"]).reset_index(drop=True),
                tables_dir / "table_merged_metrics_extended.csv",
            )
        )
    if not stability_df.empty:
        written.append(_write_df(stability_df.reset_index(drop=True), tables_dir / "table_decoder_stability.csv"))
    return written


def _safe_figure_call(
    call: Callable[[], FigureResult | list[FigureResult]],
    logger: logging.Logger,
    figure_id_hint: str,
) -> list[FigureResult]:
    try:
        result = call()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Figure %s failed: %s", figure_id_hint, exc)
        return [
            FigureResult(
                figure_id=figure_id_hint,
                title=f"Figure {figure_id_hint}",
                filename_base=f"figure_{figure_id_hint}_failed",
                table_filename=f"figure_{figure_id_hint}_failed.csv",
                status="skipped",
                main_result=f"error: {exc}",
                caption="",
            )
        ]
    if isinstance(result, list):
        return result
    return [result]


def _run_figure_pack(
    merged_df: pd.DataFrame,
    request_df: pd.DataFrame,
    figures_dir: Path,
    tables_dir: Path,
    export_svg: bool,
    save_figures: bool,
    logger: logging.Logger,
) -> list[FigureResult]:
    results: list[FigureResult] = []
    results.extend(
        _safe_figure_call(
            lambda: generate_figure_a(
                merged_df=merged_df,
                figures_dir=figures_dir,
                tables_dir=tables_dir,
                export_svg=export_svg,
                save_figures=save_figures,
                logger=logger,
            ),
            logger=logger,
            figure_id_hint="A",
        )
    )
    results.extend(
        _safe_figure_call(
            lambda: generate_figure_b(
                merged_df=merged_df,
                figures_dir=figures_dir,
                tables_dir=tables_dir,
                export_svg=export_svg,
                save_figures=save_figures,
                logger=logger,
            ),
            logger=logger,
            figure_id_hint="B",
        )
    )
    results.extend(
        _safe_figure_call(
            lambda: generate_figure_c(
                request_df=request_df,
                figures_dir=figures_dir,
                tables_dir=tables_dir,
                export_svg=export_svg,
                save_figures=save_figures,
                logger=logger,
            ),
            logger=logger,
            figure_id_hint="C",
        )
    )
    results.extend(
        _safe_figure_call(
            lambda: generate_figure_d(
                merged_df=merged_df,
                figures_dir=figures_dir,
                tables_dir=tables_dir,
                export_svg=export_svg,
                save_figures=save_figures,
                logger=logger,
            ),
            logger=logger,
            figure_id_hint="D",
        )
    )
    results.extend(
        _safe_figure_call(
            lambda: generate_figure_f(
                merged_df=merged_df,
                figures_dir=figures_dir,
                tables_dir=tables_dir,
                export_svg=export_svg,
                save_figures=save_figures,
                logger=logger,
            ),
            logger=logger,
            figure_id_hint="F",
        )
    )
    results.extend(
        _safe_figure_call(
            lambda: generate_figure_g(
                merged_df=merged_df,
                figures_dir=figures_dir,
                tables_dir=tables_dir,
                export_svg=export_svg,
                save_figures=save_figures,
                logger=logger,
            ),
            logger=logger,
            figure_id_hint="G",
        )
    )
    results.extend(
        _safe_figure_call(
            lambda: generate_figure_h(
                merged_df=merged_df,
                figures_dir=figures_dir,
                tables_dir=tables_dir,
                export_svg=export_svg,
                save_figures=save_figures,
                logger=logger,
            ),
            logger=logger,
            figure_id_hint="H",
        )
    )
    results.extend(
        _safe_figure_call(
            lambda: generate_figure_i(
                merged_df=merged_df,
                figures_dir=figures_dir,
                tables_dir=tables_dir,
                export_svg=export_svg,
                save_figures=save_figures,
                logger=logger,
            ),
            logger=logger,
            figure_id_hint="I",
        )
    )
    return results


def _write_artifact_hashes(output_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for sub in ("figures", "tables"):
        for path in sorted((output_dir / sub).glob("*")):
            if not path.is_file():
                continue
            stat = path.stat()
            rows.append(
                {
                    "artifact_type": sub,
                    "artifact_name": path.name,
                    "artifact_relpath": str(path.relative_to(output_dir)),
                    "size_bytes": int(stat.st_size),
                    "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "sha256": _hash_file(path),
                }
            )
    df = pd.DataFrame(rows).sort_values(["artifact_type", "artifact_name"]).reset_index(drop=True)
    _write_df(df, output_dir / "tables" / "table_artifact_hashes.csv")
    return df


def _figure_strength_note(results: list[FigureResult]) -> str:
    available = {r.figure_id for r in results if r.status == "ok"}

    def _keep(ids: list[str]) -> str:
        return ", ".join([f"Figure {i}" for i in ids if i in available]) or "none available"

    main_paper = _keep(["A", "B", "D", "H", "F"])
    supplement = _keep(["C", "G"])
    readme = _keep(["D", "F", "I"])
    fellowship = _keep(["A", "F", "G", "H", "I"])
    return (
        "## Figure Priority Recommendations\n\n"
        f"- Main paper: {main_paper}\n"
        f"- Supplement: {supplement}\n"
        f"- GitHub README: {readme}\n"
        f"- Fellowship/demo applications: {fellowship}\n"
    )


def _write_markdown_summary(
    output_dir: Path,
    results: list[FigureResult],
    logger: logging.Logger,
) -> Path:
    lines: list[str] = []
    lines.append("# Extended Analysis Figure Summary")
    lines.append("")
    lines.append("This summary is auto-generated by `08_extended_analysis/run_extended_analysis.py`.")
    lines.append("")
    lines.append("## Figure-by-Figure Results")
    lines.append("")
    for r in results:
        lines.append(f"### Figure {r.figure_id}: {r.title}")
        lines.append(f"- Status: `{r.status}`")
        lines.append(f"- Figure base: `{r.filename_base}`")
        lines.append(f"- Table: `tables/{r.table_filename}`")
        lines.append(f"- Main result: {r.main_result}")
        if r.caption:
            lines.append(f"- Suggested manuscript caption: {r.caption}")
        lines.append("")

    lines.append(_figure_strength_note(results))
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Figures are generated from scripts only; no manual post-editing is required.")
    lines.append("- Each figure has a corresponding CSV table in `tables/`.")
    lines.append("- SHA-256 hashes are exported for all generated artifacts in `tables/table_artifact_hashes.csv`.")
    lines.append("")

    out_path = output_dir / "extended_analysis_summary.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote markdown summary: %s", out_path)
    return out_path


def main() -> int:
    args = parse_args()
    paper_root = Path(args.paper_root).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else (paper_root / "results" / "08_extended_analysis")
    figures_dir, tables_dir, logs_dir = _ensure_dirs(output_dir)
    logger = _setup_logger(logs_dir=logs_dir, level_name=args.log_level)
    logger.info("paper root: %s", paper_root)
    logger.info("output dir: %s", output_dir)

    configure_matplotlib()
    results_root = paper_root / "results"
    matrix_df, request_df, manifest_df = load_replay_data(results_root=results_root, logger=logger)
    quality_df = load_quality_data(results_root=results_root, logger=logger)

    if matrix_df.empty:
        logger.error("No replay matrix data was discovered; cannot continue.")
        return 1

    merged_df = build_merged_metrics(matrix_df=matrix_df, quality_df=quality_df)
    stability_df = decoder_stability_table(merged_df)

    core_tables = _write_core_tables(
        tables_dir=tables_dir,
        matrix_df=matrix_df,
        quality_df=quality_df,
        request_df=request_df,
        manifest_df=manifest_df,
        merged_df=merged_df,
        stability_df=stability_df,
    )
    logger.info("Wrote %d core tables.", len(core_tables))

    figure_results = _run_figure_pack(
        merged_df=merged_df,
        request_df=request_df,
        figures_dir=figures_dir,
        tables_dir=tables_dir,
        export_svg=args.export_svg,
        save_figures=not args.skip_figures,
        logger=logger,
    )

    # Persist figure manifest table.
    figure_manifest_df = pd.DataFrame([asdict(r) for r in figure_results])
    _write_df(figure_manifest_df, tables_dir / "table_figure_manifest.csv")

    # Artifact hashes and markdown narrative.
    _write_artifact_hashes(output_dir=output_dir)
    _write_markdown_summary(output_dir=output_dir, results=figure_results, logger=logger)

    ok_count = sum(1 for r in figure_results if r.status == "ok")
    skip_count = sum(1 for r in figure_results if r.status != "ok")
    logger.info("Extended analysis complete: %d figures/tables succeeded, %d skipped.", ok_count, skip_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
