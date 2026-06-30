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
- [x] **Docker can't import PyJHora.** FIXED 2026-06-28: the backend build context is now
      the **repo root** (`web/docker-compose.yml`: `context: ..`, `dockerfile:
      web/backend/Dockerfile`) so the image can vendor the PyJHora library. The Dockerfile
      `COPY src /src` lands it exactly where `astrology.py`'s `../../src` import resolves
      inside the container (`/app/../../src` → `/src`), so `from jhora...` works with zero
      code changes. Added a repo-root `.dockerignore` (excludes the ~712MB `.git`,
      node_modules, venvs, `*.log`, `.env`) to keep the context lean. VERIFIED with podman:
      image builds, container imports jhora (`PYJHORA_AVAILABLE: True`), computes a chart,
      and `/health` returns `pyjhora_available:true` (run on an isolated port against the
      host Mongo). The build also surfaced a **dependency conflict** that only bit on a
      clean install: `pymongo==4.6.0` vs `motor==3.7.1` (needs pymongo>=4.9) — bumped
      `requirements.txt` to `pymongo==4.15.4` (the version the working venv already had).
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
- [~] **Kill inline styles.** Reduced the worst offenders: the copy-pasted inline-styled
      navbars + profile banners + error blocks across BirthChart/Dhasa/Transit/
      Compatibility/Ask/Dashboard are gone (replaced by the shared components below, which
      use CSS classes in `Shared.css`). Remaining: per-page content still has inline styles
      (controls, cards) — incremental cleanup, no visual change intended.
- [x] **Shared `<PageHeader>` / `<ProfileBanner>`.** DONE 2026-06-28: extracted the
      copy-pasted navbar (back button + accent icon + title/subtitle) into
      `components/PageHeader.js` (accent variants: saffron/indigo/terracotta/gold) and the
      profile banner into `components/ProfileBanner.js` (renders nothing without a profile;
      optional `actions` slot for the Ask page's New Chat/History/Export/Keys group, and
      `onChangeProfile`/`changeIcon` for Dashboard's clear-then-navigate). Rolled across
      Dashboard, BirthChart, Dhasa, Transit, Compatibility, Ask. (No separate `<AppLayout>`/
      `<Navbar>` — `PageHeader` + the existing `.dashboard-container`/`.dashboard-content`
      cover it; Dashboard keeps its own brand+logout navbar.)
- [x] **Shared primitives.** DONE 2026-06-28: `<ErrorBanner>`, `<LoadingState>`, plus
      `<Card>`/`<Button>`/`<DataField>` (`components/*.js`, `ui-*` classes in `Shared.css`)
      in the saffron Vedic style with accent variants. Full-page spinner blocks on
      BirthChart/Transit/Dhasa/Compatibility now render `<Card><LoadingState/></Card>`;
      BirthChart's "Chart Details" rebuilt as `<Card>` + `<DataField>` grid (~140 inline-
      style lines removed) as the exemplar. `<Button>` is available but not yet adopted
      everywhere. Remaining: route the rest of the per-page loading/content blocks through
      these (incremental).
- [x] Centralize the planet/rasi constants — `src/constants/jyotish.js` (PLANET_ABBR,
      RASI_NAMES, RASI_ABBR); used by both chart components. (2026-06-27)
- [x] Add an ESLint/Prettier pass. DONE 2026-06-28: added `prettier` (devDep) +
      `.prettierrc`/`.prettierignore`, `lint`/`format`/`format:check` npm scripts, and ran
      prettier over all of `src/` (also cleared a pre-existing `no-useless-concat`). CI=true
      build (warnings-as-errors) passes. Vite migration still noted as a future option.
- [x] Add a `.env.example`-driven config check so a missing API base URL fails loudly.
      DONE 2026-06-28: `api.js` throws at startup in production builds when
      `REACT_APP_API_URL` is unset (was a silent localhost fallback → confusing CORS
      errors); warns in dev. Documented both vars in `web/frontend/.env.example`.

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

## 4. Mobile / responsive (P1) — DONE 2026-06-28

- [x] **Audit + SVG charts.** The chart SVGs already scale (`viewBox` + `width:100%` +
      `max-width:600px; height:auto`), so labels scale proportionally and stay legible.
      `<meta viewport>` was already present. Added a global `Responsive.css` (loaded last)
      so stray wide elements (`img/svg/table`) can't cause horizontal scroll.
- [x] **Hamburger/drawer nav.** New `components/NavDrawer.js` (+ `NavDrawer.css`): a
      slide-in drawer with links to every feature (Dashboard/Birth Chart/Dhasa/Transit/
      Advanced/Compatibility/Ask) + Change Chart + Logout. The hamburger shows only on
      ≤768px (desktop still navigates via dashboard cards); wired into `PageHeader`
      (every inner page) and the Dashboard navbar. (The app has no link-heavy desktop
      navbar to "collapse", so the drawer is an *additive* mobile convenience.)
- [x] **Single-column reflow + tap targets.** Feature grid / cards / forms already use
      `auto-fit` + the existing 768px queries (single-column, profile-banner stacks).
      Added: edit/delete icon buttons → 44px touch targets; form inputs/selects → 16px
      font (stops iOS focus-zoom) + 44px min-height; per-chart controls stack full-width;
      display headings tuned down.
- [x] **AI chat on mobile.** `.chat-main` becomes a `72vh` panel so messages scroll
      internally and the input stays reachable; chat input is 16px; input bar respects the
      iOS home-indicator safe area; messages go full-width on very small screens.
- [x] `<meta viewport>` already present. **PWA/installable DONE 2026-06-28**: added
      `public/manifest.json` (standalone, saffron theme), generated saffron app icons
      (192/512 + maskable + apple-touch), linked them + theme-color/apple meta in
      `index.html`, and a conservative `public/sw.js` (network-first navigations, SWR for
      static assets, **never caches `/api`**) registered in `index.js` for production builds.

## 5. New features (P1/P2) — grounded in what the PyJHora engine already supports

The engine (`src/jhora/...`, see `features_per_book.txt`) supports far more than the
web exposes. High-value additions:

- [x] **Chart style toggle: North vs South Indian** (P1). DONE 2026-06-27: new
      `SouthIndianChart.js` (fixed-sign 4x4 grid); toggle on Birth Chart page switches
      both Rasi + Navamsa, preference saved to localStorage. Lagna cell marked with a
      saffron corner. Reuses the same data (planet `house` = sign number).
