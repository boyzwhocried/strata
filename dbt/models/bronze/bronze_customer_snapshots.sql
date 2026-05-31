-- Monthly full-snapshot extract of the customer master, 1:1 from source.
-- Attributes drift across snapshots; silver turns this into SCD2 history.
select
    customer_id,
    snapshot_month,
    full_name,
    birth_date,
    gender,
    occupation,
    city,
    income_band,
    risk_class
from {{ source('raw', 'customer_snapshots') }}
