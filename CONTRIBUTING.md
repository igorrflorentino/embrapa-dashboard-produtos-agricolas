# Contribuindo — Embrapa Commodities Dashboard

Obrigado por considerar contribuir com este projeto! Este guia explica como colaborar de forma eficiente e padronizada.

---

## 📋 Pré-requisitos

Antes de começar, certifique-se de ter:

- **Python 3.12.11** (via `pyenv`)
- **uv** (gerenciador de pacotes)
- **Git** com suporte a hooks
- **gcloud CLI** (para autenticação GCP)

Setup rápido:
```bash
# macOS / Linux
./setup.sh

# Windows
setup.bat
```

---

## 🌿 Fluxo de Branches

Seguimos o modelo **GitHub Flow** simplificado:

```
main (protegida)
 └── feature/nome-da-feature
 └── fix/descricao-do-bug
 └── docs/descricao-da-mudanca
 └── refactor/descricao
 └── chore/descricao
```

### Regras

1. **`main` é a branch de produção** — sempre deve estar em estado deployável.
2. **Nunca faça push direto para `main`** — sempre via Pull Request.
3. **Nomeie branches com prefixo semântico**: `feature/`, `fix/`, `docs/`, `refactor/`, `chore/`.
4. **Mantenha branches curtas** — PRs menores são revisados mais rápido.

---

## 📝 Padrão de Commits (Conventional Commits)

Utilizamos [Conventional Commits](https://www.conventionalcommits.org/) para mensagens padronizadas:

```
<tipo>[escopo opcional]: <descrição>

[corpo opcional]

[rodapé opcional]
```

### Tipos permitidos

| Tipo | Quando usar |
|---|---|
| `feat` | Nova funcionalidade |
| `fix` | Correção de bug |
| `docs` | Apenas documentação |
| `style` | Formatação (sem mudança de lógica) |
| `refactor` | Refatoração (sem mudança de comportamento) |
| `perf` | Melhoria de performance |
| `test` | Adição/correção de testes |
| `build` | Mudanças no build (pyproject.toml, Dockerfile, etc.) |
| `ci` | Mudanças no CI/CD (GitHub Actions) |
| `chore` | Tarefas auxiliares (deps, configs) |

### Exemplos

```bash
feat(ibge): adicionar ingestão de dados de silvicultura
fix(bcb): corrigir parsing de datas no SGS API
docs: atualizar README com instruções de deploy
refactor(core): extrair SourceTransientError para módulo compartilhado
test(pipeline): adicionar testes para delta ingestion
ci: adicionar step de SQLFluff no workflow
chore(deps): atualizar dbt-core para 1.9
```

### Escopos comuns

`ibge`, `bcb`, `core`, `gcp`, `dbt`, `cli`, `doctor`, `backup`, `monitor`, `config`, `ci`, `deps`, `docs`

Esta lista é aberta — adicione novos escopos quando criar um módulo ou fonte nova (ex.: `comex`, `comtrade`, `nfe`).

---

## 🔄 Fluxo de Pull Request

### 1. Crie a branch

```bash
git checkout main
git pull origin main
git checkout -b feature/minha-feature
```

### 2. Desenvolva

```bash
# Instale hooks de pré-commit (uma vez)
make precommit-install

# Rode lint e testes antes de commitar
make lint
make test

# Para mudanças no dbt
make dbt-build    # sempre dev primeiro!
make dbt-test
```

### 3. Abra o PR

- **Título**: siga o padrão de Conventional Commits (ex.: `feat(ibge): adicionar nova série temporal de PEVS`)
- **Descrição**: explique O QUE mudou e POR QUÊ
- **Checklist**:
  - [ ] `make lint` passa sem erros
  - [ ] `make test` passa sem erros
  - [ ] Testes novos foram adicionados (se aplicável)
  - [ ] Documentação foi atualizada (se aplicável)
  - [ ] Mudanças no dbt foram validadas com `make dbt-build` (dev)

### 4. Code Review

- O CI (GitHub Actions) deve passar: **`Lint, test, dbt parse`**.
- A branch deve estar **atualizada com `main`** antes do merge (branch protection exige isso).
- Aprovações de review são recomendadas mas não obrigatórias pela branch protection atual.
- Use **Squash and Merge** para manter o histórico limpo.

---

## 🛠️ Desenvolvimento Local

### Comandos mais usados

Referência completa em [`CLAUDE.md` → Commands](CLAUDE.md#commands). Os mais frequentes:

```bash
make lint               # Ruff check + format
make test               # pytest (sem credenciais GCP)
make dbt-build          # Transformações dev
make ingest-all         # Ingestão Bronze de todas as fontes em cli.INGESTS
```

### Qualidade de código

Regras de estilo (Ruff, SQLFluff, pre-commit) estão documentadas em [`CLAUDE.md` → Code Style](CLAUDE.md#code-style).

### Testes

Referência completa de comandos de teste em [`CLAUDE.md` → Commands](CLAUDE.md#commands). Resumo:

```bash
make test                                            # toda a suíte (sem GCP)
uv run pytest tests/test_ibge_client.py::test_name   # teste específico
```

### Mudanças no dbt

1. **Sempre itere em dev**: `make dbt-build` (escreve em `dbt_dev_silver`, `dbt_dev_gold`)
2. **Valide com testes**: `make dbt-test`
3. **Só rode prod após validação**: `make dbt-build-prod-with-backup`
4. Use `--full-refresh` após mudanças de schema

---

## 📁 Onde colocar cada coisa

| Tipo de mudança | Local |
|---|---|
| **Adicionar uma nova fonte de dados** | Siga o checklist em [`docs/adding_a_data_source.md`](docs/adding_a_data_source.md) |
| Novo pipeline de ingestão | `src/embrapa_commodities/<fonte>/` |
| Primitivos compartilhados entre fontes | `src/embrapa_commodities/core/` |
| Novo modelo dbt | `dbt/models/<camada>/` (Gold é por fonte: `gold_<fonte>_*`) |
| Novo macro dbt | `dbt/macros/` |
| Testes Python | `tests/` |
| Scripts auxiliares | `scripts/` |
| Documentação técnica | `docs/` |
| Feature plans detalhados | `PLANS/` |

---

## ⚠️ Regras Importantes

1. **Nunca commite credenciais** — `.gitignore` cobre `.env`, `sa-*.json`, `sa-*.b64`.
2. **Nunca commite `dbt/profiles.yml`** — use o template `profiles.yml.example`.
3. **Sem hardcode** — tudo via `.env` e `config.py`.
4. **Sempre adicione testes** para nova lógica de negócio.
5. **Docstrings em português** — comentários técnicos podem ser em inglês.

---

## 📄 Licença

Ao contribuir, você concorda que suas contribuições serão licenciadas sob a [Apache License 2.0](LICENSE).
