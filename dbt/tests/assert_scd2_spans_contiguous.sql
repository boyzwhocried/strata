-- SCD2 spans must tile the timeline with no gaps and no overlaps: each closed
-- span's valid_to equals the next span's valid_from. Returns any break.
with ordered as (
    select
        customer_id,
        scd_version,
        valid_from,
        valid_to,
        lead(valid_from) over (
            partition by customer_id order by scd_version
        ) as next_valid_from
    from {{ ref('silver_dim_customer') }}
)
select *
from ordered
where valid_to is not null
  and valid_to <> next_valid_from
