-- Raw premium payment facts, appended from every monthly batch. Contains
-- duplicate re-sends, late arrivals (_batch later than the event month),
-- nulls (unpaid), out-of-order paid dates and the occasional negative amount.
select
    payment_id,
    policy_id,
    due_date,
    paid_date,
    amount,
    currency,
    method,
    _ingested_at,
    _batch
from {{ source('raw', 'premium_payments') }}
