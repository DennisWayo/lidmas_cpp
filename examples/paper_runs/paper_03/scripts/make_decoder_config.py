#!/usr/bin/env python3
"""Generate per-decoder decoder_io adapter configs for replay runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Base JSON adapter config path.")
    parser.add_argument("--decoder", required=True, help="Decoder name.")
    parser.add_argument("--out", required=True, help="Output JSON config path.")
    parser.add_argument(
        "--neural-model",
        default="",
        help="Path to neural model (required when decoder is neural_mwpm).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_path = Path(args.base)
    out_path = Path(args.out)

    with base_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    decoder = args.decoder.strip()
    cfg["decoder_name"] = decoder

    if decoder == "neural_mwpm":
        model = args.neural_model.strip()
        if not model:
            raise SystemExit("neural_mwpm requires --neural-model.")
        cfg["neural_model_path"] = model
        cfg["neural_weights_path"] = model
    else:
        cfg["neural_model_path"] = ""
        cfg["neural_weights_path"] = ""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
