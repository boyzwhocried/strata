-- Dedup can only remove rows, never invent them: silver must never carry more
-- rows than bronze for any stream. duplicates_removed < 0 would mean a fan-out
-- bug in a silver model.
select *
from {{ ref('gold_rpt_reconciliation') }}
where duplicates_removed < 0
