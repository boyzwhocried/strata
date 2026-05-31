"""Strata synthetic insurance data generator.

Deterministic, seeded generation of a small insurance book (customers,
policies, premium payments, claims, agents) plus deliberate data-quality
mess. The mess is the point: late-arriving facts, duplicates, slowly
changing dimensions, dirty categoricals, nulls and out-of-order timestamps.
Cleaning it up is the job of the silver and gold dbt layers.
"""
