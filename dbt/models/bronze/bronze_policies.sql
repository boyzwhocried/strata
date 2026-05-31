-- Raw policy master, 1:1 from source. Categoricals (status, product_line) are
-- still dirty here on purpose.
select
    policy_id,
    customer_id,
    agent_id,
    product_line,
    premium_amount,
    sum_assured,
    currency,
    start_date,
    term_months,
    status
from {{ source('raw', 'policies') }}
