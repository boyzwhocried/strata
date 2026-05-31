-- Raw claim facts, appended from every monthly batch. Late arrivals and
-- duplicate re-sends present; status categorical still dirty.
select
    claim_id,
    policy_id,
    claim_type,
    filed_date,
    assessed_date,
    claim_amount,
    paid_amount,
    currency,
    status,
    _ingested_at,
    _batch
from {{ source('raw', 'claims') }}
