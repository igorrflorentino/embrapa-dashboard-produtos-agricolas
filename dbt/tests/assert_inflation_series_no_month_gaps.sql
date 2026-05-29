-- Chain-index continuity guard for silver_bcb_inflation.
--
-- The index_value chains monthly % changes with
--   exp(sum(log(1 + pct/100)) over (partition by series order by date))
-- which assumes a CONTIGUOUS monthly series. A gap (a missing month) makes the
-- window treat two non-adjacent months as adjacent, so the cumulative index
-- under-counts inflation from that point on — a silent, compounding error in
-- every val_real_* column downstream.
--
-- BCB SGS monthly series are normally gap-free; this fails (returns rows) if a
-- gap > 1 month ever appears between consecutive observations of a series.
with ordered as (
    select
        series_code,
        reference_date,
        lag(reference_date) over (
            partition by series_code
            order by reference_date
        ) as prev_date
    from {{ ref('silver_bcb_inflation') }}
)
select
    series_code,
    prev_date,
    reference_date,
    date_diff(reference_date, prev_date, month) as month_gap
from ordered
where prev_date is not null
  and date_diff(reference_date, prev_date, month) > 1
