-- A negative loss ratio is impossible (claims paid and premium collected are
-- both non-negative). Catches sign or join-fanout errors in the mart.
select
    policy_id,
    loss_ratio
from {{ ref('gold_policy_performance') }}
where loss_ratio < 0
