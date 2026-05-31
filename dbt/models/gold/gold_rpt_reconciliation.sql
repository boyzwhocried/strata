-- Pipeline reconciliation: prove bronze -> silver integrity for each fact
-- stream. duplicates_removed is exactly the re-sends collapsed by silver;
-- silver must never carry MORE rows than bronze (asserted by a test).
with streams as (
    select
        'premium_payments'                                            as stream,
        (select count(*) from {{ ref('bronze_premium_payments') }})   as bronze_rows,
        (select count(*) from {{ ref('silver_premium_payments') }})   as silver_rows,
        (select count(*) from {{ ref('silver_premium_payments') }}
            where is_late_arrival)                                    as late_arrival_rows

    union all

    select
        'claims',
        (select count(*) from {{ ref('bronze_claims') }}),
        (select count(*) from {{ ref('silver_claims') }}),
        (select count(*) from {{ ref('silver_claims') }} where is_late_arrival)
)

select
    stream,
    bronze_rows,
    silver_rows,
    bronze_rows - silver_rows as duplicates_removed,
    late_arrival_rows
from streams
order by stream
