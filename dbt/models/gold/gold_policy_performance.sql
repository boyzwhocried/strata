-- One row per policy: premium collection vs claims paid, with a loss ratio.
-- Sums stay within a single policy, so each row is single-currency (no mixing).

with pay as (
    select
        policy_id,
        count(*)                                                    as premiums_due,
        count(*) filter (where is_paid)                             as premiums_paid,
        sum(case when is_paid and not is_invalid_amount
                 then amount else 0 end)                            as premium_collected
    from {{ ref('silver_premium_payments') }}
    group by policy_id
),

clm as (
    select
        policy_id,
        count(*)                          as claims_filed,
        sum(coalesce(paid_amount, 0))     as claims_paid
    from {{ ref('silver_claims') }}
    group by policy_id
)

select
    pol.policy_id,
    pol.customer_id,
    pol.product_line,
    pol.status,
    pol.currency,
    pol.premium_amount,
    pol.sum_assured,
    coalesce(pay.premiums_due, 0)       as premiums_due,
    coalesce(pay.premiums_paid, 0)      as premiums_paid,
    coalesce(pay.premium_collected, 0)  as premium_collected,
    coalesce(clm.claims_filed, 0)       as claims_filed,
    coalesce(clm.claims_paid, 0)        as claims_paid,
    case when coalesce(pay.premium_collected, 0) > 0
         then round(coalesce(clm.claims_paid, 0) / pay.premium_collected, 4)
    end                                 as loss_ratio
from {{ ref('silver_policies') }} pol
left join pay on pol.policy_id = pay.policy_id
left join clm on pol.policy_id = clm.policy_id
