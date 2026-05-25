---
name: embrapa-commodities-design
description: Use this skill to generate well-branded interfaces and assets for Embrapa's Commodities Market-Intelligence Dashboard (and adjacent internal collateral), either for production or throwaway prototypes / mocks / slides. Contains essential design guidelines, colors, typography, fonts, brand assets, and UI-kit components for prototyping. Brazilian Portuguese (pt-BR) is the default UI language.
user-invocable: true
---

# Embrapa Commodities — design skill

Read the **README.md** in this skill folder first — it contains the brand foundations, content rules, visual foundations, and iconography guidance. Then explore:

- `colors_and_type.css` — every design token. Import this into any HTML artifact you generate.
- `assets/` — Embrapa logo + Tríade lockup PNGs. Always copy these out into your artifact rather than referencing across folders.
- `ui_kits/dashboard/` — pixel-fidelity recreation of the Looker-Studio-style commodities dashboard. Includes well-factored React components (Atoms, Charts, DataTable, FilterBar, AppShell, Overview, Screens) you can lift wholesale.
- `slides/` — 6-slide sample deck on the Embrapa 5.0 template (cover · transition · bullets · numbered topics · KPI+chart · closing).
- `preview/` — small specimens of every token (colors, type, spacing, components, brand). Use these to verify a generated artifact matches the system.
- `extracted/` — plain-text extractions of the source Embrapa brand PDFs, in case you need to re-quote a specific rule.

## What to do when invoked

If you are creating **visual artifacts** (slides, mocks, throwaway prototypes, screenshots, deck exports), copy the assets you need out of `assets/` into your project and produce static HTML files for the user to view. Always link `colors_and_type.css` and start from the tokens defined there.

If you are working on **production code**, you can copy assets and read the rules here to become an expert in designing with this brand. The dashboard UI-kit components are intentionally cosmetic — port their visual shape into your real components rather than copying them verbatim.

## Rules you must respect

1. **Two palettes coexist.** Corporate (Verde Embrapa + Azul Embrapa) wraps; Presentations (Yale Blue + neutral grays) delivers data inside the wrap. Never paint charts in `#006f35` — that's the chrome.
2. **Orange `#cc4b10` is reserved for the "Empregados / Acesso Restrito" tag.** Use `#B23A2B` terracotta for error states.
3. **"Menos é mais."** Less copy, tighter scale (body 15px), prefer weight over size for hierarchy.
4. **Numbers are first-class.** Every metric labels its unit, currency, and inflation convention (`val_real_ipca_brl`, not "value"). Use `font-variant-numeric: tabular-nums` for any column of figures.
5. **Portuguese (pt-BR), impersonal voice.** No emoji. Sentence case. `R$ 1.234,56` formatting.
6. **The Tríade lockup (Embrapa + MAPA + Gov.BR) appears in the footer** of any institutional-facing surface.
7. **Roboto Flex** is the system font — drop Univers `.woff2` into `fonts/` and swap the stack if you have a license.

## When the user invokes this skill without guidance

Ask what they want to build. If they're not sure, suggest:
- A new dashboard view or section
- A slide deck for a stakeholder update
- A handover document or one-pager
- A printable executive summary
- A landing page for the data product

Then ask the questions in the design-system prompt: target audience, surface (Looker / slide / print / HTML), portuguese tone formal vs. accessible, variations they want.

Act as an expert designer who outputs HTML artifacts **or** production code, depending on the need. Always cite where in this skill folder the rules came from — it builds the user's trust in the system.
