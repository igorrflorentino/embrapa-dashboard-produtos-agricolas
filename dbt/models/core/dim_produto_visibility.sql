{{ config(materialized='view') }}

-- ────────────────────────────────────────────────────────────────────────────
-- dim_produto_visibility — the HIDDEN-prefix registry for the Ciclo de Vida
-- visibility gate (F7).
--
-- A researcher can set a commodity's Ciclo de Vida to "Fazer Ingestão mas deixar
-- indisponível": ingest its data into Gold but HIDE the commodity from the
-- dashboard. This view emits ONLY the (source, code) of such hidden commodities
-- (the exact codigo_produto; latest-wins, active). The gate is a NOT EXISTS predicate
-- over this view (see macros/hidden_code_predicate.sql + serving/sql.visibility_clause):
-- a Gold code with NO row here stays visible — so PPM (no catalog rows) and any
-- code outside the catalog are unaffected.
--
-- Kept SEPARATE from dim_produto_catalog ON PURPOSE: the Curadoria admin editor,
-- the orphan/lifecycle readers and gold_produto_agrupamento must still see a
-- hidden-but-active row (you have to be able to edit/un-hide it). The gate only
-- touches the RESEARCHER-facing Gold reads (marts, direct-Gold readers, cross-source
-- picker). `banco` is already the short source token (pevs/pam/ppm/comex/comtrade),
-- matching the Gold tables' source — verified on prod data.
--
-- Grain: one row per hidden (source, code). Empty when nothing is hidden
-- (the no-op steady state today: all active catalog rows are "deixar disponível").
-- ────────────────────────────────────────────────────────────────────────────

with current_catalog as (

    select
        banco           as source,
        codigo_produto,
        ciclo_de_vida,
        active,
        row_number() over (
            partition by codigo_produto, banco
            order by edited_at desc, change_id desc
        ) as _rn
    from {{ source('research_inputs', 'produto_catalog_log') }}

)

select
    source,
    codigo_produto as code
from current_catalog
where _rn = 1
  and active
  and ciclo_de_vida = 'Fazer Ingestão mas deixar indisponível'
