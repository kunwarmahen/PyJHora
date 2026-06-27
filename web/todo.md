# PyJHora Web — Modernization & Feature Plan

Status: planning. No app code changed yet. Direction agreed: **Refined Vedic** —
keep the spiritual/Indian-astrology identity, but calm it down (drop rotating
mandala / glow-pulse / gradient-text-everywhere), give it real typographic
hierarchy, make it mobile-first, and clean up the code.

Legend: **P0** = correctness/blocking, **P1** = high value, **P2** = nice to have.

---

## 1. Bugs & correctness (P0 — fix first)

- [x] **Timezone hardcoded to IST.** ~~`/api/astrology/birth-chart` passes `tz=5.5`~~
      FIXED 2026-06-27: birth-chart, predict, and compatibility-analysis now pass the
      profile's `timezone` (compute layer falls back to 5.5 only when it's None).
      Audited all endpoints — horoscope/doshas/yogas/dhasa/transit/ask already correct.
- [x] **Navamsa (D9) never rendered.** FIXED 2026-06-27: backend now returns D9 with
      1-based `house` + a `d9_lagna`; `NorthIndianChart` is reusable (`planets`/`lagna`/
      `title` props); Birth Chart page renders both Rasi (D1) and Navamsa (D9).
- [x] **Hover sign-name uses raw DOM `setAttribute`.** FIXED 2026-06-27: replaced with
      React `useState` (`hoveredHouse`); added tap-to-toggle for touch devices.
- [x] **Lat/Long required even after LocationSearch.** FIXED 2026-06-27: LocationSearch
      is now the source of truth; manual lat/long/timezone moved into a collapsible
      "Advanced" override and are no longer `required`. Save validates that coordinates
      exist (from search or manual override).
- [x] **Date/field robustness.** DONE 2026-06-27: added `src/utils/format.js`
      (`formatDate`, `orDash`) and routed all `dob.split('T')[0]` renders + raw
      `tob`/`place` through them across Dashboard, ProfileSelection, BirthChart,
      AskAstrologer, Compatibility (DhasaPage already had a safe local `formatDate`).
      Missing values now show "—" instead of crashing on `.split` of undefined.
- [ ] **Docker can't import PyJHora.** `backend/Dockerfile` build context is `./backend`
      and compose mounts only `./backend:/app`, but `astrology.py` imports jhora from
      `../../src` — that path doesn't exist in the container, so PyJHora fails in Docker
      (works locally only). Fix: vendor/copy `src/` into the image, pip-install PyJHora,
      or adjust the build context + mount. (Found 2026-06-27 during the 4.8.7 bump.)
- [x] **Bump PyJHora to latest (4.8.7).** DONE 2026-06-27: overlaid upstream `src/` +
      `pyproject.toml` (we had zero local `src/` edits, so no conflicts). Verified the
      backend imports it and computes Rasi/D9/dashas correctly with the right timezone.
      Updated `web/backend/requirements.txt` with the actual PyJHora runtime deps; left
      root `requirements.txt` as-is (already complete and newer than upstream's, which
      is missing pandas/Pillow/pyephem that the code still imports).
- [x] **Remove committed artifacts.** DONE 2026-06-27: deleted `backend.log` (also
      already gitignored), dead `backend/astrology_fixed.py`, and `ChartTestPage.js`
      + its `/chart-test` route/import. Stale div-based CSS in `NorthIndianChart.css`
      replaced with the SVG card styles actually in use.

## 2. Code quality / refactor (P1)

- [x] **Health endpoint 500.** FIXED 2026-06-27: `/health` read `AstrologyCompute.PYJHORA_AVAILABLE`
      but the flag was module-level only → AttributeError → 500. Exposed it as a class
      attribute. Verified `/health` now returns 200 with `pyjhora_available: true`.
- [~] **Kill inline styles.** DONE for `BirthChartPage.js` + `NorthIndianChart.js`
      (rebuilt on `ledger.css`, zero inline styles). Remaining: the other pages still
      use inline styles / legacy CSS — addressed during the §3 rollout.
- [ ] **Shared `<AppLayout>` / `<Navbar>` / `<ProfileBanner>`.** These are copy-pasted
      across Dashboard, BirthChart, Dhasa, Compatibility, etc. Extract once.
- [ ] **Shared primitives:** `<Card>`, `<Button>`, `<PageHeader>`, `<DataField>`,
      `<LoadingState>`, `<ErrorBanner>` to replace the repeated ad-hoc blocks.
- [x] Centralize the planet/rasi constants — `src/constants/jyotish.js` (PLANET_ABBR,
      RASI_NAMES, RASI_ABBR); used by both chart components. (2026-06-27)
- [ ] Add an ESLint/Prettier pass; CRA is fine for now but note migration to Vite
      as a future option (faster dev, smaller config).
- [ ] Add a `.env.example`-driven config check so a missing API base URL fails loudly.

## 3. Visual redesign (P1) — REVERTED, keep the original look

