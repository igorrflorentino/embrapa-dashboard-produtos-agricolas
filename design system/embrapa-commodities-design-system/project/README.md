# Embrapa Commodities — Design System

A design system for the **Dashboard de Inteligência de Mercado de Commodities da Embrapa** — an internal data product built on top of [`igorrflorentino/embrapa-dashboard-commodities`](https://github.com/igorrflorentino/embrapa-dashboard-commodities). The pipeline ingests IBGE PEVS (Pesquisa da Extração Vegetal e da Silvicultura) plus BCB inflation and FX series into a single Gold table on BigQuery, surfaced through Looker Studio for decision-makers at Embrapa.

This design system describes how that dashboard, plus any supporting slides, mockups, and internal collateral, should look and feel — in line with Embrapa's institutional brand.

---

## What this product is

| | |
|---|---|
| **Owner / institution** | Embrapa — Empresa Brasileira de Pesquisa Agropecuária |
| **Ministry** | Ministério da Agricultura e Pecuária (Governo Federal do Brasil) |
| **Product** | Market-intelligence dashboard over historical extractive-vegetable production (IBGE PEVS) enriched with currency (USD, EUR, CNY) and inflation (IPCA, IGP-M, IGP-DI) corrections |
| **Audience** | Embrapa analysts and leadership; commodity-economics researchers; policy stakeholders |
| **Language** | **Portuguese (pt-BR)** — primary. Some technical terms in English are acceptable (API names, column names like `val_real_ipca_brl`). |
| **Surface** | Looker Studio (production) + supporting slide decks (Embrapa 5.0 template) + handover docs |

The medallion pipeline (`Bronze → Silver → Gold`) terminates in a single denormalized table `gold.gold_commodity_matrix`, one row per `(reference_year, state, city, product_code)`, with three monetary conventions (`val_yearfx_*`, `val_real_ipca_*`, `val_real_igpm_*`). All design decisions here should respect that data shape — and the fact that comparing across years requires the IPCA-chained columns.

---

## Sources used to build this system

| Source | What we got from it |
|---|---|
| `uploads/Guia de Identidade Visual para Aplicativos Mobile.pdf` (Embrapa, 34 pp.) | Mobile color palette, leaf-icon system, 38.2% golden-ratio rule, employee/restricted-access conventions |
| `uploads/organized_cropped_cropped.pdf` (Manual de Identidade Visual, fragments) | Logo construction (8:3 ratio, "m"-module), Univers typography rules, monochrome rules, triade/assinatura institucional rules |
| `uploads/Template Embrapa para apresentações.pptx.pdf` (Embrapa 5.0, Jan 2023, 92 slides) | Presentations palette (Yale Blue + grays), Roboto typography, 12×6 grid system, slide layout taxonomy |
| `uploads/Triade RGB Do lado do povo brasileiro.pdf` | Tríade lockup rules (Embrapa + Mapa + Gov BR), language variants |
| Logo PNGs (colorida / monocromática branca / preta — Embrapa + Tríade) | Bitmap masters at the resolutions we need for UI |
| GitHub: [`igorrflorentino/embrapa-dashboard-commodities`](https://github.com/igorrflorentino/embrapa-dashboard-commodities) | Pipeline architecture, data shape, monetary conventions (`val_yearfx_*` vs. `val_real_ipca_*`), product-code domain, geographic granularity |

> The reader is encouraged to explore the upstream repo directly — it is the source of truth for column names, data quality flags, and the IPCA chain math the dashboard surfaces.

---

## CONTENT FUNDAMENTALS

### Voice & tone

Embrapa is a **federal research institution**. Its voice is **technical, neutral, accessible, and institutional** — not corporate-cheerful, not playful, never marketing-y. The Embrapa 5.0 presentation template is grounded by the *Canção do Exílio* by Gonçalves Dias as filler — a clue that the brand wants to feel **culturally Brazilian, scientifically credible, and quietly proud**, never hyped.

Three rules govern every string we write:

1. **"Menos é mais."** This is verbatim from the Mobile guide. Less copy is always better. Tooltips, button labels, and chart titles get the shortest faithful translation of intent.
2. **Plain, formal Portuguese.** Use você sparingly; institutional documents prefer impersonal voice ("Selecione um produto" rather than "Selecione seu produto"). No abbreviations users have to decode (`Pesquisa Agropecuária`, not `Pesq. Agrop.`).
3. **Numbers are first-class.** This is a data product. Every metric should be labeled with its **unit, currency, and inflation convention** — `val_real_ipca_brl` is not "Value", it is "Valor real (IPCA) — R$".

### Casing

- **Sentence case** for headings, buttons, menu items, and chart titles. (`Filtrar por produto`, not `Filtrar Por Produto`.)
- **UPPERCASE with tracking** only for the `overline` style — small section labels above a card or chart (`PRODUÇÃO EXTRATIVA`, `DADOS BCB`).
- **Product names and acronyms** stay as authored: `IBGE`, `BCB`, `PEVS`, `IPCA`, `IGP-M`, `SIDRA`, `Looker Studio`.

### "I" vs. "you" (Eu vs. Você)

- Default: **impersonal voice.** ("Os dados são atualizados diariamente.")
- When direct address is needed (CTAs, empty states): **você**, never tu. ("Você pode filtrar por estado.")
- **Never first person.** ("Selecionamos os melhores produtos" is wrong tone.)

### Emoji & special characters

- **No emoji.** Ever. The mobile guide is explicit about iconographic restraint; emoji are out of band.
- Bullet character is `•` for unordered lists; numbered lists use `1.`, `2.`, … (matches the presentation template).
- En-dash `–` (not em-dash) for ranges (`1994–2023`); hyphen `-` for compound words.

### Specific examples (taken verbatim from sources)

| Context | Example we use | Notes |
|---|---|---|
| Mission tone | "Pipeline Medalhão para análise histórica de produção extrativa vegetal brasileira" | technical, descriptive, no flourish |
| Section heading | "Convenções monetárias do Gold" | concrete, plural noun |
| Chart label | "Valor real (IPCA) — R$" | unit + convention always disclosed |
| Empty state | "Selecione um produto para visualizar a série histórica." | impersonal, action-first |
| Footer | "© Empresa Brasileira de Pesquisa Agropecuária • Ministério da Agricultura e Pecuária" | full razão social + ministry |

### Numbers and units

- Currency: `R$ 1.234.567,89` (pt-BR locale, dot thousands, comma decimal). Foreign: `US$ 1,234.56`, `€ 1.234,56`, `¥ 1.234,56`.
- Large numbers: prefer absolute up to 6 digits, then abbreviate as `1,2 mi`, `1,2 bi` (lowercase, with non-breaking space). Never `M` / `B` (English).
- Quantity columns: `quantity_tons` → `t`; `quantity_m3` → `m³` (with the superscript 3).
- Dates: `28 jun 2023` for inline; `2023-06-28` only in data tables / debug.
- Data-quality flag values stay verbatim and English (`OK`, `MISSING_VALUE`, etc.) — they come from the Gold table.

---

## VISUAL FOUNDATIONS

### The two palettes

Embrapa runs **two coexisting palettes** and the dashboard inherits from both:

| Palette | Anchor | Where it lives | Source |
|---|---|---|---|
| **Corporate** | `#006f35` Verde Embrapa + `#06617c` Azul Embrapa | Header band, footer, brand chrome, app icons, any surface where the logo is dominant | Manual de Identidade Visual; Guia Mobile (2014) |
| **Presentations** | `#1D4D7E` Yale Blue + neutral grays | Data surfaces — charts, tables, KPI cards, dashboard inner panels | Template Embrapa 5.0 (Jan 2023) |

The **corporate palette wraps**, the **presentations palette delivers data**. That separation keeps brand presence strong without bleeding green into every chart and washing out signal.

The orange `#cc4b10` is reserved exclusively for the "Empregados / Acesso Restrito" tag — never for errors, warnings, or accents. Use `#B23A2B` terracotta for error states instead.

### Typography

- **Display + body:** Univers (the official Embrapa face) — six cuts shipped: 55 Roman, 55 Oblique, 65 Bold, 65 Bold Oblique, 75 Black, 75 Black Italic, 85 Extra Black, 85 Extra Black Italic. Loaded from `fonts/` as `@font-face`. Weight tokens: `--fw-regular: 400`, `--fw-bold: 700`, `--fw-black: 800`, `--fw-display: 900`.
- **Fallback stack** mirrors the Manual: Univers → Verdana (web fallback prescribed by the manual) → Arial (internal documents) → system. Bundled web Verdana / Arial cuts are in `fonts/` under the `Embrapa Verdana` and `Embrapa Arial` families.
- **The wordmark** is set in Univers Extra Black Italic (85). The `.brand-italic` class binds to this cut — use it for hero moments, dashboard title bar, slide covers. **Never** body.
- **Manual prescription:** "Em destaques e títulos, utilize o peso Bold e o peso Medium para textos." Univers ships in 400 + 700 (+ 800, 900 for display) here; `font-synthesis-weight: auto` produces an acceptable faux-medium (500) for overlines, button labels, and small UI text.
- **Mono:** IBM Plex Mono for numeric data, table cells, and code. The brand has no mono spec; Plex Mono is institutional-warm and works well for long commodity-value strings. Tabular numerals (`font-variant-numeric: tabular-nums`) required for any column of values.
- **Scale is tight.** Body is 15px. We prefer weight over size for hierarchy — institutional restraint.

### Spacing & layout

- **8-point baseline.** All spacing tokens are 4 → 96 px multiples of 4/8.
- **Golden ratio for hero brand moments.** The mobile guide is explicit: logo width = 38.2% of canvas width on splash screens, employee-facing app screens, and slide covers. We honor this for the Looker Studio cover and slide titles.
- **12×6 grid for slides.** Slide templates use the Embrapa 5.0 grid; the deck samples in `slides/` are built on it.
- **Generous "área de respiro"** (breathing room). The mobile guide is explicit: never let content touch margins. Default container gutter is 24px; cards have 20–24px inner padding.

### Backgrounds

- **Solid color, paper-white, or full-bleed photography.** Never gradients, never gradient meshes, never animated noise.
- Hero / cover panels use **solid `--embrapa-green`** (`#006f35`) or **solid `--embrapa-blue`** (`#06617c`). The mobile guide specifies these as the only acceptable splash-screen colors (besides white).
- For full-bleed imagery, slides use a **dark linear "máscara" gradient** over photos to lift the type — replicated in `slides/CoverPhoto.jsx`.
- No repeating patterns, textures, or hand-drawn flourishes. The leaf logo is the only ornament the brand has, and it lives in the logo, not as wallpaper.

### Imagery

- **Warm, real, agronomic.** Reference photography is field-grown crops, smallholder farmers, research-station laboratories, biome landscapes (cerrado, amazônia, pampa). Not corporate stock.
- Skin tones: **diverse, Brazilian.** Embrapa products serve all biomes.
- Saturation is **natural, not punched.** No HDR. No teal-and-orange grading.
- We do not invent imagery here — slide layouts use `<image-slot>` placeholders so the user drops in real photos.

### Animation

- **Slow and deliberate.** All transitions are 120–360ms.
- Easing: `cubic-bezier(0.2, 0, 0, 1)` (standard) for most. No spring, no bounce, no overshoot.
- **Fade + tiny translate** is the dominant entry pattern. Never scale-in from 0, never rotate-in.
- Hover/press states are **opacity and color shifts only** — no shadow lifts on small UI, no scale transforms.

### Hover / press

- **Hover** on interactive surfaces: background darkens by ~6% lightness (or `rgba(0,60,29,0.04)` overlay on neutral surfaces). Links additionally shift color toward `--embrapa-green`.
- **Press** state: background darkens by ~12%; no scale change. (We avoid the App Store "shrink-on-press" — it doesn't fit institutional product feel.)
- **Disabled**: 40% opacity, `cursor: not-allowed`.

### Borders

- **1px hairlines** everywhere. Default border color is `rgba(0, 60, 29, 0.14)` — a green-tinted neutral, never pure gray, so the brand thread is woven into the chrome.
- **2px** only for active/focused inputs (in `--embrapa-blue`).
- No double borders, no dashed/dotted borders in production UI.

### Shadow system

Four steps, all soft and low-saturation (green-shifted):

| Token | Use |
|---|---|
| `--shadow-1` | barely-there lift — input fields on hover |
| `--shadow-2` | resting card |
| `--shadow-3` | popovers, dropdowns, modals (at rest) |
| `--shadow-4` | dragged / focused modal / toast |

No inner glows, no neon, no colored shadows.

### Protection gradients vs. capsules

Two patterns for laying type over imagery:

- **Protection gradient** (preferred for slide covers): a `linear-gradient(180deg, rgba(0,60,29,0.0) 0%, rgba(0,60,29,0.85) 100%)` mask from bottom — replicated from the Embrapa 5.0 template's "máscara com degradê".
- **Capsule** (for badges and KPI highlights only): pill on `var(--embrapa-green)` with white text, `--radius-pill`, never on photos.

### Layout rules (fixed elements)

- **Header band**: 56px, solid `var(--embrapa-green)`, logo left, primary nav inline, user/utility on the right.
- **Sidebar (when used)**: 260px, `var(--bg-surface)` with hairline right border. Active item: left 3px green accent bar + medium-weight type.
- **Footer**: tríade lockup (Embrapa + Ministério + Gov.BR) center, copyright + SAC link below — matches the institutional "Sobre" template.

### Transparency & blur

- **Rarely used.** When used: a hairline overlay (`rgba(255,255,255,0.6)`) over imagery for "máscara" effects. No glass-morphism, no `backdrop-filter: blur()` in the production dashboard.
- Modals get a dim layer at `rgba(0,60,29,0.45)` — the green tint keeps things on-brand even in the darkening overlay.

### Corner radii

- Tight. UI corners stay between **4–10px**. The leaf in the logo carries all the curve identity; UI containers stay quiet.
- **`--radius-pill`** for tags, status chips, and the "Empregados" employee badge.
- Never `border-radius: 50%` except for avatars (38–40px) and the leaf icon mask itself.

### Cards

| Property | Value |
|---|---|
| Background | `var(--bg-surface)` (white) or `var(--bg-surface-2)` (warm gray) for nested |
| Border | `1px solid var(--border-default)` |
| Shadow | `var(--shadow-2)` at rest, `var(--shadow-3)` on hover (interactive cards only) |
| Radius | `var(--radius-lg)` = 10px |
| Padding | `var(--space-5)` = 24px |
| Header | `.overline` label above a `.h4` title; no icon-on-color circles |

---

## ICONOGRAPHY

The Embrapa Mobile Guide explicitly endorses **Google Material Design's system icons** as the iconography baseline for digital products. Custom Embrapa app icons follow specific rules — a leaf-shaped external mask, monochrome figures, 45° diagonal lines, no light/shadow — but those rules are for *app store icons*, not in-product UI icons.

For this dashboard:

- **In-UI icons**: [Material Symbols](https://fonts.google.com/icons) (Outlined style, weight 400). Loaded from CDN. This is the most faithful "what the brand told us to use" choice we can make without hand-rolling SVGs. We have **flagged this as a CDN substitution** since the source repo has no production icon font.
- **Brand chrome**: the Embrapa wordmark + leaf is treated as a *logo*, not an icon. It sits in the header at 36px tall (mobile guide minimum on screen) and in the footer at full tríade size.
- **Custom illustrations / pictograms**: none invented. The Embrapa template ships a small set of pictograms (Lavoura, Alimento, Negócio, Renda) used in tópicos-especiais slides — we mock those as placeholders for the user to provide.
- **Emoji**: never. The Embrapa visual language has no emoji.
- **Unicode glyphs as icons**: only the bullet `•`, en-dash `–`, multiplication × in dimensions, and the leaf wordmark itself. No special-character iconography elsewhere.

**Asset inventory** (under `assets/`):

```
logo-embrapa-color.png            962×478 px, transparent PNG, official colored mark
logo-embrapa-white.png            mono negative (white) for dark backgrounds
logo-embrapa-black.png            mono positive (black) for restricted printing
triade-horizontal-color.png       Embrapa + Mapa + Gov.BR — horizontal, colored
triade-horizontal-white.png       Tríade — mono negative
triade-horizontal-black.png       Tríade — mono positive
triade-vertical-color.png         Tríade — vertical orientation, colored
triade-vertical-white.png         Tríade — vertical mono negative
triade-vertical-black.png         Tríade — vertical mono positive
```

---

## Index — what's in this folder

| Path | Purpose |
|---|---|
| `README.md` | This file. The expert's brief. |
| `SKILL.md` | Agent-Skill front-matter wrapper — drop this folder into a Claude Code skills directory and it becomes invocable. |
| `colors_and_type.css` | Single CSS file with every design token. Import this in everything. |
| `assets/` | Logos and tríade lockups (PNG). |
| `extracted/` | Plain-text extractions of the source PDFs — useful when you need to re-quote brand rules. |
| `preview/` | Small HTML cards that render in the Design System review tab. |
| `ui_kits/dashboard/` | Pixel-fidelity recreation of the Looker Studio dashboard surface. Open `ui_kits/dashboard/index.html`. |
| `slides/` | Sample slides built on the Embrapa 5.0 template — title, section divider, KPI, two-up, chart, closing. Open `slides/index.html`. |
| `uploads/` | Original user-provided source materials. **Do not link from production UI** — copy out into `assets/` first. |

---

## Known caveats / things we couldn't do

- **No direct access to the live Looker Studio dashboard.** The UI kit recreates a Looker Studio-style surface from the data schema (`gold_commodity_matrix`) described in the upstream repo, not from screenshots of the production report. Confirm with the dashboard owner before treating it as pixel-faithful.
- **Custom icon set** — Embrapa has no published in-product icon font. The dashboard uses an inline-SVG icon set (stroke-based, 1.8 weight) at `ui_kits/dashboard/Icon.jsx` as a documented substitution. Documented in ICONOGRAPHY.
- **Imagery** — no source photographs were provided. All photo slots are `<image-slot>` placeholders for the user to drop in.
