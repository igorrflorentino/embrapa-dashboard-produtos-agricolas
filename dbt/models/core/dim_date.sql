-- ────────────────────────────────────────────────────────────────────────────
-- dim_date — conformed calendar dimension at MONTH grain.
--
-- The serving marts join this to attach localized month labels (pt-BR) and
-- quarter/semester attributes without each mart re-deriving them. Month grain is
-- deliberate: the finest fact cadence in this project is monthly (COMEX); annual
-- sources (PEVS, COMTRADE) key on `reference_year` directly and never fan out
-- against this dimension. Daily FX lives in Silver and is not a serving concern.
--
-- Grain: one row per calendar month. PK = date_month (first day of the month).
-- ────────────────────────────────────────────────────────────────────────────

with spine as (

    {{ dbt_utils.date_spine(
        datepart="month",
        start_date="cast('1970-01-01' as date)",
        end_date="cast('2051-01-01' as date)"
    ) }}

)

select
    date_month,
    extract(year  from date_month)                       as reference_year,
    extract(month from date_month)                       as reference_month,
    extract(quarter from date_month)                     as quarter,
    if(extract(month from date_month) <= 6, 1, 2)        as semester,
    last_day(date_month, month)                          as month_end_date,
    format_date('%Y-%m', date_month)                     as year_month,
    extract(month from date_month) = 12                  as is_year_end,
    case extract(month from date_month)
        when 1  then 'Janeiro'
        when 2  then 'Fevereiro'
        when 3  then 'Março'
        when 4  then 'Abril'
        when 5  then 'Maio'
        when 6  then 'Junho'
        when 7  then 'Julho'
        when 8  then 'Agosto'
        when 9  then 'Setembro'
        when 10 then 'Outubro'
        when 11 then 'Novembro'
        when 12 then 'Dezembro'
    end                                                  as month_name_pt,
    case extract(month from date_month)
        when 1  then 'Jan'
        when 2  then 'Fev'
        when 3  then 'Mar'
        when 4  then 'Abr'
        when 5  then 'Mai'
        when 6  then 'Jun'
        when 7  then 'Jul'
        when 8  then 'Ago'
        when 9  then 'Set'
        when 10 then 'Out'
        when 11 then 'Nov'
        when 12 then 'Dez'
    end                                                  as month_abbr_pt
from spine