**Decision 2026-06-27:** the "Jyotisha Ledger" redesign (indigo/brass/parchment, then a
warm-saffron variant) was built on the Birth Chart page + Dashboard, but the owner
preferred the **original saffron/cream Vedic design** (the look still on the Dasha,
Compatibility, etc. pages). Reverted Dashboard + Birth Chart to the original; deleted
the ledger design system (`ledger.css`, `LedgerLayout.js`, `GrahaTable.js`, preview HTML).

**Kept from the effort (functional, look-agnostic):**
- Timezone bug fix, /health fix, PyJHora 4.8.7, backend requirements (all backend).
- Navamsa (D9) chart now rendered alongside Rasi on Birth Chart — in the original style.
- `NorthIndianChart` is reusable (props for D9) with React-state hover (no raw DOM);
  colors reverted to the original saffron/indigo.
- Profile form: LocationSearch is source of truth, lat/long/tz an optional override.
- Dead code removed (ChartTestPage, astrology_fixed.py).

**If the design is revisited later:** the original `App.css` token system is the basis;
do incremental cleanups (kill inline styles, shared navbar) WITHOUT changing the visual
identity. Don't reintroduce a wholesale new theme unless the owner asks.

> Lesson learned: the owner likes the existing saffron/cream Vedic identity — modernize
> by cleaning it up, not replacing it.

## 4. Mobile / responsive (P1)

- [ ] Audit every page at 360px / 768px. The SVG chart (fixed 600px viewBox) needs
      to scale and stay legible; planet labels currently crowd on small screens.
- [ ] Hamburger/drawer nav instead of the desktop navbar on phones.
- [ ] Profile cards, feature grid, and the two-column forms need single-column
      reflow + larger tap targets (edit/delete buttons are 16px icons — too small).
- [ ] Make the AI chat (`AskAstrologerPage`) usable on mobile (sticky input, scroll).
- [ ] Add `<meta viewport>` + test; PWA/installable as a stretch goal.

## 5. New features (P1/P2) — grounded in what the PyJHora engine already supports

The engine (`src/jhora/...`, see `features_per_book.txt`) supports far more than the
web exposes. High-value additions:

- [x] **Chart style toggle: North vs South Indian** (P1). DONE 2026-06-27: new
      `SouthIndianChart.js` (fixed-sign 4x4 grid); toggle on Birth Chart page switches
      both Rasi + Navamsa, preference saved to localStorage. Lagna cell marked with a
      saffron corner. Reuses the same data (planet `house` = sign number).
- [ ] **Divisional charts D1–D60** (P1): at minimum D9 (Navamsa), D10 (Dasamsa,
      career), D7, D12, D24 with a varga picker.
- [ ] **Panchanga / daily almanac** (P1): tithi, nakshatra, yoga, karana, vaara,
      sunrise/sunset, rahu kalam — a "today" panel.
- [ ] **Vimsottari Dasa with drill-down** (P1): the Dhasa page exists; add nested
      Dasa→Bhukti→Antara→Sookshma tree with current-period highlighting.
- [ ] **More dasha systems** (P2): Ashtottari, Narayana, Kalachakra, Yogini, etc.
      (engine has ~10 under `dhasa/`).
- [ ] **Ashtakavarga** (P2): Bhinna + Sarva tables/heatmap.
- [ ] **Yogas & Doshas surfaced as cards** (P1): backend already has `/doshas`,
      `/yogas`; present them with plain-language explanations (Manglik, Kaal Sarp…).
- [ ] **Arudha Padas, Karakas, Special Lagnas, Upagrahas** (P2): engine supports;
      add to an "advanced" chart details section.
- [ ] **Transits / Gochara** (P1): backend `/transit` exists; add a current-transits
      view over the natal chart + key upcoming transits.
- [ ] **Strength tables** (P2): Shadbala / planetary & rasi strength.
- [ ] **Export / share** (P1): download chart as PNG/PDF, shareable read-only link.
- [ ] **Compare two profiles side by side** beyond compatibility (P2).
- [ ] **AI astrologer upgrades** (P1): stream responses, suggested prompts,
      conversation history per profile, cite which chart factors informed an answer.
- [ ] **Multi-language / Sanskrit term glossary tooltips** (P2).

## 6. Suggested execution order

1. P0 bug fixes (timezone first — it makes every other chart correct).
2. Redesign **one** page end-to-end (recommend Birth Chart) using new tokens +
   shared components, as the visual standard to approve.
3. Roll the design system + shared layout across remaining pages.
4. Mobile pass.
5. Layer in new features by priority (chart-style toggle, panchanga, D9/D10,
   yogas/doshas cards, transits, export).

## 7. Open questions for the owner

- Default chart style: North or South Indian? (engine has both)
- Is `astrology_fixed.py` the canonical compute path or dead code?
- Target devices: is this mobile-first, or desktop-primary with mobile support?
- Auth/data: stick with current JWT + Mongo, or is that out of scope for now?
- Any branding (name other than "PyJHora", logo, colors) you want for the public face?
