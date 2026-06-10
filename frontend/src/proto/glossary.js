// Glossário data — per-banco terms used across the dashboard.
// Each banco gets a list of terms. Terms have:
//   term  — short name (case as authored)
//   short — one-line definition (institutional voice)
//   tag   — small chip label (column/source/etc.); optional
//   cat   — category for grouping inside the banco; optional
//
// IDs match window.BANCOS in bancos.js.

const GLOSSARY = {
  ibge_pevs: {
    label: 'IBGE PEVS',
    sub:   'Produção da Extração Vegetal e da Silvicultura',
    terms: [
      { term: 'PEVS',     cat: 'Fonte',    tag: 'IBGE',  short: 'Pesquisa da Extração Vegetal e da Silvicultura — apuração anual do IBGE com quantidade produzida e valor da produção de produtos não-madeireiros e madeireiros nativos.' },
      { term: 'SIDRA',    cat: 'Fonte',    tag: 'IBGE',  short: 'Sistema IBGE de Recuperação Automática — portal de tabelas oficiais. Base do ingest Bronze do pipeline.' },
      { term: 'Castanha-do-pará', cat: 'Produto', tag: '49101', short: 'Semente de Bertholletia excelsa, principal produto extrativista da Amazônia. Unidade: toneladas.' },
      { term: 'Açaí (fruto)',     cat: 'Produto', tag: '49103', short: 'Fruto da palmeira Euterpe oleracea. Inclui açaí de várzea e plantios manejados como extrativos.' },
      { term: 'Erva-mate',        cat: 'Produto', tag: '49108', short: 'Folhas e ramos de Ilex paraguariensis para fabricação de chá e chimarrão. Concentrada no Sul.' },
      { term: 'Madeira em tora',  cat: 'Produto', tag: '49215', short: 'Toras de espécies nativas. Unidade: m³. Sujeita a controle de licenciamento ambiental.' },
      { term: 'Lenha',            cat: 'Produto', tag: '49216', short: 'Madeira para combustão direta. Unidade: m³. Principal item em volume da PEVS.' },
      { term: 'gold_pevs_production', cat: 'Coluna', tag: 'BigQuery', short: 'Tabela Gold desnormalizada. Uma linha por (ano, UF, município, código_produto). Origem de todo o dashboard.' },
      { term: 'val_yearfx_*',          cat: 'Coluna', tag: 'gold',     short: 'Valor nominal em moeda corrente convertido pelo câmbio médio do ano. Auditoria histórica — não comparar entre anos.' },
      { term: 'val_real_ipca_*',       cat: 'Coluna', tag: 'gold',     short: 'Valor projetado para hoje pela cadeia IPCA. Padrão deste dashboard para comparações inter-anuais.' },
      { term: 'val_real_igpm_*',       cat: 'Coluna', tag: 'gold',     short: 'Idem usando IGP-M. Alternativa institucional ao IPCA; maior aderência a séries de commodities.' },
      { term: 'data_quality_flag',     cat: 'Coluna', tag: 'gold',     short: 'Flag por linha: OK · MISSING_VALUE · MISSING_QUANTITY · ESTIMATED · BOUNDARY_HISTORIC · OUTLIER.' },
    ],
  },

  ibge_pam: {
    label: 'IBGE PAM',
    sub:   'Produção Agrícola Municipal — área, produção e rendimento das lavouras',
    terms: [
      { term: 'PAM',       cat: 'Fonte',    tag: 'IBGE',  short: 'Produção Agrícola Municipal — apuração anual do IBGE com área plantada/colhida, produção e rendimento médio das lavouras temporárias e permanentes.' },
      { term: 'Lavoura temporária', cat: 'Conceito', short: 'Cultura de ciclo curto, replantada a cada safra (soja, milho, algodão, arroz, feijão).' },
      { term: 'Lavoura permanente', cat: 'Conceito', short: 'Cultura de ciclo longo, sem replantio anual (café, cana-de-açúcar, laranja, cacau).' },
      { term: 'Soja (grão)',   cat: 'Produto', tag: '54011', short: 'Principal lavoura brasileira em área e valor. Concentrada no Centro-Oeste e Sul.' },
      { term: 'Milho (grão)',  cat: 'Produto', tag: '54012', short: 'Primeira e segunda safra (milho safrinha). Forte em MT, PR e GO.' },
      { term: 'Café (grão)',   cat: 'Produto', tag: '54013', short: 'Lavoura permanente; arábica e conilon. Concentrado em MG, ES e SP.' },
      { term: 'Área colhida',  cat: 'Coluna', short: 'Área efetivamente colhida da lavoura, em hectares (ha). Base do denominador do rendimento.' },
      { term: 'Rendimento médio', cat: 'Coluna', short: 'Produtividade da lavoura = produção ÷ área colhida, em kg/ha. Média área-ponderada (nunca somada).' },
      { term: 'gold_pam_production', cat: 'Coluna', tag: 'BigQuery', short: 'Tabela Gold. Uma linha por (ano, UF, município, lavoura), com área, produção, rendimento e valor.' },
      { term: 'data_quality_flag',     cat: 'Coluna', tag: 'gold',     short: 'Flag por linha: OK · MISSING_VALUE · MISSING_QUANTITY · ESTIMATED · BOUNDARY_HISTORIC · OUTLIER.' },
    ],
  },

  mdic_comex: {
    label: 'MDIC COMEX',
    sub:   'Comércio Exterior brasileiro — exportações e importações por UF e parceiro',
    terms: [
      { term: 'SECEX',     cat: 'Fonte',    tag: 'MDIC',  short: 'Secretaria de Comércio Exterior do MDIC — divulga as estatísticas mensais de comércio exterior brasileiro.' },
      { term: 'NCM',       cat: 'Classificação', tag: 'OMA', short: 'Nomenclatura Comum do Mercosul — código de 8 dígitos derivado do SH para classificar mercadorias em comércio exterior.' },
      { term: 'SH4 · SH6', cat: 'Classificação', tag: 'OMA', short: 'Sistema Harmonizado a 4 ou 6 dígitos. Compatível com classificações internacionais (UN Comtrade).' },
      { term: 'FOB',       cat: 'Termo',    tag: 'Incoterm', short: 'Free On Board — valor da mercadoria posta a bordo no porto de embarque, base padrão para exportação brasileira.' },
      { term: 'CIF',       cat: 'Termo',    tag: 'Incoterm', short: 'Cost, Insurance and Freight — valor da mercadoria + custos de frete e seguro até o porto de destino.' },
      { term: 'UF de origem', cat: 'Coluna', short: 'Unidade da Federação onde está estabelecido o exportador / produtor da mercadoria declarada.' },
      { term: 'Via',          cat: 'Coluna', short: 'Modalidade de transporte utilizada: marítima, aérea, rodoviária, ferroviária, fluvial, dutos.' },
      { term: 'Peso líquido', cat: 'Coluna', short: 'Peso da mercadoria sem embalagem, em quilogramas. Utilizado em cálculos de preço médio.' },
      { term: 'gold_comex_flows', cat: 'Coluna', tag: 'BigQuery', short: 'Tabela Gold. Uma linha por (ano-mês, UF, NCM, país, via, fluxo).' },
    ],
  },

  un_comtrade: {
    label: 'UN COMTRADE',
    sub:   'Estatísticas de Comércio Internacional — UN Statistics Division',
    terms: [
      { term: 'UNSD',     cat: 'Fonte',         tag: 'ONU', short: 'United Nations Statistics Division — mantém a base UN Comtrade com dados de comércio reportados pelas autoridades aduaneiras dos países.' },
      { term: 'Reporter', cat: 'Coluna',        short: 'País que está reportando a operação à UNSD.' },
      { term: 'Partner',  cat: 'Coluna',        short: 'País contraparte da operação reportada.' },
      { term: 'Flow',     cat: 'Coluna',        short: 'Direção do fluxo: export, import, re-export ou re-import.' },
      { term: 'HS6',      cat: 'Classificação', tag: 'OMA', short: 'Sistema Harmonizado a 6 dígitos — padrão internacional comum a Brasil (NCM) e ao mundo.' },
      { term: 'BEC',      cat: 'Classificação', tag: 'ONU', short: 'Broad Economic Categories — agrupamento por uso final (bens de consumo, capital, intermediários).' },
      { term: 'Mirror data', cat: 'Método',     short: 'Comparação entre o que um país declara exportar e o que o parceiro declara importar (e vice-versa). Útil para detectar sub-declaração.' },
      { term: 'gold_comtrade_flows', cat: 'Coluna', tag: 'BigQuery', short: 'Tabela Gold. Uma linha por (ano, reporter, partner, HS6, flow).' },
    ],
  },

  sefaz_nf: {
    label: 'SEFAZ NFe',
    sub:   'Fluxos de comércio interno brasileiro reconstruídos a partir de NFe',
    pending: true,
    terms: [
      { term: 'NFe',     cat: 'Documento', tag: 'SEFAZ', short: 'Nota Fiscal Eletrônica — documento fiscal autorizado pela SEFAZ que registra cada operação de circulação de mercadoria no Brasil.' },
      { term: 'CFOP',    cat: 'Classificação', tag: 'CONFAZ', short: 'Código Fiscal de Operações e Prestações — identifica a natureza da operação (venda, transferência, devolução etc).' },
      { term: 'CNAE',    cat: 'Classificação', tag: 'IBGE',   short: 'Classificação Nacional de Atividades Econômicas — identifica o setor de atividade do estabelecimento.' },
      { term: 'ICMS',    cat: 'Tributo',   tag: 'CONFAZ', short: 'Imposto sobre Circulação de Mercadorias e Serviços — base e alíquota constam na NFe.' },
      { term: 'UF origem · destino', cat: 'Coluna', short: 'Localização do remetente e do destinatário da NFe. Permite reconstruir fluxos inter-estaduais.' },
      { term: 'Município', cat: 'Coluna', short: 'IBGE 7 dígitos. Identifica origem e destino com granularidade fina.' },
      { term: 'Agregação privada', cat: 'Método', short: 'Linhas que representariam fluxos com menos de N=5 estabelecimentos são agregadas ou suprimidas para preservar sigilo fiscal.' },
      { term: 'gold_nfe_flows', cat: 'Coluna', tag: 'BigQuery', short: 'Tabela Gold planejada. Uma linha por (ano-mês, par UF/município, CFOP, NCM).' },
    ],
  },

  // ── Thematic groups (cross-cutting — not tied to a single banco) ────────
  // DRAFT: definitions to be reviewed by the team during integration/deploy.
  cross_analysis: {
    label: 'Análise cruzada',
    sub:   'Perspectivas multi-fonte — comparam séries de bancos diferentes',
    kind:  'tema',
    terms: [
      { term: 'Cruzamento entre fontes', cat: 'Perspectiva', short: 'Compara de 2 a 4 séries anuais de bancos diferentes no mesmo eixo de tempo, alternando entre base 100, eixo duplo e painéis.' },
      { term: 'Base 100',  cat: 'Método', short: 'Reindexação de cada série a 100 no ano inicial, para comparar trajetórias independentemente da unidade.' },
      { term: 'Eixo duplo', cat: 'Método', short: 'Duas unidades em eixos verticais distintos (esquerda/direita) — compara o formato das curvas, não o nível absoluto.' },
      { term: 'Coeficiente de exportação', cat: 'Perspectiva', tag: 'IBGE × MDIC', short: 'Parcela da produção de cada UF (IBGE) que segue para exportação (MDIC). Mede a orientação exportadora por estado.' },
      { term: 'Participação no mercado mundial', cat: 'Perspectiva', tag: 'MDIC × Comtrade', short: 'Exportação brasileira como fração da exportação mundial do produto (UN Comtrade).' },
      { term: 'Espelho comercial', cat: 'Perspectiva', tag: 'MDIC × Comtrade', short: 'A mesma exportação vista por MDIC, Comtrade e parceiros; a divergência ao longo do tempo é um diagnóstico de qualidade entre fontes.' },
      { term: 'Balanço da cadeia', cat: 'Perspectiva', tag: 'massa', short: 'Reconstitui o destino da produção — comércio interno (SEFAZ), exportação (MDIC) e consumo/estoque — com massa conservada, mais a fatia no mercado mundial.' },
      { term: 'Defasagem safra → embarque', cat: 'Perspectiva', tag: 'lead-lag', short: 'Quantos meses os embarques (MDIC, mensal) seguem o pico da safra (IBGE), estimado por correlação cruzada por defasagem.' },
    ],
  },

  curadoria: {
    label: 'Curadoria',
    sub:   'Enriquecimento — conhecimento do pesquisador sobre os dados',
    kind:  'tema',
    terms: [
      { term: 'Curadoria (enriquecimento)', cat: 'Conceito', short: 'Camada de anotações institucionais e compartilhadas sobre as dimensões dos bancos. Alimenta as análises curadas no modo multi-fonte.' },
      { term: 'Nível de industrialização', cat: 'Dimensão', short: 'Classificação de cada código de produto como Bruta, Processada ou Misturado. Base da análise de valor agregado.' },
      { term: 'Bruta · Processada · Misturado', cat: 'Dimensão', short: 'Produto sem transformação · produto com beneficiamento industrial · código que agrega os dois (não separável).' },
      { term: 'Finalidade econômica', cat: 'Dimensão', short: 'Finalidade atribuída ao par regime × fluxo: Consumo ou Processamento. Combinada com a direção (importação = comprar, exportação = vender), classifica cada transação.' },
      { term: 'Consumo · Processamento', cat: 'Dimensão', short: 'Os dois destinos do bem: consumo final, ou transformação/beneficiamento industrial. É a finalidade que a curadoria atribui a cada par regime × fluxo.' },
      { term: 'Par regime × fluxo', cat: 'Conceito', short: 'Unidade de classificação da finalidade econômica: um regime aduaneiro cruzado com uma direção de fluxo. Um regime ou fluxo isolado não determina o mercado — só o par.' },
      { term: 'Valor agregado', cat: 'Análise', short: 'Exportação separada entre bruta e processada, com participação do processado no tempo e prêmio de preço do processado sobre o bruto.' },
      { term: 'Rascunho → aplicado', cat: 'Operação', short: 'As edições da curadoria ficam em rascunho; "Aplicar à base" grava no log de classificação (SCD2) e o JOIN ao vivo atualiza as análises para todos os pesquisadores.' },
    ],
  },
};

window.GLOSSARY = GLOSSARY;

// Coverage lint: every visible banco should have a glossary section.
if (window.auditBancoCoverage) {
  window.auditBancoCoverage('glossário (glossary.js)', (b) => !!window.GLOSSARY[b.id]);
}
