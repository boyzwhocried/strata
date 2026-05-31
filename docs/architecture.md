# Architecture

This document explains the parts of Strata that carry the real engineering: how
the synthetic mess is produced, and how each transform resolves it. The README
is the overview; this is the detail.

## 1. The synthetic source

`generate/domain.py` builds a small insurance book from a single seed, so the
same `--seed` always yields byte-identical output. Five source objects:

- `agents`, `policies`: static masters written as one parquet file each.
- `customer_snapshots`: a monthly full-snapshot extract of the customer master.
- `premium_payments`, `claims`: facts, written as one parquet file per ingest
  batch under `data/raw/<table>/`.

Facts are partitioned into monthly batches because that is how warehouses
actually receive data: a periodic extract, sometimes containing rows that belong
to an earlier period. Bronze reads the whole directory, so adding a batch is
purely additive.

### The mess injectors

Each injector is deterministic and bounded by a fraction, so the volume of mess
is stable across runs:

- **Late arrivals.** An event dated in month M is assigned an ingest batch of
  month M, M+1, or M+2 (weighted toward on-time). The ingest timestamp is forced
  to be on or after the event date, so freshness logic stays sane.
- **Duplicates.** A small fraction of fact rows are re-emitted with identical
  business keys, and about half of those land in the following batch. This is an
  idempotent re-send, not a new event.
- **SCD drift.** Between monthly snapshots, a customer's `city`, `income_band`,
  or `risk_class` can change with low probability. Most customers never change;
  some change more than once.
- **Dirty categoricals.** A fraction of categorical values are lower-cased,
  title-cased, or given stray leading or trailing whitespace. All are
  recoverable with `upper(trim(...))`.
- **Bad values.** A small fraction of payment amounts are negated, and unpaid
  premiums leave `paid_date` null.

## 2. Bronze

Five views, one per source, selected one to one. No casting beyond what the
parquet already carries, no cleaning. The point of bronze is auditability: if a
downstream number looks wrong, bronze is the unmodified source of truth to
compare against. dbt-duckdb resolves `{{ source(...) }}` to `read_parquet(...)`
over the raw directory via the `external_location` set in
`models/bronze/_bronze__sources.yml`.

## 3. Silver

### 3.1 SCD Type 2 from snapshots (`silver_dim_customer`)

The centerpiece. It turns monthly snapshots into a history table with one row per
customer per attribute span. The pipeline, in order:

1. **Normalize first.** Trim and upper-case the tracked attributes. This has to
   happen before change detection, otherwise `MID` versus `  mid ` would look
   like a real change and manufacture false history.
2. **Flag changes.** For each customer ordered by snapshot month, compare the
   current attribute tuple to the previous month's with `lag(...)`. A difference
   (including the first row, whose `lag` is null) sets a change flag.
3. **Version.** A running `sum()` of the change flag over the customer's timeline
   gives a 1-based version number that increments only when something actually
   changed.
4. **Collapse.** Group by `(customer_id, version)` to get one row per span, with
   `valid_from = min(snapshot_month)`. The attributes are constant within a
   version, so any aggregate returns the right value.
5. **Close the spans.** `valid_to = lead(valid_from)` over the customer's
   versions (an exclusive upper bound). The final span has `valid_to = null` and
   `is_current = true`.

Two singular tests defend the result: exactly one current row per customer, and
contiguous spans (every closed `valid_to` equals the next `valid_from`). The
model also carries an enforced contract, so its column set and types cannot
drift unnoticed.

### 3.2 Deduplication (`silver_premium_payments`, `silver_claims`)

Idempotent re-sends share a business key. Silver keeps one row per key using
`row_number()` partitioned by the key, ordered by `_ingested_at` then `_batch`
descending, then filters to the first. The latest landing wins, which is exactly
what you want when a corrected batch is re-sent: it overwrites rather than
double counts. The reconciliation report exposes `duplicates_removed` as
`bronze_rows - silver_rows`, and a test asserts that value is never negative (a
negative would mean a silver model fanned out rows, a classic join bug).

### 3.3 Quality and behaviour flags

Silver derives boolean flags rather than dropping suspicious rows, so nothing is
silently discarded and the gold scorecard can count everything:

- `is_paid`, `days_to_pay`, `is_paid_before_due`
- `is_invalid_amount` (amount at or below zero)
- `is_late_arrival` (batch month later than the event's own month)
- claims: `is_paid_claim`, `is_assessed`, `settlement_days`

## 4. Gold

- `gold_fct_premium_payments`, `gold_fct_claims`: facts enriched with policy,
  agent, and current-customer attributes (the customer join is to the current
  SCD2 span only).
- `gold_policy_performance`: one row per policy with premiums due and collected,
  claims paid, and a loss ratio. Sums stay within a single policy, so every row
  is single-currency and no currencies are mixed.
- `gold_rpt_reconciliation`: per-stream bronze to silver row counts, duplicates
  removed, and late-arrival counts. Enforced contract.
- `gold_rpt_data_quality`: a tall metric / value scorecard, easy to threshold or
  chart.

## 5. Lineage and docs

`make docs` runs `dbt docs generate`, which produces the full column-level
lineage graph from the `ref()` and `source()` calls. Because every dependency is
declared through those functions, the graph is exact, not hand-drawn.

## 6. Conventions

- Schemas are kept literal (`bronze`, `silver`, `gold`) via a
  `generate_schema_name` override, so the warehouse layout reads the way the
  architecture does.
- Bronze is views (cheap, always fresh against raw); silver and gold are tables
  (queried repeatedly, worth materializing).
- All dbt commands run from the repo root so the relative paths in
  `profiles.yml` and the source `external_location` resolve. The Makefile and
  `strata.ps1` enforce this.
