{#-
    IBGE PAM/PPM 1985 reform-boundary source correction.

    IBGE labels the 1985 PAM + PPM monetary value (variable 215) "Mil Cruzeiros" — the SAME label
    as 1984 — but its MAGNITUDE is ~1000x too small: it behaves as if already denominated in Mil
    Cruzados (the 1986-02-28 Cruzado reform unit; 1 Cz$ = 1000 Cr$). Confirmed on live prod
    (2026-06-27): the deflated value + implied price collapse ~1000x at 1985 ONLY, in BOTH PAM and
    PPM, while QUANTITY is normal, and multiplying 1985 by 1000 lands it EXACTLY on the 1984 + 1986
    trend. The currency seed (historical_currency_factors) correctly matches the "Mil Cruzeiros"
    label, so this is an IBGE SOURCE mis-denomination (a likely post-reform restatement of the 1985
    surveys in Cruzados), NOT a seed bug.

    Returns the multiplier to apply ON TOP of the seed factor: 1000 for a 1985 "Mil Cruzeiros" value
    row, else 1. Scoped to the exact (year, label) so it self-disables the moment IBGE restates or
    relabels the value, and it is wired ONLY into silver_ibge_pam + silver_ibge_ppm. PEVS is
    intentionally NOT corrected — it has no 1985 monetary rows exhibiting this artifact. Regression-
    guarded by dbt/tests/assert_pam_ppm_1985_value_not_cliffed.sql.
-#}
{% macro ibge_1985_cruzado_correction(year_col, unit_col) -%}
    case
        when {{ year_col }} = 1985 and lower(trim({{ unit_col }})) = 'mil cruzeiros' then 1000
        else 1
    end
{%- endmacro %}
