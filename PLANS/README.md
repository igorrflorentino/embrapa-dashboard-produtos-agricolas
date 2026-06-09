# PLANS/

Directory for storing detailed plans of complex features.

Each `.md` file in this directory should contain the complete technical scope of a feature that takes more than one work session.

## Suggested format

```markdown
# Feature Title

## Context
Why this feature is needed.

## Scope
What is included and excluded.

## Technical Design
Architecture decisions, data flow, interfaces.

## Tasks
- [ ] Task 1
- [ ] Task 2

## Risks & Mitigations
Possible problems and how to resolve them.

## Acceptance Criteria
How to know the feature is done.
```

## Existing plans

| File | Feature | Status |
|---|---|---|
| `raw_zone_architecture.md` | Two-phase raw zone (extract→raw→bronze) | Implemented |
| `comex_flows.md` | COMEX source (bulk MDIC CSV) → `gold_comex_flows` | Implemented |
| `comtrade_flows.md` | UN Comtrade source (keyed API) → `gold_comtrade_flows` | Implemented |

> Create new plans with descriptive names: `scheduler-pipeline.md`, `api-rest-publica.md`, `novas-fontes-conab.md`, etc.
