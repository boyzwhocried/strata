{{ config(materialized='table', contract={'enforced': true}) }}

-- Type-2 slowly changing customer dimension, built from monthly full snapshots.
--
-- Pipeline:
--   1. normalise categoricals first, so case/whitespace noise does NOT look
--      like a real attribute change and create spurious history.
--   2. flag a row whenever any tracked attribute differs from the prior month.
--   3. cumulative-sum the flags into a version number per customer.
--   4. collapse each version into one span (valid_from .. valid_to).
--
-- valid_to is the next span's valid_from (exclusive upper bound); the open span
-- has valid_to = null and is_current = true.

with src as (
    select
        customer_id,
        snapshot_month,
        trim(full_name)           as full_name,
        upper(trim(gender))       as gender,
        trim(occupation)          as occupation,
        upper(trim(city))         as city,
        upper(trim(income_band))  as income_band,
        upper(trim(risk_class))   as risk_class,
        birth_date
    from {{ ref('bronze_customer_snapshots') }}
),

flagged as (
    select
        *,
        case
            when coalesce(full_name, '')   != coalesce(lag(full_name)   over w, '~')
              or coalesce(gender, '')      != coalesce(lag(gender)      over w, '~')
              or coalesce(occupation, '')  != coalesce(lag(occupation)  over w, '~')
              or coalesce(city, '')        != coalesce(lag(city)        over w, '~')
              or coalesce(income_band, '') != coalesce(lag(income_band) over w, '~')
              or coalesce(risk_class, '')  != coalesce(lag(risk_class)  over w, '~')
            then 1 else 0
        end as is_change
    from src
    window w as (partition by customer_id order by snapshot_month)
),

versioned as (
    select
        *,
        sum(is_change) over (
            partition by customer_id
            order by snapshot_month
            rows between unbounded preceding and current row
        ) as version
    from flagged
),

spans as (
    select
        customer_id,
        cast(version as integer) as scd_version,
        min(snapshot_month)      as valid_from,
        min(full_name)           as full_name,
        min(gender)              as gender,
        min(occupation)          as occupation,
        min(city)                as city,
        min(income_band)         as income_band,
        min(risk_class)          as risk_class,
        min(birth_date)          as birth_date
    from versioned
    group by customer_id, version
)

select
    {{ dbt_utils.generate_surrogate_key(['customer_id', 'scd_version']) }} as customer_sk,
    customer_id,
    scd_version,
    full_name,
    gender,
    occupation,
    city,
    income_band,
    risk_class,
    birth_date,
    valid_from,
    lead(valid_from) over (partition by customer_id order by scd_version) as valid_to,
    lead(valid_from) over (partition by customer_id order by scd_version) is null as is_current
from spans
