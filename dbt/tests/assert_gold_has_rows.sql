-- Singular test: gold_commodity_matrix must always have rows. If it goes empty,
-- something silent broke upstream (Bronze, Silver dedup, or the seeds).
-- A dbt test "fails" when the SELECT returns ≥1 row, so we emit a single row
-- only when the table is empty.
select 1 as empty_gold
from (select count(*) as n from {{ ref('gold_commodity_matrix') }})
where n = 0
