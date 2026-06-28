# PyJHora Web — Modernization & Feature Plan

Status: planning. No app code changed yet. Direction agreed: **Refined Vedic** —
keep the spiritual/Indian-astrology identity, but calm it down (drop rotating
mandala / glow-pulse / gradient-text-everywhere), give it real typographic
hierarchy, make it mobile-first, and clean up the code.

Legend: **P0** = correctness/blocking, **P1** = high value, **P2** = nice to have.

---

## 1. Bugs & correctness (P0 — fix first)

- [x] **Wrong ayanamsa (planets one house off vs JHora).** FIXED 2026-06-27 (default set
      to `LAHIRI`), REVISED 2026-06-28: the real JHora default is **True Chitra Paksha**
      ("Spica in middle of Chitra always" = swe `TRUE_CITRA`), not traditional Lahiri.
      PyJHora defaults to `TRUE_PUSHYA`. Backend + frontend defaults are now `TRUE_CITRA`,
      which matches a verified JHora chart to ~0.02 arc-min on every body. Traditional
      Lahiri differs by only ~1', but that flips a body sitting on a navamsa/varga cusp
      (e.g. this chart's Sun at Taurus ~20°00' → Gemini vs Cancer navamsa).
- [x] **User-selectable ayanamsa.** DONE 2026-06-28: backend `calculate_birth_chart`
      takes an `ayanamsa` arg (default Lahiri) + resets after each request so endpoints
      don't leak; `GET /api/astrology/ayanamsas` lists the curated options; Birth Chart
      page has a dropdown (Lahiri/True Chitra/KP/Raman/Yukteshwar/True Pushya/Fagan),
      persisted in localStorage, refetches on change. FOLLOW-UP: thread the selected
      ayanamsa through the Dasha/Compatibility pages too (they currently use Lahiri).
- [x] **North Indian chart clutter.** FIXED 2026-06-27: crowded houses now use a
      compact one-line-per-planet layout (name + inline degree) with adaptive
      spacing/size, instead of two stacked lines that overflowed the triangles.
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
- [x] **`search_location` was a stub → LocationSearch broken.** FIXED 2026-06-28:
      `AstrologyCompute.search_location` returned `{"error": "Not implemented yet"}`,
      so `/api/location/search` (which indexes `result[0..3]`) 500'd on every query.
      Implemented it with geopy Nominatim (OpenStreetMap) for coordinates +
      timezonefinder for the UTC offset (both already PyJHora deps); returns
      `[display_name, lat, lon, tz]` or `None` (→ friendly "not found"). Verified
      Chennai/Mumbai/NYC/London/Tokyo resolve with correct tz. NOTE: tz reflects the
      place's *current* DST rules — fine for picking a location, a known limitation for
      historical births (the app stores a single tz offset anyway).
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

- [x] **Rahu/Ketu off by one house in vargas vs JHora.** FIXED 2026-06-28: PyJHora
      defaults to TRUE nodes; Jagannatha Hora defaults to MEAN. The ~1.6° true/mean gap
      is invisible in wide D1 signs but straddles a 3° Dasamsa (D10) cusp, flipping
      Rahu/Ketu one house off (slower planets unaffected). Backend now calls
      `drik.set_planet_list(set_rahu_ketu_as_true_nodes=False)` once at import to match
      JHora. (Aligns nodes everywhere, same spirit as the Lahiri ayanamsa default.)

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
- [x] **Divisional charts D1–D60** (P1). DONE 2026-06-28: backend
      `calculate_divisional_chart(varga_factor=N)` + `SUPPORTED_VARGAS` (Parashara's
      16 Shodasavarga: D1/2/3/4/7/9/10/12/16/20/24/27/30/40/45/60, each with
      code/name/significance); `POST /api/astrology/divisional-chart?varga=N&ayanamsa=X`
      and `GET /api/astrology/vargas`. Birth Chart page now has a varga picker below the
      Rasi chart (default D9); Rasi/Navamsa reuse the main birth-chart response, others
      fetch on demand. Renders through the same North/South `Kundali` component, respects
      the chart-style toggle + selected ayanamsa, choice persisted in localStorage.