- [x] **North/South chart visual parity** (P2). DONE 2026-06-29: North diamond now
      drawn at `size=580` inside the 600 viewBox (was 480 — 60px of dead padding made
      it render smaller than the South grid); South grid `max-width` 560→580 so both
      render at the same ~580px. North houses gained an always-on rāśi abbreviation in
      the header line (expands to the full sign name on hover), matching the South
      cells. Typography unified (planets ~13px/700, degrees ~10px in `--text-secondary`,
      lagna saffron). Crowded-house handling brought to parity: North uses graduated
      sizing (≤3 / 4–5 / 6+ planets) with degree floored at 8px; South gains a
      `si-crowded` class (4+ items) that tightens type + spacing to stay inside the cell.
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
- [x] **More dasha systems** (P2). DONE 2026-06-28: `get_dasha_periods` + `SUPPORTED_DASHAS`
      add Ashtottari, Yogini (graha) and Narayana, Kalachakra (raasi), normalized to a flat
      maha-period list (graha lords vs rasi signs) with ISO start/end dates. Endpoints
      `GET /dasha-systems`, `POST /dasha-periods`. DhasaPage gained an "Other Dasha Systems"
      picker + period table (current period highlighted). (Engine has more under `dhasa/` if
      we want to expand the list.)
- [x] **Ashtakavarga** (P2). DONE 2026-06-28: `get_ashtakavarga` returns Bhinna (8×12) +
      Sarva (12, total 337). `POST /ashtakavarga`. Shown on the new Advanced page as a SAV
      heatmap row + BAV table.
- [x] **Yogas & Doshas surfaced as cards** (P1). DONE 2026-06-28: both compute paths
      were stubs — implemented `get_doshas` (8 doshas, present/absent + descriptions)
      and `get_yogas` (via PyJHora `yoga.get_yoga_details`, ~34/284 present for a sample
      chart, each with name/description/benefits). Both endpoints take `ayanamsa`.
      Birth Chart page shows a Yogas card grid (golden accent, count header) and a
      Doshas card grid (present = vermillion); both refetch on ayanamsa change and
      load independently so a failure won't blank the chart.
- [x] **Arudha Padas, Karakas, Special Lagnas, Upagrahas** (P2). DONE 2026-06-28:
      `get_chart_details` returns Arudha padas (A1..A12, AL/UL labelled), Chara karakas
      (8, Jaimini), Special lagnas (Sree/Indu/Bhrigu Bindu/Pranapada/Kunda) and Upagrahas
      (Gulika/Maandi + the 5 solar: Dhuma/Vyatipata/Parivesha/Indrachapa/Upaketu).
      `POST /chart-details`. Rendered as DataField grids in the Advanced page's "Chart
      Factors" card.
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
      validates the result.
  - **Live "now" anchoring** (DONE 2026-06-29): the default snapshot now uses the
    *viewer's* current wall-clock and timezone instead of birthplace noon. Fixed two
    bugs: (1) the frontend "today" default used `toISOString()` (UTC), rolling over to
    tomorrow for users west of UTC — now uses local calendar fields; (2) the backend
    hardcoded `swe.julday(..., 12.0)` against the birth `Place`, so the Moon (~0.5°/hr)
    was placed at birthplace noon rather than the present instant. The endpoint now
    accepts `current_time` + `current_tz`; `get_transits` builds a separate
    `transit_place` carrying the viewer's tz and computes the JD at the actual time
    (falls back to local-noon + birth tz when absent, so older callers are unaffected).
    Response includes `transit_time`; the page shows an "As of {date}, {time}" badge.
  - **Time-travel steppers** (DONE 2026-06-29): the page now tracks the full transit
    *moment* (epoch ms, default = now) instead of just a date. Added a time input plus
    ±1 steppers for minute / hour / day / year (DST- and rollover-aware via the JS
    `Date` setters) and a "Now" reset. Every refresh sends the chosen `current_time` +
    DST-correct `current_tz`, so nudging by an hour visibly moves the Moon.
- [x] **Strength tables** (P2). DONE 2026-06-28: `get_shadbala` returns the six-fold
      strength (sthana/kaala/dig/cheshta/naisargika/drik) plus total rupa, required rupa,
      ratio and rank for Sun..Saturn. `POST /shadbala`. Shown as a table in the Advanced
      page (ratio ≥ 1.0 highlighted). (Rasi-strength not included yet.)
- [x] **Export / share** (P1). DONE 2026-06-28:
      - **Export**: `utils/exportChart.js` rasterizes a chart to PNG (SVG charts are
        serialized with computed styles inlined so `var(--…)` paints resolve; the South
        Indian DOM-grid falls back to html2canvas) and to PDF (jsPDF). Both libs are
        dynamically imported so they stay out of the main bundle (separate chunks).
        `ChartExportButtons` (PNG/PDF) shows via an `exportable` prop on the North/South
        chart components — enabled on Birth Chart (Rasi + varga), Compare, Transit, and
        the shared view.
      - **Share**: `shares.py` (`shared_charts` collection) + `POST /api/astrology/share`
        (auth → token, idempotent per user+details+ayanamsa) and public, no-auth
        `GET /api/astrology/share/{token}` (recomputes the chart). Frontend: a **Share**
        button on Birth Chart creates the link + copies it; a public `/share/:token`
        `SharedChartPage` renders the Rasi + Navamsa read-only with a "create a free
        account" CTA. Verified create/get round-trip against Mongo.
- [x] **Compare two profiles side by side** (P2). DONE 2026-06-28: new `ComparePage`
      (route `/compare`, dashboard card + drawer link). Person 1 = selected profile,
      Person 2 picked from a dropdown; computes both charts (reusing `calculateBirthChart`
      at the selected ayanamsa) and shows the two Kundalis side by side + a placements
      table (Lagna/Moon/Sun + all 9 grahas) with shared-sign rows highlighted.
- [ ] **AI astrologer upgrades** (P1): see the dedicated plan in **§8** below
      (model selection, varga context, saved history, full dasha tree, streaming,
      multi-turn, richer context). Supersedes this one-liner.
