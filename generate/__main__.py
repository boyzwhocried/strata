"""CLI: generate the synthetic raw layer.

    python -m generate --seed 42 --months 12 --customers 2000

Writes deterministic parquet batches under ``data/raw/``. Re-running with the
same flags reproduces identical output, so the whole platform is idempotent
from the very first step.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .domain import build_all

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(prog="generate", description=__doc__)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--months", type=int, default=12, help="monthly batches from 2024-01")
    ap.add_argument("--customers", type=int, default=2000)
    ap.add_argument("--agents", type=int, default=60)
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "data",
        help="output root (raw/ is written underneath)",
    )
    args = ap.parse_args()

    t0 = time.perf_counter()
    summary = build_all(
        seed=args.seed,
        months=args.months,
        n_customers=args.customers,
        n_agents=args.agents,
        out_root=args.out,
    )
    summary["elapsed_s"] = round(time.perf_counter() - t0, 2)

    print(json.dumps(summary, indent=2))
    print(f"\nraw written to {args.out / 'raw'}")


if __name__ == "__main__":
    main()
