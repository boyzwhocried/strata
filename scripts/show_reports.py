"""Print the gold-layer reports to the terminal.

Powers `make report` / `strata.ps1 report`. Reads the built DuckDB file; run a
build first if it does not exist yet.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

# DuckDB's table renderer uses box-drawing glyphs; force UTF-8 so it prints on
# a Windows (cp1252) console too.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB = Path(__file__).resolve().parent.parent / "data" / "strata.duckdb"


def _table(con: duckdb.DuckDBPyConnection, title: str, sql: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    con.sql(sql).show(max_rows=40, max_width=120)


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"{DB} not found. Run a build first (make build).")
    con = duckdb.connect(str(DB), read_only=True)

    _table(
        con,
        "Pipeline reconciliation (bronze -> silver)",
        "select * from gold.gold_rpt_reconciliation",
    )
    _table(
        con,
        "Data-quality scorecard",
        "select * from gold.gold_rpt_data_quality",
    )
    _table(
        con,
        "Sample SCD2 history (one customer, multiple versions)",
        """
        select customer_id, scd_version, city, income_band, risk_class,
               valid_from, valid_to, is_current
        from silver.silver_dim_customer
        where customer_id = (
            select customer_id
            from silver.silver_dim_customer
            group by customer_id
            having max(scd_version) >= 3
            order by customer_id
            limit 1
        )
        order by scd_version
        """,
    )
    print()


if __name__ == "__main__":
    main()