- [x] **Multi-language / Sanskrit term glossary tooltips** (P2). Glossary tooltips DONE
      2026-06-28: `constants/glossary.js` (~30 Jyotish terms) + a reusable `<GlossaryTerm>`
      (dotted underline, hover/tap/focus popover, case-insensitive lookup, renders plainly
      if unknown). Wired into the Advanced page's section titles/labels; reusable anywhere.
      Full UI multi-language (i18n) INFRA + FIRST PAGES DONE 2026-06-28: added
      `react-i18next`/`i18next`/`i18next-browser-languagedetector` (pinned i18next@23 /
      react-i18next@14 — i18next@26 pulls a TS6 peer that conflicts with CRA's TS4.9),
      `src/i18n/index.js` config + `locales/{en,hi,sa}.json` (English/Hindi/Sanskrit;
      `escapeValue:false`, language persisted in localStorage key `lang` via the detector).
      `<LanguageSwitcher>` (globe + native-name `<select>`, saffron-styled) added to the
      Dashboard navbar and the shared `PageHeader` nav-right, so it shows on every inner
      page. Fully translated: NavDrawer + PageHeader + ProfileBanner (nav chrome),
      DashboardPage (feature cards via `dashboard.features.*` keys), BirthChartPage
      (header, chart-details, controls, nakshatra/lagna labels, yogas/doshas, errors).
      Interpolation used for `{{code}}`/`{{name}}`/`{{count}}`. CI build passes (+~22kB gz
      for i18next + locale JSON). FULL UI ROLLOUT DONE 2026-06-29: all 13 pages + shared
      components now translated (Login/Register/ProfileSelection/SharedChart/Dhasa/Transit/
      Advanced/Compatibility/Compare/Predictions/Ask + NavDrawer/PageHeader/ProfileBanner/
      LoadingState/PanchangaPanel). Namespaces: common/auth/profile/shared/nav/dashboard/
      birthChart/dhasa/transit/advanced/compare/compat/predictions/ask/panchanga. Added
      `utils/format.js → intlLocale(lang)` (en→en-US, hi→hi-IN, sa→en-IN) for localized
      `toLocaleDateString`; Dhasa/Transit dates now follow the language. Module-level helpers
      (Dhasa `formatDuration`/`LEVELS`) take `t`; Ask example questions use i18next
      `returnObjects` arrays. `LanguageSwitcher` also pinned top-right on the navless
      Login/Register/ProfileSelection/SharedChart screens. CI build green.
      NOT TRANSLATED (intentional — data layer): engine-returned names/values
      (planet/sign/nakshatra/yoga/dosha/koota/dhasa-lord names, AI answers) come from the
      backend in English. PyJHora itself ships native name files for en/ta/te/hi/ka/ml via
      `utils.set_language()` (NO Sanskrit), but the web backend (`astrology.py`) uses its OWN
      hardcoded English/transliterated tables (`ZODIAC_NAMES`, `nakshatra_names`), so it does
      NOT currently honor a language. To localize data later, two paths:
      (A) **frontend mapping** — extend `constants/jyotish.js` (already has RASI_NAMES etc.)
          to map canonical English→hi/sa and wrap `sign_name`/`nakshatra` render sites; covers
          all 3 langs incl. Sanskrit, no backend change, but only the finite enumerations
          (not free-text yoga/dosha descriptions).
      (B) **backend `set_language`** — thread a `lang` param through endpoints + call
          `utils.set_language()` with reset-after (like the ayanamsa pattern); gives Hindi
          data natively but needs the backend refactored off its own tables and still has NO
          Sanskrit. Recommended: (A) for names, leave free-text/AI English (AI already
          answers in whatever language the user asks). Tracked as its own item below.

- [ ] **Localize engine-returned chart-data names (i18n data layer)** (P2). The UI chrome is
      fully translated (en/hi/sa, see above), but values that come back from the backend are
      still English: planet / sign / nakshatra / yoga / dosha / koota / dhasa-lord names (plus
      panchanga limb *values* and AI answers). **Plan — Option A (frontend mapping), recommended
      because it's the only path that covers Sanskrit:**
      - Extend `web/frontend/src/constants/jyotish.js` (already has `RASI_NAMES`/`RASI_ABBR`/
        `PLANET_ABBR`) with English→hi/sa lookup tables for: 12 rasis, 27 (+Abhijit) nakshatras,
        9 grahas (Sun…Ketu), and the dasha-lord names (same as grahas). Source the hi/sa strings
        from PyJHora's own `src/jhora/lang/list_values_hi.txt` (Hindi) and hand-author Sanskrit
        (PyJHora has no `sa` file).
      - Add a small `localizeName(canonicalEnglish, kind, lang)` helper (returns the mapped name,
        falls back to the English input if unmapped) and wrap the render sites: every `sign_name`,
        `nakshatra`, and planet-key/`lord` display across NorthIndianChart / SouthIndianChart /
        BirthChart / Transit / Compare / Dhasa / Panchanga / Predictions.
      - Drive it off the current i18n language (`i18n.language`), same as the rest of the UI.
      - OUT OF SCOPE for A (leave English): free-text yoga/dosha *descriptions*, Ashtakoot koota
        names, and AI answers (the AI already replies in the language the user writes in; a future
        nicety is to add a language hint to the system prompt).

      **Plan — Option B (backend `utils.set_language()`), the fallback if we want native
      engine-localized data server-side (e.g. for non-web consumers, or to also localize
      free-text yoga/dosha/dhasa *descriptions* PyJHora generates):**
      - Supported by PyJHora out of the box for **en/ta/te/hi/ka/ml only — NO Sanskrit**
        (`const.available_languages`, `src/jhora/lang/list_values_*.txt` +
        `msg_strings_*.txt` + `*_msgs_*.json`). So under B, `sa` users would fall back to en
        (or we'd have to author Sanskrit `lang/` files upstream — a big, separate effort).
      - Today `web/backend/astrology.py` ignores all this: it builds its OWN
        `ZODIAC_NAMES` / `nakshatra_names` (and similar) constants and indexes them directly.
        Step 1 is to **stop hardcoding** — replace those module constants with reads from
        `jhora.utils.resource_strings` / `get_resource_lists()` so names flow from the active
        language. (Audit every `ZODIAC_NAMES[...]`, `nakshatra_names[...]`, planet-name and
        dhasa/bhukti label site; ~the same call sites the grep in this entry found.)
      - Step 2: thread a `lang` request param through the endpoints (birth-chart, divisional,
        dhasa, transit, panchanga, doshas, yogas, compatibility, chart-details, ashtakavarga,
        shadbala) and wrap each handler with `utils.set_language(lang)` **+ reset to the
        default afterwards** so requests don't leak language into each other — mirror exactly
        the existing per-request ayanamsa set/reset pattern (`drik.set_ayanamsa_mode` →
        reset), since `set_language` is likewise process-global module state.
      - Step 3: frontend passes the current `i18n.language` (mapped sa→en fallback) on every
        astrology call in `services/api.js`; values then arrive already localized, so the
        Option-A frontend mapping is NOT needed for the 5 supported langs.
      - Tradeoffs vs A: B also localizes PyJHora's free-text predictions/yoga/dosha messages
        (A can't) and keeps one source of truth; but B is a backend refactor, is racy unless
        the set/reset is airtight (global state under concurrency — consider a lock or
        per-request language arg if PyJHora exposes one), and **cannot do Sanskrit**.
      - **Decision rule:** if Sanskrit must work → A (or A for `sa` + B for the others, a
        hybrid). If Sanskrit is droppable and localized free-text descriptions are wanted → B.

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

---

## 8. Ask AI Astrologer — make it professional (P1)

Goal: turn the current 3-button demo into a serious, configurable AI-prediction
workspace. **Decisions captured 2026-06-28** (owner answered the clarifying round):

- **Local models:** auto-detect installed Ollama models **+** support a generic
  OpenAI-compatible local endpoint (LM Studio / llama.cpp / vLLM / text-gen-webui).
- **Divisional charts:** **multi-select** vargas to include in the AI context.
- **Saved responses:** save every Q&A to MongoDB tied to the profile, **with a
  history view** to revisit past conversations.
- **Context depth:** include the **full dasha tree** (Maha→Antar→Pratyantar),
  **yogas & doshas**, **current transits (Gochara)**, and **Ashtakavarga / house
  strengths**.
- **Streaming:** yes — stream answers token-by-token (SSE).
- **Multi-turn:** yes — conversation memory so follow-ups work.
- **Scope:** multi-user / shareable — plan for per-user isolation, per-user API
  keys, and rate limiting (not just personal/local).

### Current state (audit, 2026-06-28)

- `llm_service.py` hardcodes 3 providers and model IDs: Ollama `qwen2.5:14b`,
  Gemini `gemini-1.5-flash`, OpenAI `gpt-4o-mini`. No per-model selection.
- `/api/astrology/ask` ([main.py:545]) recomputes chart + dashas server-side
  (frontend also computes them on the page — duplicated work) and sends only:
  Lagna, Sun, Moon, **D1** planetary positions, and a **partial** dasha view
  (current Maha + its Antardashas + next Maha). No Pratyantar, no other vargas,
  no yogas/doshas/transits/ashtakavarga.
- Nothing is persisted. `database.py` has an unused `Prediction` model.
- No streaming, no conversation memory. Each question is single-shot.
- Frontend `AskAstrologerPage.js` has a static 3-option radio list; provider
  availability (is a key set? is Ollama up?) is not surfaced until a call fails.

### 8.1 Provider & model selection (P1) — DONE 2026-06-28

- [x] Generalized the LLM layer beyond the 3-value enum. `llm_service.py` now has a
      `ProviderType` (`ollama` | `openai-compatible` | `gemini` | `openai`) + a
      `ModelConfig` (provider_type + model + optional base_url + api_key).
      `resolve_config()` builds it from explicit fields or a legacy provider string
      (`qwen`/`gemini`/`chatgpt` still map correctly). Dispatch routes to
      `_call_ollama` / `_call_openai_style` / `_call_gemini`.
- [x] `GET /api/llm/providers` — returns all providers with `available`/`reason`,
      `default_model`, and `models`. Ollama proxies `GET {url}/api/tags` (verified:
      auto-listed 10 installed models locally); OpenAI-compatible proxies
      `GET {base_url}/models`; Gemini/OpenAI report availability from the API key and
      expose a curated model list.
- [x] Generic **OpenAI-compatible endpoint** support (LM Studio/llama.cpp/vLLM/
      text-gen-webui) via one `/v1/chat/completions` code path with configurable
      base URL + key + model (shared with the real OpenAI path).
- [x] `/api/astrology/ask` now accepts `{ provider_type, model, base_url?, api_key? }`
      (new fields take precedence; `llm_provider` kept as fallback). Response echoes
      the resolved `provider` + `model`.
- [x] Frontend: provider dropdown → model dropdown (populated from
      `/api/llm/providers`), availability warning, free-text model entry when a
      provider lists none, and an "Advanced (endpoint URL)" override for local
      providers. Choices persisted in localStorage; AI message header shows the model.
- [x] Default model ids + endpoints moved to env (`OLLAMA_URL`,
      `OLLAMA_DEFAULT_MODEL`, `OPENAI_COMPATIBLE_URL/MODEL/API_KEY`,
      `GEMINI_DEFAULT_MODEL`, `OPENAI_DEFAULT_MODEL`); `.env.example` updated.
      `config.py` now `load_dotenv()`s so `os.getenv` in `llm_service` sees `.env`.
- [x] FOLLOW-UP: thread the same model selection into `/predict` and
      `/compatibility-analysis`. DONE 2026-06-28: `PredictionRequest` +
      new `CompatibilityAnalysisRequest` carry `provider_type/model/base_url/api_key`
      (+ `ayanamsa`, and `sections/vargas` on predict); both endpoints resolve the model
      via the shared `_resolve_cfg` (request key → user's stored key → env key), enforce
      the AI rate limit, and echo the resolved `provider`+`model`. `/compatibility-analysis`
      changed from loose `BirthDetails` params to a single request body so the body fields
      are actually read (the old `llm_provider` in the body was silently ignored). api.js
      `generatePrediction`/`analyzeCompatibilityAI` now accept a `model` object like
      `askQuestion`.
- [x] FOLLOW-UP: per-user API-key entry in the UI — DONE in §8.6 (encrypted
      per-user keys, "API Keys" modal, used ahead of env keys at ask-time).

### 8.2 Divisional-chart (varga) context selection (P1) — DONE 2026-06-28

- [x] Multi-select varga picker on the Ask page ("Charts to Consult" card) using the
      existing `VARGAS` constant (mirrors backend `SUPPORTED_VARGAS`). Default bundle
      D1/D9/D10; D1 is always-on (disabled chip) since it's the natal base. Selection
      persisted in localStorage (`ai_vargas`).
- [x] `build_chart_context` takes a `vargas` list, computes each (≠ D1) via
      `calculate_divisional_chart`, and adds a `vargas` section. The prompt renders one
      compact line per chart — code + name + significance + Asc + each planet's sign
      (sign-only for token economy; 3 vargas ≈ +140 tokens). `/ask` request carries
      `vargas`; response echoes the included list.
- [x] Verified live: asking about marriage/career with D1/D9/D10 returns an answer
      that references the Navamsa (D9) and Dasamsa (D10) placements we sent.
- [ ] FOLLOW-UP: per-question varga suggestions (career→D10, marriage→D9/D7, ...) as a
      one-click hint. NOTE: with sign-only varga data, models sometimes embellish exact
      degrees/nakshatra — fine for signs; revisit if more precision is wanted.

### 8.3 Richer astrological context (P1) — MOSTLY DONE 2026-06-28

- [x] Centralized prompt assembly into a `ChartContextBuilder` (`chart_context.py`,
      `build_chart_context`). Returns one structured, token-budgeted context dict;
      each section is toggleable via a `sections` map on the request. `/ask` now
      calls it (replacing the old inline D1+partial-dasha assembly) and returns the
      full `context` + `sections` so the UI can show exactly what was sent.
- [x] **Full dasha tree**: `_running_dasha_chain` reuses `get_dasha_children` to send
      the *currently running* chain Maha→Bhukti→Antara→Sookshma (each level
      recomputed at full precision), labeled and dated, marked active as of TODAY.
      (Verified live: Rahu Maha / Moon Bhukti / Moon Antara / Rahu Sookshma.)
- [x] **Yogas & Doshas**: includes present yogas (name + description, capped at
      ~140 chars each) and doshas (present with detail, absent name-only) via
      `get_yogas`/`get_doshas`. (Sample chart: 35 yogas, 3 doshas present.)
- [x] **Transits (Gochara)**: includes `get_transits` (each graha's sign/deg/
      nakshatra, house from natal Lagna & Moon, retrograde flag) + Jupiter/Saturn
      sign-ingress highlights.
- [x] Frontend "what was sent to AI" modal now shows the **real** server-assembled
      context after a question (was a stale client-side approximation), with a note
      listing dasha chain / yogas / doshas / transits.
- [x] Rendered prompt measured at ~2.1k tokens with all sections on — comfortably
      within model context windows.
- [x] **Ashtakavarga / house strengths in AI context**: DONE 2026-06-28.
      `build_chart_context` now has `sections["ashtakavarga"]` + `sections["shadbala"]`
      (both default-on) calling `get_ashtakavarga`/`get_shadbala`; the prompt renders the
      Sarva Ashtakavarga (bindus/sign, /337) and per-planet Shadbala (rupa, ratio, rank).
      Full context measures ~2.2k tokens. The Ask "what was sent" note lists them too.
- [x] Strengthen the **system prompt**: DONE 2026-06-28: `SYSTEM_PROMPT` now encodes
      classical Parashari reasoning rules — house significations (1–12), natural karakas,
      dignity (exalt/debil/own/moolatrikona), graha drishti (incl. Mars/Jupiter/Saturn
      special aspects), yoga/dosha handling, dasha+gochara timing, and varga corroboration
      — instructing the model to cite the chart factors behind each claim. Applied to the
      ask, predict, and compatibility paths (single-shot system + streaming system msg).
- [x] FOLLOW-UP: thread the same `ChartContextBuilder` into `/predict`. DONE 2026-06-28:
      `/predict` now calls `build_chart_context` (D1 + running dasha chain + yogas + doshas
      + transits + selected vargas), and `_build_prediction_prompt` renders the full
      `_render_context_block` (was the thin lagna/moon/sun-only prompt, which also had a
      `sun_info` NameError). Implemented the real `AstrologyCompute.get_horoscope_predictions`
      (was the "Not implemented yet" stub) as the lightweight natal summary used by
      `/horoscope`, the basic-prediction fallback, and the compatibility-analysis charts.

### 8.4 Save responses + history (P1) — DONE 2026-06-28

- [x] New Mongo collection `ai_conversations` (per user + profile) via
      `conversations.py`: each doc holds `messages [{role, content, ts, model,
      provider, vargas, sections}]` + title/created_at/updated_at, scoped to
      `user_id` on every query.
- [x] Endpoints: both `/api/astrology/ask` and `.../ask/stream` persist the turn
      (creating the conversation on first message, returning `conversation_id`);
      `GET /api/ai/conversations?profile_id=` (list), `GET /api/ai/conversations/{id}`
      (full thread), `DELETE /api/ai/conversations/{id}`. All auth-scoped.
- [x] Frontend: **History** panel on the Ask page — lists saved conversations for
      the profile (title, Q&A count, model, date), click to reload a thread,
      delete inline, plus a **New Chat** button. Verified list/get/delete live.
- [~] FOLLOW-UP: token usage + latency metadata per answer (latency captured via
      `elapsed_ms`; token usage still not captured). The dead `Prediction` model in
      database.py was removed 2026-06-28 (also dropped its now-unused import in main.py).

### 8.5 Streaming + multi-turn (P1) — DONE 2026-06-28

- [x] Streaming SSE endpoint `POST /api/astrology/ask/stream` that proxies token
      streams from Ollama (`/api/chat` stream), OpenAI + OpenAI-compatible
      (`/chat/completions` stream), and Gemini (`streamGenerateContent?alt=sse`).
      Emits `meta` / `token` / `done` / `error` events; persists the full answer
      on completion. `llm_service.stream_answer` + per-provider `_stream_*`.
- [x] Frontend renders the streamed answer progressively (fetch + ReadableStream
      SSE parser in `streamAskQuestion`; axios can't stream in-browser), with a
      blinking cursor while generating; markdown renderer kept.
- [x] Multi-turn: prior turns (last `HISTORY_WINDOW`=8 msgs) are loaded from the
      saved conversation and fed back; the chart/varga/dasha context is sent once
      as the system message (chat path) or prepended once (single-shot), not
      re-sent per turn. Verified: a follow-up resolved "that ascendant" → Virgo
      from the prior turn.
- [x] FOLLOW-UP: a Stop/cancel button for an in-flight stream — DONE in §8.7
      (abort handle wired to a Stop button that replaces Send while generating).

### 8.6 Multi-user hardening (P1, since scope = shareable) — DONE 2026-06-28

- [x] Per-user API-key storage (encrypted at rest). New `user_settings.py`:
      one `user_settings` doc per user, `api_keys: {provider: <fernet-encrypted>}`,
      symmetric key derived from `API_KEY_ENCRYPTION_KEY` (falls back to
      `SECRET_KEY`). Endpoints `GET/PUT/DELETE /api/user/api-keys[/{provider}]`
      return only masked status (`••••••1234`), never the raw key. Resolution
      order at ask-time: request key → user's stored key → env key
      (`_resolve_cfg`). `/api/llm/providers` now reflects per-user keys, so a user
      who saved a Gemini/OpenAI key sees it as available even with no env key
      (`has_user_key` flag). Frontend: "API Keys" modal on the Ask page (set/
      replace/clear per provider, masked status pill), refreshes providers on save.
      Verified live: set→masked status→provider flips available→delete; bad
      provider rejected (400).
- [x] Rate limiting / quotas per user on AI endpoints. New `ratelimit.py`:
      in-process sliding window, per-minute burst + per-day quota, configurable via
      `AI_RATE_LIMIT_PER_MIN` (20) / `AI_RATE_LIMIT_PER_DAY` (300). `/ask` and
      `/ask/stream` call `_enforce_rate_limit` → HTTP 429 + `Retry-After` and a
      friendly message; frontend surfaces the 429 detail. (In-memory: resets on
      restart, not shared across workers — move to Redis if scaled out.) Graceful
      errors already surface per-provider reasons (Ollama down / key missing /
      model not pulled) via `list_providers` + the stream `error` event.
- [x] Per-user isolation: API keys and conversations are scoped to `user_id` on
      every query (verified another user reads `None` for a conversation).

### 8.7 Professional polish (P1/P2) — DONE 2026-06-28

- [x] "What was sent to the AI" modal shows the real server-assembled structured
      context (vargas, dasha tree, yogas/doshas/transits) + the exact model/provider
      (done in 8.3; per-answer inspector in place).
- [x] Answer affordances under each AI message: **Copy** (clipboard), **Regenerate**
      (replays the prompt behind the last answer; backend `replace_last_assistant`
      swaps it in place so history isn't polluted with a duplicate turn), and
      **thumbs up/down** persisted on the message (`POST /api/ai/conversations/{id}/
      feedback`, toggleable). **Export** the whole conversation to Markdown
      (client-side download). (PDF left as browser-print; MD covers the ask.)
- [x] Loading/cost transparency: AI message header shows model name + generation
      time (`elapsed_ms` measured server-side, sent in the `done`/response and
      persisted). (Token usage not captured — providers vary; elapsed is reliable.)
- [x] Disclaimer/safety footer pinned under the chat (astrology guidance, not
      medical/financial/legal/psychological advice).
- [x] Stop/cancel a streaming generation: the abort handle from `streamAskQuestion`
      is wired to a **Stop** button shown while generating (replaces Send).
- [x] FOLLOW-UP (DONE 2026-06-28): **token usage per answer** — the streaming
      path now captures provider-reported token counts (Ollama `prompt_eval_count`/
      `eval_count`; OpenAI/-compatible via `stream_options.include_usage`; Gemini
      `usageMetadata`), threads a mutable `usage` dict through `stream_answer`,
      persists it on the assistant message and emits it in the `done` SSE event;
      the AI message header shows a compact `N tokens` with a prompt+completion
      breakdown tooltip. **Regenerate with a *different* model** — the Regenerate
      button is now a split button; its caret opens a menu of every available
      provider/model, and picking one regenerates against it (and makes it the
      active selection). **Export to PDF** — the Export button is a menu
      (Markdown / PDF); PDF is rendered client-side with jsPDF (lazy-loaded) via
      `utils/exportConversation.js`, stripping markdown to paginated plain text
      with model/token meta + the safety disclaimer.
      FIX (same day): the Export/Regenerate dropdowns were invisible — the chart
      cards below the profile banner animate in with `fadeIn`, whose `forwards`
      fill leaves a non-`none` `transform` that creates a stacking context, so an
      in-flow menu was painted *behind* them. Both menus now render through a
      React portal on `document.body` (`PortalMenu`, `position: fixed`,
      z-index 1101 like the modals), anchored to the trigger via
      `getBoundingClientRect()`, re-positioned on scroll/resize and auto-flipping
      upward when there's no room below.
- [ ] FOLLOW-UP: automatic retry on transient stream failures.

### 8.8 Suggested build order

1. 8.1 provider/model selection (backend `/api/llm/providers` + generalized
   service) — unblocks everything and is the owner's first ask.
2. 8.3 `ChartContextBuilder` (full dasha tree + yogas/doshas/transits) +
   8.2 varga multi-select — the prediction-quality core.
3. 8.4 save + history (DB + endpoints + panel).
4. 8.5 streaming, then multi-turn.
5. 8.6 multi-user hardening + 8.7 polish.

### 8.9 Agentic tool-calling mode (let the AI fetch what it needs) (P1) — IN PROGRESS 2026-06-29

**Idea (owner, 2026-06-29):** today every question ships a big pre-assembled
context block (pass-all). Add a second mode where we **publish our compute
functions as tools** and let the model decide what extra data it needs, emit a
tool call, we execute it (calling `AstrologyCompute`) and feed the result back,
looping until it answers. User can **toggle between the two modes**. Full design:
[docs/AI_TOOL_CALLING_DESIGN.md](docs/AI_TOOL_CALLING_DESIGN.md).

**Decisions captured 2026-06-29** (owner answered the clarifying round):

- **Provider support:** **native function-calling where available** (OpenAI,
  Gemini, capable Ollama/OpenAI-compatible models) **+ a prompt-based JSON
  tool-protocol fallback** for models without native tool-calling. One internal
  tool-loop abstraction; the per-provider layer either uses native `tools=` or
  the JSON protocol.
- **Baseline seed (configurable):** default seed = **natal chart + running dasha
  chain** (≈ what pass-all sends as its core today). But the seed is **user-
  selectable** so we can A/B what actually helps — **reuse the existing `sections`
  toggles + varga selector**: in tool mode a section that's toggled *on* is
  pre-computed & seeded; a section that's *off* becomes an on-demand **tool**.
  Natal is always seeded (the base); `dasha_tree` on by default; everything else
  defaults to "tool". (Can graduate to an explicit tri-state seed/tool/off later.)
- **Mode toggle:** **per-conversation** — chosen when a conversation starts and
  stored on the conversation doc, so each thread records how it was answered.
  Default stays **pass-all** until tool mode proves reliable.

**Tools to publish** (1:1 over existing `AstrologyCompute` statics, same
birth-details args): `get_natal_chart` (D1), `get_dasha_chain` /
`get_dasha_children`, `get_yogas`, `get_doshas`, `get_transits`,
`get_ashtakavarga`, `get_shadbala`, `get_chart_details`,
`get_divisional_chart(varga_factor)`, `get_panchanga`. Each already returns a
clean status/dict — thin JSON-schema wrappers, minimal new surface.

**Build order / status:**
- [x] (1) **Tool registry** (`tools.py`) — 11 tools (get_natal_chart, get_dasha_chain,
      get_dasha_children, get_yogas, get_doshas, get_transits, get_ashtakavarga,
      get_shadbala, get_chart_details, get_divisional_chart, get_panchanga) as thin
      JSON-schema wrappers over `AstrologyCompute`. Birth details + ayanamsa are
      **server-injected** (model can't redirect to another person); name + arg
      validation; results mirror `chart_context` section shapes. Unit-tested.
- [x] (2) **Provider-agnostic tool-loop** (`llm_service.run_tool_loop`) — neutral
      internal message format converted per provider; **non-streaming tool rounds**
      (reliable tool-call detection) then the final answer emitted as token events;
      native function-calling for OpenAI-style + Ollama; **JSON-protocol fallback**
      (Gemini for now, and auto-fallback if a native round throws); round cap (6) →
      forced final answer; usage summed across rounds. Verified live on Ollama
      (gemma4:12b) single- and multi-tool (called chart_details + dasha_chain + D10).
- [x] (3) **Endpoint wiring** — `/ask` + `/ask/stream` branch on the conversation's
      `mode`; stream emits `tool_call` / `tool_result` / `notice` SSE events; the
      completed `tool_trace` is persisted on the assistant message. Conversation doc
      gains a `mode` field (locked on first turn); `serialize_conversation` +
      `list_conversations` expose it.
- [x] (4) **Seed = toggled-on sections** — tool mode renders the seed via
      `_render_context_block(..., tool_mode=True)` (closing text no longer claims the
      chart is complete); all tools exposed so the model can fetch the rest.
- [x] (5) **Frontend** — per-conversation **Answer mode** toggle (Full context / Tool
      calls), locked once a thread has an AI turn; `mode` sent through
      `streamAskQuestion`; new `onToolCall/onToolResult/onNotice` callbacks render
      tool-call **step pills** in the transcript; steps rebuilt from `tool_trace` when
      loading a saved thread.
- [x] (6) **Inspector** — `messageInfo` shows `{ mode, seed_context, tools_used }`
      for tool-mode answers instead of a static block.
- [x] DONE 2026-06-29: **native Gemini function-calling** — `_chat_once_gemini`
      sends `tools: [{functionDeclarations}]` + `toolConfig.functionCallingConfig`,
      parses `functionCall` parts, and feeds results back as `functionResponse` parts
      in a user turn (consecutive results merged into one turn per Gemini's rules; a
      schema sanitizer drops keys Gemini rejects e.g. `default`, and omits empty
      `parameters`). All providers now attempt native first; a failed native round
      still auto-falls back to the JSON protocol. Converters unit-tested against the
      verified v1beta REST shape; live round-trip not yet run here (no Gemini key in
      this env) — verify in-app with a real key.
- [ ] FOLLOW-UP: localize the new frontend strings (Answer mode card + step labels
      use English literals for now — see §5 i18n).
- [ ] FOLLOW-UP: explicit tri-state seed/tool/off per section (today: seeded if the
      section toggle is on, otherwise fetched via tool).
- [ ] FOLLOW-UP: cache identical tool results within one answer; cap repeated calls.
- [x] FOLLOW-UP (DONE 2026-06-29): **visualize the call flow** during a smart-lookup
      answer. The tool result data now flows through: `run_tool_loop`'s `tool_result`
      event carries the full `result`; the stream + `/ask` persist it into each
      `tool_trace` entry; the frontend stores it on each step (live + rebuilt from the
      saved trace). Under each answer the step pills now have a **"▸ Behind the scenes"**
      toggle that expands a panel listing every tool call in order with its args and the
      JSON data it returned — a readable trace of *how* the AI reasoned, not just
      *which* tools it used. (The "Tool calls" mode is surfaced to users as **"Smart
      lookup"**.) UPDATE 2026-06-29: the panel is now a **graphical vertical timeline**
      (`TraceNode` — dot-on-a-connector-line) running seed → each tool call (with a
      "view data" disclosure) → answer, with coloured/iconned nodes.
- [x] DONE 2026-06-29: **persisted-trace storage strategy** — chose the **lazy
      side-collection** (owner pick). The assistant message now keeps only the *light*
      trace (`tool_trace` = name/args/ok) plus an opaque `trace_id`, so listing/loading
      threads stays fast. The full per-call results live in a separate
      `ai_tool_traces` collection (`tool_traces.py`), keyed by `trace_id`, written in
      `_save_turn` and fetched lazily via `GET /api/ai/conversations/{id}/traces/
      {trace_id}` only when the user expands "Behind the scenes" on a reopened answer.
      Live answers still show full data from the SSE stream (zero extra storage).
      Traces are user-scoped and deleted with their conversation. Verified end-to-end
      against Mongo (save/fetch/isolation/delete).

**Open risks:** weak local models loop/hallucinate tool names (cap max tool
rounds, validate names, fall back to pass-all on repeated failure); streaming +
tool loop interleaving (stream → pause on tool call → execute → resume); token
cost of multi-round tool results vs one pass-all block (measure with the existing
usage capture).

---

## Transit chat — in-context gochara reading (DONE 2026-06-29)

- [x] DONE 2026-06-29: **embedded AI chat on the Transits page**. New
      `components/TransitChat.js` renders a collapsible "Ask about these transits"
      card below the gochara chart on `TransitPage`. It reuses the existing
      `streamAskQuestion` (`/api/astrology/ask/stream`) — **no backend changes** —
      with `mode: "pass_all"` and `sections: { transits:true, dasha_tree:true, … rest
      false }`, so the model interprets exactly the transits on screen (natal D1 is
      always seeded) without a redundant `get_transits` recompute or drift from the
      displayed chart. Keeps its **own** conversation thread (own `conversation_id`),
      so the seed context stays transit-only and doesn't pollute the full astrologer
      thread. Model/provider come from the same `localStorage` keys the Ask page
      writes (`ai_provider_type` / `ai_model` / `ai_base_url`); API keys resolve
      server-side. **Smart suggestion chips** are derived from the live data: Sade
      Sati when Saturn is 12th/1st/2nd from natal Moon, retrograde grahas, upcoming
      slow-mover ingresses, plus summary / "which matters most". Streams token-by-token
      with a Stop button; ReactMarkdown render; i18n in en/hi/sa under `transitChat`.
      Verified: lint clean + production build compiles.
- [ ] FOLLOW-UP: this chat's thread isn't surfaced in the Ask page's conversation
      switcher UI (it is saved + listable via `/api/ai/conversations`, just not shown
      there). Consider a "Transit reading" label/filter so reopened threads are
      findable.
- [ ] FOLLOW-UP: refactor — extract a shared message-bubble/streaming-input component
      so `TransitChat` and the 2.2k-line `AskAstrologerPage` share one chat UI instead
      of two. Deferred to keep this change low-risk.

---

## AI Capabilities page — tool catalog / capability disclosure (DONE 2026-06-29)

- [x] DONE 2026-06-29: **a dedicated page that lists every tool the AI astrologer can
      call**, surfaced *outside* the Ask page (owner ask). Backend: `tools.tool_catalog()`
      enriches the existing registry with a human-friendly `label` + `category` (the model
      never sees these — single source of truth is still the `TOOLS` registry, so the page
      can't drift from the real toolset) and a read-only `GET /api/ai/tools` (static,
      user-independent, no auth dependency) returns it. Frontend: `pages/AiToolsPage.js`
      groups the 11 tools into **Core chart / Timing / Strengths & afflictions** cards;
      each tool shows its friendly name, the model-facing description, and a **Show
      technical schema** toggle that reveals the inputs (name/type/required/description)
      only on demand — the "human-friendly + optional schema" presentation the owner chose.
      Wired via `getAiTools()` (`services/api.js`), a `/ai-tools` route (`App.js`), a
      **Wrench** nav entry (`NavDrawer.js`) **and** a dashboard feature card
      (`DashboardPage.js`) — the latter matters because the hamburger drawer is hidden on
      desktop (>768px), where navigation is via dashboard cards. i18n: `nav.aiTools`,
      `aiTools.*` page strings, and `dashboard.features.aiTools` in en/hi/sa. Verified:
      backend compiles + endpoint returns 11 tools in 3 categories; lint clean; locale
      JSON valid.

## Compatibility (Guna Milan) — real Ashtakoot + charts + on-demand AI (DONE 2026-06-29)

- [x] DONE 2026-06-29: **implemented the compatibility backend** (it was a stub returning
      `{"error": "Not implemented yet"}`, so the page showed bogus/empty scores).
      `AstrologyCompute.get_compatibility` now computes each person's **Moon nakshatra+pada**
      and runs PyJHora's North-Indian `Ashtakoota` (the classic 36-point Guna Milan). Returns
      the **8 kootas with their correct individual maxima** — Varna 1, Vashya 2, Tara(Dina) 3,
      Yoni 4, Graha Maitri 5, Gana 6, Bhakoot(Rasi) 7, Nadi 8 (sum 36) — plus a verdict and
      each partner's Moon nakshatra/pada. The old frontend table hard-coded mislabeled kootas
      (reused `dinam`/`ganam`, wrong maxes); the page now renders `result.kootas` dynamically.
- [x] DONE 2026-06-29: **per-person timezones** — `get_compatibility` takes `male_tz`/
      `female_tz` (fallback `tz`); both `/compatibility` and `/compatibility-analysis`
      endpoints pass each profile's own timezone so partners born in different zones score
      right.
- [x] DONE 2026-06-29: **side-by-side charts on the Compatibility page** — after a check it
      renders both kundalis (North/South per `chartStyle`) using the shared chart components,
      matching the Compare Charts page so both give a visual comparison.
- [x] DONE 2026-06-29: **on-demand AI analysis** — replaced the old non-functional `useQwen`
      checkbox with a **"Get detailed AI analysis"** button that calls `/compatibility-analysis`
      with the model the user picked in *Ask AI Astrologer* (localStorage `ai_provider_type/
      ai_model/ai_base_url`, same pattern as `TransitChat`) and shows **which model answered**.
      i18n: `compat.pada/charts/aiHint/aiLoading/aiModel/aiGenerate/aiRegenerate/aiError` in
      en/hi/sa. Verified: backend computes 22.5/36 on a sample, both files compile, page lint
      clean, locale JSON valid.
- [x] DONE 2026-06-29: **neutral AI comparison on the Compare Charts page** (owner ask —
      parity with the Compatibility page, but Compare Charts is relationship-agnostic, so it
      is NOT Guna Milan). New `llm_service.compare_charts` + `_build_comparison_prompt` (a
      neutral "compare & contrast these two charts as individuals" prompt covering
      personality/Lagna, mind/Moon, vitality/Sun, similarities, differences, synthesis — no
      score, no marriage assumption) and `POST /api/astrology/compare-analysis`
      (`CompareAnalysisRequest`, model-config aware via `_resolve_cfg`). Frontend:
      `compareChartsAI` (`services/api.js`) + an on-demand "Get AI comparison" card on
      `ComparePage` that uses the model picked in Ask AI Astrologer and shows which model
      answered; the reading is cleared whenever the pairing changes. i18n: `compare.aiTitle/
      aiHint/aiLoading/aiModel/aiGenerate/aiRegenerate/aiError` in en/hi/sa. Verified: backend
      compiles + route registered + prompt builds, frontend lint clean, locale JSON valid.

## Sarvatobhadra Chakra — transit grid + layman AI reading (DONE 2026-06-29)

- [x] DONE 2026-06-29: **brought the Sarvatobhadra Chakra to the web** (it previously
      existed only in the desktop PyQt UI, `jhora.ui.chakra.Sarvatobadra`, with no web
      surface). Owner ask: build the chakra and have the AI explain, in layman terms, what
      the person can expect. Scope agreed: **current transits (gochara) + vedha** on a
      **new dedicated page**, anchored to the **birth star, Moon sign, name star, birth
      tithi & weekday**.
- [x] **Backend chakra engine** (`astrology.py`): ported the authentic 9×9 grid (28
      nakshatras incl. Abhijit on the outer ring, 50 aksharas, 12 rasis, and the 3×3 centre
      of five tithi groups Nanda/Bhadra/Jaya/Rikta/Purna + weekdays) into a typed,
      programmatic `_build_sbc_grid()` — faithful to the desktop layout. New
      `AstrologyCompute.get_sarvatobhadra_chakra(...)` places each transiting graha on BOTH
      its nakshatra cell and its rasi cell, derives the native's anchor cells (janma star,
      Moon sign, optional naama-nakshatra, birth tithi group, birth weekday), and computes
      **occupation** (a graha on an anchor cell) + **saamne/frontal vedha** (a graha on the
      cell mirrored through the chakra centre, `(8-r, 8-c)`). Returns the full grid,
      anchors, planet placements, structured `findings`, and a transit-day panchanga with
      same-tithi-group / same-weekday coincidence flags. Benefic/malefic split drives a
      supportive-vs-stressful tone. Verified the mirror-vedha invariant on two charts
      (e.g. 1990-05-15 → birth weekday Tuesday, correct).
- [x] **Layman AI reading** (`llm_service.py`): `analyze_sarvatobhadra` +
      `_build_sarvatobhadra_prompt` — a jargon-light, ~250-350-word reading (headline tone,
      what each flagged graha stirs up + which life area, 2-4 gentle suggestions, a line of
      reassurance) that trusts the pre-computed findings and avoids death/disease/precise-date
      predictions. `POST /api/astrology/sarvatobhadra` (compute) and
      `POST /api/astrology/sarvatobhadra-analysis` (AI, model-config aware via `_resolve_cfg`,
      rate-limited) added to `main.py` with `SarvatobhadraAnalysisRequest`.
- [x] **Frontend** (`SarvatobhadraPage.js`, route `/sarvatobhadra`, nav + dashboard card,
      `getSarvatobhadra`/`analyzeSarvatobhadraAI` in `services/api.js`): renders the 9×9
      grid with per-ring colour coding, graha chips (green benefic / red malefic), anchor
      highlight + dashed vedha-source cells and a legend; a date/time picker (defaults to
      now, "Now" reset) and an optional **name-star dropdown** (27 nakshatras with their
      naama syllables — no fragile transliteration); an anchors panel; a colour-toned
      findings list; and an on-demand AI reading card that uses the model picked in Ask AI
      Astrologer. i18n: `nav.sarvatobhadra`, `dashboard.features.sarvatobhadra`, and the full
      `sbc.*` block in en (hi/sa get the nav + card labels, body falls back to en). Verified:
      backend imports OK + compute invariants pass; `npm run build` compiles; lint clean;
      locale JSON valid.
