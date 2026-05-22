"""/sobre-api — Documentação do pipeline e do BigQuery."""

from __future__ import annotations

from dash import html

from embrapa_commodities.dashboard.components.section_header import section_header
from embrapa_commodities.dashboard.data import GoldStore

PREFIX = "sobre_api"


def _code_block(text: str) -> html.Pre:
    return html.Pre(
        text,
        style={
            "background": "#1a1f1c",
            "color": "#e6e6e6",
            "fontFamily": "IBM Plex Mono, monospace",
            "fontSize": "12.5px",
            "lineHeight": "1.55",
            "padding": "14px 16px",
            "borderRadius": "var(--radius-sm)",
            "overflowX": "auto",
            "whiteSpace": "pre",
        },
    )


def layout(store: GoldStore) -> html.Div:
    return html.Div(
        className="screen",
        children=[
            html.Div(
                className="page-hero",
                children=html.Div(
                    children=[
                        html.Div("Referência", className="overline"),
                        html.H1("Sobre a API", className="page-title"),
                        html.P(
                            "Como o pipeline funciona, onde os dados ficam, e "
                            "como consultar o BigQuery diretamente fora deste "
                            "dashboard. Apropriado para analistas e pesquisadores "
                            "que precisem cruzar com outras bases.",
                            className="page-sub",
                        ),
                    ]
                ),
            ),
            html.Div(
                className="card",
                children=[
                    section_header(
                        overline="Arquitetura",
                        title="Pipeline Bronze → Silver → Gold (Medalhão)",
                    ),
                    html.P(
                        "O dashboard não consulta as APIs do IBGE/BCB em tempo "
                        "real. A coleta, transformação e enriquecimento são "
                        "executadas em batch e materializadas no BigQuery. O "
                        "Dash apenas lê a tabela final do Gold.",
                        className="page-sub",
                    ),
                    _code_block(
                        "IBGE SIDRA  ─┐\n"
                        "BCB SGS     ─┼─►  Python (uv)         "
                        "─►  GCS Parquet (landing/)\n"
                        "             ┘                         "
                        "         │\n"
                        "                                       "
                        "         ▼\n"
                        "                  dbt-bigquery  ─►  Bronze "
                        "(STRING, append-only, partitioned)\n"
                        "                                ─►  Silver "
                        "(tipado, dedup, cadeia IPCA/IGP-M)\n"
                        "                                ─►  Gold   "
                        "(gold.gold_commodity_matrix)\n"
                        "                                       "
                        "         │\n"
                        "                                       "
                        "         ▼\n"
                        "                                  Dash on Cloud Run  ←  você está aqui"
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    section_header(
                        overline="BigQuery",
                        title="Onde a tabela vive",
                    ),
                    html.Div(
                        className="conv-grid",
                        children=[
                            _kv_card("Projeto", "embrapa-dashboard-commodities"),
                            _kv_card("Dataset", "gold"),
                            _kv_card("Tabela", "gold_commodity_matrix"),
                        ],
                    ),
                    html.Div(
                        className="conv-grid",
                        style={"marginTop": "12px"},
                        children=[
                            _kv_card("Location", "us-central1"),
                            _kv_card("Particionada por", "reference_year (int64)"),
                            _kv_card(
                                "Clusterizada por",
                                "state_acronym, product_code, city_name",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    section_header(
                        overline="Consulta direta",
                        title="Querying via BigQuery console / bq CLI / Python",
                    ),
                    html.H4(
                        "Cloud Console (interativo)",
                        style={"marginTop": "16px", "marginBottom": "8px"},
                    ),
                    html.P(
                        [
                            "Abra ",
                            html.A(
                                "console.cloud.google.com/bigquery",
                                href="https://console.cloud.google.com/bigquery?project=embrapa-dashboard-commodities",
                                target="_blank",
                            ),
                            ", autentique com sua conta, navegue até o dataset ",
                            html.Code("gold", className="mono"),
                            " e clique na tabela. A aba 'Preview' mostra "
                            "linhas; 'Query' abre o editor SQL.",
                        ],
                        className="page-sub",
                    ),
                    html.H4(
                        "bq CLI",
                        style={"marginTop": "20px", "marginBottom": "8px"},
                    ),
                    _code_block(
                        "# autenticar\n"
                        "gcloud auth application-default login\n\n"
                        "# top 10 estados em 2024 pelo valor real IPCA em BRL\n"
                        "bq query --use_legacy_sql=false \\\n"
                        "  --location=us-central1 \\\n"
                        '  "SELECT state_name, SUM(val_real_ipca_brl) AS total\n'
                        "   FROM \\`embrapa-dashboard-commodities.gold.gold_commodity_matrix\\`\n"
                        "   WHERE reference_year = 2024\n"
                        "   GROUP BY state_name\n"
                        "   ORDER BY total DESC\n"
                        '   LIMIT 10"'
                    ),
                    html.H4(
                        "Python (pandas + google-cloud-bigquery)",
                        style={"marginTop": "20px", "marginBottom": "8px"},
                    ),
                    _code_block(
                        "from google.cloud import bigquery\n\n"
                        'client = bigquery.Client(location="us-central1")\n\n'
                        'sql = """\n'
                        "  SELECT reference_year, state_acronym, product_description,\n"
                        "         SUM(val_real_ipca_brl) AS valor_real_brl\n"
                        "  FROM `embrapa-dashboard-commodities.gold.gold_commodity_matrix`\n"
                        "  WHERE reference_year BETWEEN 2015 AND 2024\n"
                        "  GROUP BY 1, 2, 3\n"
                        "  ORDER BY 1, 2, valor_real_brl DESC\n"
                        '"""\n\n'
                        "df = client.query(sql).result().to_dataframe(create_bqstorage_client=True)"
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    section_header(
                        overline="Permissões",
                        title="O que sua conta GCP precisa ter",
                    ),
                    html.Ul(
                        style={"fontSize": "13.5px", "color": "var(--fg-2)", "lineHeight": "1.7"},
                        children=[
                            html.Li(
                                [
                                    html.Code("roles/bigquery.dataViewer", className="mono"),
                                    " no dataset ",
                                    html.Code("gold", className="mono"),
                                    " (leitura de tabelas e metadados).",
                                ]
                            ),
                            html.Li(
                                [
                                    html.Code("roles/bigquery.jobUser", className="mono"),
                                    " no projeto (executar queries — sem isso o "
                                    "bq nem o cliente Python conseguem rodar SQL).",
                                ]
                            ),
                            html.Li(
                                [
                                    html.Code("roles/bigquery.readSessionUser", className="mono"),
                                    " — opcional, mas habilita a BQ Storage API "
                                    "(downloads ~10× mais rápidos via Arrow).",
                                ]
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card subtle",
                children=[
                    section_header(
                        overline="Reprodução",
                        title="Quer rodar o pipeline você mesmo?",
                    ),
                    html.P(
                        [
                            "Todo o código de ingestão, transformação dbt e "
                            "deploy do dashboard está no repositório ",
                            html.A(
                                "igorrflorentino/embrapa-dashboard-commodities",
                                href="https://github.com/igorrflorentino/embrapa-dashboard-commodities",
                                target="_blank",
                            ),
                            ". Veja ",
                            html.Code("docs/ownership_transfer.md", className="mono"),
                            " para o passo-a-passo de reprovisionar a "
                            "infraestrutura num novo projeto GCP — todo o "
                            "estado fica em variáveis de ambiente, nada hardcoded.",
                        ],
                        className="page-sub",
                    ),
                ],
            ),
        ],
    )


def _kv_card(label: str, value: str) -> html.Div:
    return html.Div(
        className="conv",
        children=[
            html.Div(label, className="overline", style={"marginBottom": "6px"}),
            html.Div(
                value,
                style={
                    "fontFamily": "IBM Plex Mono, monospace",
                    "fontSize": "13.5px",
                    "color": "var(--fg-1)",
                    "wordBreak": "break-word",
                },
            ),
        ],
    )


def register_callbacks(dash_app, store: GoldStore) -> None:
    """Static page — no callbacks."""
    return None


__all__ = ["PREFIX", "layout", "register_callbacks"]