- [x] **Panchanga / daily almanac** (P1). DONE 2026-06-28: backend
      `AstrologyCompute.get_panchanga(date, place, lat, lon, tz)` resolves the five
      limbs at sunrise (tithi w/ paksha, vaara, nakshatra+pada, yoga, karana — each
      with end time), plus sunrise/sunset and the day's periods (rahu kalam, yamaganda,
      gulika, abhijit muhurta, durmuhurtam). Standard Sanskrit name tables + helpers
      (`_tithi_name`, `_karana_name`, `_fmt_hours`) live in `astrology.py`; `date`
      defaults to "today" in the place's own timezone. `GET /api/astrology/panchanga`
      (query params, auth-protected). Frontend: self-contained `PanchangaPanel`
      component (own fetch, won't blank the page on failure) with a date picker,
      rendered on the Birth Chart page; styled in `Dashboard.css` in the original
      saffron/gold identity. UPDATED 2026-06-28: location toggle — "Birth place"
      (profile) vs "Current location" (browser geolocation → lat/lon, tz from
      `getTimezoneOffset`, reverse-geocoded name via BigDataCloud, graceful
      fallback). Fixed a vaara bug exposed by western longitudes: reading the
      weekday exactly at sunrise hit a float boundary that flipped to the prior
      vedic day (NYC/London showed Sat for a Sun) — now read at local noon.
- [x] **Vimsottari Dasa with drill-down** (P1). DONE 2026-06-28: the Dhasa page is now
      a nested Maha→Bhukti→Antara→Sookshma tree. Maha+Bhukti ship in the initial
      `/dhasa` payload; deeper levels lazy-load via a new `get_dasha_children`
      (`POST /api/astrology/dhasa/children?lords=Venus,Saturn`) which walks the lord-path
      from the natal chart with PyJHora's `vimsottari_immediate_children` so every level
      is recomputed at full sub-day precision (not from rounded dates). The current
      period auto-expands the whole live chain (each node opens itself when it's the
      running one, cascading the fetch down to Sookshma). Frontend rebuilt around a
      recursive `DashaNode` (level-aware label/accent/indent). Scoped the page to
      Vimsottari only — the old multi-system dropdown was misleading (`get_dashas`
      ignored `dhasa_type` and always computed Vimsottari); other systems remain the
      separate P2 below. Also fixed `getDhasa`/`getTransits` in api.js to pass
      `dhasa_type`/`current_date` as query params (they were sent in the body and
      silently ignored).
- [ ] **More dasha systems** (P2): Ashtottari, Narayana, Kalachakra, Yogini, etc.
      (engine has ~10 under `dhasa/`).
- [ ] **Ashtakavarga** (P2): Bhinna + Sarva tables/heatmap.
- [x] **Yogas & Doshas surfaced as cards** (P1). DONE 2026-06-28: both compute paths
      were stubs — implemented `get_doshas` (8 doshas, present/absent + descriptions)
      and `get_yogas` (via PyJHora `yoga.get_yoga_details`, ~34/284 present for a sample
      chart, each with name/description/benefits). Both endpoints take `ayanamsa`.
      Birth Chart page shows a Yogas card grid (golden accent, count header) and a
      Doshas card grid (present = vermillion); both refetch on ayanamsa change and
      load independently so a failure won't blank the chart.
- [ ] **Arudha Padas, Karakas, Special Lagnas, Upagrahas** (P2): engine supports;
      add to an "advanced" chart details section.
- [x] **Transits / Gochara** (P1). DONE 2026-06-28: implemented `get_transits` (was a
      stub) — current graha positions (sign/deg/nakshatra+pada/retrograde) for today or
      a chosen date, each with the house counted from the natal Lagna AND natal Moon
      (classic gochara reference), plus the next sign-ingress dates for Jupiter & Saturn
      (the headline Sade-Sati/Jupiter-transit events). Lunar-node ingresses are skipped:
      PyJHora's retrograde node-entry search returns a full ~18yr nodal cycle, not the
      next boundary, so its dates aren't trustworthy. New `TransitPage` (route `/transit`,
      dashboard card) renders transits on the natal Lagna via the shared North/South
      `Kundali`, respecting the chart-style toggle + selected ayanamsa, with a date
      picker and a graha table. `POST /api/astrology/transit` now takes `ayanamsa` and
      validates the result. NOTE: transit positions are computed at local noon for a
      stable daily snapshot.
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
