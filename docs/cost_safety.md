# Cost Safety — Budget Alerts e Quotas no GCP

Mesmo rodando manual, **uma query mal-comportada** (loop num dashboard, full-scan
sem partition, full-refresh acidental em prod) pode gerar uma fatura inesperada
em horas. Este documento lista os 2 guard-rails de custo que precisam ser
configurados **uma vez** no Cloud Console — não são código.

---

## 1. Budget mensal com alertas (3 minutos)

1. **Cloud Console → Billing → Budgets & alerts**
2. **Create budget**:
   - Name: `embrapa-commodities-monthly`
   - Projects: selecione `embrapa-dashboard-commodities`
   - Services: deixe em branco (cobre tudo do projeto)
3. **Budget amount**:
   - Type: **Specified amount**
   - Target amount: **R$ 100/mês** (sugerido para uso acadêmico — o pipeline
     real custa centavos por execução; folga é proteção contra bug)
4. **Threshold rules** (e-mails automáticos):
   - **50%** of budget — alerta inicial
   - **90%** — preocupação séria
   - **100%** — apaga o terminal e investiga
5. **Notifications**:
   - Marque **Email alerts to billing admins and users**
   - (Opcional) Conecte um Pub/Sub topic + Cloud Function se quiser
     **kill-switch automático** que desabilita o billing quando ultrapassa
     100% — exagero para o caso acadêmico.

> Budget alerts são **avisos**, não bloqueios. Para hard limit, ver §2.

---

## 2. Custom quota: limite duro de bytes BigQuery (5 minutos)

Mesmo com BI Engine ativo, queries que escapam do cache (custom queries no
Looker, joins novos) podem escanear vários GB. Estabeleça um teto diário.

1. **Cloud Console → IAM & Admin → Quotas & System Limits**
2. Filtrar por: `bigquery.googleapis.com` + `Query usage per day per user`
3. **Edit quota**:
   - Set to: **100 GB / day** (sugerido — o build completo de Silver+Gold
     scan ~400 MB no estado atual, então 100 GB cobre ~250 builds/dia)
4. **Submit**

Ao atingir o limite, BigQuery passa a rejeitar novas queries até a meia-noite
UTC com `quotaExceeded`. **Nenhuma surpresa de fatura.**

---

## 3. (Opcional) Authorized View para readers externos

Se o dashboard for compartilhado com terceiros que **não** deveriam consumir
custos do projeto:

1. Crie um dataset `gold_readonly` num projeto separado (`embrapa-readers`).
2. **Create authorized view** apontando para `gold.gold_pevs_production`.
3. Compartilhe esse projeto separado com os readers.

Os readers consomem do projeto deles; o seu fica isolado.

---

## 4. Checagem rápida do gasto atual

```bash
gcloud billing accounts list
gcloud billing projects describe embrapa-dashboard-commodities
```

Ou pelo Console: **Billing → Reports** — gráfico de custo por SKU dos últimos
30 dias. Em condições normais o projeto deve ficar < R$ 5/mês (BigQuery
storage + BI Engine + GCS Standard ⇒ Coldline).
