-- Conformed agent dimension: trimmed names, canonical branch/region tokens.
select
    agent_id,
    trim(agent_name)     as agent_name,
    upper(trim(branch))  as branch,
    upper(trim(region))  as region,
    hire_date
from {{ ref('bronze_agents') }}
