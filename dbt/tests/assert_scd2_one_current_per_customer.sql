-- Every customer must have exactly one open (current) SCD2 span. Returns the
-- offenders; an empty result is a pass.
select
    customer_id,
    count(*) as current_rows
from {{ ref('silver_dim_customer') }}
where is_current
group by customer_id
having count(*) <> 1
