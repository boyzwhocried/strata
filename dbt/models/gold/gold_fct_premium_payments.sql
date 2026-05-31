-- Premium payment fact enriched with policy, agent and current-customer
-- attributes. One row per deduped payment.
select
    p.payment_id,
    p.policy_id,
    pol.customer_id,
    pol.agent_id,
    a.branch,
    a.region,
    pol.product_line,
    c.income_band       as customer_income_band,
    c.city              as customer_city,
    p.due_date,
    p.paid_date,
    p.amount,
    p.currency,
    p.method,
    p.is_paid,
    p.days_to_pay,
    p.is_invalid_amount,
    p.is_paid_before_due,
    p.is_late_arrival,
    p._batch,
    p._ingested_at
from {{ ref('silver_premium_payments') }} p
left join {{ ref('silver_policies') }}     pol on p.policy_id = pol.policy_id
left join {{ ref('silver_agents') }}        a  on pol.agent_id = a.agent_id
left join {{ ref('silver_dim_customer') }}  c  on pol.customer_id = c.customer_id
                                              and c.is_current
