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
- [ ] Verify dates: `dob.split('T')[0]` assumes ISO; confirm backend always returns
      that shape, and handle missing `tob`/`place` gracefully (currently raw render).
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
- [ ] Centralize the planet/rasi/nakshatra constants (duplicated across components).
- [ ] Add an ESLint/Prettier pass; CRA is fine for now but note migration to Vite
      as a future option (faster dev, smaller config).
- [ ] Add a `.env.example`-driven config check so a missing API base URL fails loudly.

## 3. Visual redesign — Refined Vedic / "Jyotisha Ledger" (P1)

Direction chosen 2026-06-27: **"Jyotisha Ledger"** — birth chart as a precise
astronomical instrument on aged manuscript. Indigo ink + antique brass + parchment;
saffron is a precise accent only (no gradients). Type: Fraunces (display) / Inter
(body) / IBM Plex Mono (astronomical data). Tokens are prefixed `--jl-*` in
`src/styles/ledger.css` so they coexist with the legacy theme during rollout.
**Birth Chart page rebuilt as the reference implementation** (see preview note below).

- [x] **Tokens:** established as `--jl-*` in `ledger.css` (ink/brass/parchment +
      saffron accent + 3 type roles). Legacy `App.css` tokens untouched for now.
- [x] **Remove the noise** (on the redesigned page): no mandala/pulse-glow/gradient
      text; one static paper-grain background. Legacy pages still have it — rolls out
      as they migrate.
- [x] **Typography:** Fraunces / Inter / IBM Plex Mono with a real scale, applied on
      Birth Chart page.
- [x] **Cards:** soft 1px parchment border, 6px radius, no heavy shadows / saffron bars
      (chart cards + table). Applied on Birth Chart page.
- [x] **North Indian chart restyle:** brass-on-parchment, solid strokes (gradient
      removed), mono glyphs, lagna in saffron. Done in `NorthIndianChart.js`.
- [ ] **Roll the `--jl-*` system + ledger layout across the other pages** (Dashboard,
      Profile Selection, Dhasa, Compatibility, Predictions, Ask Astrologer, Login/Register).
- [ ] Extract a shared `LedgerLayout` (topbar + folio) from BirthChartPage during rollout.
- [ ] **Dark mode** (token-based night-sky variant) — toggle, not default.
- [ ] Empty states, skeleton loaders (Birth Chart has a ledger loading state; others pending).
- [ ] Optional degrees toggle on the chart; consider South-Indian style toggle (§5).

> **Preview:** `frontend/ledger-preview.html` (gitignored throwaway) renders the new
> Birth Chart look with sample data — open in a browser to review the direction without
> running the full stack.

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

- [ ] **Chart style toggle: North vs South Indian** (P1). South Indian is the more
      common style for many users; engine has both.
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
