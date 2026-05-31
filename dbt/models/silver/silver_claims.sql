-- Conformed claim fact: dedup latest-by-ingest, normalise status, derive
-- settlement + late-arrival flags.

with normd as (
    select
        claim_id,
        policy_id,
        upper(trim(claim_type))         as claim_type,
        filed_date,
        assessed_date,
        cast(claim_amount as double)    as claim_amount,
        cast(paid_amount as double)     as paid_amount,
        upper(trim(currency))           as currency,
        upper(trim(status))             as status,
        _ingested_at,
        _batch
    from {{ ref('bronze_claims') }}
),

derived as (
    select
        *,
        (status = 'PAID')                                       as is_paid_claim,
        (status in ('PAID', 'APPROVED', 'REJECTED'))            as is_assessed,
        case when assessed_date is not null
             then date_diff('day', filed_date, assessed_date)
        end                                                     as settlement_days,
        (_batch > cast(strftime(filed_date, '%Y%m') as int))    as is_late_arrival
    from normd
),

dedup as (
    select
        *,
        row_number() over (
            partition by claim_id
            order by _ingested_at desc, _batch desc
        ) as _rn
    from derived
)

select * exclude (_rn)
from dedup
where _rn = 1
