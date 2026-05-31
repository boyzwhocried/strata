-- Conformed premium payment fact.
--
--   * dedup: idempotent re-sends share a payment_id; keep the row from the
--     latest batch / ingest timestamp (the standard idempotent-reload pattern).
--   * normalise currency and method.
--   * derive quality + behaviour flags used downstream and by tests:
--       is_paid, days_to_pay, is_invalid_amount, is_paid_before_due,
--       is_late_arrival (landed in a batch after the due month).

with normd as (
    select
        payment_id,
        policy_id,
        due_date,
        paid_date,
        cast(amount as double)                              as amount,
        upper(trim(currency))                               as currency,
        upper(trim(method))                                 as method,
        _ingested_at,
        _batch,
        (paid_date is not null)                             as is_paid,
        case when paid_date is not null
             then date_diff('day', due_date, paid_date)
        end                                                 as days_to_pay,
        (amount <= 0)                                       as is_invalid_amount,
        (paid_date is not null and paid_date < due_date)    as is_paid_before_due,
        (_batch > cast(strftime(due_date, '%Y%m') as int))  as is_late_arrival
    from {{ ref('bronze_premium_payments') }}
),

dedup as (
    select
        *,
        row_number() over (
            partition by payment_id
            order by _ingested_at desc, _batch desc
        ) as _rn
    from normd
)

select * exclude (_rn)
from dedup
where _rn = 1
