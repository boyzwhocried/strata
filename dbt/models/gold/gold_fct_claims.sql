-- Claim fact enriched with policy and agent context. One row per deduped claim.
select
    cl.claim_id,
    cl.policy_id,
    pol.customer_id,
    pol.agent_id,
    a.branch,
    a.region,
    pol.product_line,
    cl.claim_type,
    cl.filed_date,
    cl.assessed_date,
    cl.claim_amount,
    cl.paid_amount,
    cl.currency,
    cl.status,
    cl.is_paid_claim,
    cl.is_assessed,
    cl.settlement_days,
    cl.is_late_arrival,
    cl._batch
from {{ ref('silver_claims') }}        cl
left join {{ ref('silver_policies') }} pol on cl.policy_id = pol.policy_id
left join {{ ref('silver_agents') }}   a   on pol.agent_id = a.agent_id
