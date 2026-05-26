# Política de Segurança

## Versões Suportadas

| Versão | Suporte |
|---|---|
| 0.1.x | ✅ Suporte ativo |

---

## Reportando Vulnerabilidades

Se você descobrir uma vulnerabilidade de segurança neste projeto, **não abra uma issue pública**.

### Canal privado

Envie um email para: **igorlopesc@gmail.com**

<!-- Alternativa: se o repositório tiver GitHub Security Advisories habilitado:
Use o recurso [Security Advisories](https://github.com/igorrflorentino/embrapa-dashboard-commodities/security/advisories/new) do GitHub para reportar de forma privada.
-->

### O que incluir no reporte

- Descrição da vulnerabilidade
- Passos para reproduzir
- Impacto potencial
- Versão afetada
- Sugestão de correção (se houver)

### Tempo de resposta

| Etapa | Prazo |
|---|---|
| Confirmação de recebimento | 48 horas |
| Avaliação inicial | 7 dias |
| Correção (se confirmado) | 30 dias |

Vulnerabilidades críticas que afetam dados em produção serão priorizadas.

---

## Práticas de Segurança do Projeto

Resumo das práticas implementadas. Detalhes técnicos completos em [`ARCHITECTURE.md` → Segurança e Autenticação](ARCHITECTURE.md#segurança-e-autenticação) e [`docs/iam_setup.md`](docs/iam_setup.md).

- **Autenticação**: Service Account Impersonation (OAuth 2.0) — nenhum keyfile JSON distribuído. Detalhes em [`docs/architecture.md`](docs/architecture.md).
- **Proteção de credenciais**: gitleaks no pre-commit, `.gitignore` abrangente, variáveis sensíveis filtradas nos logs.
- **Infraestrutura**: Cloud Run com IAM obrigatório, 4 Service Accounts com roles mínimas, budget alerts.
- **Dependências**: lockfile determinístico (`uv.lock`), `--frozen` no CI, separação dev/runtime.

---

## Escopo

Esta política cobre:
- O código-fonte deste repositório
- As configurações de infraestrutura GCP descritas na documentação
- Os workflows de CI/CD (GitHub Actions)

**Fora de escopo:**
- Vulnerabilidades em dependências upstream (reporte ao projeto upstream)
- Vulnerabilidades nos serviços GCP em si (reporte ao Google)
- Configurações específicas de ambientes individuais de desenvolvedores

---

## Agradecimentos

Agradecemos a todos que ajudam a manter este projeto seguro. Contribuidores que reportarem vulnerabilidades válidas serão reconhecidos (com permissão) no CHANGELOG.
