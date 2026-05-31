-- Conformed policy master: canonical categorical tokens, explicit numeric types.
select
    policy_id,
    customer_id,
    agent_id,
    upper(trim(product_line))      as product_line,
    cast(premium_amount as double) as premium_amount,
    cast(sum_assured as double)    as sum_assured,
    upper(trim(currency))          as currency,
    start_date,
    term_months,
    upper(trim(status))            as status
from {{ ref('bronze_policies') }}
