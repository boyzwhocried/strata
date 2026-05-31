"""Insurance domain model plus deliberate data-quality mess injectors.

Everything is driven by a single seed, so the same ``--seed`` always produces
byte-identical raw output. Facts are written as monthly batches under
``data/raw/<table>/`` so the bronze layer can demonstrate incremental,
late-arriving ingestion the way a real warehouse receives source extracts.

The injected mess, and which layer is responsible for resolving it:

    duplicates           idempotent re-sends of the same row   -> silver dedup
    late-arriving facts  event dated month M lands in batch M+2 -> gold as-of logic
    slowly changing dims  customer attributes drift over time   -> silver SCD2
    dirty categoricals   "ACTIVE" / "active" / "Activ "         -> silver normalize
    nulls / bad ranges   unpaid premiums, negative amounts      -> silver + tests
    out-of-order time    paid before due                        -> tests flag it
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import polars as pl
from faker import Faker

# Window starts here; --months counts monthly batches forward from this date.
START = dt.date(2024, 1, 1)

PRODUCT_LINES = ["LIFE", "MICRO", "HEALTH", "GENERAL"]
PAYMENT_METHODS = ["TRANSFER", "AUTODEBIT", "CASH", "VA"]
INCOME_BANDS = ["LOW", "MID", "HIGH", "PREMIUM"]
RISK_CLASSES = ["STANDARD", "PREFERRED", "SUBSTANDARD"]
CLAIM_TYPES = ["DEATH", "HOSPITAL", "ACCIDENT", "MATURITY", "SURRENDER"]
POLICY_STATUS = ["ACTIVE", "LAPSED", "MATURED", "CANCELLED"]
CLAIM_STATUS = ["FILED", "APPROVED", "REJECTED", "PAID"]
BRANCHES = {
    "Jakarta": "WEST",
    "Bandung": "WEST",
    "Medan": "WEST",
    "Semarang": "CENTRAL",
    "Yogyakarta": "CENTRAL",
    "Surabaya": "EAST",
    "Makassar": "EAST",
}
CITIES = list(BRANCHES.keys())


def add_months(d: dt.date, n: int) -> dt.date:
    """First-of-month date n months after the month containing d."""
    total = (d.year * 12 + (d.month - 1)) + n
    return dt.date(total // 12, total % 12 + 1, 1)


def month_floor(d: dt.date) -> dt.date:
    return dt.date(d.year, d.month, 1)


def batch_key(d: dt.date) -> int:
    """YYYYMM integer used to name a raw batch file."""
    return d.year * 100 + d.month


def dirtify(rng: np.random.Generator, values: list[str], frac: float) -> list[str]:
    """Corrupt a fraction of categorical values the way real source feeds do:
    case drift and stray whitespace. Silver normalises these back to a canonical
    token with upper(trim(...)). Fuzzy typo repair (truncations, misspellings)
    needs a lookup or edit-distance step and is left as a v2 extension."""
    out = list(values)
    n = len(out)
    if n == 0:
        return out
    idx = rng.choice(n, size=int(n * frac), replace=False)
    for i in idx:
        v = out[i]
        mode = int(rng.integers(0, 4))
        if mode == 0:
            out[i] = v.lower()
        elif mode == 1:
            out[i] = v + "  "
        elif mode == 2:
            out[i] = "  " + v
        else:
            out[i] = v.title()
    return out


# --------------------------------------------------------------------------
# Dimensions
# --------------------------------------------------------------------------

def gen_agents(rng: np.random.Generator, faker: Faker, n: int) -> pl.DataFrame:
    branches = CITIES
    rows = []
    for i in range(n):
        b = branches[int(rng.integers(0, len(branches)))]
        rows.append(
            {
                "agent_id": f"AGT{i + 1:04d}",
                "agent_name": faker.name(),
                "branch": b,
                "region": BRANCHES[b],
                "hire_date": START - dt.timedelta(days=int(rng.integers(200, 3000))),
            }
        )
    return pl.DataFrame(rows)


def gen_customers_base(rng: np.random.Generator, faker: Faker, n: int) -> pl.DataFrame:
    rows = []
    for i in range(n):
        rows.append(
            {
                "customer_id": f"CUST{i + 1:06d}",
                "full_name": faker.name(),
                "birth_date": faker.date_of_birth(minimum_age=18, maximum_age=72),
                "gender": "M" if rng.random() < 0.5 else "F",
                "occupation": faker.job(),
                "city": CITIES[int(rng.integers(0, len(CITIES)))],
                "income_band": INCOME_BANDS[int(rng.integers(0, len(INCOME_BANDS)))],
                "risk_class": RISK_CLASSES[int(rng.integers(0, len(RISK_CLASSES)))],
            }
        )
    return pl.DataFrame(rows)


def gen_customer_snapshots(
    rng: np.random.Generator, base: pl.DataFrame, months: int
) -> pl.DataFrame:
    """Monthly full-snapshot extract of the customer master. A few attributes
    drift month to month; silver collapses unchanged runs into SCD2 spans.
    Categoricals are dirtied so we can prove normalisation happens *before*
    change detection (case noise must not create spurious history)."""
    snaps: list[dict] = []
    for c in base.iter_rows(named=True):
        city = c["city"]
        income = c["income_band"]
        risk = c["risk_class"]
        for m in range(months):
            if m > 0:
                if rng.random() < 0.03:
                    income = INCOME_BANDS[int(rng.integers(0, len(INCOME_BANDS)))]
                if rng.random() < 0.02:
                    city = CITIES[int(rng.integers(0, len(CITIES)))]
                if rng.random() < 0.015:
                    risk = RISK_CLASSES[int(rng.integers(0, len(RISK_CLASSES)))]
            snaps.append(
                {
                    "customer_id": c["customer_id"],
                    "snapshot_month": add_months(START, m),
                    "full_name": c["full_name"],
                    "birth_date": c["birth_date"],
                    "gender": c["gender"],
                    "occupation": c["occupation"],
                    "city": city,
                    "income_band": income,
                    "risk_class": risk,
                }
            )
    df = pl.DataFrame(snaps)
    df = df.with_columns(
        pl.Series("income_band", dirtify(rng, df["income_band"].to_list(), 0.06)),
        pl.Series("risk_class", dirtify(rng, df["risk_class"].to_list(), 0.05)),
    )
    return df


def gen_policies(
    rng: np.random.Generator,
    customers: pl.DataFrame,
    agents: pl.DataFrame,
    months: int,
) -> pl.DataFrame:
    cust_ids = customers["customer_id"].to_list()
    agent_ids = agents["agent_id"].to_list()
    n_pol = int(len(cust_ids) * 1.4)
    rows = []
    for i in range(n_pol):
        cid = cust_ids[int(rng.integers(0, len(cust_ids)))]
        aid = agent_ids[int(rng.integers(0, len(agent_ids)))]
        line = PRODUCT_LINES[int(rng.integers(0, len(PRODUCT_LINES)))]
        start_m = int(rng.integers(0, months))
        start_date = add_months(START, start_m) + dt.timedelta(
            days=int(rng.integers(0, 27))
        )
        term = int(rng.choice([12, 24, 36, 60, 120]))
        currency = "USD" if rng.random() < 0.08 else "IDR"
        if currency == "IDR":
            premium = float(rng.integers(1, 40)) * 100_000.0
        else:
            premium = float(rng.integers(20, 500))
        sum_assured = round(premium * term * float(rng.uniform(1.2, 3.0)), 2)
        roll = rng.random()
        status = (
            "ACTIVE"
            if roll < 0.72
            else "LAPSED"
            if roll < 0.85
            else "MATURED"
            if roll < 0.94
            else "CANCELLED"
        )
        rows.append(
            {
                "policy_id": f"POL{i + 1:07d}",
                "customer_id": cid,
                "agent_id": aid,
                "product_line": line,
                "premium_amount": premium,
                "sum_assured": sum_assured,
                "currency": currency,
                "start_date": start_date,
                "term_months": term,
                "status": status,
            }
        )
    df = pl.DataFrame(rows)
    df = df.with_columns(
        pl.Series("status", dirtify(rng, df["status"].to_list(), 0.05)),
        pl.Series("product_line", dirtify(rng, df["product_line"].to_list(), 0.04)),
    )
    return df


# --------------------------------------------------------------------------
# Facts (written as monthly batches, with late arrivals and duplicates)
# --------------------------------------------------------------------------

def _ingest_ts(
    rng: np.random.Generator, event_date: dt.date, late_offset: int
) -> tuple[dt.datetime, int]:
    """Land an event in batch month = event-month + late_offset. The ingest
    timestamp is forced to be on or after the event date so freshness checks
    behave."""
    bmonth = add_months(month_floor(event_date), late_offset)
    landed = max(bmonth + dt.timedelta(days=int(rng.integers(0, 27))), event_date)
    ts = dt.datetime.combine(landed, dt.time(int(rng.integers(0, 24)), int(rng.integers(0, 60))))
    return ts, batch_key(bmonth)


def _late_offset(rng: np.random.Generator) -> int:
    return int(rng.choice([0, 0, 0, 0, 1, 1, 2], p=None))


def gen_payments(
    rng: np.random.Generator, policies: pl.DataFrame, months: int
) -> pl.DataFrame:
    window_end = add_months(START, months)
    rows = []
    seq = 0
    for p in policies.iter_rows(named=True):
        base = month_floor(p["start_date"])
        for k in range(months):
            due = add_months(base, k)
            if due >= window_end:
                break
            if due < START:
                continue
            seq += 1
            paid_prob = 0.9 if p["status"] in ("ACTIVE", "MATURED") else 0.55
            paid = rng.random() < paid_prob
            if paid:
                # usually a few days late, occasionally paid early (out of order)
                delay = int(rng.integers(-3, 20))
                paid_date = due + dt.timedelta(days=delay)
                event_date = paid_date
            else:
                paid_date = None
                event_date = due
            amount = round(p["premium_amount"] * float(rng.uniform(0.98, 1.02)), 2)
            if rng.random() < 0.01:  # rare bad amount, silver/tests should catch
                amount = -amount
            ts, bkey = _ingest_ts(rng, event_date, _late_offset(rng))
            rows.append(
                {
                    "payment_id": f"PAY{seq:09d}",
                    "policy_id": p["policy_id"],
                    "due_date": due,
                    "paid_date": paid_date,
                    "amount": amount,
                    "currency": p["currency"],
                    "method": PAYMENT_METHODS[int(rng.integers(0, len(PAYMENT_METHODS)))],
                    "_ingested_at": ts,
                    "_batch": bkey,
                }
            )
    df = pl.DataFrame(rows)
    df = df.with_columns(
        pl.Series("method", dirtify(rng, df["method"].to_list(), 0.05))
    )
    return _inject_duplicates(rng, df, frac=0.015)


def gen_claims(
    rng: np.random.Generator, policies: pl.DataFrame, months: int
) -> pl.DataFrame:
    window_end = add_months(START, months)
    rows = []
    seq = 0
    for p in policies.iter_rows(named=True):
        if rng.random() > 0.09:  # only ~9% of policies ever file a claim
            continue
        n_claims = int(rng.integers(1, 3))
        for _ in range(n_claims):
            seq += 1
            span = (window_end - p["start_date"]).days
            if span <= 1:
                continue
            filed = p["start_date"] + dt.timedelta(days=int(rng.integers(1, span)))
            ctype = CLAIM_TYPES[int(rng.integers(0, len(CLAIM_TYPES)))]
            claim_amount = round(
                p["sum_assured"] * float(rng.uniform(0.05, 1.0)), 2
            )
            roll = rng.random()
            status = (
                "PAID"
                if roll < 0.45
                else "APPROVED"
                if roll < 0.6
                else "REJECTED"
                if roll < 0.8
                else "FILED"
            )
            if status in ("PAID", "APPROVED"):
                assessed = filed + dt.timedelta(days=int(rng.integers(5, 45)))
                paid_amount = (
                    round(claim_amount * float(rng.uniform(0.6, 1.0)), 2)
                    if status == "PAID"
                    else None
                )
            else:
                assessed = (
                    filed + dt.timedelta(days=int(rng.integers(5, 45)))
                    if status == "REJECTED"
                    else None
                )
                paid_amount = None
            event_date = assessed or filed
            ts, bkey = _ingest_ts(rng, event_date, _late_offset(rng))
            rows.append(
                {
                    "claim_id": f"CLM{seq:08d}",
                    "policy_id": p["policy_id"],
                    "claim_type": ctype,
                    "filed_date": filed,
                    "assessed_date": assessed,
                    "claim_amount": claim_amount,
                    "paid_amount": paid_amount,
                    "currency": p["currency"],
                    "status": status,
                    "_ingested_at": ts,
                    "_batch": bkey,
                }
            )
    df = pl.DataFrame(rows)
    df = df.with_columns(
        pl.Series("status", dirtify(rng, df["status"].to_list(), 0.05))
    )
    return _inject_duplicates(rng, df, frac=0.02)


def _inject_duplicates(
    rng: np.random.Generator, df: pl.DataFrame, frac: float
) -> pl.DataFrame:
    """Re-send a fraction of rows, sometimes in a later batch. Identical
    business keys; silver must dedup to one row per key."""
    n = df.height
    if n == 0:
        return df
    idx = rng.choice(n, size=int(n * frac), replace=False)
    dups = df[list(idx)].clone()
    bumped = [
        batch_key(add_months(month_floor(START), 0))  # placeholder, replaced below
        for _ in range(dups.height)
    ]
    # Move ~half of the duplicates into the following batch month.
    new_batches = []
    for b in dups["_batch"].to_list():
        if rng.random() < 0.5:
            y, m = divmod(b, 100)
            nb = batch_key(add_months(dt.date(y, m, 1), 1))
            new_batches.append(nb)
        else:
            new_batches.append(b)
    dups = dups.with_columns(pl.Series("_batch", new_batches))
    return pl.concat([df, dups], how="vertical")


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def _write_partitioned(df: pl.DataFrame, out_dir: Path, by: str) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = 0
    for part in df.partition_by(by):
        key = part[by][0]
        if isinstance(key, dt.date):
            label = f"{key.year}{key.month:02d}"
        else:
            label = str(key)
        part.write_parquet(out_dir / f"part_{label}.parquet")
        files += 1
    return files


def build_all(
    seed: int, months: int, n_customers: int, n_agents: int, out_root: Path
) -> dict:
    rng = np.random.default_rng(seed)
    faker = Faker()
    Faker.seed(seed)

    raw = out_root / "raw"
    if raw.exists():
        for child in raw.glob("**/*.parquet"):
            child.unlink()

    agents = gen_agents(rng, faker, n_agents)
    customers_base = gen_customers_base(rng, faker, n_customers)
    snapshots = gen_customer_snapshots(rng, customers_base, months)
    policies = gen_policies(rng, customers_base, agents, months)
    payments = gen_payments(rng, policies, months)
    claims = gen_claims(rng, policies, months)

    (raw / "agents").mkdir(parents=True, exist_ok=True)
    agents.write_parquet(raw / "agents" / "part_all.parquet")
    (raw / "policies").mkdir(parents=True, exist_ok=True)
    policies.write_parquet(raw / "policies" / "part_all.parquet")

    snap_files = _write_partitioned(snapshots, raw / "customer_snapshots", "snapshot_month")
    pay_files = _write_partitioned(payments, raw / "premium_payments", "_batch")
    clm_files = _write_partitioned(claims, raw / "claims", "_batch")

    return {
        "seed": seed,
        "months": months,
        "agents": agents.height,
        "customers": customers_base.height,
        "customer_snapshots": snapshots.height,
        "policies": policies.height,
        "premium_payments": payments.height,
        "claims": claims.height,
        "snapshot_batches": snap_files,
        "payment_batches": pay_files,
        "claim_batches": clm_files,
    }
