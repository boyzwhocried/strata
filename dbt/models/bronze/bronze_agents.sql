-- Raw agent dimension, 1:1 from source. No cleaning.
select
    agent_id,
    agent_name,
    branch,
    region,
    hire_date
from {{ source('raw', 'agents') }}
