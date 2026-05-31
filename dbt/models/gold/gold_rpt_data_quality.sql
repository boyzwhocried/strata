-- Data-quality scorecard: one row per metric, tall format so it renders as a
-- readable report card and is easy to threshold or chart. Counts how much of
-- the deliberately injected mess the pipeline surfaced or resolved.

with payments as (select * from {{ ref('silver_premium_payments') }}),
     claims   as (select * from {{ ref('silver_claims') }}),
     dim      as (select * from {{ ref('silver_dim_customer') }}),
     hist     as (
        select customer_id
        from dim
        group by customer_id
        having max(scd_version) > 1
     )

select metric, value, unit from (
    select 1 as ord, 'payments_total'            as metric, cast(count(*) as bigint) as value, 'rows' as unit from payments
    union all
    select 2,  'payments_unpaid',          count(*) filter (where not is_paid),          'rows' from payments
    union all
    select 3,  'payments_invalid_amount',  count(*) filter (where is_invalid_amount),     'rows' from payments
    union all
    select 4,  'payments_paid_before_due', count(*) filter (where is_paid_before_due),    'rows' from payments
    union all
    select 5,  'payments_late_arrival',    count(*) filter (where is_late_arrival),       'rows' from payments
    union all
    select 6,  'claims_total',             count(*),                                      'rows' from claims
    union all
    select 7,  'claims_late_arrival',      count(*) filter (where is_late_arrival),        'rows' from claims
    union all
    select 8,  'customers_scd_rows',       count(*),                                      'rows' from dim
    union all
    select 9,  'customers_current',        count(*) filter (where is_current),            'rows' from dim
    union all
    select 10, 'customers_with_history',   (select cast(count(*) as bigint) from hist),    'rows' from (select 1)
)
order by ord
