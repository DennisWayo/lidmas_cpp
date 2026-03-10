#!/usr/bin/env python3
"""Train a linear neural_mwpm guidance model from LiDMaS simulations.

The model format matches plugins/neural/NeuralWeightModel.cpp:
{
  "type": "linear",
  "bias": ...,
  "weights": {
    "manhattan": ...,
    "dx": ...,
    "dy": ...,
    "near_boundary": ...
  },
  "clamp": [lo, hi]
}

Training objective:
  mean_ler + fail_penalty * mean_decoder_fail_rate
over a set of hybrid sigma points at fixed distance.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple


def parse_sigmas(text: str) -> List[float]:
    out: List[float] = []
    for tok in text.split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.append(float(tok))
    if not out:
        raise ValueError("no sigma values provided")
    return out


def model_json(candidate: Dict[str, float], train_info: Dict[str, float] | None = None) -> Dict:
    doc = {
        "type": "linear",
        "bias": candidate["bias"],
        "weights": {
            "manhattan": candidate["w_manhattan"],
            "dx": candidate["w_dx"],
            "dy": candidate["w_dy"],
            "near_boundary": candidate["w_near_boundary"],
        },
        "clamp": [candidate["clamp_lo"], candidate["clamp_hi"]],
    }
    if train_info is not None:
        # Keep metadata keys distinct from parser keys ("type", "bias", "weights", "clamp", ...).
        doc["train_info"] = train_info
    return doc


def sample_candidate(rng: random.Random) -> Dict[str, float]:
    clamp_lo = rng.uniform(0.6, 1.0)
    clamp_hi = rng.uniform(max(1.05, clamp_lo + 0.15), 2.5)
    return {
        "bias": rng.uniform(0.85, 1.15),
        "w_manhattan": rng.uniform(-0.08, 0.08),
        "w_dx": rng.uniform(-0.05, 0.05),
        "w_dy": rng.uniform(-0.05, 0.05),
        "w_near_boundary": rng.uniform(-0.30, 0.30),
        "clamp_lo": clamp_lo,
        "clamp_hi": clamp_hi,
    }


def perturb(best: Dict[str, float], rng: random.Random) -> Dict[str, float]:
    c = dict(best)
    c["bias"] += rng.gauss(0.0, 0.03)
    c["w_manhattan"] += rng.gauss(0.0, 0.015)
    c["w_dx"] += rng.gauss(0.0, 0.01)
    c["w_dy"] += rng.gauss(0.0, 0.01)
    c["w_near_boundary"] += rng.gauss(0.0, 0.05)
    c["clamp_lo"] += rng.gauss(0.0, 0.05)
    c["clamp_hi"] += rng.gauss(0.0, 0.08)

    c["bias"] = min(1.25, max(0.75, c["bias"]))
    c["w_manhattan"] = min(0.12, max(-0.12, c["w_manhattan"]))
    c["w_dx"] = min(0.08, max(-0.08, c["w_dx"]))
    c["w_dy"] = min(0.08, max(-0.08, c["w_dy"]))
    c["w_near_boundary"] = min(0.6, max(-0.6, c["w_near_boundary"]))
    c["clamp_lo"] = min(1.1, max(0.4, c["clamp_lo"]))
    c["clamp_hi"] = min(3.0, max(1.05, c["clamp_hi"]))
    if c["clamp_hi"] <= c["clamp_lo"] + 0.05:
        c["clamp_hi"] = min(3.0, c["clamp_lo"] + 0.2)
    return c


def neutral_candidate() -> Dict[str, float]:
    return {
        "bias": 1.0,
        "w_manhattan": 0.0,
        "w_dx": 0.0,
        "w_dy": 0.0,
        "w_near_boundary": 0.0,
        "clamp_lo": 0.5,
        "clamp_hi": 2.0,
    }


def run_point(
    bin_path: Path,
    model_path: Path,
    distance: int,
    sigma: float,
    trials: int,
    seed: int,
    timeout_s: int,
) -> Tuple[float, float]:
    with tempfile.TemporaryDirectory(prefix="lidmas_train_point_") as tmp:
        out_csv = Path(tmp) / "out.csv"
        cmd = [
            str(bin_path),
            "--surface_threshold",
            "--mode=hybrid",
            "--decoder=neural_mwpm",
            f"--neural_model={model_path}",
            f"--d={distance}",
            f"--sigma_start={sigma}",
            f"--sigma_end={sigma}",
            "--sigma_step=0.05",
            f"--trials={trials}",
            f"--seed={seed}",
            f"--out={out_csv}",
        ]
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if proc.returncode != 0:
            return math.inf, math.inf
        if not out_csv.exists():
            return math.inf, math.inf
        with out_csv.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if len(rows) != 1:
            return math.inf, math.inf
        row = rows[0]
        ler = float(row.get("ler", "nan"))
        fail = float(row.get("decoder_fail_rate", "nan"))
        if not math.isfinite(ler) or not math.isfinite(fail):
            return math.inf, math.inf
        return ler, fail


def evaluate_candidate(
    candidate: Dict[str, float],
    bin_path: Path,
    distance: int,
    sigmas: List[float],
    trials: int,
    base_seed: int,
    fail_penalty: float,
    timeout_s: int,
) -> Dict[str, float]:
    with tempfile.TemporaryDirectory(prefix="lidmas_train_model_") as tmp:
        model_path = Path(tmp) / "model.json"
        with model_path.open("w", encoding="utf-8") as f:
            json.dump(model_json(candidate), f, indent=2)
            f.write("\n")

        lers: List[float] = []
        fails: List[float] = []
        for i, sigma in enumerate(sigmas):
            ler, fail = run_point(
                bin_path=bin_path,
                model_path=model_path,
                distance=distance,
                sigma=sigma,
                trials=trials,
                seed=base_seed + i,
                timeout_s=timeout_s,
            )
            if not math.isfinite(ler) or not math.isfinite(fail):
                return {
                    "objective": math.inf,
                    "mean_ler": math.inf,
                    "mean_fail_rate": math.inf,
                }
            lers.append(ler)
            fails.append(fail)

    mean_ler = sum(lers) / len(lers)
    mean_fail = sum(fails) / len(fails)
    objective = mean_ler + fail_penalty * mean_fail
    return {
        "objective": objective,
        "mean_ler": mean_ler,
        "mean_fail_rate": mean_fail,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a neural_mwpm linear model using LiDMaS simulator feedback.")
    parser.add_argument(
        "--bin",
        default="build/lidmas",
        help="Path to lidmas binary",
    )
    parser.add_argument(
        "--out",
        default="examples/decoder_comparison/trained_model.json",
        help="Output model JSON path",
    )
    parser.add_argument("--distance", type=int, default=5, help="Code distance used for training")
    parser.add_argument(
        "--sigmas",
        default="0.30,0.35,0.40,0.45,0.50,0.55",
        help="Comma-separated hybrid sigma values used for training objective",
    )
    parser.add_argument("--trials", type=int, default=300, help="Trials per sigma point during training")
    parser.add_argument("--seed", type=int, default=1337, help="Base random seed")
    parser.add_argument("--candidates", type=int, default=28, help="Random candidates sampled")
    parser.add_argument("--refine-steps", type=int, default=18, help="Local perturbation steps from best candidate")
    parser.add_argument(
        "--fail-penalty",
        type=float,
        default=4.0,
        help="Penalty multiplier for decoder_fail_rate in objective",
    )
    parser.add_argument("--timeout-s", type=int, default=60, help="Timeout per single-sigma evaluation")
    args = parser.parse_args()

    bin_path = Path(args.bin).resolve()
    if not bin_path.exists():
        raise FileNotFoundError(f"lidmas binary not found: {bin_path}")
    sigmas = parse_sigmas(args.sigmas)

    rng = random.Random(args.seed)
    best_candidate = neutral_candidate()
    best_metrics = evaluate_candidate(
        candidate=best_candidate,
        bin_path=bin_path,
        distance=args.distance,
        sigmas=sigmas,
        trials=args.trials,
        base_seed=args.seed,
        fail_penalty=args.fail_penalty,
        timeout_s=args.timeout_s,
    )

    print(
        "baseline objective={:.6f} mean_ler={:.6f} mean_fail={:.6f}".format(
            best_metrics["objective"],
            best_metrics["mean_ler"],
            best_metrics["mean_fail_rate"],
        )
    )

    for i in range(args.candidates):
        cand = sample_candidate(rng)
        metrics = evaluate_candidate(
            candidate=cand,
            bin_path=bin_path,
            distance=args.distance,
            sigmas=sigmas,
            trials=args.trials,
            base_seed=args.seed + 1000 + i * 17,
            fail_penalty=args.fail_penalty,
            timeout_s=args.timeout_s,
        )
        print(
            "rand {:02d} objective={:.6f} mean_ler={:.6f} mean_fail={:.6f}".format(
                i + 1,
                metrics["objective"],
                metrics["mean_ler"],
                metrics["mean_fail_rate"],
            )
        )
        if metrics["objective"] < best_metrics["objective"]:
            best_candidate = cand
            best_metrics = metrics
            print("  -> new best")

    for i in range(args.refine_steps):
        cand = perturb(best_candidate, rng)
        metrics = evaluate_candidate(
            candidate=cand,
            bin_path=bin_path,
            distance=args.distance,
            sigmas=sigmas,
            trials=args.trials,
            base_seed=args.seed + 100000 + i * 31,
            fail_penalty=args.fail_penalty,
            timeout_s=args.timeout_s,
        )
        print(
            "ref {:02d} objective={:.6f} mean_ler={:.6f} mean_fail={:.6f}".format(
                i + 1,
                metrics["objective"],
                metrics["mean_ler"],
                metrics["mean_fail_rate"],
            )
        )
        if metrics["objective"] < best_metrics["objective"]:
            best_candidate = cand
            best_metrics = metrics
            print("  -> new best")

    train_info = {
        "method": "random_search_plus_local_refine",
        "objective_name": "mean_ler_plus_penalty_times_mean_fail_rate",
        "objective_value": best_metrics["objective"],
        "mean_ler": best_metrics["mean_ler"],
        "mean_fail_rate": best_metrics["mean_fail_rate"],
        "mode": "hybrid",
        "distance": int(args.distance),
        "sigmas_csv": ",".join(str(x) for x in sigmas),
        "trials_per_sigma": int(args.trials),
        "seed": int(args.seed),
        "fail_penalty": float(args.fail_penalty),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(model_json(best_candidate, train_info=train_info), f, indent=2)
        f.write("\n")

    print(f"trained model written: {out_path.resolve()}")
    print(
        "best objective={:.6f} mean_ler={:.6f} mean_fail={:.6f}".format(
            best_metrics["objective"],
            best_metrics["mean_ler"],
            best_metrics["mean_fail_rate"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

