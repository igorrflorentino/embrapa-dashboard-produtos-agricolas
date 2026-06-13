-- Pre-1994 BRL guard for gold_comtrade_flows (the global trade table whose
-- partition range starts in 1960).
--
-- The PTAX series before 1994 is denominated in the old currencies
-- (Cz$/NCz$/Cr$/CR$), so multiplying the source US$ by it produces an
-- old-currency number off by 10^3-10^9 — never a R$ value. The model therefore
-- NULLs val_yearfx_{brl,eur} and every val_real_* for reference_year < 1994
-- (same guard as the PEVS/PAM golds). Vacuous on today's 2022-2023 ingestion
-- window by design: it arms the first historical backfill, which would
-- otherwise silently publish corrupted BRL/real columns with no failing test.
--
-- Fails (returns rows) when any pre-1994 row carries a non-NULL BRL-derived value.

select
    reference_year,
    flow,
    reporter_code,
    partner_code,
    cmd_code
from {{ ref('gold_comtrade_flows') }}
where reference_year < 1994
  and (
    val_yearfx_brl is not null
    or val_yearfx_eur is not null
    or val_real_ipca_brl is not null
    or val_real_igpm_brl is not null
    or val_real_igpdi_brl is not null
    or val_real_ipca_usd is not null
    or val_real_igpm_usd is not null
    or val_real_igpdi_usd is not null
    or val_real_ipca_eur is not null
    or val_real_igpm_eur is not null
    or val_real_igpdi_eur is not null
  )
