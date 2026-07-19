# PyJHora Web — Modernization & Feature Plan

> **Reading note (2026-07-16).** This file is a **living plan + build log**: entries
> describe the code as it stood when they were written, so older ones name files
> that have since moved. The §4 backend split (see `improvements-2026-07.md`) was a
> pure file move — behaviour is unchanged, only locations:
> - `backend/astrology.py` → the **`backend/astrology/`** package (`engine.py` +
>   14 `compute_*.py` mixins + `core.py`); `AstrologyCompute` and the import
>   surface are identical, so every code reference below still resolves.
> - `backend/main.py` → app wiring only; the ~160 handlers are in **`backend/routes/*`**,
>   request models in **`backend/models.py`**, shared helpers in **`backend/deps.py`**.
> - `backend/llm_service.py` → keeps the tool loop; provider adapters are in
>   **`backend/llm/providers/*`** and all `_build_*_prompt` + `_render_context_block`
>   in **`backend/llm/prompts.py`**.
>
> The "Status: planning" line below is likewise historical — nearly everything here
> has since shipped (§1–§26 plus the whole of `improvements-2026-07.md`).

Status: planning. No app code changed yet. Direction agreed: **Refined Vedic** —
keep the spiritual/Indian-astrology identity, but calm it down (drop rotating
mandala / glow-pulse / gradient-text-everywhere), give it real typographic
hierarchy, make it mobile-first, and clean up the code.

Legend: **P0** = correctness/blocking, **P1** = high value, **P2** = nice to have.
🔴 = **still open / not done** (spot-marker for the owner — every unchecked item carries it).

---

## 1. Bugs & correctness (P0 — fix first)

- [x] **(P1) Notifications — digest email "never came" & push shows "unavailable"** (owner report
      2026-07-04): two independent, environmental causes, each with a fix:
      - **Email.** SMTP + the digest pipeline both work (verified end-to-end: `send_digest_for_user`
        returns `email:True`). The *scheduled* mail never fired because `scheduler.py` only sent when
        the local hour *exactly* equalled the preferred hour (7am IST) **and** the process happened to
        be running during that single hour — a restart/downtime skipped the whole day. FIXED
        2026-07-04: send at **or after** the preferred hour (`local.hour >= hour`), still once-per-day
        via the atomic `last_sent_date` claim, so a missed hour is delivered later the same day.
        (The "Send me a test now" button was and is the immediate path.)
      - **Browser push.** Server VAPID keys *are* configured; the badge reads "unavailable" because
        the app was opened over a plain-HTTP LAN hostname (`http://…:3000`). Service Workers + Push
        only exist in a **secure context** (HTTPS or `http://localhost`) — a browser rule, unfixable
        in JS. FIXED 2026-07-04 (UX): `push.js` gains `pushUnavailableReason()` (`isSecureContext`
        check), and Settings → Notifications now shows a tooltip + hint distinguishing the three cases
        (server not configured / insecure page / unsupported browser) instead of a bare "unavailable".
        To actually enable push: serve over HTTPS or use `localhost`. README + `.env.example` document
        the secure-context requirement.
- [x] **(P1) Today / Daily Digest — label/value run together** (owner report 2026-07-03):
      the panchanga & dasha detail rows rendered "TithiKrishna Tritiya", "MahadashaRahu" etc —
      the shared `.kv-label`/`.kv-value` spans had no separator/layout (the inline pattern elsewhere
      bakes a `": "` into the label text). FIXED 2026-07-03: the digest detail-lists now use a
      `.digest-details` flex layout (label left, value right) in `Dashboard.css`, so pairs are spaced
      cleanly on the Today, panchanga, dasha and transit-ingress rows.
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
- [x] **Kill inline styles.** Phase 1 (2026-06-28) removed the copy-pasted inline-styled
      navbars + profile banners + error blocks via shared components. BROAD SWEEP DONE
      2026-06-30: added a "Page-level shared utilities" section to `Shared.css`
      (`.page-controls`/`.controls-group`/`.control-input`/`.control-btn`, the North/South
      `.chart-toggle`, `.stepper`, `.info-pills`/`.info-pill`, `.chart-grid`/`.card-grid`,
      light `.data-table`, `.detail-list`, `.form-select`, `.ai-panel` (+`.ui-btn--ai`),
      `.score-box`/`.koota-*`/`.compat-person*`, `.kv-label`/`.kv-value`, `.card-intro`/
      `.card-note`/`.readonly-banner`, `.fade-in`, `.mt-xl`, `.ui-card--pad-lg`/`--flush`,
      `.ui-card-header--sm`, and text/weight helpers) plus page-specific classes in
      `Dashboard.css` (nakshatra cards, dhasa tree/badges/current-period, compat). Converted
      pages off inline styles: Transit 51→3, BirthChart 40→1, Compatibility 49→3, Dhasa
      44→14, Sarvatobhadra 38→26, Compare 13→4, Advanced 10→1, SharedChart 3→1, and
      **AskAstrologer 99→13** — the dense modal/tool-trace/settings clusters were swept in a
      follow-up pass (2026-06-30): TraceNode timeline (`.trace-node*`), tool-call pills + trace
      panel (`.tool-pill*`/`.tool-trace-*`/`.trace-*`), settings cards/toggles (`.ask-card*`/
      `.ask-toggle-btn`/`.ask-grid`/`.ask-warning`/`.ask-link-btn`/`.ask-viewdata-btn`), the
      history panel (`.history-*`, reusing `.ui-card`), the chat area/error banner/info button,
      and BOTH modals onto shared `.modal-overlay`/`.modal-panel`/`.modal-header`/`.modal-title`/
      `.modal-close`/`.modal-body` (+ info-modal inner blocks), plus staggered `.fade-in--d2/d4/d6`.
      App-wide ~398→~95 `style={{}}` sites removed (~300). What REMAINS inline is intentional:
      genuinely **data-driven** styles (Dhasa per-level `--lvl-accent`/avatar, the TraceNode dot
      colour, PortalMenu positioning, Sarvatobhadra chakra-cell colours, Ashtakavarga heatmap
      tint, Learn progress-bar widths, Dashboard per-feature gradient, comparison-match
      highlight), **lucide icon colour props**, and trivial one-off single-property overrides
      (a font-size/margin layered on a utility class). Hover effects that were JS
      `onMouseOver/onMouseOut` handlers are now CSS `:hover`. Lint clean, prod build green
      throughout. See also the shared chat component below (TransitChat + AskAstrologer now
      share `components/chat/*`).
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
- [x] **AI astrologer upgrades** (P1): see the dedicated plan in **§8** below
      (model selection, varga context, saved history, full dasha tree, streaming,
      multi-turn, richer context). Supersedes this one-liner. DONE — all of §8.1–§8.9
      shipped (2026-06-28 → 2026-06-30); this umbrella item was stale, ticked 2026-07-03.
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
      NOT TRANSLATED at that point (data layer): engine-returned names/values —
      planet/sign/nakshatra/yoga/dosha/koota/dhasa-lord names, AI answers. Being addressed
      since 2026-07-16 as a **hybrid** of frontend mapping + PyJHora's per-call `language=`;
      see the P3 item below and 📖 [`docs/I18N_DATA_LAYER_DESIGN.md`](docs/I18N_DATA_LAYER_DESIGN.md)
      for the design (this note used to sketch the two options and got B's cost wrong — the
      doc supersedes it).

- [ ] 🔴 **Localize engine-returned chart-data names (i18n data layer)** (P3 — was
      DEPRIORITIZED per owner 2026-07-03). **IN PROGRESS since 2026-07-16.**

      📖 **Full design, decisions and traps: [`docs/I18N_DATA_LAYER_DESIGN.md`](docs/I18N_DATA_LAYER_DESIGN.md).**
      That doc is the source of truth — this entry is just the task status, so keep the detail
      there and don't re-litigate it here.

      Outcome is a **hybrid**: frontend mapping (A) owns the fixed enumerations (rasis /
      nakshatras / grahas — the only path that covers Sanskrit), PyJHora's per-call `language=`
      (B) owns the engine free text (yoga/dosha names + descriptions, which A structurally
      cannot do). Sanskrit routes to Hindi wherever B is involved — a stopgap, not the
      destination.

      **Done:** A machinery (`scripts/gen-name-locales.js` + `i18n/localizeName.js` +
      22 tests, the repo's first frontend tests) · BirthChart + both chart components ·
      B for yogas + raja yogas (`to_engine_language`, `lang` param on 2 routes, 12 tests;
      suite 222 → 234).

      **Left:** roll the A pattern across ~22 files (65 `sign_name` sites, 39 `.nakshatra`,
      45 RASI/PLANET-constant uses) — Transit / Compare / Dhasa / Panchanga / Predictions /
      KP / Jaimini / Chakras / Bhava / Marriage / digests.

      **Two things that will bite anyone resuming this** (both explained in the doc):
      - ⚠️ Never pass `language` to `get_yoga_details` — PyJHora eval()s the message file's
        KEYS as function names and the hi/en key sets differ, so the language changes **which
        yogas are detected**. Detect in English, translate by key.
      - ⚠️ Canonical English is an IDENTITY (`fullName` keys flagsByPlanet + onSelectPlanet).
        Apply `ln()` only where text is rendered, never to a lookup key.

      **Open decisions for the owner** (full list in the doc §6): author Sanskrit `lang/`
      files upstream · the hand-authored Sanskrit is unreviewed · doshas (gain Hindi, lose our
      better descriptions?) · the `म्रृगशीर्षा` typo in `list_values_hi.txt`.

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
- [x] FOLLOW-UP: per-question varga suggestions (career→D10, marriage→D9/D7, ...) as a
      one-click hint. DONE 2026-06-30: `constants/jyotish.js → VARGA_SUGGESTIONS` maps ~10
      topics (career/marriage/children/wealth/property/education/siblings/parents/
      spirituality/health) to their classical vargas + trigger keywords. The Ask page
      derives `vargaSuggestions` from the live question text and renders dashed **"+ D10
      (career…)"** chips above the composer for any suggested varga not already selected;
      clicking one adds it to `selectedVargas` (so it's seeded into the AI context). NOTE:
      with sign-only varga data, models sometimes embellish exact degrees/nakshatra — fine
      for signs; revisit if more precision is wanted.

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
- [x] FOLLOW-UP: token usage + latency metadata per answer. Latency (`elapsed_ms`)
      and the streaming token counts were already captured; DONE 2026-06-30 the
      **non-streaming** `/ask` path now captures token usage too — `_complete` /
      `ask_question` thread a mutable `usage` dict into each provider call
      (`_call_ollama` reads `prompt_eval_count`/`eval_count`, `_call_openai_style`
      the `usage` object, `_call_gemini` the `usageMetadata`) via a shared
      `_fill_usage` helper, and the endpoint persists it on the message and returns
      it in the response (parity with the stream `done` event). The dead `Prediction`
      model in database.py was removed 2026-06-28 (also dropped its now-unused import
      in main.py).

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
- [x] FOLLOW-UP: automatic retry on transient stream failures. DONE 2026-06-30:
      `LLMService.stream_answer` is now a retry wrapper around a stream-generator
      factory. A stream that fails **before emitting any content** with a transient
      error (provider unreachable, timeout, 5xx/429 — classified by
      `_is_transient_stream_error` on the provider's single error chunk) is retried
      up to `MAX_STREAM_RETRIES` (2) with a linear backoff (`STREAM_RETRY_BACKOFF`),
      clearing `usage` between attempts. Permanent errors (e.g. "API key not set")
      and mid-stream failures (content already sent — can't re-send without
      duplicating) are surfaced as-is. Unit-tested: retry-then-succeed,
      exhaust-retries, and that a non-transient/normal first chunk is never retried.

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
- [x] FOLLOW-UP: localize the new frontend strings (Answer mode card + step labels).
      DONE 2026-07-03: added a batch of `ask.*` i18n keys (en) covering the **Answer mode**
      card (heading/hint/locked-hint + "Full context"/"Smart lookup"), the **Context sections**
      tri-state card (heading, both hints, per-section labels via `labelKey`, and the
      Seed/Tool/Off state pills + "Click to change" title), the **Behind the scenes** trace
      timeline ("Starting summary sent to the AI", "view what was sent", "Looked up {{tool}}"
      with interpolation, "view data", "Writing the answer…"/"Wrote the answer above"), and the
      varga **"Suggested charts:"** hint. `CONTEXT_SECTIONS` now carries `labelKey` (module-level,
      translated at render via `t()`). hi/sa fall back to en (`fallbackLng:"en"`), matching the
      recent-feature pattern. Tool names themselves (`fmtTool` output) stay English (data layer,
      see the deprioritized item below). ESLint clean, prod build green.
- [x] FOLLOW-UP: explicit tri-state seed/tool/off per section. DONE 2026-06-30: each
      context section is now Seed (pre-sent in the prompt), Tool (the AI fetches it on
      demand in Smart-lookup mode) or Off (excluded entirely). Backend:
      `chart_context.build_chart_context` normalizes section values (legacy bools OR the new
      "seed"/"tool"/"off" strings) — only "seed"/True is rendered into the prompt; it stores
      the raw tri-state in `_sections` so the "what was sent" inspector shows the actual
      handling. `tools.SECTION_TOOL` maps each section to its fetch tool + `ALWAYS_TOOLS`
      (natal/chart-details/dasha-children/divisional/panchanga); new
      `tools.tool_names_for_sections(sections)` returns the always-on tools plus the tool for
      any section set to "tool" (a "seed" section's tool is withheld since the data is already
      in the prompt; "off" withholds it too). Both `/ask` and `/ask/stream` pass
      `tool_names=...` into `run_tool_loop` so the exposed toolset matches the tri-state
      (`None`/legacy → all tools, unchanged). Frontend: a **Context sections** card on the Ask
      page — in Smart-lookup mode each row cycles Seed→Tool→Off (colour-coded pill); in
      Full-context mode it's On(Seed)/Off (Tool maps to Seed since there are no tools).
      Default for Smart lookup = dasha seeded, everything else Tool (matches the §8.9
      decision); persisted in `localStorage` (`ai_sections`); sent as `sections` through
      `streamAskQuestion`. (New card labels are English literals — folded into the i18n
      follow-up above.)
- [x] **graha drishti (aspects) — capability capture + AI context + tool** (owner ask
      2026-06-30). DONE 2026-06-30. Aspects used to be *reasoned about by the model* (the
      system prompt encodes drishti rules incl. Mars 4/8, Jupiter 5/9, Saturn 3/10 special
      aspects) but were **never computed and sent** — error-prone inference from raw
      placements. Now computed at **full depth** (graha drishti + rasi/Jaimini drishti +
      Parashari sphuta strength) and surfaced via **both** paths:
      - **Capability capture**: `AstrologyCompute.get_aspects(...)` — for each of the 9
        grahas, the houses (1-based) and planets it casts **graha drishti** on (incl. the
        special aspects), the planets it aspects by **rasi drishti**, and a **0-100%
        strength** per graha→planet aspect so partial vs full aspects can be weighed. Built
        on PyJHora's existing `house.graha_drishti_from_chart` / `raasi_drishti_from_chart`
        + `strength.planet_aspect_relationship_table_pvr` (sphuta drishti, normalized %) —
        no hand-rolled math; ayanamsa set/reset like the other methods.
      - **Pass-all context** (§8.3): **default-on** `sections["aspects"]` in
        `chart_context.build_chart_context`; rendered in `_render_context_block` as one
        terse line per graha (`Mars [special aspects]: houses 2,3,11; planets Sun 35%;
        rasi-drishti on …`). Measured rendered context stays within budget.
      - **Smart-lookup tool** (§8.9): `get_aspects` published as the **12th tool** in
        `tools.py` (birth-details server-injected) + added to `tool_catalog()`/`_DISPLAY`
        (Core chart) so it shows on the AI Capabilities page, and to `SECTION_TOOL` so it
        participates in the tri-state above. Verified: get_aspects computes (Mars special
        aspects + Sun 35% on the test chart), seeds + renders in pass-all, dispatches as a
        tool (registry now 12 tools/catalog), backend imports clean, frontend build green.
        (Aspect-section label is English literal — folded into the i18n follow-up above.)
      - **User-facing display** (owner ask 2026-06-30 — "show this to the user on the portal
        too, not just the AI"): new `POST /api/astrology/aspects` endpoint + `getAspects` in
        `services/api.js`; reusable **`AspectsCard`** (`components/AspectsCard.js` + `Aspects.css`)
        — a per-graha table (houses/planets aspected with strength %, rasi-drishti, ★ for
        special aspects) shown on **both** the Birth Chart page (under Yogas/Doshas) and the
        Advanced page (table only). **Aspect lines drawn on the Rasi chart**: `NorthIndianChart`
        (SVG `<line>`s house-centre→house-centre) and `SouthIndianChart` (a `0..4` `viewBox`
        SVG overlay on the fixed-sign grid, non-scaling stroke) gained `aspects`/`showAspects`/
        `focusPlanet` props; colour-coded per graha (`ASPECT_COLORS`). A **"Show aspects on
        chart" toggle** (persisted, off by default) on Birth Chart turns the lines on/off, and
        hovering a table row **focuses** just that graha's lines (dims the rest). i18n `aspects.*`
        in en (hi/sa fall back). Lint + production build green.
      - **Strength-weighted lines** (owner ask 2026-06-30): `get_aspects` now returns each
        aspected house as `{house, strength}` (per-house sphuta % read from the `vt` house
        columns, idx 9+), so both chart overlays **scale each line's width + opacity by the
        aspect strength** — full aspects draw bold/solid, partial ones thin/faint. The
        AspectsCard "houses" column renders the same as strength-tinted pills, and the AI
        context line now shows `house(strength%)`. Consumers updated across astrology.py /
        llm_service render / AspectsCard / North+South overlays; verified + build green.
- [x] FOLLOW-UP: cache identical tool results within one answer; cap repeated calls.
      DONE 2026-06-30: `run_tool_loop` keeps a per-answer `tool_cache` keyed by
      `name + sorted-JSON(args)` and a `call_counts` map. An identical (name+args)
      call is served from the cache instead of re-dispatching (the `tool_result`
      event carries a `cached: true` flag); a call repeated past `MAX_DUP_TOOL_CALLS`
      (3) is short-circuited with an error result nudging the model to use the data
      it has and answer — breaking the loop a weak model can fall into. Unit-tested:
      5 identical requests → exactly 1 real `tools.dispatch`, 2 cache hits, 2 capped.
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
- [x] FOLLOW-UP: this chat's thread is now surfaced in the Ask page's conversation
      switcher. DONE 2026-06-30: conversations carry a `source` field
      ("astrologer" default / "transit") set at creation — `create_conversation`
      stores it, `list_conversations`/`serialize_conversation` expose it,
      `AskQuestionRequest.source` carries it, and `TransitChat` sends
      `source: "transit"` through `streamAskQuestion`. The Ask page's History panel
      shows a **"Transit"** badge on those threads and — only once at least one
      exists — a **All / Astrologer / Transit readings** filter row. i18n keys
      `ask.sourceTransit` + `ask.filter.*` added in en/hi/sa.
- [x] FOLLOW-UP: refactor — shared chat component. DONE 2026-06-30: created
      `components/chat/*` — `StreamingMarkdown` (markdown body + blinking cursor +
      "thinking…" placeholder), `SuggestionChips`, `ChatComposer` (text field + Send/Stop,
      Enter-to-send, single- or multi-line), and `ChatBubble` (left/right bubble) — styled by
      a "Shared chat primitives" section in `Chat.css`. `TransitChat` was fully rewritten onto
      them (its ~20 inline-styled elements gone, now `.transit-chat__*`/`.chat-*` classes);
      `AskAstrologerPage` adopted `ChatComposer` (replacing its duplicated input bar) and
      `StreamingMarkdown` (its message body). The two chats now share one chat UI instead of
      two. (Their *bubble layouts* still differ by design — Ask is a full-width chat log,
      Transit is compact left/right bubbles — so `ChatBubble` is Transit-only; the genuinely
      shared pieces are the composer, chips, and streaming-markdown.)

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
- [x] DONE 2026-06-29: **fixed the Compatibility "Check" crash + markdown parity.** Two bugs:
      (1) the page crashed with *"Objects are not valid as a React child (found: object with
      keys {type, loc, msg, input, url})"* — FastAPI 422 responses put `detail` as an **array
      of validation objects**, and several pages did `setError(err.response?.data?.detail)`,
      handing that array straight to React. Added `errorMessage(err, fallback)` in
      `utils/format.js` that flattens any detail shape (string / array of `{msg,...}` / object)
      into a readable string; routed all Compatibility + Compare catch blocks through it.
      (2) Under that, the real failure surfaced: `POST /api/astrology/compatibility` declared
      its birth fields as **bare function args**, so FastAPI treated them as **query params**
      while the frontend sent a JSON body → six `"Field required"`. Added a `CompatibilityRequest`
      Pydantic model (flat keys matching the existing `services/api.js` payload) and switched the
      endpoint to accept it as the request body. (3) Markdown parity: the Compatibility + Compare
      AI readings rendered raw text in a `white-space: pre-wrap` div; both now use `<ReactMarkdown>`
      with the shared `sbc-ai-markdown` styles, matching the Sarvatobhadra reading. Verified:
      `main.py` parses, both pages lint clean. NOTE: restart the backend to pick up the new route
      signature.

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
      `_build_sarvatobhadra_prompt` — a jargon-light, ~500-word reading (headline tone,
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
- [x] **Post-review polish 2026-06-29**: (1) the AI reading is now rendered with
      `react-markdown` (was raw text, so `*  **bold**` leaked through) — added scoped
      `.sbc-ai-markdown` spacing in `Dashboard.css`; reading length bumped to ~500 words.
      (2) Desktop layout reflowed to **~75% chakra / 25% sidebar** via `.sbc-layout`
      (stacks below 900px); chakra cap raised 460→760px with `clamp()`-scaled cell + graha
      chip text so it stays legible larger; anchors/findings became a compact, smaller-text
      sidebar.

## Learn the Chart — AI quiz & graded feedback (DONE 2026-06-29)

Owner ask (2026-06-29): a feature where the user can "learn to make sense of a
chart." Pick a person's chart → the AI generates questions about *that* chart →
the user answers → the AI grades each answer, says what's right/wrong and **why**,
with detailed reasoning. A guided, interactive way to actually learn jyotish from
your own (or a saved) chart rather than just reading a generated report.

**SHIPPED 2026-06-29** — all plan items below done. Backend: `quiz.py`
(`quiz_sessions` collection) + `llm_service.generate_quiz`/`grade_quiz_answers`
(strict-JSON gen + grading, robust `_extract_json` tolerant of fences/prose, MCQ
graded deterministically in `main.py`, free-text graded by the LLM against
`expected_points` + chart facts) + endpoints `POST /api/astrology/quiz/generate`,
`/quiz/grade`, `GET /quiz/history`, `/quiz/stats`, `DELETE /quiz/{id}`. The answer
key (correct_index/expected_points/rationale) is stored server-side and stripped
from the generate response (`quiz.public_items`) so it can't be read in devtools;
revealed only in graded results. Adaptive difficulty reads `get_stats` →
`suggest_level` + weak-topic emphasis. Frontend: `LearnChartPage.js` (route
`/learn`, nav + dashboard card, `GraduationCap` icon) with setup → MCQ → free-text
→ results → history phases, `learn.*` i18n (en full; hi/sa nav+card). Verified:
backend imports + `_extract_json`/`_normalize_items`/`compute_topic_scores`/
`suggest_level` unit-tested; `npm run build` compiles, lint clean, locale JSON valid.

**Fix 2026-06-29 — "Empty response from model" on small local models:** gemma4:12b
returned `done_reason:length, eval_count:4096, response:""` — the full /ask context
(~3.5k tokens incl. ashtakavarga+shadbala+all vargas) left no room, so it exhausted
its output budget before emitting any JSON. Fixes: (1) `_quiz_context()` in `main.py`
tailors the context to the chosen topics (planets→base only; yogas→yogas+doshas;
dashas→dasha_tree+transits; vargas→D1/D9/D10) — drops the heavy sections; (2) raised
the quiz output budget to 8192 tokens; (3) `generate_quiz`/`grade_quiz_answers` retry
once on empty/unparseable output, grading degrades to the per-item rationale instead
of 500ing, and the error now guides the user to fewer questions / a bigger model.
Verified gemma4:12b returns a full 5-item quiz (~87s on this box).

**Decisions captured (owner, 2026-06-29):**
- **Answer format:** both — an **MCQ warm-up → free-text** flow. Each session/round
  starts with multiple-choice to build confidence, then moves to open-ended
  free-text questions the AI grades with partial credit + explanation.
- **Difficulty:** offer **both modes, user chooses** — either manually pick
  Beginner / Intermediate / Advanced, *or* turn on **Adaptive** (difficulty auto
  raises/lowers based on recent scores). A simple toggle: "Adaptive" on/off; when
  off, the level selector drives it.
- **Topics (all four, user-selectable per session):** Planets/signs/houses ·
  Yogas & doshas · Dashas & transits · Vargas (D9/D10 etc.). Default = all on.
- **Progress:** **save per user** in Mongo — quiz history, per-topic scores, weak
  areas, streaks. Feeds the "review your weak spots" view and Adaptive difficulty.

### Plan

- [x] **Reuse the existing chart-context path.** Questions and grading MUST be
      grounded in real computed facts, not the model's astro guesses. Build the quiz
      context from the same `chart_context.py` builder that `/api/astrology/ask`
      uses (Rasi/D9 placements, lagna, yogas, doshas, current dasha/bhukti,
      transits, requested vargas). The chart facts are the **answer key**: the
      grader scores the user against this context, not against free-floating model
      opinion. This also keeps it provider-agnostic (qwen/gemini/openai/compat) via
      the user's saved model config + `_resolve_cfg`, and rate-limited like the
      other AI endpoints.

- [x] **Backend — quiz generation** (`llm_service.py` + `main.py`):
      `generate_quiz(chart_context, topics, level, n_mcq, n_freetext)` →
      `POST /api/astrology/quiz/generate`. Prompt instructs the model to emit
      **structured JSON** (not prose): a list of items, each with `id`, `topic`,
      `difficulty`, `format` (`mcq`|`free`), `prompt`, for MCQ `options[]` +
      `correct_index`, and a hidden `rationale`/`expected_points[]` used later for
      grading. Validate/parse the JSON server-side (reject + retry once on malformed
      output). Questions must reference *this* chart ("Your Moon is in Scorpio in
      the 4th — what does that suggest about…") using the real placements.

- [x] **Backend — grading** (`llm_service.py` + `main.py`):
      `grade_answers(chart_context, items, user_answers)` →
      `POST /api/astrology/quiz/grade`. MCQ graded **deterministically** against
      `correct_index` (no LLM needed → cheap + reliable). Free-text graded by the
      LLM against `expected_points` **and** the chart facts: returns per-item
      `score` (0–1 / partial credit), `verdict` (correct / partial / incorrect),
      `what_was_right`, `what_was_wrong`, and **detailed `reasoning`** citing the
      actual chart. Plus a session summary: overall %, per-topic breakdown, and 2–3
      "study these next" pointers. Guardrails: same jargon-light, no
      death/disease/precise-date tone as the Sarvatobhadra reading.

- [x] **Backend — persistence** (`database.py` / new `quiz.py`): a `quiz_sessions`
      collection keyed by `user_id` + `profile_id`: stored items, answers, grades,
      topic scores, level, adaptive flag, timestamps. Endpoints:
      `GET /api/astrology/quiz/history` (list past sessions) and
      `GET /api/astrology/quiz/stats` (per-topic mastery, streak, weak areas →
      powers Adaptive + the review view). Decide: store the full Q/A transcript
      (richer review) vs just scores (lighter) — lean to full transcript, it's small.

- [x] **Backend — adaptive difficulty:** when Adaptive is on, `quiz/generate`
      reads `quiz/stats` to pick the next level per topic (weak topic → easier &
      more questions; mastered topic → harder / fewer). When off, honor the
      user-selected level. Keep the rule simple and explainable (e.g. rolling avg of
      last N items per topic with thresholds).

- [x] **Frontend — new page** `LearnChartPage.js`, route `/learn` (gated by
      `ProtectedRoute`), nav entry + a Dashboard feature card, in the existing
      saffron Vedic style using `PageHeader`/`ProfileBanner`/`Card`/`Button`.
      Flow: profile picker → setup panel (topic checkboxes, level selector +
      Adaptive toggle, question counts) → **MCQ round** (tap an option, immediate or
      end-of-round reveal) → **free-text round** (textarea per question) → **Submit**
      → **results view**: per-question right/wrong/partial with the AI's reasoning
      (render via `react-markdown` like the SBC reading), session score, per-topic
      bars, and "study next" chips. Add a **History / progress** view (past sessions,
      mastery per topic, streak, "drill my weak spots" shortcut).

- [x] **Frontend — API + i18n:** add `generateQuiz`/`gradeQuiz`/`getQuizHistory`/
      `getQuizStats` to `services/api.js`; add a `learn.*` i18n block (en full;
      hi/sa nav + card labels, body falls back to en — same pattern as `sbc.*`).

- [x] **Verify:** backend imports + a JSON-schema sanity test on generate/grade
      output; one end-to-end quiz on a known chart (e.g. the verified True-Chitra
      chart) where MCQ keys and free-text reasoning actually match the placements;
      `npm run build` compiles; lint clean; locale JSON valid.

### Open questions (non-blocking — sensible defaults chosen, will confirm before/while building)
- Quiz length per session? Default: ~5 MCQ + ~3 free-text, user-adjustable.
- Reveal MCQ answers immediately or only at end-of-round? Default: end-of-round
  (keeps it a real test; less hand-holding).
- Should the quiz also be answerable for *another person's* shared chart, or only
  the user's own saved profiles? Default: any saved profile the user can view.

---

## Map location picker — pick birthplace on a map (DONE 2026-06-29)

Goal: let users set the birthplace by **clicking/dragging a pin on a map** (the
"Google Maps" feel) in addition to the existing text search — using **only free,
key-less services** (no paid Google/Mapbox billing).

- [x] **Stack: Leaflet + OpenStreetMap, $0 / no API key.** `react-leaflet@4` +
      `leaflet@1.9` with the default OSM raster tiles (free; polite `User-Agent`
      already set on our Nominatim calls). Coordinates are captured client-side from
      the pin/click — no geocoding call needed just to get lat/long. Adds ~50 KB gz
      to the main bundle.
- [x] **Backend — reverse geocode endpoint.** `POST /api/location/reverse`
      ({lat,long} → place + tz). `AstrologyCompute.reverse_geocode` computes the
      timezone **offline** via `timezonefinder` (works for any clicked point, no
      network) and uses Nominatim *reverse* only for a friendly place name; if that
      lookup fails/rate-limits it still returns coords + tz with a "lat, lon" label,
      so a clicked point is always usable. Reuses the geopy/timezonefinder deps that
      `search_location` already pulled in — no new backend packages.
- [x] **Frontend — `MapPicker` component.** Three ways to set location, all free:
      type a place (existing `LocationSearch`), **click/drag the pin**, or **"Use my
      location"** (browser `navigator.geolocation`). Collapsible "Pick on map" toggle
      keeps the form compact; saffron-themed to match. Reverse-geocode is **debounced
      (600 ms)** so a drag stays well under Nominatim's 1 req/sec policy. Wired into
      `ProfileSelectionPage` next to `LocationSearch`, sharing `handleLocationSelect`.
- [x] **Production kill-switch (both layers).** Frontend
      `REACT_APP_ENABLE_MAP_PICKER` (default true) hides the map and falls back to
      text search; backend `MAP_PICKER_ENABLED` (default true) makes
      `/api/location/reverse` return 403 — defense in depth. Both documented in the
      `.env`/`.env.example` files; `/health` now reports `map_picker_enabled`.
- [x] **Verify:** `reverse_geocode(28.61,77.21)` → "…New Delhi, Delhi, India", tz
      5.5 (offline tz confirmed); config flag loads; `npm run build` compiles; lint
      clean. NOTE: same *current-DST* tz caveat as text search — fine for picking a
      place, a known limitation for historical births.
- [x] **Search ⇄ map two-way sync (FIXED 2026-06-30).** Reported: after a text
      search the map still opened on the old/empty spot. Cause — `MapPicker` read
      `latitude`/`longitude` props only in the initial `useState`, so later changes
      never moved the pin. Added a prop-sync `useEffect` that drops/recentres the pin
      whenever the coords change (text search OR editing an existing profile), with an
      epsilon guard (`markerRef`) so it ignores the echo of the user's own pin
      drag/click and never fights the map back. Search → open map now lands on the
      searched place, and the user can still drag to refine.

---

## 9. Engine features to resurface to the web (planned 2026-06-30)

Audit of `src/jhora/...` vs the web backend (`astrology.py` exposes ~18 compute methods;
`main.py` ~30 astrology endpoints) found a large set of classical capabilities the engine
supports that have **no web surface**. Owner picked the following to add (2026-06-30):
**all four feature pages below + Longevity**. (Graha-drishti / aspects — formerly backlog
— was since SHIPPED, see §8.9.) Build order suggestion: 9.1 Varshaphal → 9.2 Almanac →
9.4 Raja Yogas/more dashas → 9.3 Pancha Pakshi → 9.5 Longevity (each independent; sequence
is by value).

Each follows the established pattern: a thin `AstrologyCompute` method (server-injects
birth details + ayanamsa, resets global state after), an auth-protected endpoint in
`main.py`, a dedicated page in the saffron Vedic style (`PageHeader`/`ProfileBanner`/
`Card`), the North/South `Kundali` where a chart is shown, an optional on-demand AI
reading via `_resolve_cfg` (model the user picked in Ask AI Astrologer, rate-limited),
and i18n keys (en full; hi/sa nav+card, body falls back to en — the `sbc.*`/`learn.*`
pattern). Where useful, also publish as a smart-lookup **tool** (§8.9) so the AI can fetch it.

### 9.1 Varshaphal / Annual Horoscope (Tajaka) (P1) — the biggest gap

An entire classical sub-system with zero web presence. The Tajaka/Varshaphal chart is the
solar-return for a chosen year (Sun returns to its natal longitude), read with its own
yogas, sensitive points (Sahams), and annual dashas.

Engine entry points (verified to exist):
- **Annual chart:** `horoscope/transit/tajaka.py → varsha_pravesh(jd_at_dob, place,
  divisional_chart_factor=1, years=N)` returns the year-entry chart.
- **Sahams (37):** `horoscope/transit/saham.py` — `punya_saham`, `vidya_saham`,
  `yasas_saham`, `mitra_saham`, `mahatmaya_saham`, … (each takes `planet_positions`,
  `night_time_birth`). Sensitive points like Western "Arabic parts".
- **Tajaka yogas:** `horoscope/transit/tajaka_yoga.py` — Ishkavala, Induvara, Ithasala,
  Eesarpha, Nakta, Yamaya, etc. (`*_from_jd_place` variants exist for several).
- **Tajaka aspects:** `tajaka.py` trinal/sextile/square/benefic-aspect helpers (the
  Tajaka aspect scheme differs from Parashari drishti — relevant to the annual reading).
- **Annual dashas:** `dhasa/annual/mudda.py → mudda_dhasa_bhukthi(jd,place,years,…)`,
  `dhasa/annual/patyayini.py → get_dhasa_bhukthi(...)`, plus `varsha_vimsottari_*` and
  `dhasa/raasi/narayana.py → varsha_narayana_dhasa_bhukthi(...)`. (`horoscope/main.py`
  has `_get_varsha_vimsottari_dhasa` / `_get_varsha_narayana_dhasa` as references.)

Plan — **SHIPPED 2026-07-02**:
- [x] **Backend** `AstrologyCompute.get_varshaphal(dob, tob, place, year, lat, lon, tz,
      ayanamsa)` → the annual (Tajaka) chart formatted for the `Kundali`, the year-entry
      instant, the **Muntha** (natal Lagna sign advanced one sign per completed year, with
      its house in the annual chart), the **year-lord (Varsheshwara)** via
      `tajaka.lord_of_the_year`, the 8 curated Sahams (Punya/Vidya/Yasas/Mitra/Karma/Roga/
      Vivaha/Puthra — each a longitude → sign+degree+house, day/night formula honoured via
      the annual entry's sunrise/sunset), the present **Tajaka yogas** (Ishkavala/Induvara
      chart-level + Ithasala/Eesarpha planet pairs, each wrapped so a failure is skipped and
      engine debug prints muffled), and the **annual Mudda (Varsha Vimsottari) maha-dasha**
      (9 periods with start/end + `current`). Ayanamsa set/reset like every method. KEY
      DETAIL pinned empirically: `varsha_pravesh(years=N)` returns the solar return in
      `birth_year+N-1`, but `lord_of_the_year`/`muntha`/`mudda` advance `jd + years·year_value`
      — so the code uses `years=age+1` for the chart and `age` for the rest, where
      `age = year − birth_year`. Guards `year < birth_year`.
- [x] **Alternate annual-dasha systems** (2026-07-02): a **Mudda / Patyayini / Varsha-Narayana**
      picker on the Varshaphal page (persisted `varsha_dasha`), `dasha_system` param on
      `get_varshaphal` + the endpoint. Engine: `mudda.mudda_dhasa_bhukthi` (planet, dur=days),
      `patyayini.get_dhasa_bhukthi(jd_years,…)` (planet incl. **Lagna** as a lord, dur=float
      years, takes the **annual** JD from `next_solar_date(…, years=age+1)`), and
      `narayana.varsha_narayana_dhasa_bhukthi(dob,tob,…)` (**sign** lords). A shared
      `_annual_dasha()` normalizes all three to `{system, system_key, lord_type, periods:
      [{lord_name,start,end,current}]}` by deriving each end from the **next** period's start
      (raw-last falls back to start+duration) and **dropping same-calendar-day rows** — which
      cleanly removes Patyayini's sub-day slivers (very weak planets) and Narayana's zero-span
      compression tail, no unit-guessing. Response also lists `dasha_systems`. Table header
      switches Period lord ⇄ Period sign by `lord_type`. Verified: mudda 9 / patyayini 7 /
      narayana 16 periods on the test chart, correct current period in each, bogus→mudda.
      UX (2026-07-02): the system picker lives in the **top controls bar** (with the year
      stepper + chart-style toggle), not buried by the bottom table; switching systems does a
      **soft in-place refresh** of just the dasha card (small spinner, no full-page reload /
      scroll jump) via a `dashaRef` so the main fetch isn't re-triggered.
- [x] **Endpoint** `POST /api/astrology/varshaphal?year=YYYY&ayanamsa=X` (auth), `BirthDetails`
      body + `year` query param. Returns 400 on pre-birth year.
- [x] **Frontend** `VarshaphalPage.js` (route `/varshaphal`, dashboard card + drawer entry):
      a **year stepper** (± with a numeric input, floored at the birth year; default = current
      calendar year), the annual `Kundali` (North/South toggle, selected ayanamsa, exportable),
      an info-pill row (year / entry instant / annual Lagna / Muntha / year-lord / ayanamsa),
      an annual placements table, a Sahams table, a Tajaka-yogas card grid, and the annual-dasha
      table (current period highlighted via a new reusable `.data-table tr.is-current` rule).
- [x] **On-demand AI reading** (`llm_service.analyze_varshaphal` + `_build_varshaphal_prompt`)
      — a ~500-word year-ahead forecast grounded in the computed Muntha/year-lord/Sahams/Tajaka
      yogas/annual-dasha (jargon-light, safety footer, no death/disease/precise-date),
      model-config aware via `_resolve_cfg` + rate-limited. `POST /api/astrology/varshaphal-analysis`
      (`VarshaphalAnalysisRequest`); page has a "Get year-ahead reading" card using the model
      picked in Ask AI Astrologer, cleared when the year changes.
- [x] **Smart-lookup tool** (§8.9): `get_varshaphal(year)` published as the **13th tool**
      (`tools.py`, birth-details server-injected) + in `ALWAYS_TOOLS`, `_DISPLAY` (Timing), so
      the main astrologer can pull an annual snapshot for "how is 2026 for me?". Verified via
      `tools.dispatch`.
- [x] i18n `nav.varshaphal`, `dashboard.features.varshaphal` (en/hi/sa) + full `varshaphal.*`
      block (en; hi/sa fall back). Verified: `varsha_pravesh` round-trips on the 1990-05-15
      True-Chitra chart (entry 2026-05-15 for year 2026, year-lord Mercury, 8 sahams, 9 dasha
      periods); prompt renders ~1k tokens with real data; backend imports clean (13 tools, both
      routes); `npm run build` green (+2.7 kB); ESLint clean; locale JSON valid.

### 9.2 Almanac extensions — Eclipses, Festival/Vratha calendar, Hora (P1) — SHIPPED 2026-07-02

Grow the existing self-contained `PanchangaPanel` into a fuller almanac, or a dedicated
**Almanac/Calendar page**. All three are date-range/location driven (not birth-chart
bound), so they can live on one page with the current Panchanga.

Engine entry points:
- **Eclipses:** `panchanga/eclipse.py → next_solar_eclipse(...)`, `next_lunar_eclipse(...)`
  (return type/time; visibility from the place where swe supports it).
- **Vratha / festival & special-date finders:** `panchanga/vratha.py` — `pradosham_dates`,
  `special_vratha_dates`, `tithi_dates` (→ Ekadashi/Amavasya/Purnima/Sankashti by tithi
  index), `nakshathra_dates`, `yoga_dates`, `_ashtaka_manvaadhi_dates`. All take
  `(panchanga_place, start_date, end_date, …)`.
- **Conjunctions (Graha Yuddha / planetary meetings):** `vratha.py → conjunctions(place,
  start, end, minimum_separation_longitude, planets_in_same_house=False)` — find upcoming
  planetary conjunction dates.
- **Hora (planetary hours):** the day's hora-lord sequence for muhurta (check
  `panchanga/drik.py`/`drik1.py` for a `hora`/`hora_lord` helper; if absent, derive from
  sunrise→sunset / weekday-lord ordering — small assembly).

Plan:
- [x] **Backend** methods on `AstrologyCompute`: `get_planetary_hours(date, place, lat, lon,
      tz)` (24 horas — 12 day sunrise→sunset + 12 night — via `drik.shubha_hora`, each tagged
      benefic/malefic and the running daytime hora flagged), `get_eclipses(place, lat, lon, tz,
      from_date, count=3)` (next N solar + N lunar, GLOBAL visibility, each stepping past the
      previous max), `get_festival_dates(place, lat, lon, tz, start, end, types[])` (tithi-driven
      Ekadashi/Pradosham/Purnima/Amavasya/Sankashti + Vinayaka-Chaturthi/Krishna-Ashtami via
      `vratha.tithi_dates`). **KEY gotcha:** the vendored `eclipse.next_lunar_eclipse` returns
      the maximum instant WITHOUT the tz offset its sibling instants carry (a swe wrapper quirk),
      so the lunar maximum is derived as the midpoint of the (correctly localized) partial phases
      instead of trusting that field — no `src/` edit. Constants: `HORA_PLANETS`/`HORA_BENEFICS`,
      `FESTIVAL_TYPES`/`DEFAULT_FESTIVAL_TYPES`.
- [x] **Endpoints** (auth, GET): `/api/astrology/almanac/hora`, `.../almanac/eclipses`,
      `.../almanac/festivals` (`types` = comma-separated keys), `.../almanac/conjunctions`.
      Verified against known 2026 dates: total solar eclipse **2026-08-12**, partial lunar
      **2026-08-28**; July Ekadashis 07-10 & 07-24, Purnima 07-28, Amavasya 07-13.
- [x] **Conjunctions (Graha Yuddha)** ADDED 2026-07-02: `get_conjunctions(place, lat, lon, tz,
      start, end, max_sep=3.0)` scans the five tara grahas (Mars/Mercury/Jupiter/Venus/Saturn —
      Sun/Moon/nodes excluded by tradition) day-by-day, collapsing consecutive in-range days into
      one event with the closest approach (min separation + date) and a war flag (<1°). Rolled our
      OWN one-pass daily scan rather than the engine's `vratha.conjunctions` — the latter has debug
      `print()`s and returns only thin "day within X°" data (no separation/closest-date). Frontend:
      a fifth `ConjunctionPanel` on the Almanac page (date-range picker, war tag). Verified 2026:
      Venus–Jupiter 0.06° on 06-10, Mars–Saturn 0.11° on 04-20, etc.
- [x] **Frontend**: dedicated **`AlmanacPage`** (route `/almanac`, dashboard card + nav drawer,
      `CalendarDays` icon) with a page-level location toggle (birth place vs current geolocation,
      reusing the PanchangaPanel pattern) shared across four self-contained sections: **Today**
      (the existing `PanchangaPanel`, now with a `hideLocationToggle` prop so it sits under the
      shared control), **Planetary Hours** (day/night hora grids, current hora highlighted, per-day
      date picker), **Eclipses** (solar/lunar cards with begin/max/end in local time), **Festivals**
      (date-range picker + toggleable type chips, sorted list). Saffron/gold identity, `almanac-*`
      classes in `Dashboard.css`.
- [x] i18n `almanac.*` (en full; hi/sa get nav + dashboard-card labels, body falls back to en —
      the `sbc.*`/`learn.*` pattern). Same current-DST tz caveat as the rest of the almanac. Build
      + lint clean. All five sections shipped (Panchanga · Hora · Eclipses · Festivals · Conjunctions).

### 9.3 Pancha Pakshi Sastra (P2) — unique daily-timing system

A bird-cycle predictive timing system (Tamil Siddha tradition) that exists only in the
desktop PyQt UI (`ui/pancha_pakshi_sastra_widget.py`), never on the web. Assigns the
native a "birth bird" from nakshatra+paksha, then rates activities by the bird's
state (rule/eat/walk/sleep/die) across the day's segments.

Engine entry points: `panchanga/pancha_paksha.py` — `construct_pancha_pakshi_information(
dob, tob, place, nakshathra_bird_index=None)`, `_get_birth_bird_from_nakshathra`,
`_get_paksha`, `get_matching_pancha_pakshi_data_from_db(bird, weekday, paksha)`.

Plan — **SHIPPED 2026-07-02**:
- [x] **Backend** `AstrologyCompute.get_pancha_pakshi(dob, tob, place, lat, lon, tz, date)`
      → birth bird (fixed from birth star + paksha), and the query day's activity-strength
      timeline: 10 main periods (5 daytime from sunrise + 5 nighttime) each split into 5
      sub-windows, coloured by effect (very-bad..very-good) with the running sub-window
      flagged, plus best/avoid summaries (top/bottom 5 by effect then rating). Built our OWN
      clean JSON from the raw `get_matching_pancha_pakshi_data_from_db` rows + the birds/
      activities/relations/effect constant tables — NOT the UI-oriented
      `construct_pancha_pakshi_information` (which is coupled to `resource_strings`/language +
      image filenames). Timing mirrors the engine (sunrise + day_length/5 per main period,
      sub-duration = df·period). `date` defaults to today in the place's tz. Ayanamsa-independent.
- [x] **Endpoint** `POST /api/astrology/pancha-pakshi?date=…` (auth, `BirthDetails` body).
- [x] **Frontend** `PanchaPakshiPage.js` (route `/pancha-pakshi`, dashboard card + drawer,
      `Bird` icon): birth-bird badge, best/quiet-windows summary cards (green/red), a
      colour-coded day-timeline (10 segments × 5 sub-cells, current window outlined) with a
      strength legend, a date picker + "Today" reset, and a jargon-light AI day-guide
      (`analyze_pancha_pakshi` via `_resolve_cfg`, model the user picked in Ask, rate-limited,
      safety footer). `pp-*` classes in `Dashboard.css` (saffron/terracotta identity).
- [x] **Smart-lookup tool** (§8.9): `get_pancha_pakshi(date)` published as a tool (in
      `ALWAYS_TOOLS` + `_DISPLAY` Timing) returning birth bird + best/avoid windows, so the
      main astrologer can answer "what's a good time today for X".
- [x] i18n `nav.panchaPakshi`, `dashboard.features.panchaPakshi` (en/hi/sa) + full
      `panchaPakshi.*` block (en; hi/sa fall back). Verified live: 1990-05-15 chart → birth bird
      **Owl** (from Uttara Ashadha, Krishna paksha), 10 segments, best window 13:40–14:06
      (Ruling/very-good). Build +lint clean.

### 9.4 Raja Yogas (dedicated) + expanded Dasha systems (P2) — SHIPPED 2026-07-02

- [x] **Raja Yogas card.** `AstrologyCompute.get_raja_yogas(dob,tob,place,…,ayanamsa)` +
      `POST /api/astrology/raja-yogas`. Surfaces (a) the fundamental **Kendra-Trikona** raja
      yogas via `raja_yoga.get_raja_yoga_pairs_from_planet_positions` (quadrant lord + trine
      lord associated), each with a coarse **strength** blended from both planets' dignity
      (`const.house_strengths_of_planets`), and (b) the named special types via
      `get_raja_yoga_details` — **Dharma-Karmadhipati / Vipareeta / Neecha-Bhanga** — with
      their classical description/benefits + the forming planet-pair label. Rendered as a
      **Raja Yogas** card on the **Birth Chart page** (golden accent, count header, strength
      chips, graceful "none found"), loading independently like the Yogas/Doshas cards.
      Published as a `get_raja_yogas` smart-lookup tool too. Verified across charts (1995-08-22
      → 3 Kendra-Trikona pairs; 2000-01-01 → Dharma-Karmadhipati + Neecha-Bhanga; test chart
      1990-05-15 → none, card shows the empty note).
- [x] **More dasha systems.** Added **10** systems to `SUPPORTED_DASHAS` + `get_dasha_periods`,
      all normalizing to the existing flat maha-period shape (graha-lord vs rasi-sign),
      verified to return dated periods on the test chart: **graha** — Shodasottari (8),
      Dwadasottari (8), Panchottari (7), Shatabdika (7 — `graha/sataatbika.py`); **raasi** —
      Kendradhi-Rasi (24), Sudasa (23), Drig (24 — takes `planet_positions,dob,tob`, special-
      cased), Chara (12), Sthira (12), Trikona (12). All use `dhasa_level_index=1` for the flat
      maha list. They auto-appear in the Dhasa page's "Other Dasha Systems" picker (labels come
      from the backend, no i18n needed). Now 14 systems total (`/dasha-systems` count = 14).
- [x] **Sudarsana Chakra** (its own renderer, per owner). `get_sudarsana_chakra(…,year_offset)`
      + `POST /api/astrology/sudarsana-chakra`: the annual (solar-return) chart for
      `year_offset` past birth (0 = natal, via `drik.next_solar_date`), returned as one planet
      set + three reference lagnas (Lagna / Chandra / Surya). A collapsible **Sudarsana Chakra**
      section on the Dhasa page renders the three wheels as three Kundalis (North/South toggle,
      selected ayanamsa) with a ±year stepper. Simplified surface (three ascendants) rather than
      the engine's rotating house-lists — clean reuse of the existing `Kundali`.
- [x] i18n: `dhasa.sudarsana.*` (en; hi/sa fall back). Build + lint clean; all 10 dashas +
      raja-yogas + sudarsana verified live via authenticated HTTP.

### 9.5 Longevity / Ayur (P2) — jargon-light, with disclaimer (owner approved 2026-06-30)

Owner OK'd adding it provided it's gentle and clearly framed. `prediction/longevity.py →
life_span_range(jd, place)` returns a life-span band (short/medium/long ayu via the
classical Balarishta/Alpa/Madhya/Purna-ayu checks + Jaimini corrections).

Plan — **SHIPPED 2026-07-02**:
- [x] **Backend** `AstrologyCompute.get_longevity(dob, tob, place, lat, lon, tz, ayanamsa)`
      → the ayu *category* (Alpa/Madhya/Purna) + the three contributing sign-pair verdicts
      (Lagna-lord vs 8th-lord, Lagna vs Moon, Lagna vs Hora-lagna). NOT a death date/age.
      Ayanamsa reset after. **KEY:** the engine's `longevity.life_span_range` has a Py3 bug
      (`counter.keys()[0]` crashes in the all-three-agree branch — which is exactly the test
      chart's case), so we **reimplement the tiny aggregation** (reproducing the movable/fixed/
      dual `_get_aayu` matrix, a pure classical rule) while reusing the same chart inputs
      (`charts.rasi_chart`, `house.house_owner_from_planet_positions`, `drik.hora_lagna`) — no
      edit to vendored `src/`.
- [x] **Endpoint** `POST /api/astrology/longevity` (auth).
- [x] **Frontend**: a card on the **Advanced** page (not its own page) titled "Ayu — vitality
      indication" with an intro + a 3-segment band highlighting Alpa/Madhya/**Purna**, a factors
      table, and an explicit disclaimer (conditional, multi-factorial, never a death date/medical
      advice). Loads independently (doesn't gate the page spinner).
- [x] AI: published as a `get_longevity` smart-lookup **tool** with an explicit guardrail in its
      description ("use ONLY when the person explicitly asks about vitality/longevity, frame it
      gently as conditional"). i18n `advanced.longevity.*` (en; hi/sa fall back). Verified live:
      test chart → **Alpa** with the three Alpa factors. Build + lint clean.

### 9.6 Previously-parked engine capabilities — NOW SELECTED (owner ask 2026-07-02)

Owner asked to build the six formerly-parked items. Clarifying round answered 2026-07-02:
**(1)** Sphuta + full 37 Sahams + Argala → a **new dedicated "Sensitive Points" page**.
**(2)** **Both** the Vedic clock and the Vakra-gathi retrograde plot → their **own page**
(web SVG reimplementations of the desktop pyqtgraph widgets). **(3)** **Full treatment** —
each new page gets an on-demand AI reading + smart-lookup tool(s). **(4)** Surya-Siddhanta +
Hijri → **extend the existing Almanac/Panchanga** (SS as an alternate-engine toggle, Hijri
date shown). Follows the established pattern (thin `AstrologyCompute` method that server-
injects birth details + resets global state, auth endpoint, saffron page, on-demand AI via
`_resolve_cfg`, i18n, and a §8.9 smart-lookup tool). See **§11** for the live build log.

**Engine-entry notes pinned during the audit (2026-07-02):**
- **Sphuta** (`chart/sphuta.py`): ~15 sphutas — each `fn(drik.Date(y,m,d), (h,m,s), place)`
  returns `(sign, degree)`. Note `dob` must be a `drik.Date`, not a tuple.
- **Sahams** (`transit/saham.py`): 36 natal sahams — `fn(planet_positions, night_time_birth)`
  (a few take positions only → wrap in try/except TypeError); return a raw longitude.
- **Argala** (`chart/house.py → get_argala(house_to_planet_dict)`): returns `(argala,
  virodhargala)`, each 12 ascendant-relative rows × 4 (planet indices as strings) for the
  argala houses [2,4,5,11] / virodhargala [12,10,9,3].
- **Retrograde**: `drik.planets_in_retrograde(jd,place)` (list) +
  `drik.next_planet_retrograde_change_date(planet, Date, place)` (next station);
  `ui/vakra_gathi_plot.get_retrogression_orbit_data(planet)` is a pure-numpy epicycle
  (x,y) loop — reimplement server-side (no pyqtgraph), downsample for the SVG.
- **Vedic clock**: build from `drik.sunrise/sunset` + ghati math (1 ghati = 24 min from
  sunrise, 60/day) + reuse `drik.shubha_hora` for the running hora lord.
- **Surya-Siddhanta**: the vendored `panchanga/surya_sidhantha.py` is **buggy**
  (`kali_ahargana` calls `drik.vaara(jd)` with no `place`; `_planet_mean_longitude` does
  `.index` on a dict) — DO NOT call it. Instead use the reliable **`SURYASIDDHANTA`
  ayanamsa mode** (in `const.available_ayanamsa_modes`) as the alternate panchanga engine.
- **Hijri**: `panchanga/hijri.py` imports `pyIslam`/`hijridate` (not installed) at module
  top → can't import it. Reimplement the tiny place-independent **tabular** formula inline
  (`_islamic_from_jd_tabular`, pure arithmetic).

---

## 10. Owner-requested additions (2026-07-02)

### 10.1 Show Arudha padas (AL/UL/A2–A11) in the charts (P1) — SHIPPED 2026-07-02

**Correction 2026-07-02:** this item was originally written as "show *nakshatra* padas in the
charts", but the owner clarified they meant the **Arudha padas** — Arudha Lagna and the other
bhava arudhas — not nakshatra padas. (A first pass had implemented the nakshatra-pada version;
it was reverted and replaced with this.) The nakshatra-pada-on-cells idea is **dropped** (padas
already appear in the D1 nakshatra table where they matter).

The backend **already computes** the 12 bhava arudhas via `arudhas.bhava_arudhas_from_planet_positions`
(surfaced by `get_chart_details` → `arudha_padas`, and shown as a DataField grid on the Advanced
page), but they were **not drawn in the chart cells** — the North/South `Kundali` cells showed only
planet name + degree.

Owner decision (2026-07-02): show the arudhas **on the chart cells** (both North & South).

- [x] **Backend.** `get_chart_details` `arudha_padas` entries now also carry `sign` (1-based
      rasi, Aries=1) and `short` (compact chart label: **AL** for bhava 1, **UL** for bhava 12,
      else `A2..A11`) alongside the existing `bhava`/`label`/`sign_name`, so the frontend can
      place each marker in the right cell. Verified live (AL→Taurus, A2/A3 both →Scorpio, UL→
      Aquarius on the 1990-05-15 test chart — multiple arudhas per sign handled).
- [x] **Chart cells (North + South).** `NorthIndianChart` and `SouthIndianChart` gained
      `arudhas` + `showArudhas` props. For each rasi cell, the arudhas whose `sign` matches are
      appended as a distinct **italic temple-gold** item (North: one joined line `AL A7`, size
      floored & respecting the crowded-house graduated sizing; South: a `.si-pl-arudha` pill),
      clearly separated from indigo planets and the saffron lagna. Gated behind a **"Show arudhas"
      toggle** on the Birth Chart page (persisted `localStorage.showArudhas`, off by default,
      `Landmark` icon), sitting next to the aspects toggle.
- [x] **On the Rasi (D1) AND every divisional (varga) chart** (owner ask 2026-07-02, follow-up).
      Bhava arudhas are per-chart (they depend on that chart's lagna/positions), so each chart
      gets its **own** arudhas rather than reusing D1's: a shared `_format_arudha_padas()` helper
      shapes the raw `bhava_arudhas_from_planet_positions(...)` output, and it's now called on the
      D1 and D9 charts inside `calculate_birth_chart` (returned as `d1_arudha_padas` /
      `d9_arudha_padas`) and on each divisional chart inside `calculate_divisional_chart`
      (returned as `arudha_padas`). The Rasi chart sources its arudhas from the birth-chart
      response (dropping the separate `getChartDetails` call); the varga picker passes each
      varga's own arudhas (D1/D9 reused from the birth-chart response, others from the
      divisional-chart response) into the varga `Kundali`. Verified live that they differ per
      varga (AL → Taurus D1 / Cancer D9 / Aquarius D10 / Scorpio D60 on the 1990-05-15 chart).
- [x] i18n: added an `arudhas.showOnChart` / `arudhas.hideOnChart` block (en; hi/sa fall back).
      `npm run build` green, ESLint clean, locale JSON valid.
- [x] **AI capability — let the model use arudhas** (owner ask 2026-07-02). Mirrors exactly how
      graha drishti was wired (dedicated tool + pass-all section + system-prompt rule):
      - Backend `AstrologyCompute.get_arudha_padas(...)` — a focused slice of `get_chart_details`
        returning just the D1 bhava arudhas (AL/UL/A2..A11 with `sign`/`short`) + an explanatory
        `note`; ayanamsa set/reset like the others.
      - **Smart-lookup tool**: `get_arudha_padas` published as a tool in `tools.py`
        (`SECTION_TOOL["arudhas"]`, catalog "Arudha padas (AL/UL)" under Core chart) so the model
        can fetch it on demand; tri-state seed/tool/off honoured.
      - **Pass-all context**: default-on `sections["arudhas"]` in `chart_context.build_chart_context`
        → rendered as one compact line in `_render_context_block` (`AL Taurus, A2 Scorpio, …`).
      - **System prompt**: added rule 8 — use AL for the *perceived* self/image/status (vs the real
        Lagna), UL for the spouse.
      - **Frontend**: added `{ arudhas }` to the Ask page's `CONTEXT_SECTIONS` + `DEFAULT_SECTION_STATE`
        (defaults to "tool" in Smart-lookup). Verified: method + dispatch (12 padas), catalog,
        tri-state gating, pass-all render, prompt rule; backend clean, `npm run build` green.
      - **Table**: decided NOT to add another arudha table — the Advanced page already renders the
        full arudha grid, so the chart overlay + Advanced table + AI access cover it.

Follow-up (optional, not requested): a legend/tooltip explaining the AL/UL/A2.. labels.

### 10.2 Birth-time correction / rectification (P1) — full feature, experimental — SHIPPED 2026-07-02

Owner ask (2026-07-02): a birth date-time **correction** capability. The engine supports it
(BV Raman methods) — but PyJHora **explicitly flags it "experimental — accuracy not
guaranteed"** (`src/jhora/panchanga/README.md`, `const.py`), so this ships with a clear
disclaimer, framed as a *suggestion to verify*, never an authoritative correction.
Owner decisions (2026-07-02): build the **full feature** — all three methods (default
Nakshatra), the on-demand AI reading, and the apply-to-profile button — **with disclaimer**.

Engine entry points (verified in `panchanga/drik.py`):
- `_birthtime_rectification_nakshathra_suddhi(jd, place)` — **self-derives** the expected
  janma star from the birth-time ishtakaal and returns a corrected time (needs **no** known-
  star input, contrary to the original plan's `expected_nakshatra` assumption).
- `_birthtime_rectification_lagna_suddhi(jd, place)` and `_janma_suddhi(jd, place, gender)`
  only return a **yes/no "correction needed"** flag — no time. So the wrapper runs its own
  symmetric ±-search (mirroring the nakshatra loop) to produce a suggested time.
- Tunables: `const.birth_rectification_step_minutes` (0.25) × `birth_rectification_loop_count`
  (120) ⇒ searches ±30 min around the entered time.

- [x] **Backend** `AstrologyCompute.get_birth_time_rectification(dob, tob, place, lat, lon,
      tz, ayanamsa, method, gender=None)` (`astrology.py`) → suggested corrected time, the
      signed delta, which rule fired, before/after Moon & Lagna, and full before/after chart
      summaries (reuses `calculate_birth_chart`). Server-injects birth details + ayanamsa and
      **resets global state after**. Guards the experimental engine calls in try/except. **KEY
      gotcha pinned:** the nakshatra engine returns only a *time-of-day* tuple (no date), so a
      converged time that crossed midnight looks ~24 h away — the delta is wrapped into the
      nearest ±12 h to recover the true small signed shift (the search is bounded to ±30 min).
      janma without a gender returns a clean `failed` (→ 400), not a 500.
- [x] **Endpoint** `POST /api/astrology/rectify-birth-time` (auth), `BirthDetails` body +
      `method`/`gender`/`ayanamsa` query params. Returns 400 on bad input / non-success.
- [x] **Frontend** `BirthTimeRectificationPage.js` (route `/rectify`, dashboard card + drawer
      entry, `Clock4` icon), saffron/terracotta Vedic style. Method toggle (Nakshatra default /
      Lagna / Janma), a gender picker shown only for Janma (not stored on the profile), chart-
      style toggle. Output: entered-vs-suggested time + signed delta pills, a **prominent
      experimental disclaimer** (`.readonly-banner`), a **what-moved** before→after table
      (Moon star/pada + rising sign), the **before/after `Kundali` side-by-side**, and an
      **"Apply suggested time to this profile"** button (confirm dialog → `updateProfile` PUT,
      so the corrected time flows into every other chart).
- [x] **On-demand AI reading** `llm_service.explain_rectification` + `_build_rectification_prompt`
      (~200-250-word jargon-light note on *why* the suggested time fits + how to verify, safety
      footer, no death/disease/precise-date), model-config aware via `_resolve_cfg` +
      rate-limited. `POST /api/astrology/rectify-birth-time/explain` (`RectifyExplainRequest`);
      the page's reading card uses the model picked in Ask AI Astrologer.
- [x] i18n `nav.rectify`, `dashboard.features.rectify` (en/hi/sa) + full `rectify.*` block
      (en; hi/sa fall back). Verified: all three methods round-trip on test charts (nakshatra
      already-consistent on the 1990-05-15 True-Chitra chart; midnight-crossing case wraps to
      −5.75 min correctly; janma no-gender → 400); response JSON-serializable (~3.7 kB); backend
      imports clean + both routes registered; `npm run build` green (+3 kB); ESLint clean;
      locale JSON valid. **Default method = Nakshatra Śuddhi** (self-serve).

**FOLLOW-UP — event-based (interactive) rectification — SHIPPED 2026-07-02.** Owner clarified
they expected the app to *ask questions and rectify the DOB from the answers*, not just run the
silent śuddhi algorithm. Owner decisions: **known life events + dates** as the input,
**deterministic scoring with an AI explanation**, added as a **new mode on the same `/rectify`
page** (not a replacement). This is the classical life-events method.
- [x] **Backend** `AstrologyCompute.get_event_rectification(dob,tob,place,events,lat,lon,tz,
      ayanamsa,window_minutes=120)`. Given dated events, a **two-pass scan** (coarse 15-min over
      the clamped ±window, then fine 2-min around the best) scores each candidate birth time:
      for every event it finds the running **Vimsottari maha+bhukti** (built from
      `vimsottari.vimsottari_mahadasa` + `_vimsottari_bhukti`) and awards points when a period
      lord **rules / occupies** one of the event's significator houses (counted from the
      *candidate's* Lagna) or **is its natural karaka**, plus a small **Jupiter/Saturn transit**
      bonus. Both levers are birth-time-sensitive (house lords via Lagna; dasha balance via the
      Moon's natal fraction). Returns the winning time, signed delta, a 0-100 **fit %**, and a
      per-event **auditable match list**, plus the same before/after Moon/Lagna + charts.
      `EVENT_SIGNIFICATORS` (12 event types → houses + karakas) + `SIGN_LORD` added as module
      constants. Guards empty/invalid events → clean 400.
- [x] **Endpoints** `POST /api/astrology/rectify-birth-time/events` (compute) +
      `.../events/explain` (AI). `llm_service.explain_event_rectification` +
      `_build_event_rectification_prompt` narrate the *pre-computed* per-event matches (~220-280w,
      honest about the fit %, safety footer), model-config aware + rate-limited. New request
      models `RectifyEventsRequest` / `RectifyEventsExplainRequest` (+ `RectifyEventItem`); added
      `List` to the `typing` import.
- [x] **Frontend** — the `/rectify` page gained a top-level **Approach** toggle
      (By rule / By life events). Event mode: an events editor (type dropdown from 12 curated
      events + date picker, add/remove rows), a **search-window** picker (±2h / ±6h / whole day),
      a **Rectify from events** button, and a **"Why this time fits the events"** table (per event:
      Maha/Bhukti + the matched reasons). Reuses the shared what-moved table, before/after charts,
      apply-to-profile, and AI card (which calls the events-explain endpoint in this mode). New
      `api.js` `rectifyByEvents` / `explainEventRectificationAI`; `rectify.*` i18n extended (en;
      hi/sa fall back).
- [x] Verified end-to-end via `TestClient`: events endpoint 200 (1988-11-23 test chart, marriage
      2015 + career 2012 → suggests 23:25, fit 54%, per-event dasha matches shown), empty events →
      400; whole-day scan < 0.1s; `npm run build` green; ESLint clean; locale JSON valid.

**FOLLOW-UP — conversational (chat) rectification — SHIPPED 2026-07-02.** Owner asked for the
interview to also work as a **back-and-forth chat** ("ask questions and rectify"). Added a 3rd
**Conversational** mode on `/rectify`. The AI *only collects* the events; the deterministic
`get_event_rectification` engine still decides the time (stays auditable).
- [x] **Backend** `llm_service.rectification_chat(messages, collected_events, name, config)` — one
      interview turn. Strict-JSON prompt (`RECT_CHAT_SYSTEM` + `RECT_EVENT_TYPES` = the 12 engine
      event keys) → `{reply, events, ready}`; asks one event at a time, maps free text to a valid
      type + ISO date (partial year/month → mid-year/mid-month), returns the **full cumulative**
      event list, and sets `ready` at ≥3 events or when the user is done. Reuses `_extract_json`.
      **KEY:** small local models (gemma4:12b) returned an EMPTY body on later turns (done_reason
      length) — same issue the quiz hit — so the turn uses a **2048-token budget + one retry** on
      empty/unparseable output, then degrades gracefully (keeps prior events, re-asks). Endpoint
      `POST /api/astrology/rectify-birth-time/chat` (`RectifyChatRequest`/`RectifyChatMessage`),
      rate-limited, model-config via `_resolve_cfg`.
- [x] **Frontend** — `/rectify` **Approach** toggle gains **Conversational**. A start button seeds
      the opening question, then a chat log (reuses `components/chat/ChatBubble` + `ChatComposer`,
      new `.rectify-chat__log` CSS) with a "thinking…" bubble while the turn is in flight. Events
      the AI understands show as **chips** (`t(rectify.event.*)` + date); a **"Rectify from these
      events"** button (highlighted once `ready`) runs the shared event-rectify path. The result
      block, per-event match table, before/after charts, apply-to-profile and AI "why it fits" card
      are all shared with the events mode (keyed on `result.confidence != null`, not the mode).
      `api.js` `rectifyChat`; `rectify.*` i18n extended (modeChat/chatTitle/chatIntro/chatStart/
      chatThinking/chatPlaceholder/collected; en, hi/sa fall back).
- [x] Verified: chat endpoint 200 via `TestClient`; **live Ollama (gemma4:12b)** round-trip — the
      opening question, then "married Nov 2015, first job July 2012" correctly extracted
      `marriage 2015-11-20` + `career 2012-07-15` and asked a natural follow-up; `npm run build`
      green (+0.8 kB); ESLint clean; locale JSON valid.

---

## 11. Formerly-parked engine features (build log, 2026-07-02)

The six §9.6 items, owner-approved for a full build — **all SHIPPED 2026-07-03**. Decisions
+ engine notes are in §9.6.

### 11.1 Sensitive Points page — Sphuta + 36 Sahams + Argala (P2) — SHIPPED 2026-07-03
- [x] **Backend** `AstrologyCompute.get_sphuta` (12 sphutas → sign/degree/house — note the
      engine fns take a `drik.Date`, not a tuple), `get_sahams` (36 natal sahams, night-birth
      from natal sunrise/sunset, → sign/degree/house), `get_argala` (per-bhava argala +
      virodhargala planet lists with a net verdict). Each server-injects birth details + resets
      ayanamsa. Shared `_natal_jd_place` helper. `SPHUTA_DEFS`/`NATAL_SAHAMS`/`ARGALA_*` consts.
- [x] **Endpoints** `POST /api/astrology/sensitive-points` (aggregates all three) +
      `POST /api/astrology/sensitive-points-analysis` (AI reading via `_resolve_cfg`,
      rate-limited; `llm_service.analyze_sensitive_points` + `_build_sensitive_points_prompt`).
- [x] **Frontend** `SensitivePointsPage.js` (route `/sensitive-points`, dashboard card +
      drawer, `Crosshair` icon): Sphuta table, Sahams table, Argala table (net argala/
      virodhargala pill), on-demand AI reading card. `.sp-net*` CSS in Dashboard.css.
- [x] **Smart-lookup tools** (§8.9): `get_sphuta`, `get_sahams`, `get_argala` (in `ALWAYS_TOOLS`
      + `_DISPLAY` under a new "Sensitive points" category). Verified via `tools.dispatch`.
- [x] i18n `nav.sensitivePoints`, `dashboard.features.sensitivePoints`, full `sensitive.*`
      (en; hi/sa nav+card, body falls back to en).

### 11.2 Vedic Clock & Retrograde page — both visualizations (P2) — SHIPPED 2026-07-03
- [x] **Backend** `get_vedic_clock` (sunrise/sunset, day length, ghati/vighati snapshot,
      running hora lord via `shubha_hora`, tithi/nakshatra/yoga now) + `get_retrograde`
      (currently-retrograde grahas via `planets_in_retrograde`, next station dates via
      `next_planet_retrograde_change_date`, and the vakra-gathi epicycle (x,y) loop per planet
      recomputed server-side with numpy — no pyqtgraph — normalized to [-1,1]). `RETRO_PERIODS`
      const; Rahu/Ketu flagged perpetually retrograde.
- [x] **Endpoints** `POST /api/astrology/vedic-clock`, `POST /api/astrology/retrograde`,
      `POST /api/astrology/celestial-analysis` (AI reading; `analyze_celestial` +
      `_build_celestial_prompt`).
- [x] **Frontend** `VedicClockPage.js` (route `/vedic-clock`, dashboard card + drawer, `Timer`
      icon): a live SVG ghati/vighati clock — the hand ticks client-side by advancing the
      snapshot ghati by *real elapsed seconds* (1 ghati = 1440 s, timezone-independent, no
      device-tz math) — a shaded day-arc, a digital ghati:vighati + hora-lord readout; the SVG
      retrograde-loop plot with a planet picker; a retrograde status/stations table. `.vc-*` CSS.
- [x] **Smart-lookup tools** (§8.9): `get_vedic_clock`, `get_retrograde` (Timing category).
- [x] i18n `nav.vedicClock`, `dashboard.features.vedicClock`, full `vedicClock.*`.

### 11.3 Almanac extension — Surya-Siddhanta engine toggle + Hijri date (P1) — SHIPPED 2026-07-03
- [x] **Backend** `get_panchanga` gained a `system` param (`drik` default / `surya_siddhanta`
      → computes the limbs under the `SURYASIDDHANTA` ayanamsa mode, reset in `finally`; the
      vendored `surya_sidhantha.py` module itself is buggy so it is NOT called) and always
      returns the `hijri` date via the inline `_hijri_tabular` (pure arithmetic — `hijri.py`
      can't be imported, it needs pyIslam/hijridate). `GET /panchanga` + the `get_panchanga`
      smart-lookup tool pass `system` through.
- [x] **Frontend** `PanchangaPanel`: a Drik ⇄ Surya-Siddhanta engine toggle (persisted in
      `localStorage.panchanga_system`) + a Hijri date line. i18n `panchanga.engine/engineDrik/
      engineSurya/hijri` (en/hi/sa).
- [x] **Almanac AI day-guide** (owner ask 2026-07-03, follow-up): a plain-language reading of
      the day's panchanga + planetary hours (Abhijit/benefic-hora good windows, Rahu-Kalam/
      Yamaganda/Gulika to avoid, honours the SS engine + Hijri). Location-driven, NOT birth-
      chart bound → new `AlmanacAnalysisRequest` (place/lat/lon/tz/date/system + model fields,
      no `BirthDetails`) + `POST /api/astrology/almanac-analysis`; `llm_service.analyze_almanac`
      + `_build_almanac_prompt` (~250-300w, safety footer). Frontend: a self-contained
      `AlmanacReading` card at the bottom of `AlmanacPage` (own date picker, uses the page's
      active location + the persisted engine). `api.js analyzeAlmanacAI`; i18n `almanac.ai*`
      (en full; hi/sa title). Verified: endpoint registered, prompt assembles (~1.5k chars with
      Abhijit/Hijri/SS engine); build green (+325 B), eslint clean, locale JSON valid.
- [x] Verified 2026-07-03: all 5 new endpoints 200 via `TestClient` (dependency-override auth)
      on the 1990-05-15 chart — sphuta 12 / sahams 36 / argala 12; vedic-clock ghati+hora;
      retrograde now=[Mercury,Rahu,Ketu] + 240-pt loops; panchanga SS + hijri 1448 Muharram 17.
      Prompt builders assemble (~2.9k / ~1.3k chars). `CI=true` build green (+4.9 kB), ESLint
      clean, locale JSON valid. 22 tools total.

---

## 12. Settings page — single source of truth (P1, owner ask 2026-07-03)

Decision (owner 2026-07-03): **move ALL scattered controls into one Settings page** and
**remove the per-page copies** (single source of truth, not central-defaults-with-overrides).
Today these live as per-page dropdowns/toggles persisted ad-hoc in `localStorage`:
- **AI model/provider** (`ai_provider_type`, `ai_model`, `ai_base_url`, endpoint override) — Ask page.
- **AI context config**: Answer mode (`ai_mode`), Context sections tri-state (`ai_sections`),
  vargas to consult (`ai_vargas`) — Ask page.
- **Ayanamsa** (`ayanamsa`) — Birth Chart + threaded through most pages.
- **Chart style** North/South (`chart_style`) — Birth Chart / Transit / Compare / Varshaphal / etc.
- **Language** (`lang`) — LanguageSwitcher (Dashboard navbar + PageHeader).
- **Almanac engine** (`panchanga_system`), **varsha dasha system** (`varsha_dasha`), **aspects-on-chart** toggle, etc.
- **Per-user API keys** (already a modal on Ask; move into Settings → "AI & API Keys").

Plan:
- [x] **New `SettingsPage.js`** (route `/settings`, gear icon in the Dashboard navbar +
      NavDrawer). DONE 2026-07-03: tabbed **General** (language, chart style N/S, ayanamsa),
      **AI** (provider + model + endpoint, Answer mode, **Max response length slider** — see §12.1
      below, + links to API keys & AI Capabilities), **API Keys** (fold of the existing per-user
      encrypted-key set/replace/clear, masked status), **Almanac** (Drik/Surya-Siddhanta engine),
      **Account** (change-password form + logout). Saffron/indigo identity, `Settings.css`.
- [x] **Centralize the settings state**: DONE 2026-07-03: `contexts/SettingsContext.js`
      (`SettingsProvider`/`useSettings`) reads+writes the SAME historical `localStorage` keys
      (`lang`/`ayanamsa`/`chartStyle`/`panchanga_system`/`ai_provider_type`/`ai_model`/
      `ai_base_url`/`ai_mode` + new `ai_max_tokens`), so the Settings page is the canonical editor
      and every existing page keeps reading the values unchanged. Wired into `App.js` under
      Auth/Profile providers. Language changes drive i18next immediately.
- [x] **Remove the per-page controls (phase 2a/2b)** — DONE 2026-07-03: pages now consume
      `useSettings` read-only and their inline editors are gone. **Ayanamsa** dropdown removed from
      BirthChart + Advanced; the display/read-only pages (Transit/Varshaphal/Rectification/
      Sarvatobhadra/Compare/Compatibility/Dhasa/SensitivePoints/PanchaPakshi/Learn) read
      `settings.ayanamsa`. **Chart-style N/S** toggle removed from BirthChart/Transit/Varshaphal/
      Rectification; all chart pages read `settings.chartStyle`. **Almanac engine** (Drik/Surya)
      toggle removed from `PanchangaPanel` → `settings.panchangaSystem`. Backing localStorage keys
      unchanged (SettingsContext writes them), so nothing breaks; build + eslint green across all 13
      files. (Owner note: chart-style N/S is now Settings-only — trivial to re-add an inline
      quick-toggle if it's missed mid-task.)
- [x] **Remove the Ask-page AI-config cards (phase 2c)** — DONE 2026-07-03 (owner decision:
      **model + keys only**; keep answer-mode/sections/vargas as per-question controls on Ask).
      - Removed the **provider/model/endpoint selector card** — replaced with a compact read-only
        summary (current model + "Change in Settings" link); the model/provider/endpoint are set in
        Settings now. The page still reads `ai_provider_type`/`ai_model`/`ai_base_url` from the shared
        localStorage keys Settings writes (send path + regenerate-with-model unchanged), and keeps the
        provider list fetch for the regenerate-with-a-different-model menu + on-load model validation.
      - Removed the **API-keys button + modal** (managed in Settings → API Keys now); dropped
        `refreshKeyStatus`/`openKeysModal`/`handleSaveKey`/`handleClearKey`/`refreshProviders`, the
        key state, `KEY_PROVIDERS`, `PROVIDER_ICONS`, `handleProviderChange`, `showAdvanced`, and the
        `KeyRound` import. Build + eslint green.
      - **KEPT on Ask (per-question):** Answer mode (still per-conversation, locked after first turn),
        Context sections tri-state, and the vargas "Charts to Consult" card + question-based varga
        suggestions. These are question-specific context tuning, not global settings.
      - Note: the "view what was sent to the AI" inspector button was preserved (moved into the model
        summary card header).
- [x] i18n `settings.*` (en; hi/sa fall back) + `nav.settings`. DONE 2026-07-03.
- [x] **System-health tab (owner ask 2026-07-04).** DONE: surfaced the backend `/health`
      endpoint (previously never shown in the UI) as a new **Settings → System** tab.
      `astrologyService.getHealth()` (`GET /health`) is fetched on mount; the panel renders one
      status row per service — **API server** (`status==="healthy"`), **Astrology engine
      (PyJHora)** (`pyjhora_available`), **Local AI model (Qwen)** (`qwen_enabled`, optional),
      **Map location picker** (`map_picker_enabled`, optional) — each with a pill: green **OK**,
      grey **Off** for optional/disabled features, red **Down** for required ones. A **Re-check**
      button re-runs the fetch; an unreachable server shows a warning line instead. New
      `.settings-health-*` styles in `Settings.css`; `settings.tabs.system` + `settings.system.*`
      i18n (en full, hi/sa translated). Build + eslint green. Note: `/health` was thin at first
      (4 booleans); it now also probes Ollama and returns a `local_ai` block (see §22) — extend it
      further (DB/ephemeris-path/per-provider key readiness) and the panel picks up new checks
      automatically.
- [x] **AI Capabilities + language → Settings-only** (owner ask 2026-07-03). DONE: removed the
      **AI Capabilities** dashboard tile + its NavDrawer link (page still reachable via Settings → AI
      → "View AI capabilities"; route `/ai-tools` intact). Removed the **`<LanguageSwitcher>`** from
      the Dashboard navbar, the shared `PageHeader` (all inner pages), and the standalone Login/
      Register/ProfileSelection/SharedChart screens — language is changed in Settings → General now
      (i18next browser-language detection + persisted choice still apply; only the manual pre-login
      override is gone). Deleted the now-dead `LanguageSwitcher.js`/`.css`, the `.auth-lang`/
      `.profile-lang-switch` styles, and the unused `nav.aiTools`/`nav.language`/
      `dashboard.features.aiTools` i18n keys (en/hi/sa). Build + eslint green.

### 12.1 Max response length (output tokens) control (P1, owner ask 2026-07-03) — DONE 2026-07-03

Owner: expose a control so a user whose AI answers get cut off can raise the length; give them a
slider.
- [x] **Backend**: `ModelConfig.max_tokens` (optional) is now honored at every provider payload
      site — one `max_tokens = cfg.max_tokens or max_tokens` override in `_complete`, `stream_answer`,
      `_chat_once_openai/ollama/gemini`, and `_complete_chat` — so it flows through the pass-all,
      streaming AND smart-lookup (tool-loop) answer paths. `AskQuestionRequest.max_tokens` (+ the
      transit-chat request) carries it; `_resolve_cfg` sets `cfg.max_tokens` **clamped to 256..32768**
      (None → provider default 4096). Verified live on Ollama gemma4:e4b: `max_tokens=300` → exactly
      300 completion tokens; a tiny value clamps up to the 256 floor.
- [x] **Frontend**: a **Max response length slider** (512–8192, step 256) in Settings → AI with a
      "Use the model's default length" checkbox (0 = auto); persisted as `ai_max_tokens`. The Ask
      page reads it and sends `max_tokens` on every `streamAskQuestion` call (`api.js` stream body).
      Note: SSE streaming uses raw `fetch` so it also bypasses the §13 silent-refresh (tracked there).
- [x] FOLLOW-UP (DONE 2026-07-03): `max_tokens` now threads into **every** AI endpoint, not just
      Ask/transit-chat. Backend: added the optional `max_tokens` field to all remaining AI request
      models — `PredictionRequest` (already had it), Compatibility/Compare/Sarvatobhadra/Varshaphal/
      PanchaPakshi/SensitivePoints/Celestial/Almanac analyses, the three Rectify (explain/events-
      explain/chat) requests, and `QuizGenerate`/`QuizGrade`. No new plumbing: `_resolve_cfg` already
      reads `getattr(request, "max_tokens", None)` and clamps to 256..32768, so the field alone wires
      it through. Frontend: each page's `readModelConfig()` now returns
      `maxTokens: parseInt(localStorage.getItem("ai_max_tokens") || "0", 10) || undefined`, and every
      axios AI call in `api.js` sends `max_tokens: model.maxTokens || undefined`. Build + eslint green.

## 13. User account & auth improvements (P1, owner ask 2026-07-03)

**Root cause of frequent logout (found 2026-07-03):** `config.py:ACCESS_TOKEN_EXPIRE_MINUTES = 30`
and there is **no refresh token** — the JWT simply dies after 30 min and the app kicks you to
login. Decision: **refresh tokens + "Remember me"** (owner pick).

Plan:
- [x] **Refresh-token flow** (backend). DONE 2026-07-03: new `refresh_tokens.py` (`refresh_tokens`
      collection) — opaque `secrets.token_urlsafe(48)` stored **SHA-256 hashed** with
      `username/ttl_days/expires_at/revoked`; `issue/verify/revoke/revoke_all/rotate`. Access token
      stays short (`ACCESS_TOKEN_EXPIRE_MINUTES=30`); `_issue_token_pair()` mints access+refresh on
      register/login. `POST /api/auth/refresh` **rotates** (revokes the presented token, returns a
      new pair — single-use, so a leaked token can't be reused) and `POST /api/auth/logout` revokes.
      Config `REFRESH_TOKEN_EXPIRE_DAYS=30` / `REFRESH_TOKEN_SHORT_DAYS=1`. `Token` model gained
      `refresh_token`. Verified live (curl): register/login return both tokens; refresh rotates (old
      → 401, new → 200); logout revokes (→ 401).
- [x] **"Remember me" checkbox** on Login. DONE 2026-07-03: `remember_me` on Login/Register requests
      picks the 30d vs 1d refresh TTL; a "Keep me signed in" checkbox (default on) on `LoginPage`
      (i18n `auth.rememberMe`); Register always issues a durable (30d) session.
- [x] **Frontend silent refresh**. DONE 2026-07-03: `services/api.js` response interceptor — on a
      401 (non-auth call, once per request) it transparently `POST /auth/refresh`es (a single shared
      in-flight promise across concurrent 401s), stores the new pair, and retries the original
      request; only a *failed* refresh clears tokens + bounces to `/login`. Tokens via
      `setTokens/getRefreshToken/clearTokens` (both in localStorage — known XSS tradeoff vs httpOnly
      cookies, acceptable given the app already used localStorage bearers). `AuthContext` login/
      register take `rememberMe`; logout revokes the refresh token server-side (best-effort).
      This kills the "logged out every 30 min" pain. NOTE: the SSE **streaming** calls
      (`streamAskQuestion` etc.) use raw `fetch`, not axios — they bypass this interceptor, so a
      token that expires *mid-stream* still fails; low-impact, revisit if it bites (could pre-refresh
      before a stream).
- [x] **Change password** (logged-in). DONE 2026-07-03: `POST /api/auth/change-password`
      (auth-scoped) verifies current password, min-6 new, updates the hash, `revoke_all`s existing
      refresh tokens (logs out other devices) and returns a fresh pair so the current session stays
      in. `authService.changePassword` in api.js. Verified live (wrong-current → 400; correct →
      new pair + old refresh & old password both rejected). UI form → Settings → Account (§12).
- [x] **Profile/account management**. DONE 2026-07-03: Settings → Account now shows the account
      overview (username + **Member since** — `register` now stamps `created_at`; `GET /api/user/profile`
      already returned username/email). **Update email**: `PUT /api/auth/email` (validates format via
      regex, rejects an email already used by another account) + an email form. **Delete account**:
      `DELETE /api/auth/account` (password-confirmed, irreversible) **cascade-purges** every user-scoped
      collection — `saved_profiles/charts/user_settings/ai_conversations/ai_tool_traces/shared_charts/
      quiz_sessions` (by `user_id`) + `refresh_tokens` (by `username`) + the `users` row; a danger-zone UI
      with a typed-password confirm, then local logout → `/login`. Birth-profile CRUD already lived in
      ProfileSelection (unchanged). Verified live (curl, isolated `pyjhora_test` DB): register→email
      update (valid/invalid)→change-password→seed profile→delete→login 401, and a Mongo sweep confirming
      **0 leftover docs** across all 9 collections.
- [x] (P2) **Forgot / reset password** via email. DONE 2026-07-03: provider-agnostic SMTP
      (`email_service.py`, stdlib `smtplib` in a thread — no new dep; Gmail app-password/SendGrid/
      Mailgun/SES all work; **graceful no-op that logs the link when `SMTP_HOST` is unset**, so dev
      works). `password_reset.py` stores single-use, TTL'd, **hashed** tokens (mirrors
      `refresh_tokens`); any prior unused token for the user is invalidated on a new request.
      `POST /api/auth/forgot-password` (username OR email; **always** the same generic response so
      it can't enumerate accounts; IP-throttled via the login limiter) emails a
      `{APP_BASE_URL}/reset-password?token=…` link; `POST /api/auth/reset-password` consumes the
      token atomically (race-safe), sets the hash, `revoke_all`s sessions and returns a fresh pair so
      the user is signed straight in. Frontend: `ForgotPasswordPage`/`ResetPasswordPage` (+ routes,
      "Forgot password?" link on Login). Config: `SMTP_*`/`APP_BASE_URL`/`PASSWORD_RESET_TTL_MINUTES`
      in `config.py` + `.env.example`. VERIFIED in-process (TestClient): forgot→token→reset→old-pw 401/
      new-pw 200→token-reuse rejected→bad-token rejected. (Unblocks the email digest channel below.)
- [x] (P2) Optional niceties. DONE 2026-07-03: **"Log out other devices"** — `POST /api/auth/logout-all`
      (`revoke_all` then returns a fresh pair so *this* device stays in; frontend stores it via
      `setTokens`), button in Settings → Account. **Login brute-force rate-limit** — `ratelimit.login_*`
      (a per-client-IP failed-attempt window, default 10 fails / 15 min, env `LOGIN_RATE_MAX_FAILS`/
      `LOGIN_RATE_WINDOW_SEC`); the login endpoint 429s when tripped and clears the counter on success.
      Verified: 429 after threshold, blocks even the correct password until the window passes. **Password-
      strength hint on register** — a no-lib weak/fair/strong meter (length + character-class score) under
      the password field. (Keyed by IP not username to avoid a victim-lockout DoS. A full per-session
      *list* view isn't built — opaque hashed refresh tokens make it possible but it wasn't needed;
      "log out other devices" covers the practical case.)

## 14. Layman FAQ / Help page (P1, owner ask 2026-07-03) — SHIPPED 2026-07-18

A friendly, jargon-light FAQ so a non-astrologer understands what the app does.
Owner framing: **"think that a person is not an expert and we have to help him"** —
so the content assumes zero prior knowledge and explains every term where it
first appears.

- [x] **`HelpPage.js`** at `/help` (with `/faq` as an alias people type). 42
      questions across five areas: *Getting started* (what this is, what a birth
      chart is, why the exact time matters, what to do without one, Essentials vs
      Everything, and "do I have to believe in this?"), *Reading your chart*
      (what the square diagram actually shows, North vs South style, houses,
      signs, Rasi vs Navamsa, nakshatras, yogas/doshas, retrograde), *What each
      page does* (a one-line tour of all 16 features, each linking straight
      there), *The AI astrologer* (what it can see, Full context vs Smart lookup,
      which model, how far to trust it, where readings go), and *Privacy & your
      account* (what's stored, share links, API keys, emails, deletion).
- [x] **Maintainable by construction**: structure in `config/help.js`, words in
      the `help.*` i18n block keyed by id. Adding a question = one id + two
      strings; hi/sa fall back to English. `config/help.test.js` (11 tests) fails
      on an id with no text, on orphaned text no section uses, on duplicate ids,
      and on a relative link — so a half-added entry can't ship as a blank row.
- [x] **Entry points**: a "?" button in every page header (via `PageHeader`) and
      on the dashboard navbar, plus a Help entry in the nav-drawer footer beside
      the other always-available actions — it isn't a feature, it's the way out
      when a feature doesn't make sense.
- [x] **Glossary** rendered from `constants/glossary.js`, the same table the
      hover definitions use, so the two can't drift.
- [x] Search filters on the rendered question + answer text (not our ids), and
      answers collapse by default so the whole list stays scannable. `#id` in the
      URL opens and scrolls to one answer — which is what makes the optional
      contextual links possible.
- [ ] 🟡 (Optional, deferred) contextual "?" links from each feature page into
      its specific FAQ anchor. The anchor support is built (`/help#aiModes`
      works); only the per-page links are outstanding.

**Verified:** 152 frontend tests pass, prod build clean, `/help` serves and the
content is present in the built bundle.

## 15. UI redesign — compact density + tabs (P1, owner ask 2026-07-03) — MOCK FIRST

Owner feedback: tiles/cards and their content are **too big**; wants a **more compact** layout and
**tabbed sections** (e.g. one page with tabs for *Nakshatra Information*, *Panchanga*, *Yogas/Doshas*,
etc.), and busy pages **tabbed on desktop**. **Keep the saffron/cream Vedic identity** (no wholesale
re-theme — owner reaffirmed the existing look).

**Process (owner directive 2026-07-03): build a MOCK first, get it verified, THEN do the real
implementation.** Do not start converting real pages until the mock is approved.
- [x] **Density/compact pass** — SHIPPED. Mock built and approved (two rounds:
      v1, then v2 rebuilt once the app had grown to 39 features and gained a dark
      theme). The compact scale lives in `App.css` as density tokens
      (`--card-pad`, `--card-radius`, `--tile-*`, …) consumed by
      `Shared.css`/`Dashboard.css`, so the app re-scales from one place.
- [x] **Tabbed layout** — SHIPPED. Owner picked the **saffron pill** (over the
      underline variant I recommended). Shared `<Tabs>` + `useTabs`
      (`components/Tabs.js`) with the resolution rules as pure, unit-tested
      functions in `config/tabs.js` (17 tests).
- [x] **Owner verified the mock** → decisions captured: compact density; saffron
      pill; the six-tab Birth Chart grouping; full rollout; tab state in the URL;
      restyle the three existing bars; hide the Advanced tab in Essentials.
- [x] **Real implementation** — rolled out page by page, verifying the prod build
      after each.

### How it works
- **Tab state lives in the URL** (`?tab=`), so Back/Forward work, refresh keeps
  your place, and a tab is linkable — load-bearing because AI readings and
  digests already deep-link into pages. Settings' pre-existing one-way `?tab=`
  keeps working: same parameter, now two-way. A second bar on one page takes its
  own key (Compatibility uses `?tab=` + `?system=`).
- **`advanced: true` tabs are hidden in Essentials**, *except* when the URL names
  one — deep-links must never dead-end, mirroring `AdvancedNotice`.
- The initial resolve never writes the URL, so arriving on a page costs no
  history entry.

### Density is a preference, not a decree (owner ask, 2026-07-18)
Settings → General → **Display density**: Compact / Comfortable, applied
instantly and synced across devices like theme. `:root` is compact;
`:root[data-density="comfortable"]` restores the pre-§15 spacing. Also added
`density` to the backend `PREFERENCE_KEYS` whitelist — without it the server
drops the key silently and the choice never leaves the browser.

### Pages tabbed
Settings (10) · Admin (3) · KP (2) — these three already had **divergent**
hand-rolled bars (`.settings-tabs` pill on `--border-color`, `.admin-tabs`
underline on `--border`, KP a segmented control); unifying them deleted the
duplication. Then Birth Chart (6: Chart / Nakshatra & Lagna / Panchanga / Yogas
& Doshas / Aspects / Advanced), Compatibility (two bars), Chakras (4),
Sensitive Points (3), Planetary Strength (4). Per-page AI reading cards stay
**outside** the tabs so they remain visible on every section.

### Where tabs deliberately do NOT go
The mock's rollout table ranked pages by counting `ui-card-header`, which
overstated the work twice over — worth recording so it isn't re-derived:
- **Segmented form controls, not navigation**: Varshaphal's dasha system, Period
  digest's solar/lunar basis, Tithi Pravesha's window rung, Rectification's
  method. They carry `role="group"`/`aria-pressed` and select a *value*. Styling
  them as pills would misreport what they do.
- **Sub-headings inside one card**: Jaimini and Varshaphal use
  `ui-card-header--sm` within a single Card; tabbing would fragment it.
- **Too few real sections**: Nakshatra Profile (syllables live inside the
  attributes card, leaving two sections) — a tab would hide Tarabala for no
  scroll saving.
- **Side-by-side by design**: Compare Charts shows two charts together; tabs
  would hide half the comparison.

## 16. New feature ideas — engine-grounded backlog (P1/P2, owner ask 2026-07-03)

Owner prioritized (2026-07-03): **Muhurta, Prashna, Daily digest/notifications, KP** first; the rest
are the fuller brainstorm. All are grounded in what `src/jhora/...` already supports (audit engine
entry points before building each, same pattern as §9/§11: thin `AstrologyCompute` method that
server-injects birth details + resets global state, auth endpoint, saffron page, on-demand AI via
`_resolve_cfg`, i18n, and a §8.9 smart-lookup tool).

**Prioritized (owner pick):**
- [x] **Muhurta / electional astrology** (P1). DONE 2026-07-03: `AstrologyCompute.get_muhurta(
      activity, start, end, place…)` scans each day in the range (capped 31), scoring it from the
      Panchanga — per-activity favourable **nakshatra** (classical lists per activity:
      general/marriage/travel/business/housewarming/education/medical) + **vaara** + **tithi**
      (Rikta & Amavasya penalised) + **yoga** (the nine inauspicious yogas penalised) + Vishti-karana
      penalty — then for non-"avoid" days extracts concrete **windows**: the Abhijit muhurta (skipped
      for marriage/travel per tradition) + the benefic planetary **horas** (Moon/Mercury/Jupiter/
      Venus) that don't overlap Rahu-Kalam/Yamaganda/Gulika. Returns per-day ratings + a ranked
      `best_windows` list. Reuses `get_panchanga`+`get_planetary_hours`; new constants
      `MUHURTA_*`/`MUHURTA_ACTIVITIES`. `POST /api/astrology/muhurta` (data) + `.../muhurta-analysis`
      (AI rationale via `_build_muhurta_prompt`). Frontend `MuhurtaPage` (route `/muhurta`, card +
      drawer, `CalendarCheck`): activity picker, date range, best-windows list (quality chips),
      day-by-day grid, AI rationale. Also a §8.9 smart-lookup tool `get_muhurta`. Verified live
      (marriage 07-05→07-12 → 8 days, 12 windows). i18n `muhurta.*` (en; hi/sa nav+card labels).
- [x] **Prashna / horary** (P1). DONE 2026-07-03: `AstrologyCompute.get_prashna(question, date,
      time, place…)` casts a chart for the **moment the question is asked** (defaults to now + here)
      by reusing `calculate_birth_chart`, layering the day's Panchanga + running hora lord for
      classical horary context. `POST /api/astrology/prashna` (chart) + `.../prashna-analysis`
      (returns `{reading, chart}`; `_build_prashna_prompt` reads it Prashna-style — Ascendant =
      querent, Moon = mind/matter, house/lord = outcome, with a likely-yes/no/mixed answer + timing).
      Frontend `PrashnaPage` (route `/prashna`, card + drawer, `HelpCircle`): question box → casts
      using the querent's **browser geolocation** (falls back to the profile place), renders the
      moment-chart via the shared North/South `Kundali` + the horary reading side by side. Verified
      live. i18n `prashna.*`.
- [x] **Daily digest & notifications** (P1). DONE 2026-07-03 — all three channels:
      - **In-app "Today"** — `AstrologyCompute.get_daily_digest(dob,tob,place…)` assembles the day's
        Panchanga + running Vimsottari dasha (flagging a Bhukti change within 30 days) + headline
        transits (Sade-Sati by Saturn's house-from-Moon, Jupiter-from-Moon, retrogrades, next Jup/Sat
        ingress) into a `highlights` list + structured sections. `POST /api/astrology/daily-digest`
        (+ `.../daily-digest-analysis` for a warm AI reading via `_build_daily_digest_prompt`).
        Frontend `DailyDigestPage` (route `/daily-digest`, card + drawer, `Sun`): highlights, panchanga
        / dasha / transit cards, AI reading.
      - **Email (opt-in)** — reuses the §13 SMTP layer. `notifications.py` stores per-user prefs
        (`user_settings.notifications`: daily_digest/email/push/profile_id/hour) + `push_subscriptions`.
        `POST /api/notifications/digest/send` computes the chosen profile's digest and delivers on the
        enabled channels (a scheduler/cron — or the "send me a test now" button — calls it).
      - **PWA push** — Web Push via VAPID (`pywebpush`, added to requirements; **graceful no-op when
        VAPID keys unset** → subscribe endpoints 503). `sw.js` gained `push`/`notificationclick`
        handlers; `utils/push.js` subscribes the SW + registers the subscription
        (`POST /api/notifications/push/(un)subscribe`). Prefs UI: a new **Settings → Notifications**
        tab (master switch, profile/hour pickers, email + push toggles with availability badges, test
        button). Config: `VAPID_*` + `python -m notifications genkeys` (now prints **single-line**
        base64url keys that drop straight into `.env`). Verified live (prefs get/set, push subscribe
        503 when unset, digest highlights).
      - **Scheduler** — DONE 2026-07-03: an opt-in in-process asyncio scheduler (`scheduler.py`, env
        `DIGEST_SCHEDULER_ENABLED`/`DIGEST_SCHEDULER_INTERVAL_MINUTES`, started in the app lifespan)
        delivers each opted-in user's digest **once a day at their preferred local hour** (interpreted
        in the target profile's tz). Multi-worker/multi-tick safe: it **atomically claims** the day via
        a conditional `find_one_and_update` on `user_settings` (`notifications.last_sent_date != today`)
        so only the winner sends. Delivery logic is shared with the manual endpoint via a new `digest.py`
        (`send_digest_for_user`). A deployer can leave the scheduler off and cron `/digest/send` instead.
        Verified: tick sends once + claims the date, a second tick no-ops, wrong-hour users are skipped.
      - **FOLLOW-UP 2026-07-17 (digest quality + per-recipient delivery):**
        (1) **Per-profile delivery email** — `SavedProfile.notify_email` (+ `SaveProfileRequest`,
            save/update routes, ProfileContext, ProfileSelectionPage form field `profile.notifyEmail*`
            in en/hi/sa). At send time `send_digest_for_user` **groups blocks by recipient**: a subject
            with their own address gets a personal email carrying only their section(s); everyone else
            stays in the owner's **combined** copy, which always covers all profiles. Push stays
            owner-only. Returns `sent.recipients` count.
        (2) **Shared-sky de-duplication** — `_split_highlights` sorts each block's lines into *sky*
            (panchanga headline, `Retrograde now:`, `… enters … on YYYY-MM-DD` ingresses) vs *personal*
            (dasha, Sade-Sati, Jupiter/Saturn-from-Moon, pravesha lagna, Tajaka yogas). `_shared_sky`
            hoists the common set into ONE "Across the sky today" header when 2+ blocks match, else
            falls back to full per-section (safe when days differ). Renderers updated.
        (3) **One clock for every profile** — `observer_clock(user_id, profiles)` now falls back to the
            first profile's birth offset (via `_offset_clock`) when no current location is set, so a
            multi-profile digest never straddles two calendar days (was: each profile derived its own
            "today" from its own birth tz). Current location still wins.
        (4) **De-clichéd prompts** — `_build_daily_digest_prompt` + `_build_period_digest_prompt`
            demote the shared sky to background context, center the reading on each chart's
            *distinguishing* signal, ban restating mechanical facts verbatim + the stock phrases
            ("slow down", "trust the timing", "audit your projects", "bridge period", …) and the fixed
            "Today's alignment of…" opener, and ask for varied flowing prose over the old bold-labelled
            3-beat template. Tests: `tests/test_digest.py` (7, pure — split/hoist/render/offset-clock).
      - **FOLLOW-UP 2026-07-17 (consent + unsubscribe + Settings input polish):**
        (5) **Double opt-in consent** — new `digest_recipients.py` collection tracks per
            `(owner, email)` state `pending|confirmed|unsubscribed` with a long-lived cleartext link
            `token` (low-sensitivity capability). Saving/updating a profile whose `notify_email` is
            *external* (≠ owner account email) calls `_invite_recipient_if_external` →
            `digest_recipients.ensure` + `email_service.send_digest_confirmation` (once; a standing
            decision incl. opt-out is never re-invited). `send_digest_for_user` now **only** delivers
            a per-recipient copy when status==confirmed (pending/unsubscribed/uninvited are skipped;
            they still appear in the owner's combined copy). Every recipient email carries an
            unsubscribe footer (`email_service.digest_footer_{text,html}`).
        (6) **Public no-auth endpoints** `GET /api/digest/confirm|unsubscribe?token=` (in
            routes/notifications.py; snapshot regenerated). Frontend public pages
            `DigestConsentPage` at `/digest/confirm` + `/digest/unsubscribe` (mode prop), i18n
            `digestConsent.*` (en/hi/sa). Links point at `APP_BASE_URL` (frontend, mirrors reset).
        (7) **Recipient status surfaced** — `list_profiles` attaches `notify_status`
            (owner/pending/confirmed/unsubscribed); ProfileSelectionPage shows a pill on the card.
        (8) **updateProfile no longer wipes notify_email** — ProfileContext omits the field unless
            passed; PUT route only `$set`s it when `"notify_email" in model_fields_set` (rectification
            path was silently erasing it).
        (9) **Settings input look&feel** — `.settings-input` had NO base style → browser-default white
            box on dark theme (hit the API-access token label AND the calendar profile select); added a
            themed base mirroring `.control-input`. `.location-search-input` set a border but no bg/color
            → same white box; added `background:var(--surface)`+`color:var(--text-primary)`+placeholder.
            All token-only (tokens.test.js green).
        Tests: `tests/test_digest_recipients.py` (5, in-memory fake Mongo via asyncio.run). Suites
        green (backend 279, frontend 116).
      - **FOLLOW-UP 2026-07-17 (the four content ideas):**
        (10) **Daily action window** — `get_daily_digest` now calls `get_muhurta_subtools` and, via
             `_next_good_window` (linearises the day+night Choghadiya past midnight), picks the next
             auspicious window from the observer's `current_time`; emits `action_window` + a
             "Favourable window today: …" highlight (classed as SKY so it hoists). Daily prompt gets it
             as an optional anchor for the concrete suggestion.
        (11) **Per-person email deep-link buttons** — `_render_html/_render_text` take `app_url`+
             `open_path`; each section ends with "Open X's reading" + "Ask about the day" buttons
             carrying `?profile=<id>`. New global ProfileContext effect selects the profile from
             `?profile=` on any page (so the link lands on that chart).
        (12) **Weekly cadence per profile** — `SavedProfile.digest_frequency` ("weekly"|None=daily);
             `_clean_frequency` in the routes; `send_digest_for_user` skips weekly profiles on the
             *daily* cadence unless `_is_monday(observer)`. Form select + i18n `profile.freq*`.
        (13) **What changed since your last digest** — `digest_signals` collection snapshots
             {retro set, maha, bhukti, sade_sati} per (user, profile); `_diff_signals` yields "since
             last time" lines (empty on first-ever, no fabrication), rendered "Since your last digest"
             and fed to the daily prompt to LEAD with. Daily cadence only; advances the snapshot each send.
        Tests: test_digest.py now 15 (window/monday/sky/signal-diff). Backend 295, frontend 116 green.
      - **FOLLOW-UP 2026-07-17 (per-subject current location + UI polish):**
        (14) **Per-profile "lives now"** — `SavedProfile.current_location` (same {place,lat,lon,zone,
             source} shape as the account-level; zone derived server-side via `timezones.zone_at` in
             `_resolve_current_location`). `_profile_block` builds a per-profile clock from it
             (`_zone_clock`, factored out of `observer_clock`) and it OVERRIDES the shared observer for
             that section, so a subject abroad gets their own today; the weekly-Monday gate uses the
             subject's own clock too. Form: a second `LocationSearch` ("Lives now") + set/clear display
             + i18n `profile.currentLocation*`. Refactored the form's 3 drifted reset literals into one
             `EMPTY_FORM` const (they were missing notify_email/digest_frequency).
        (15) **Formatting fixes** — `.settings-test-row` had NO css so the "Send a test …" links ran
             together ("nowSend…") → stacked flex-column; mobile `.settings-row{align-items:stretch}`
             was ballooning the inline `.settings-segment` toggles (View/Appearance) full-width with an
             empty track → `align-self:flex-start` under the 640px query.
        Tests: test_digest.py=17 (+zone_clock). Backend 295, frontend 116 green.
- [x] **KP system (Krishnamurti Paddhati)** (P2→P1). DONE 2026-07-04 (full, incl. horary — owner
      pick). `AstrologyCompute.get_kp_details(dob,tob,place…)` forces the **KP (Krishnamurti)
      ayanamsa** and returns, for the Ascendant + all nine grahas, the sign / star (nakshatra) / sub
      / sub-sub lord (via PyJHora's `utils.kp_lords_for_longitude`), the **12 Placidus cuspal
      sub-lords** (`drik.bhaava_madhya_kp`), the **four-fold house significators** (A = planet in the
      star of a house's occupant, B = occupants, C = planet in the star of the owner, D = owner —
      computed from the rasi chart) and the current **Ruling Planets** (day-lord + Moon & Ascendant
      sign/star/sub lords). `get_kp_horary(number 1-249,…)` looks up the classical `prasna_kp_249_dict`
      to fix the horary Ascendant's sign/star/sub, casts the planets for the moment (now+here) and
      reads the ruling planets. Endpoints `POST /api/astrology/kp`, `.../kp-analysis`, `.../kp-horary`,
      `.../kp-horary-analysis` (AI via `_build_kp_prompt` / `_build_kp_horary_prompt`). New module
      helpers `_kp_lords` / `_kp_significators` / `_kp_ruling_planets`. Frontend `KPPage` (route
      `/kp`, card + drawer, `Compass`): **Natal KP** tab (sub-lord table, cuspal sub-lords, house
      significator grid, ruling-planet pills, AI reading) + **Horary** tab (number 1-249 + question →
      casts using browser geolocation, renders the moment-chart on the shared North/South `Kundali`
      + judgement). §8.9 smart-lookup tool `get_kp`. i18n `kp.*` (en; hi/sa nav+card). Verified live
      (KP details, horary #108, HTTP 200 through the app).

**Fuller brainstorm (P2, unprioritized — pick as capacity allows):**
- [x] **Muhurta sub-tools**: Tarabala/Chandrabala, Panchaka, choghadiya. DONE 2026-07-03:
      `AstrologyCompute.get_muhurta_subtools(date, place…, birth_dob/tob…)` returns the day's
      **Choghadiya** (8 day + 8 night parts from sunrise/sunset with the weekday-driven rota, each
      tagged good/neutral/bad + a "current" flag), the **Panchaka** dosha ((tithi+nakshatra+vaara+
      lagna) mod 9 → Mrityu/Agni/Raja/Chora/Roga or Panchaka-rahita, plus a Moon-in-last-5-nakshatras
      note), and — when birth details are passed — the personal **Tarabala** (engine `count_stars`
      from the natal star to today's star → the 9 taras + quality) and **Chandrabala** (transit Moon
      counted from the natal Moon → favourable 1/3/6/7/10/11). New constants `TARABALA_NAMES`/
      `CHANDRABALA_*`/`PANCHAKA_*`/`CHOGHADIYA_*` + `_choghadiya_sequence`. `POST /api/astrology/
      muhurta/subtools` (no AI — factual tables). Added as a **"Day tools"** section on `MuhurtaPage`
      (date picker → status cards for Panchaka/Tarabala/Chandrabala + day/night Choghadiya lists),
      passing the selected profile for personalization. i18n `muhurta.subtools.*` (en; hi/sa fall back).
- [x] **Bhava/house-cusp chart (Sripati/Placidus)** — DONE 2026-07-04, see **§18**. Cusp-based
      Bhava Chalit chart (Sripati/Placidus/KP/Equal) alongside the whole-sign Rasi chart.
- [x] **Jaimini deep-dive**. DONE 2026-07-04. `AstrologyCompute.get_jaimini(dob,tob,place…)` surfaces
      the **8 Chara Karakas** (Atma…Dara, ranked by longitude via `house.chara_karakas`, each with its
      D1 sign + house), the **Karakamsa** (the Atmakaraka's Navamsa sign — read as a second ascendant
      for the soul's agenda) and **Swamsa** (D9 Lagna), each with its occupants and **Jaimini
      rasi-drishti** aspects (`house.aspected_planets_of_the_raasi` on the D9), plus the **Argala /
      Virodhargala** (intervention vs counter) on the Lagna & 7th (`house.get_argala`). `POST
      /api/astrology/jaimini` + `.../jaimini-analysis` (AI via `_build_jaimini_prompt`). Frontend
      `JaiminiPage` (route `/jaimini`, card + drawer, `Layers`): Chara-karaka table, Karakamsa/Swamsa
      cards, argala table, AI reading. §8.9 tool `get_jaimini`. i18n `jaimini.*` (en; hi/sa nav+card).
      (Arudha padas + Chara karakas already existed on the Advanced page; this adds the Karakamsa-
      centred reasoning the item asked for.) Verified live.
- [x] **Nadi / Bhrigu-style yearly markers**. DONE 2026-07-03 (engine support exists —
      `drik.bhrigu_bindhu_lagna` + `next_planet_entry_date`). `AstrologyCompute.get_bhrigu_markers(
      dob,tob,place…, from_age, years)` gives two grounded, clearly-labelled classical devices:
      (1) the **Nadi annual progression** — the one-sign-per-year advance from the natal Moon (age 0 =
      Moon sign; each year's "marker sign" + its lord + the natal planets sitting there, flagging the
      Bhrigu-Bindu and Moon-sign years); and (2) **Bhrigu Bindu activations** — the natal Bhrigu Bindu
      (Rahu–Moon midpoint, sign/deg/house-from-Lagna) plus the next Jupiter & Saturn ingresses into the
      Bhrigu-Bindu and Moon signs as the turning-point trigger dates. `POST /api/astrology/bhrigu-markers`
      + `.../bhrigu-markers-analysis` (`_build_bhrigu_markers_prompt`, framed as an indicative aid not a
      fated forecast). Frontend `BhriguMarkersPage` (route `/bhrigu-markers`, card + drawer, `Waypoints`):
      horizon picker (8/12/20/30 yrs), BB info pills, progression grid, activations list, AI reading.
      New constant `RASI_LORDS`. i18n `bhrigu.*` (en; hi/sa nav+card labels).
      FIX 2026-07-03: the activations used `drik.next_planet_entry_date` which micro-steps 0.01 day —
      finding Saturn's *next* entry into a sign it just left scanned ~29 yrs (~12 s/call, ~20-30 s for
      the 4 calls) → intermittent request timeout ("Couldn't compute the markers"). Replaced with a
      local coarse-scan (1-day steps, safe for slow grahas <0.25°/day) + bisection to the hour, capped
      at one Saturn cycle (~36 yr); ~0.2 s/request now, dates verified identical to the old engine. Also
      fixed the activations-list formatting (date + text ran together — the `.detail-list`/`.kv-*` combo
      didn't space `<li>` children) with a dedicated `.bhrigu-activation` flex row.
- [x] **Transit calendar / ephemeris view** — DONE 2026-07-04, see **§18**. Daily sidereal
      ephemeris grid + a sign-ingress calendar over a selectable window (30/60/92 days).
- [x] **Remedies suggestions** (gemstones/mantras/deities per weak planet). DONE 2026-07-03:
      `AstrologyCompute.get_remedies(dob,tob,place…)` flags a planet as weak/afflicted when it is
      **debilitated** (from hard-coded exaltation/own-sign tables), **shadbala-deficient** (reuses
      `get_shadbala`, ratio < 1.0) or in a **dusthana** (6/8/12 from Lagna), then emits the curated
      traditional remedy per graha — gemstone, beeja mantra (+japa count), presiding deity, weekday,
      charity (daana) and colour — from a new `REMEDIES_TABLE` (Sun…Ketu) with `EXALTATION_SIGN`/
      `OWN_SIGNS`. Also returns a per-planet dignity+strength overview. `POST /api/astrology/remedies`
      + `.../remedies-analysis` (`_build_remedies_prompt` — leads with the gentle upayas, warns gemstones
      need qualified consultation). Frontend `RemediesPage` (route `/remedies`, card + drawer, `Gem`):
      remedy cards per weak planet, a dignity/shadbala table, AI reading, prominent
      traditional-guidance-not-advice banner. i18n `remedies.*` (en; hi/sa nav+card labels).
- [x] **Print-ready "full report" PDF** — DONE 2026-07-04, see **§18**. Single print-ready
      document (chart + D9 + positions + dashas + yogas/doshas + transits) → browser Save-as-PDF
      via `window.print()` + a `@media print` stylesheet.
- [x] **Chart-of-the-moment / "now" chart**. DONE 2026-07-04 (widget **+** standalone page — owner
      pick). `AstrologyCompute.get_now_chart(place,lat,lon,tz,current_time,current_tz,ayanamsa)` casts
      the current sky as a chart for now+here (reuses `calculate_birth_chart` at the present instant,
      like Prashna but no question) + the day's Panchanga + running hora lord. `POST
      /api/astrology/now-chart` + `.../now-chart-analysis` (AI via `_build_now_chart_prompt`).
      Frontend: `NowChartWidget` (a compact current-sky mini-kundali tile at the top of the Dashboard,
      browser-geolocation → falls back to profile place, silent on failure, links to `/now`) **and**
      `NowChartPage` (route `/now`, card + drawer, `Globe`): full moment-chart on the shared North/
      South `Kundali` + panchanga pills + Refresh + AI reading. i18n `now.*`. Verified live.
- [x] **Compatibility upgrades**. DONE 2026-07-04 (combined tabs — owner pick). `get_compatibility`
      now also returns **Dashakoota** (the South/Tamil 10-porutham via `Ashtakoota(method="South")` —
      adds Mahendra, **Rajju**, **Vedha** and Stree-Deergha to the Ashtakoot 8, score /10) and
      **Mangal (Kuja) dosha** for both charts with **cancellation nuances** (new `_mangal_dosha`:
      Mars in 1/2/4/7/8/12 from Lagna/Moon/Venus flags it; parihara from own/exalt sign, sign-specific
      house exceptions, and Jupiter conjunction softens it; both-Manglik → mutual cancellation
      verdict). `CompatibilityPage` gained a three-way tab bar (Ashtakoot / Dashakoota / Mangal) under
      the score box — the Ashtakoot koota grid, the Dashakoota porutham table (Rajju/Vedha shown), and
      per-partner Manglik cards with the cancellation list + verdict. i18n `compat.tabs/dashakoota/
      mangal.*`. Verified live (Dashakoota 7/10, both-Manglik cancellation).

## 17. Unified AI history — every AI reading/chat saved + reopenable (P1, owner ask 2026-07-03)

**Goal:** *Every* AI output across the whole app — not just the Ask-Astrologer/Transit chats — is
automatically saved to history, and clicking a history item takes the user **back to the actual page
that produced it and shows the exact saved reading** (a snapshot, no recomputation).

**Owner decisions (2026-07-03):**
- **Where:** BOTH a new **global History page** (all tools, filterable) AND per-page access on each
  tool (e.g. a "Recent readings" affordance / history control on the tool's page). Also: the current
  Ask-AI history already mixes in saved **Transit** chats — reconcile that into the unified model
  (don't leave a second, parallel history).
- **Click behavior:** show the **exact saved snapshot** — navigate to the source page, restore the
  saved inputs, and render the stored reading text verbatim. No re-running the chart/panchanga
  compute (avoids drift for time-relative tools like transits/digest).
- **Scope:** **Everything AI** — all ~20 one-shot `analyze*AI`/reading endpoints + both chats
  (astrologer, transit) + quiz + rectification interview/explanations.
- **Save trigger:** **Automatic** on every AI generation; user can **delete each item individually**.

**Current state (audit 2026-07-03):**
- Only chat threads persist, in the `ai_conversations` Mongo collection (`conversations.py`), tagged
  `source` = `"astrologer"` | `"transit"`. History UI is a **panel inside `AskAstrologerPage`**
  (filter all/astrologer/transit); clicking loads the thread *in that page* only.
- The ~20 one-shot readings (`analyzeVarshaphalAI`, `analyzePrashnaAI`, `analyzeMuhurtaAI`,
  `analyzeRemediesAI`, `analyzeBhriguMarkersAI`, `analyzeDailyDigestAI`, `analyzeSensitivePointsAI`,
  `analyzePanchaPakshiAI`, `analyzeSarvatobhadraAI`, `analyzeCompatibilityAI`, `compareChartsAI`,
  `analyzeAlmanacAI`, `analyzeCelestialAI`, `explainRectificationAI`/`explainEventRectificationAI`,
  `rectifyChat`, `generateQuiz`, `generatePrediction`, …) return their text **inline and are never
  persisted**. Backend endpoints live at `POST /api/astrology/*-analysis` in `main.py`; each just
  returns `ai_analysis` from `llm_service`.

**SHIPPED 2026-07-03 (core storage + global page + restore-on-open for all 14 AI tool pages).**
Owner follow-up answers baked in: (1) **pile up** a new history item per generation (no dedupe);
(2) retention cap **configurable via `.env`** (`AI_HISTORY_MAX`, default 100); (3) profile-less tools
group under a **"No profile"** bucket. Quiz keeps its own dedicated history/stats — intentionally NOT
double-stored here.
- [x] **Storage model** — reused the `ai_conversations` collection (option A). `conversations.py` adds
      a `SOURCE_META` registry (18 sources → `{label, route, kind}`, `kind` = `chat` | `reading`),
      `save_reading(...)` (one-turn user+assistant doc carrying `source`/`kind`/`route`/`context`/
      `profile_id`/`birth_details`), `prune_history(user)` (keeps newest `AI_HISTORY_MAX`, deletes the
      rest on every write), and `history_max()` reading the env var. `create_conversation` also stamps
      `kind`/`route`/`context`; `list_conversations`/`serialize_conversation` now surface
      `kind`/`route`/`label`/`preview`/`context`/`birth_details` and honour the cap. Verified live
      against Mongo: save→list→get round-trips the exact text + context; `AI_HISTORY_MAX=3` prunes 6
      saves down to the newest 3.
- [x] **Backend auto-persist** — one shared `_save_reading(...)` helper in `main.py` (best-effort,
      swallows errors so persistence never breaks a reading) called at the end of **every** analysis
      endpoint: varshaphal, muhurta, prashna, remedies, bhrigu, daily-digest, sensitive-points,
      celestial/vedic-clock, almanac, pancha-pakshi, sarvatobhadra, compatibility, compare, both
      rectification explains, and `predict`. Each passes the exact `context` inputs (year / activity+
      dates / date / place / question / horizon / method+gender / two-people details …). The chats
      (astrologer + transit) already persisted via `_save_turn`. `profile_id` added to the birth-bound
      analysis request models (location tools omit it → "No profile").
- [x] **API surface** — no new endpoints needed: `GET /api/ai/conversations` (no `profile_id`) returns
      everything; list items now carry `kind`/`route`/`label`/`context`. Added `listHistory()` alias in
      `api.js`. A request interceptor injects the selected `profile_id` into the birth-bound
      `*-analysis` calls so pages don't each thread it through.
- [x] **Global History page** — `HistoryPage` (route `/history`, reachable from a **Dashboard tile**
      (desktop) + the **nav-drawer** `History` entry (mobile)). Groups by
      profile (+ "No profile" bucket), filter chips All / Chats / Readings, each row shows a source
      badge + kind icon, title, a 2-line preview, model + timestamp, and an individual delete. Clicking
      selects the item's profile (so the target page recomputes for the right chart) then navigates to
      `route?reading=<id>`.
- [x] **Per-page restore** — shared `hooks/useRestoreReading.js`: on `?reading=<id>` it fetches the
      item and hands the page `{ context, reading, model, birthDetails }`, then drops the query param.
      Wired into all 14 tool pages with a uniform **pending-reading** pattern (restore inputs from
      `context`, then apply the exact saved AI text once the page's factual load settles so it isn't
      clobbered — no re-compute, no re-generation = true snapshot).
- [x] **Reconcile existing chats** — astrologer/transit now live in the same unified taxonomy/list;
      transit items deep-link back to `/transit`, astrologer to `/ask-astrologer`.
- [x] **i18n** — `nav.history` (en/hi/sa) + a `history.*` block (en; hi/sa fall back).
- [x] **Verify** — frontend production build compiles (+2.49 kB); backend `main.py`+`conversations.py`
      import clean; live Mongo round-trip + prune confirmed. ESLint clean on all touched files.
- [x] **Per-page "Recent readings" control** (DONE 2026-07-03) — reusable `components/RecentReadings.js`
      (collapsible saffron toggle → list, filtered to the page's `source` + optional `profileId`;
      click deep-links `?reading=<id>` on the *current* page so the page's `useRestoreReading` reopens
      it in place; per-item delete; renders nothing when the tool has no saved readings). Wired into all
      14 tool pages (profile-bound pages pass `profileId={selectedProfile?._id}`; location/two-people
      tools omit it). i18n `recent.*` (en; hi/sa fall back). This completes the owner's BOTH global +
      per-page ask. **Quiz stays out of the unified history** (keeps its own dedicated history/stats).
- [x] **Dashboard tile** (DONE 2026-07-03) — `/history` reachable from a desktop Dashboard tile
      (`dashboard.features.history`, en/hi/sa) as well as the nav drawer.
- [x] **RESTORE FIXES (2026-07-03)** — three real bugs found on reopen:
      (1) **Transit chat didn't restore** (route `/transit`, but `TransitChat` had no restore + is
      collapsed by default) → wired `useRestoreReading` into `TransitChat`: loads the whole thread,
      maps `assistant`→`ai`, adopts the conversation id (so a follow-up continues it), and expands the
      panel. (2) **History page never loaded the `profiles` list** (the provider only auto-loads the
      *selected* profile) → it grouped everything under "No profile" and couldn't switch to a reading's
      profile before navigating (so profile-gated pages like Bhrigu loaded the wrong/empty chart) →
      `HistoryPage` now calls `loadProfiles()` on mount. (3) **Restored reading was below the fold** on
      long pages (e.g. Bhrigu's AI card sits after the markers grid) → the hook now polls for the
      reading element and `scrollIntoView`s it. Also: reset the re-restore guard when the param clears
      so clicking the *same* item twice works. Build + eslint green.
- [x] **RESTORE FIXES round 2 (2026-07-03)** — reopening set the saved text but it stayed **invisible**
      on pages whose AI card is gated behind computed data that only loads on user action (looked like
      nothing happened). On restore we now re-run the **factual (non-AI, no-duplicate) computation** from
      the saved `context` so the gated view renders with the saved reading: Prashna → `getPrashna`,
      Muhurta → `getMuhurta`, Compatibility → `getCompatibility` + both charts, Compare → both charts,
      Rectify → rule mode already auto-runs, events mode re-runs `rectifyByEvents`. Also the
      **Ask-Astrologer chat page had no restore hook** (`/ask-astrologer?reading=<id>` did nothing) →
      wired `useRestoreReading` → `loadConversation`. Transit page also got its own Recent-readings panel
      + its model caption now points to Settings (was "Ask AI Astrologer").

**Resolved:** dedupe → **pile up** (individual delete); retention cap → **`AI_HISTORY_MAX` env**
(default 100, pruned on write); tools with **no birth profile**
(Muhurta/Almanac/Prashna-by-place) group under a "no profile" bucket in history.

---

## 18. Ephemeris, Bhava-cusp chart & print-ready Full Report (owner ask 2026-07-04)

Three engine-grounded features shipped together. All three are wired into the nav
drawer (`/ephemeris`, `/bhava`, `/report`), follow the Settings-driven chart-style +
ayanamsa convention, and reuse the shared PageHeader / ProfileBanner / Kundali /
data-table components.

- [x] **Transit calendar / ephemeris view** — `GET /api/astrology/ephemeris`
      (`AstrologyCompute.get_ephemeris`). Walks a date window (default 30, selectable
      30/60/92, clamped ≤92 for payload/perf) computing every graha's sign, degree-in-sign,
      nakshatra and retrograde state at **local noon** each day, and derives the
      **sign-ingress calendar** by watching for a sign change between consecutive days.
      `EphemerisPage` renders (a) an ingress card-grid ("Sign Ingresses" with from→to +
      date + ℞) and (b) a dense **daily ephemeris grid** (dates × 9 grahas, each cell
      `deg° SignAbbr` + ℞), with prev/next window paging, a "Today" jump, and today's row
      highlighted. Anchored to the active profile's place/tz.
- [x] **Bhava / house-cusp chart (Sripati/Placidus)** — `POST /api/astrology/bhava-chart`
      (`AstrologyCompute.get_bhava_chart`), method ∈ {SRIPATI ('O' Porphyry — matches
      Jagannatha Hora's Bhava Chalit), PLACIDUS ('P'), KP (3), EQUAL (1, KN Rao)} via
      `charts.bhava_chart(bhava_madhya_method=…)`. Unlike the Rasi chart (sign = house),
      it divides by **house cusps**, so a graha near a sign boundary can fall in a
      different bhava than its sign. Returns each of the 12 bhavas with start / madhya
      (cusp) / end longitudes + occupants, plus a `planets` map (each graha placed in the
      SIGN of the bhava it occupies) for the North/South Kundali. `BhavaChartPage` has a
      house-system selector, the Bhava Chalit Kundali, and a **house-cusp table**
      (bhava · sign · cusp `d°mm' Sign` · grahas).
- [x] **Print-ready "Full Report" PDF** — `FullReportPage` (`/report`) fans out to the
      existing endpoints (`birth-chart`, `yogas`, `doshas`, `transit`, `dhasa`) with
      `Promise.allSettled` so one failing source (e.g. the env-specific dasha path)
      degrades that section instead of blanking the report. Assembles a single document:
      masthead (name/born/place/ayanamsa/generated), vitals (Lagna/Moon/Nakshatra/Sun),
      Rasi (D1) + Navamsa (D9) charts, planetary-positions table, Vimsottari mahadasha
      timeline (when available), yogas, doshas, and current transits. A **Print / Save as
      PDF** button calls `window.print()`; `Report.css` `@media print` strips the app
      chrome (navbar, drawer, toolbar, background) and adds `break-inside: avoid` +
      `@page` margins so the browser's Save-as-PDF yields a clean paginated report.

Backend compute verified in the venv (all four bhava methods, ephemeris incl. the
92-day clamp, transit `house_from_moon`); routes registered; frontend `npx react-scripts
build` green. NOTE: the running container (:8000) still serves the pre-2026-07-04 build,
so it 404s the two new routes until it's redeployed — the code is correct, it just needs
a rebuild/restart to go live.

- [x] **DESKTOP DISCOVERABILITY FIX (2026-07-04, commit 23dfffc):** owner reported "I do
      not see [them] on the desktop". Root cause: the NavDrawer hamburger is **mobile-only
      (≤768px)** — desktop navigates via the **Dashboard feature tiles**, and the initial
      commit only added nav-drawer links. Added three Dashboard tiles (Ephemeris / Bhava /
      Full Report) with `dashboard.features.{ephemeris,bhava,report}` i18n titles+descriptions
      (en; hi/sa fall back). Build green. LESSON: every new page needs BOTH a NavDrawer link
      (mobile) AND a DashboardPage tile (desktop) to be reachable on all viewports.

---

## 19. Configurable branding / white-labelling (owner ask 2026-07-04)

- [x] **Site title + tagline via `.env`** — the hardcoded "PyJHora" wordmark is now driven by
      two build-time CRA vars (`web/frontend/.env`): `REACT_APP_SITE_TITLE` (defaults to
      "PyJHora") and `REACT_APP_SITE_TAGLINE` (blank → falls back to the translated
      `auth.tagline`). A new `src/config/branding.js` exposes `SITE_TITLE` / `SITE_TAGLINE`;
      the wordmark is wired through the nav drawer, dashboard header, and the login / register /
      forgot / reset / shared-chart pages. `App.js` sets `document.title = SITE_TITLE` on mount
      (the static `index.html` keeps a sensible default for the pre-hydration shell, since CRA
      leaves an *unset* `%REACT_APP_%` placeholder as a literal). Owner deployment set to
      **Jyotir AI** / "Where Vedic Wisdom Meets AI".
- [x] **Brand icon instead of the generic star** — new shared `src/components/BrandLogo.js`
      renders the built app icon (`public/icon-192.png`, the saffron sunburst badge) at any
      size, replacing the lucide `<Star>` in the nav drawer and dashboard header. The dashboard
      keeps the `.brand-icon` class so the saffron `pulse-glow` halo still animates around it.
- [x] **Full brand sweep across the `web/` tree (2026-07-04, follow-up)** — extended the
      rebrand so no *product* surface still hardcodes "PyJHora":
      - **Frontend i18n** — `shared.openApp`, `report.footer` and the push-`insecure` hint now
        interpolate `{{brand}}` (passed `SITE_TITLE` at each call site in SharedChartPage,
        FullReportPage, SettingsPage), across en/hi/sa.
      - **Static shell** — `index.html` uses CRA `%REACT_APP_SITE_TITLE%` substitution for the
        `<title>`/description/apple-title; `App.js` also sets `document.title` + those meta tags
        at runtime as a fallback for an unset build var. `manifest.json` (PWA name) and the
        `sw.js` push-fallback title are static brand assets (CRA can't inject env there), set to
        the owner brand alongside the icons.
      - **Backend** — new `SITE_NAME` setting (`config.py`, default "PyJHora", owner set to
        "Jyotir AI"): digest email subject/body (`digest.py`), password-reset email subject/body
        (`email_service.py`), the FastAPI docs title (`main.py`), and the AI system-prompt phrasing
        that names the chart-data source (`llm_service.py`). Documented in `backend/.env.example`.
- [x] **Full engine/infra rebrand (2026-07-04, owner ask "update engine references too")** —
      swept the remaining internal "PyJHora" mentions to the brand/engine-neutral names:
      - `astrology.py` — comments → "Jyotir AI", the `PYJHORA_AVAILABLE` flag → `ENGINE_AVAILABLE`,
        the `{"error": "PyJHora not available"}` dicts → `"Jyotir AI engine not available"`, and the
        Nominatim `user_agent` → `JyotirAIWeb`.
      - `/health` field `pyjhora_available` → `engine_available` (both `main.py` and the SettingsPage
        consumer). Settings → System label now reads "Astrology engine (Jyotir AI)".
      - `sw.js` cache key → `jyotir-ai-v1`; `dev.sh`, `docker-compose.yml` (container/network names
        `jyotirai-*`) and `Dockerfile`/compose comments rebranded.
      - **Database renamed `pyjhora_db` → `jyotirai_db`** in `config.py` default, `backend/.env(.example)`
        and `docker-compose.yml`. Requires a one-time Mongo data migration (mongodump/restore
        `--nsFrom pyjhora_db.* --nsTo jyotirai_db.*`) — the config change alone points the app at a
        fresh empty DB, so migrate before restarting.
- NOTE: **Real library refs kept.** `jhora` imports, `requirements.txt` PyJHora-4.8.7 deps, the
  README pip-install/fork URLs (`github.com/kunwarmahen/PyJHora`) and the Dockerfile "relative to
  PyJHora/" build-context path still say PyJHora — that's the actual upstream package/repo name.
  CRA bakes `REACT_APP_*` at build time, so title/tagline/icon changes need a rebuild/restart.

## 20. NAS deployment via Cloudflare Tunnel (owner ask 2026-07-05)

Ship the whole stack to the home NAS as Docker containers, fronted by Cloudflare for the
domain + SSL. Mirrors the calorieapp `deploy.sh` pattern (build locally → ship images over
SSH → `sudo docker compose up`) but tunnel-only, so **nothing is exposed on the LAN/router**.

- [x] **Single-origin architecture** — because all 109 backend routes live under `/api`
      (+ `/health`) and the frontend is a static build, one nginx serves the SPA and reverse-
      proxies `/api`,`/health` → `backend:8000`, giving Cloudflare a single HTTP origin:
      `Internet → Cloudflare edge (SSL) → cloudflared → nginx :80 → {static SPA, backend → mongodb}`.
- [x] **`cloudflared` container** (`docker-compose.nas.yml`) runs a *remote-managed* tunnel from
      a `TUNNEL_TOKEN`; the tunnel dials **out** to Cloudflare, so no port-forwarding and no
      published ports. Public hostname → service `http://web:80` is set in the CF dashboard.
- [x] **Same-origin frontend build** — `api.js` now treats `REACT_APP_API_URL=""` as *same-origin
      relative* (`/api/...`): no port, no cross-origin, no CORS. `Dockerfile.nas` bakes the empty
      value in (unset still keeps the LAN `:8000` auto-derive for `./dev.sh serve`).
- [x] **Mongo bundled** as a `mongo:4.4` container (see AVX note below) with a bind-mounted data
      dir (survives Docker reinstalls/firmware updates) + a healthcheck; the backend `depends_on`
      it `condition: service_healthy` since `connect_to_mongo()` pings and raises on startup. Data
      path is configurable via `MONGO_DATA_PATH` in `.env` (absolute, defaults to `./mongo-data`).
- [x] **`nginx/nginx.conf`** — SPA `try_files` fallback, long-cache `/static/`, and `proxy_buffering
      off` + 1 h timeouts on `/api/` for the SSE streaming (`/api/astrology/ask/stream`) and slow
      LLM calls.
- [x] **`dev.sh nas` command group** — `deploy | up | down | logs | ps | shell`. `deploy` builds
      both images locally (`jyotirai-backend`, `jyotirai-web`), gzips + scps them over an SSH
      ControlMaster (one password prompt), loads + retags on the NAS, and `docker compose up -d`.
      Config comes from `web/.env` / env vars: `NAS_HOST/USER/PATH/SSH_KEY/SSH_PORT`.
- [x] **`.env.nas.example`** documents every var (NAS conn, `TUNNEL_TOKEN`, `MONGO_PASSWORD`,
      `MONGO_DATA_PATH`, `SECRET_KEY`, `CORS_ORIGINS`, `APP_BASE_URL`, LLM/SMTP keys, branding
      build-args). **Comments live on their own lines above each var** — the shell/`env_file`
      parsers keep everything after `=`, so an inline `# comment` becomes part of the value.
- NOTE: **One-time owner setup** — create a CF *remote-managed* tunnel (Zero Trust → Networks →
  Tunnels), add a Public Hostname routed to `http://web:80`, copy the token; `cp .env.nas.example
  .env` and fill it in; then `./dev.sh nas deploy`. Assumes the NAS has the `docker compose` v2
  plugin and `sudo` docker (same as calorieapp). Tunnel-only means no LAN-direct fallback by design.

### First real deploy — issues found & fixed (2026-07-08, ASUSTOR AS6102T)

- [x] **Mongo AVX crash → pinned `mongo:4.4`.** The NAS CPU (Celeron J3355 / Apollo Lake) has no
      AVX, and `mongo:5.0+` dies on startup with `Illegal instruction` (SERVER-54407). 4.4 is the
      last AVX-free release. Its data files are an older format, so don't "upgrade" the tag without
      a dump/restore. See the version pin + comment in `docker-compose.nas.yml`.
- [x] **Healthcheck `mongosh` → `mongo`.** `mongosh` only ships in mongo 5.0+, so on 4.4 the probe
      was "not found" — `mongod` ran fine but health never went green, so `depends_on:
      service_healthy` hung and the deploy failed while Portainer showed the container "starting".
- [x] **`npm ci` lockfile mismatch.** The build box's npm 11 wrote a `package-lock.json` that
      `node:18-alpine`'s npm 10.8.2 rejected (`Missing: yaml@2.9.0`). Regenerated the lock **with
      the image's npm** (10.8.2) so both agree; it also validates under npm 11.
- [x] **`.env` inline comments corrupted values.** `NAS_USER`/`NAS_HOST`/`MONGO_PASSWORD` had the
      example's trailing `# ...` comments folded into the values (SSH "invalid characters"; broken
      DB password). Moved all example comments to their own lines (root-cause fix in the template).
- [x] **`OLLAMA_URL` trailing slash → 307.** A trailing `/` made `{url}/api/tags` a `//api/tags`
      double slash; Ollama answers `307` and httpx doesn't follow it. `llm_service.py` now
      `rstrip("/")`s the base URL at every call site so it can't recur.
- [x] **`MONGO_PASSWORD` must avoid `@`** — it's injected raw into `mongodb://user:pass@host`, and a
      literal `@` breaks URI parsing. Documented in `.env.nas.example`.

## 21. Export / import birth profiles (owner ask 2026-07-08)

Let users move their saved birth profiles (name, DOB, time, place, coordinates, timezone)
between accounts/devices as a portable JSON file. Lives on the profile-selection screen.

- [x] **Portable JSON envelope** — `{app, type:"profiles", version:1, exported_at, count, profiles:[]}`,
      where each profile is just `{profile_name, birth_details, is_default}` (no user/DB ids), so a
      file exported from one account imports cleanly into any other.
- [x] **Export** — done client-side in `ProfileContext.exportProfiles(subset?)` from the already-
      loaded `profiles` list (no round-trip); downloads `jyotirai-profiles-YYYY-MM-DD.json`. A
      matching **`GET /api/profiles/export`** endpoint returns the same envelope for API/testing.
- [x] **Selectable export** (owner ask 2026-07-09) — Export enters a selection mode on the
      profile-selection screen: each card shows a checkbox (all pre-selected), with select-all/none
      and a live count; "Export (N)" downloads only the chosen profiles. Edit/delete + the create-new
      card are hidden while selecting. i18n `profile.{cancel,exportSelectHint,exportSelectAria,
      exportSelected,selectedForExport,tapToSelect,selectAll,selectNone}` (en/hi/sa).
- [x] **Import** — **`POST /api/profiles/import`** (`ImportProfilesRequest`) bulk-inserts via one
      `insert_many`. **Dedups** on `(profile_name, dob, tob)` against existing + within the file, so
      re-importing the same file is a no-op; forces `is_default=False` so imports never clobber the
      account's current default. Returns `{imported, skipped}`. Frontend `importProfiles()` accepts
      either the envelope or a bare array and strips to the expected fields before posting.
- [x] **Default profile control** (owner ask 2026-07-09) — `is_default` existed in the schema +
      save/update endpoints but was **unreachable from the UI** (no toggle; `updateProfile` even
      reset it to false on every edit), so no profile was ever default and the digest's
      `resolve_profile` always fell through to "first saved profile". Fixed: new **`PUT
      /api/profiles/{id}/default`** (`SetDefaultRequest`) sets/clears default, clearing every other
      first so at most one is default; the update endpoint no longer writes `is_default` (edits
      can't clobber it). Frontend `ProfileContext.setDefaultProfile(id, bool)`; ⭐ star toggle +
      "Default" badge on each profile card (`ProfileSelectionPage`). i18n `profile.{defaultBadge,
      setDefaultAria,unsetDefaultAria}` (en/hi/sa). Honored by the daily digest fallback.
- [x] **UI** — Import/Export buttons in a `.profiles-toolbar` above the profiles grid
      (`ProfileSelectionPage`), hidden `<input type=file accept=.json>`, resets its value so the same
      file can be re-picked. i18n `profile.{export,import,exportEmpty,importDone,importFailed}`
      (en/hi/sa). README Features §20 + API Endpoints updated.

## 22. Local AI (Ollama) — surface the configured model + survive redeploys (owner ask 2026-07-09)

Two owner-reported bugs: (a) **Settings → System** always showed "Local AI model (Qwen)" as
**Off** and never displayed the model value; (b) `OLLAMA_URL` / `OLLAMA_DEFAULT_MODEL` set on
the server were **not reflected in Settings → AI** — the model field showed blank, so the owner
retyped it by hand every deploy and lost it (it only lived in per-browser `localStorage`).

- [x] **Root cause.** The System tab read `health.qwen_enabled`, which is the **legacy
      `USE_QWEN` flag** (default `False`) — it never looked at the Ollama config, so it read "Off"
      regardless. And the AI-tab model field only fell back to the server default inside the
      `<select>` (shown when Ollama is reachable *and* has models); in the **text-input branch**
      (Ollama unreachable at load, or no models installed yet) it bound to the empty
      `settings.aiModel` with a generic placeholder, hiding `OLLAMA_DEFAULT_MODEL` entirely.
- [x] **Backend `/health` now probes Ollama** (`main.py`) — calls `llm_service._ollama_status()`
      and returns a **`local_ai: {available, base_url, model, reason}`** block (model = effective
      `OLLAMA_DEFAULT_MODEL`, or the first installed model when that isn't pulled). No new docker
      healthcheck depends on `/health`, so the short probe is safe.
- [x] **Settings → System** (`SettingsPage.js`) — the local-AI row is driven by
      `health.local_ai.available` (not the legacy flag), flips to **OK** when Ollama is reachable,
      and shows the value **`<model> · <base_url>`** underneath (new `.settings-health-value`
      style). Visible even when unreachable so the owner can confirm what's configured. Row
      relabelled **"Local AI (Ollama)"** (`settings.system.localAi`, en/hi/sa).
- [x] **Settings → AI** (`SettingsPage.js`) — the model **text input** now placeholders the
      server default (`activeProvider.default_model`), and when the field is blank a hint reads
      *"Using the server default: <model>…"* (`settings.ai.serverDefault`, en; hi/sa fall back).
      Blank = use the server's `OLLAMA_DEFAULT_MODEL`, which is **server-side and survives
      redeploys** — no per-browser setting to redo. The backend already resolves an empty model to
      `OLLAMA_DEFAULT_MODEL`, so this is purely making the existing behaviour visible.

### 22.1 Rip out the dead pre-Ollama "Qwen" path (owner ask 2026-07-09 — "do we really need it?")

The `USE_QWEN` / `QWEN_API_URL` / `QwenPredictor` integration was a **separate, pre-Ollama**
local-LLM client (hit its own server at `QWEN_API_URL` = `localhost:5000/v1/completions`, gated
behind `USE_QWEN`, default off) that the unified `llm_service` (Ollama/OpenAI/Gemini) fully
superseded. It was dead — off by default and never wired into any modern page. Removed it and
moved its one remaining consumer onto the real service.

- [x] **Backend removal** — deleted `qwen_predictor.py`, its import, the `use_qwen && USE_QWEN`
      branches in `/api/astrology/horoscope` (+ the `generate_basic_predictions` rule-based
      fallback) and `/api/astrology/compatibility`, the `use_qwen` request field, the `USE_QWEN` /
      `QWEN_API_URL` settings, the `QWEN_API_URL` fallback in `llm_service`, and the `qwen_enabled`
      `/health` field. `horoscope` and `compatibility` now return deterministic data only; AI lives
      at `/api/astrology/predict` and `/api/astrology/compatibility-analysis`.
- [x] **Predictions page rewired to the unified LLM service** (`PredictionsPage.js`) — the old
      "Use AI (Qwen)" checkbox called `/horoscope?use_qwen=true`, which (USE_QWEN off) silently
      returned the rule-based `generate_basic_predictions`, not real AI. Now: the page fetches chart
      data from `/horoscope`, and when "Use AI" is ticked calls `astrologyService.generatePrediction`
      (→ `/api/astrology/predict`) with the user's Settings → AI provider/model (`readModelConfig()`
      from localStorage), rendering the reading as Markdown (`ReactMarkdown`) with the model name.
      i18n `predictions.{useAi,aiError,aiModel}` refreshed (Qwen wording dropped) in en/hi/sa.
      `api.js`: dropped the `use_qwen` params from `getHoroscope`/`getCompatibility`.
- [x] Docs: README (removed `qwen_predictor.py` / `USE_QWEN` / `QWEN_API_URL` mentions, backend
      component list now lists `llm_service.py`), `backend/.env.example`, and `docker-compose.yml`
      (dropped `QWEN_API_URL`/`USE_QWEN`, added `OLLAMA_URL`/`OLLAMA_DEFAULT_MODEL` with a
      host.docker.internal note). Backend `py_compile` + frontend production build both green;
      `/health` verified against live Ollama (`local_ai.available:true`, model surfaced).

## 23. Daily digest — multi-profile + "how the day looks" narrative (owner ask 2026-07-09)

Two owner asks: (a) the digest only ever went to **one** profile (the chosen `profile_id`, else
default) — extend it to cover **several** profiles; (b) the delivered email/push carried only the
terse rule-based highlights — add a warm **"how the day looks"** reading. Decisions (owner):
**subset + an "All profiles" shortcut**, **one combined message** (a section per profile), and an
**AI narrative with a rule-based fallback** so a scheduled send never fails when the LLM is down.

- [x] **Prefs schema** (`notifications.py`) — added `profile_ids: []` (explicit set),
      `all_profiles: true` (**default**: every saved profile, including any added later), and
      `include_ai: true` (embed the narrative). Legacy `profile_id` kept for back-compat; `set_prefs`
      whitelists/coerces the new keys (list-of-str / bool / bool).
- [x] **BUGFIX (2026-07-09):** the new prefs never persisted — clicking a profile checkbox reverted
      it. Root cause: `NotificationPrefsRequest` (main.py) didn't declare `profile_ids`/`all_profiles`/
      `include_ai`, so Pydantic silently dropped them and the PUT echoed back the old prefs. Added the
      three fields to the request model. Also flipped the default to **all profiles** per owner ask.
- [x] **`digest.py` rewrite** — new `resolve_profiles(user_id, prefs)` returns **every** profile to
      cover, precedence `all_profiles` → `profile_ids` (order-preserving, owned-only) → legacy
      `resolve_profile` (chosen/default/first). `send_digest_for_user` now builds one section per
      profile: `AstrologyCompute.get_daily_digest` + an AI narrative from
      `llm_service.analyze_daily_digest` (server-default config via new `_digest_cfg`, topped up with
      the user's stored key for keyed providers). **Fallback**: any LLM error/empty → that section
      falls back to highlights only (logged, never raised). One combined **email** (`_render_text` /
      `_render_html`, HTML-escaped, per-profile `<h3>` when >1) and a single **push** ("Digests for
      Alice, Bob are ready." when multiple, else the first highlight). Returns
      `{status, sent, profiles:[names], date}`.
- [x] **Scheduler** (`scheduler.py`) — `_profile_tz` now paces off `resolve_profiles(...)[0]` (the
      first chosen profile) rather than the single legacy profile, so multi-profile users still get a
      sensible once-a-day local-hour trigger. The atomic per-day `last_sent_date` claim is unchanged.
- [x] **Settings → Notifications** (`SettingsPage.js`) — the single-profile `<select>` is replaced by
      an **"All my profiles"** checkbox + a per-profile checklist (`.settings-checklist`), plus an
      **"Include AI 'how the day looks' reading"** switch. Saves `profile_ids`/`all_profiles`/
      `include_ai`; migrates a legacy `profile_id` into the checklist on first toggle. New i18n keys
      `settings.notifications.{profiles,allProfiles,noProfiles,includeAi}` + refreshed `intro` (en;
      hi/sa fall back to English as the rest of this block already does).

### 23.1 Sync the LLM/model choice across devices (owner ask 2026-07-09)

The AI provider/model/base-url/mode/max-tokens lived only in per-browser `localStorage`, so the
choice didn't follow the user across devices — and, more importantly, the **scheduled** digest had
no request context to read it from, so its AI narrative always used the server default. Now the
LLM preference is persisted server-side per user.

- [x] **Backend store** (`user_settings.py`) — new `PREFERENCE_KEYS`
      (`ai_provider_type`/`ai_model`/`ai_base_url`/`ai_mode`/`ai_max_tokens`) + `get_preferences` /
      `set_preferences` (whitelisted, string-coerced, upserted under `preferences.<key>` on the
      existing `user_settings` doc — sibling of `api_keys`/`notifications`; non-secret, so plain).
      Endpoints `GET`/`PUT /api/user/preferences` (`PreferencesRequest`).
- [x] **Digest uses it** (`digest.py` `_digest_cfg`) — rebuilds the `ModelConfig` from the user's
      stored preferences (provider/model/base-url + clamped max-tokens) instead of only the server
      default, still topping up the API key from the encrypted `api_keys` store. So a scheduled
      narrative renders with the model the user actually picked. Verified: stored openai-compatible
      prefs → that provider/model/base-url/key; empty prefs → server-default Ollama.
- [x] **Frontend sync** (`SettingsContext.js`) — on login it **pulls** the server copy of the synced
      keys (server = source of truth; seeds the server from this device if it has none yet), and each
      change is **debounced (600 ms) back up** via `authService.putPreferences`. localStorage stays
      the fast local cache so pages read values unchanged and offline still works. `api.js`
      `getPreferences`/`putPreferences`. Only the LLM keys sync today (language/ayanamsa/chart-style
      remain local by design); `SYNCED_KEYS` makes extending trivial.

## 24. Sign in with Google (owner ask 2026-07-09)

Add "Continue with Google" alongside the existing username/password auth. Decisions (owner):
**username = the Google email**, **auto-link** a Google sign-in to any existing account with the same
email (same verified email = same account), and use the **Google Identity Services** button flow
(must also work on `localhost` for testing). Feature is fully optional — unset `GOOGLE_CLIENT_ID`
and nothing changes; password auth is untouched.

- [x] **Backend endpoint** (`main.py`) — new `POST /api/auth/google` (`GoogleAuthRequest{credential,
      remember_me}`). Verifies the GIS ID token with `google-auth`
      (`id_token.verify_oauth2_token`, audience = `GOOGLE_CLIENT_ID`), requires `email_verified`, then
      **find-or-create** keyed on `google_sub`/`email`/`username==email`: an existing row gets
      `google_sub`/`auth_provider` backfilled and is signed straight in (links password ↔ Google); a
      new row is created with `username=email`, `auth_provider:"google"`, **no** `hashed_password`.
      Issues the normal JWT pair via `_issue_token_pair`. Returns 503 when `GOOGLE_CLIENT_ID` unset.
- [x] **Password-path hardening** — Google-only users have no `hashed_password`, so `login`,
      `change-password`, `delete-account` now read `user.get("hashed_password")` (delete lets a
      password-less account confirm with just its valid token). **BUGFIX:** `GET /api/user/profile`
      did `del user["hashed_password"]` → `KeyError` on the first load after Google sign-in; now
      `.pop(..., None)`. A Google-only user can set a password later via forgot-password.
- [x] **Config** — `GOOGLE_CLIENT_ID` in `config.py` (backend) + `REACT_APP_GOOGLE_CLIENT_ID` baked
      into the frontend build (must match). `google-auth==2.38.0` added to `requirements.txt`.
- [x] **Frontend** — new `GoogleSignInButton.js` loads the GIS script once, renders Google's official
      button, and exchanges the token via `authService.googleLogin` → `AuthContext.loginWithGoogle` →
      normal JWT session → `/profile-selection`. Renders **nothing** when
      `REACT_APP_GOOGLE_CLIENT_ID` is unset. Added to `LoginPage`/`RegisterPage` with an "or" divider
      (`Auth.css`).
- [x] **Deploy plumbing** — `dev.sh` passes both vars from `web/.env` into local dev (backend env +
      CRA dev server) and the NAS build arg; `Dockerfile.nas` declares the build ARG;
      `docker-compose.yml` interpolates both; NAS backend picks up `GOOGLE_CLIENT_ID` via `env_file`.
      Documented in `.env.nas.example`, `README.md` (backend + frontend env blocks).
- [x] **Nice-to-have (deferred):** Settings shows **"Set a password"** instead of "Change password"
      for password-less accounts. `GET /api/user/profile` now returns `has_password`; when false the
      Settings → Account form drops the *Current password* field and titles/button read "Set a
      password" / "Set password". `POST /api/auth/change-password` skips the current-password check
      when the account has no `hashed_password` yet (still verifies it for accounts that have one), so
      a Google-only user can set a first password in-app instead of via forgot-password. i18n:
      `settings.account.{setPassword,setBtn,passwordSet,setNote}` (en; hi/sa fall back). (2026-07-11)

### 24.1 Person's name — collect at signup, pull from Google, show in the UI (owner ask 2026-07-09)

The app only ever knew a `username` (= the email for Google users), so the UI greeted people with a
raw email. Owner ask: **collect a Name at registration (required)**, **pull it from Google** on
Google sign-in, and **display it** (dashboard greeting, Settings → Account, nav drawer). Existing
accounts with no name **silently fall back** to username.

- [x] **Backend** (`main.py`) — `RegisterRequest` gains a required `name` (trimmed, non-empty →
      stored on the user doc). Google endpoint already stores `name` for new users; now it also
      **backfills** `name` from the Google profile onto a linked/existing account that has none (never
      overwrites a user-set name). New `PUT /api/auth/name` (`UpdateNameRequest`, ≤100 chars) to edit
      it. `GET /api/user/profile` already returns the whole doc, so `name` flows to the client.
- [x] **Frontend** — `RegisterPage` adds a required Name field (first in the form);
      `authService.register` / `AuthContext.register` thread `name` through. `DashboardPage` greeting
      shows `user.name || user.username`. `SettingsPage → Account` shows Name in the overview + an
      editable Name form (`authService.updateName` → `reloadUser`). `NavDrawer` footer shows the
      name (email as a secondary line) — `nav-drawer-account` styles in `NavDrawer.css`.
- [x] **i18n** — `auth.name`/`auth.namePlaceholder` in en/hi/sa; `settings.account.{name,
      namePlaceholder,updateName,nameUpdated,nameError}` in en (hi/sa fall back to English, as the
      rest of the settings block already does).

## 25. Weekly & monthly readings (owner ask 2026-07-12)

> ⚠️ **Partly superseded — see §25.1.** The **Weekly** rung described below was replaced by a
> **Fortnightly** one once we established that a 7-day week has no rung on *either* pravesha ladder
> (which is exactly why Jagannatha Hora offers daily/fortnightly/monthly/annually and no weekly). The
> Monthly rung and all the notification plumbing here still stand. Kept as-is for the record.

Extend the digest concept beyond the day: a **Weekly** and a **Monthly** reading, delivered the same
three ways as the daily digest (**in-app page**, **email**, **push**) with **independent opt-in per
cadence**. Content should blend **current Vimshottari dasha/bhukti** with the window's **transits**,
and — where a genuine technique exists — layer in a **Varshaphal-style progressed chart**.

**Engine capability (verified 2026-07-12):** `src/jhora/horoscope/transit/tajaka.py` already
supports Tajaka progressions the same way `get_varshaphal` uses annual:
- **Monthly = real technique.** `tajaka.maasa_pravesh` / `monthly_chart(jd_dob, place, dcf, years,
  months)` builds the **Maasa Pravesha** (monthly solar-return) chart. Mirror
  `AstrologyCompute.get_varshaphal` (`astrology.py:2277`) → new `get_masa_pravesh` for the current
  lunar/solar month, then run tajaka yogas + dasha on it exactly as annual does.
- **Weekly = no native Tajaka unit.** Below the month Tajaka only has the ~2.5-day "sixty-hour"
  (`next_solar_date(..., sixty_hours=n)`), not a 7-day unit. So the weekly reading is a **dasha +
  7-day transit aggregate** (ingresses, retrograde stations, key natal aspects over the coming week),
  optionally anchored to the active Maasa-pravesha chart — not a literal "week pravesh."

DONE 2026-07-12 (mirrors §23 daily-digest plumbing throughout):
- [x] **Compute** (`astrology.py`) — `get_masa_pravesh(dob,tob,place,…,date/year/month)` wraps
      `tajaka.maasa_pravesh` (auto-selects the pravesh window containing the date via the linear
      solar-year fraction; returns chart/lagna/planets/muntha/year-lord/sahams/tajaka-yogas + the
      window start→end). `_period_digest(period,…)` is the shared builder behind `get_weekly_digest`
      / `get_monthly_digest`: blends the running dasha with `_transit_events_in_window` (all-graha
      ingresses + retrograde stations scanned across the window via `next_planet_entry_date` /
      `next_planet_retrograde_change_date`) + the opening Panchanga; **weekly = today→+7 days**,
      **monthly = the whole Maasa Pravesha window** (~30.4 days), which also carries the pravesh chart.
- [x] **Endpoints** (`main.py`) — `POST /api/astrology/{weekly,monthly}-digest`
      (+ `…-analysis`). Prompts: one shared `llm_service._build_period_digest_prompt(d,name,period)`
      behind `analyze_weekly_digest` / `analyze_monthly_digest`; readings saved to AI history (§17) as
      new sources `weekly_digest` / `monthly_digest` (registered in `conversations.py` with routes).
- [x] **Notification prefs** (`notifications.py`) — added per-cadence `weekly`/`monthly` switches,
      each with its own day (`weekly_dow` 0-6 / `monthly_dom` 1-28) + hour (`weekly_hour`/
      `monthly_hour`); daily keeps `daily_digest`/`hour`. Channels + `profile_ids`/`all_profiles`/
      `include_ai` are **shared** across cadences. Legacy daily keys untouched (back-compat).
- [x] **Delivery** (`digest.py` + `scheduler.py`) — `send_digest_for_user(user_id,prefs,cadence)`
      + `_profile_block(...,cadence)` route to the right compute + `analyze_*` via a `_CADENCES` map;
      renders cadence-aware subject/noun/push-URL. Scheduler runs a pass per cadence (`_run_cadence`):
      weekly gated on chosen weekday+hour (claim key `%G-W%V`), monthly on day-of-month+hour (claim
      key `%Y-%m`), each with its own atomic `last_sent_weekly`/`last_sent_monthly` claim so only one
      worker sends per window. Manual `POST /api/notifications/digest/send?cadence=` for cron fallback.
- [x] **Frontend** — one shared `PeriodDigestPage` (props `period`) exports `WeeklyDigestPage`
      (`/weekly-digest`) + `MonthlyDigestPage` (`/monthly-digest`): highlights, opening panchanga,
      dasha, transit-events list, the Maasa Pravesha card (monthly only), AI reading + RecentReadings.
      Nav-drawer + dashboard tiles added. Settings → Notifications now has three cadence toggles, each
      with its own day/hour picker, shared channel/profile controls, and per-cadence "send test" links.
- [x] **Tools + conversations** — `get_weekly_digest` / `get_monthly_digest` tools registered in
      `tools.py` (ALWAYS_TOOLS + display catalog) so Ask-Astrologer can pull them; sources + routes
      added to `conversations.py`.
- [x] **i18n** — new `periodDigest.*` block + `nav.weeklyDigest`/`nav.monthlyDigest`,
      `dashboard.features.{weekly,monthly}Digest`, and `settings.notifications.*` cadence keys (en;
      hi/sa fall back to English).

**Note — the monthly window is a *solar-return* month, not a calendar month.** The Monthly page shows
the Maasa Pravesha window the day falls in (e.g. "Jun 15 → Jul 17"), matching how Varshaphal shows the
whole solar year.

### 25.1 Weekly → **Fortnightly**, and the lunar (Tithi Pravesha) ladder (owner ask 2026-07-12)

Owner pushed back on the weekly rung ("why can't weekly be like monthly — at least give an option")
and then made the key observation: **Jagannatha Hora only offers daily / fortnightly / monthly /
annually.** Investigating why closed the question — those four are the **lunar (tithi) ladder**, and
it is complete, whereas the solar one is not:

| Cadence     | Solar basis (Tajaka)              | Lunar basis (tithi)                        |
|-------------|-----------------------------------|--------------------------------------------|
| Daily       | — *(no rung; sixty-hour ≈ 2.5d)*   | **Tithi** (~0.98d)                          |
| Fortnightly | — *(no rung)*                     | **Paksha Pravesha** (~14.8d)                |
| Monthly     | **Maasa Pravesha** (~30.4d)       | **Birth-tithi return** (~29.5d)             |
| Annual      | **Varshaphal** (~365d)            | **Tithi Pravesha** (~354d)                  |

A 7-day week has **no rung on either ladder** — which is exactly why JHora has no "weekly" and why the
first cut of §25 couldn't give weekly a chart. Owner decisions: **replace Weekly with Fortnightly**,
**global basis default + per-page override**, and **build all four lunar rungs**.

DONE 2026-07-12:
- [x] **Engine facts pinned.** `vratha.tithi_pravesha(birth_date, birth_time, place, year)` exists and
      works (also reachable as `charts.rasi_chart(..., pravesha_type=2)`; `const._PRAVESHA_LIST` names
      it) — it is **annual only** (the natal tithi *and* lunar month recurring, ~354d). The sub-annual
      lunar rungs are NOT in the engine, so we solve them off drik's tithi-boundary primitives
      (`_tithi_number_at_jd` + `_tithi_boundary_jd`, a bisection on the tithi change).
      **GOTCHA:** `drik.next_tithi` is marked *UNDER EXPERIMENTATION* and its backward branch is wrong
      (`inc_days = -tithi_ - required_tithi` sums the indices instead of differencing) — never use it;
      walk boundaries instead.
- [x] **Compute** (`astrology.py`) — `_tithi_num` / `_tithi_bound` / `_walk_tithi` primitives; window
      solvers `_tithi_window`, `_paksha_window` (Shukla = tithis 1-15, Krishna = 16-30; walks back to
      the paksha's first tithi and forward to the next paksha's), `_lunar_month_window` (birth-tithi
      return via `_tithi_index_start`); shared `_pravesha_block` (Lagna/planets/Muntha/year-lord/Tajaka
      yogas) now backs **every** rung, solar or lunar. Public: `get_lunar_pravesha(rung=…)` +
      `get_tithi_pravesha()`. Verified: tithi 0.85d · paksha 14.41d (boundaries land exactly on tithi
      16→1) · lunar month 29.44d (both ends on birth tithi #20) · TP 354.00d.
- [x] **Digests reworked** — `get_weekly_digest` → **`get_fortnightly_digest`** (the running paksha +
      its Paksha Pravesha chart; lunar-only by definition). `get_monthly_digest(basis=…)` and
      `get_daily_digest(basis=…)` now take the ladder: solar → Maasa Pravesha, lunar → birth-tithi
      return (monthly) / the day's tithi chart (daily). `_period_digest` returns `basis` +
      `window_label` so the UI/prompt can name the rung honestly.
- [x] **Endpoints** — `POST /api/astrology/fortnightly-digest`(+`-analysis`), `tithi-pravesha`
      (+`-analysis`); `basis` param on daily/monthly (`_basis()` normalizer). New AI-history sources
      `fortnightly_digest` + `tithi_pravesha`. Prompts: `_build_period_digest_prompt` names whichever
      chart was actually cast; new `_build_tithi_pravesha_prompt` (explains TP as the lunar-return
      counterpart, read *alongside* Varshaphal).
- [x] **Notifications** — cadence `weekly` → **`fortnightly`**. The **paksha boundary IS the schedule**:
      no day picker, just an hour; the scheduler's claim key is the running paksha's start date
      (`_paksha_claim_key`, e.g. `Krishna-2026-06-30`), so it fires exactly once per fortnight. New
      shared `basis` pref feeds the delivered readings.
- [x] **Tools** — `get_fortnightly_digest`, `get_monthly_digest(basis)`, `get_tithi_pravesha` (replaces
      `get_weekly_digest`).
- [x] **Frontend** — `WeeklyDigestPage` → **`FortnightlyDigestPage`** (`/fortnightly-digest`); Monthly
      gains a **Solar / Lunar** toggle (defaults to the global setting, overridable per page); new
      global **`praveshaBasis`** in `SettingsContext` (localStorage `pravesha_basis`) surfaced in
      Settings → General; new **`TithiPraveshaCard`** on the Varshaphal page (own fetch + AI reading,
      collapsible, opens by default when the global basis is lunar) — additive, so the solar annual
      flow is untouched and the two annual charts are read side by side, as tradition has it.
      i18n: `periodDigest.*` reworked + new `tithiPravesha.*`, `settings.general.pravesha*`.

- [x] **(P1) BUGFIX 2026-07-12 — Monthly (lunar) failed to load in prod; basis toggle showed no
      selection** (owner report on jyotirai.win). Two separate bugs:

      **(a) Timeout — the whole digest was far too slow.** `_transit_events_in_window` used
      `drik.next_planet_entry_date` / `next_planet_retrograde_change_date`, which search *forward until
      they find the event* — for a slow graha that can mean stepping months (Saturn: much of a 29-yr
      cycle). It cost **2.77s** locally, i.e. tens of seconds on the NAS, and the gateway timed the
      request out; a 504 returns HTML with no `detail` field, which is exactly why the UI showed the
      *generic* "Couldn't build your reading" rather than a real message. Additionally
      `_tithi_index_start` walked every tithi boundary (**1254** `tithi()` calls, each an
      inverse-Lagrange over 17 lunar-phase samples) — lunar-only extra cost on top.
      FIXED: (1) `_transit_events_in_window` now **samples the window daily and bisects any change**
      (`rasi_chart` is 0.04ms, `planets_in_retrograde` 0.01ms, so the scan is bounded by the window,
      not by how far away the next event is); (2) `_tithi_index_start` **jumps straight to the
      estimated recurrence** off the synodic month and settles (69 calls, not 1254) — verified
      **identical** to the old boundary-walk for all 30 tithi indices, both directions; `_paksha_window`
      reuses it (31/31 days of a lunation land exactly on tithi 1↔16).
      Result: **2.7–3.9s → 12–65ms** per digest (~60–100×). The rewrite is also **more correct**: the
      old "next event per planet" scan could only ever report *one* event per graha, so it missed most
      of them (solar month: **2 events → 7**, incl. Mercury stationing *and* re-ingressing in the same
      window). Same events it did find reproduce on identical dates.


      **(b) Toggle had no active state.** The Monthly Solar/Lunar toggle used
      `control-btn is-active` — a class combination that **exists in no stylesheet** (`.control-btn` has
      no active variant). Switched to the app's real segmented control, `.chart-toggle` /
      `.chart-toggle__btn.is-active` (saffron fill), + `aria-pressed`; gave `.chart-toggle__btn`
      `inline-flex`/`gap` so it can carry a leading icon, and a hover state. Same bug in Settings →
      General, where the new basis control wrote `settings-seg` instead of the real
      **`settings-segment`** container — fixed.

### 25.2 Varshaphal timeouts, and Tithi Pravesha promoted to a full annual view (owner ask 2026-07-12)

- [x] **(P1) BUGFIX — Varshaphal "fails sometimes"** (owner report; confirmed as *slow, then a generic
      error* = the gateway-timeout signature). Profiling showed **36,632 `sidereal_longitude` calls per
      Varshaphal** (73k for Narayana, which pays it twice): `dhasa_year_duration` → `true_sidereal_year`
      locates the Sun's ingress into sidereal Aries with `previous/next_planet_entry_date`, which default
      to **0.01-day micro-steps** — so reaching an ingress up to a year away costs ~36,500 steps. ~650ms
      locally → seconds-to-tens-of-seconds on the NAS. (Same micro-stepping trap already pinned for
      `next_planet_entry_date` in §11's Bhrigu fix — it keeps resurfacing.)
      FIXED with a documented module-level patch of `drik.true_sidereal_year` in `astrology.py`: the Sun
      moves ~0.9856°/day, so we predict each ingress to within a day and **seed the engine's own search
      ~5 days short of it**. It micro-steps those few days instead of a whole year — its own search, its
      own tolerance, so the value is **bit-identical** (verified 1970–2075: 18/18 exact) at ~36x fewer
      calls. Annual-dasha output verified identical across mudda/patyayini/narayana × 4 years (12/12).
      **get_varshaphal: 651ms → 24ms.** This also speeds up every other dasha that uses
      `dhasa_year_duration` (chara, sudasa, …).
- [x] **Tithi Pravesha crashed for 29-Feb births** — the engine centres its ±30-day search on
      `Date(year, birth_month, birth_day)`, which does not exist in a non-leap target year (numpy
      datetime error). New `_tithi_pravesha_dates()` clamps the *anchor* to 28 Feb (it only centres the
      window, so the located date is unchanged) while the birth tithi / lunar month still come from the
      true birth date. Non-leap births take the engine's own path untouched. Also guarded a latent
      `IndexError` when next year's TP couldn't be resolved.
- [x] **Tithi Pravesha → a full annual view with a Solar/Lunar toggle** (owner: *"same toggle for them"*,
      **strictly one at a time**). The bottom TP card is gone; `/varshaphal` now has a **Solar / Lunar**
      toggle like Monthly:
      - **Solar** → Varshaphal (Tajaka solar return) — unchanged.
      - **Lunar** → **Tithi Pravesha**, now at **full parity**: Kundali chart, Muntha, year-lord, the 8
        Sahams, Tajaka yogas, **and its own dasha**.
      - **The dasha is Tithi Ashtottari** — owner confirmed this is what Jagannatha Hora pairs with the
        TP chart, and the pairing is the point: a *tithi*-reckoned dasha for a *tithi*-reckoned chart.
        Engine has it at `dhasa/graha/tithi_ashtottari.py`. **GOTCHA:** its public entry point is
        `get_dhasa_bhukthi`; PyJHora's own `horoscope/main.py` calls a `get_ashtottari_dhasa_bhukthi`
        that **does not exist on that module** — that upstream path is broken, so call the real one.
        Rows are `[(lord,), (y,m,d,fh)]` with **no duration**, so ends derive from the next start.
        Verified: 8 maha periods, Jupiter 19 + Rahu 12 + Venus 21 + Sun 6 + Moon 15 + Mars 8 +
        Mercury 17 + Saturn 10 = **108 years** (the exact Ashtottari allotments).
      - The Tajaka annual dashas (Mudda/Patyayini/Narayana) stay **solar-only** — they belong to the
        solar return — so that picker hides on the Lunar side. Both compute layers return the *same*
        shape, so the whole page renders from `result` either way. History deep-links restore the right
        basis (`source === "tithi_pravesha"` → Lunar).
- [x] **⚠️ LANDMINE PINNED — `_set_ayanamsa()` must run on the MAIN thread.** Swiss Ephemeris keeps its
      sidereal mode in process-global C state; calling `set_ayanamsa_mode` from a **worker thread**
      corrupts it, and every later `swe.calc_ut` then gets a garbage JD
      (`jd -0.001010 outside Moshier planet range`) → every compute returns `failed`. Verified: on a
      worker thread `swe.julday` / `rasi_chart` / `planets_in_retrograde` all work **until**
      `_set_ayanamsa` is called, after which they all fail. **We are safe only because all 129 endpoints
      in `main.py` are `async def`** (checked: zero sync ones), so handlers run on the event loop.
      Declaring one endpoint as a plain `def` — or wrapping a compute in `run_in_threadpool` /
      `asyncio.to_thread` — would silently break every chart on the site. This is also why `TestClient`
      (which drives the app from a worker thread) reports failed transits where a real request succeeds:
      a harness artifact of the same root cause, **not** a production bug. Documented in `_set_ayanamsa`.

- [x] **(P1) FOLLOWUP 2026-07-12 — TP dasha spanned a lifetime; basis toggle hopped position** (owner report):
      - **Dasha showed 1958–2066.** Tithi Ashtottari is a **108-year life dasha**, so its *maha* periods
        run 6–21 years each — a whole-life table next to a 354-day Tithi Pravesha window is useless.
        (Mudda doesn't have this problem because it *compresses* Vimsottari into the annual chart's year;
        Tithi Ashtottari is not an annual dasha and has no such compression.) FIXED:
        `get_tithi_ashtottari` now takes `window_start`/`window_end`; when given, it computes at the
        **antara** level (`dhasa_level_index=3` — the granularity that actually subdivides a year) and
        keeps every period **overlapping** the window (not merely starting inside it, or the period
        already running when the lunar year opens would be dropped). Yields ~10–13 rows spanning the
        window with no gaps, the direct analogue of Varshaphal's 9-row annual table, current row flagged.
        Sanity-checked against the allotments: Venus maha 21y → Venus bhukti 21×21/108 = 4.08y →
        Venus antara 4.08×21/108 = 9.5 months, matching the computed row exactly. Without a window the
        full maha-level life timeline is still returned (the standalone tool path).
      - **Basis toggle hopped middle↔right.** `.page-controls` is `justify-content: space-between`, and
        the toggle was rendered *before* the solar-only dasha picker — so with 3 groups it sat in the
        middle and with 2 (Lunar, picker hidden) it jumped to the right. FIXED by ordering the groups
        **Year (left) → Annual Dasha (middle) → Annual Return (right)** and pinning the last with a new
        `.controls-group--end { margin-left: auto }`, so it stays hard right no matter how many sibling
        groups render.

---

## 26. Tithi Ashtottari must be **compressed** into the pravesha window (+ TP for arbitrary timeframes)

### 26.0 ✅✅✅ **SOLVED + SHIPPED 2026-07-13 — verified against TWO JHora charts**

> **§26.1 / §26.5 / §26.6 / §26.6b below are SUPERSEDED.** They reason in *days* and hunt an "anchor
> from birth" — both wrong. The trail is kept for context; **the shipped code follows THIS section only.**

**What shipped** (see §26.9 for the build log; §26.7's ± stepper and §26.10's all-rungs pass landed too —
§26 is now complete):
- `web/backend/varsha_tithi_ashtottari.py` — the elongation engine (new module; PyJHora has no
  annual/compressed Tithi Ashtottari, and its *existing* Tithi Ashtottari functions actively cannot
  be used — see the warning below).
- `AstrologyCompute.get_varsha_tithi_ashtottari` / `get_tithi_ashtottari_children`, wired into
  **every rung** of `get_lunar_pravesha` (§26.10 — the cycle is the elongation the window sweeps, so a
  day compresses exactly as a year does). The old §26.2 code (life-dasha antaras filtered to the window)
  is **deleted**.
- `POST /api/astrology/tithi-ashtottari-children` — one level of the tree, computed on expand.
- `TithiAshtottariTree.js` — the expandable Maha → … → Deha tree, on **Daily · Fortnightly · Monthly ·
  Varshaphal**.

**Everything is Moon−Sun ELONGATION.** Nothing is measured in days. (That is why every day-based model
failed: tithis run 0.79–1.06 days, so equal *angles* give unequal *days* — the ±1-day "noise" was
structural, not rounding. The per-maha implied "year length" scattered over 375.6–394.0 days.)

#### The algorithm

Let `E(t)` = `(sidereal Moon − sidereal Sun) mod 360` at instant `t`, and let
`advance(t, d)` = the instant at which `E` has advanced exactly `d` degrees from `t`
(E moves ~13.2°/day; a tithi = 12°).

1. **Cycle** `C = N × 360°`, where **N = the number of lunar months in the chart's year**
   (ordinary **12 → 4320°**, adhika-masa **13 → 4680°**).
2. **Lord + balance come from the chart's own elongation** — the classic "dasha from the chart" rule,
   but in tithi/elongation space instead of nakshatra space. At the chart moment `T` (for a TP chart,
   the pravesha instant):
   - `tithi = floor(E(T)/12) + 1`  →  `lord = ashtottari_adhipathi(tithi)`
   - **`elapsed_fraction_of_that_lord = (E(T) mod 12) / 12`**  ← *degrees* within the tithi, **not** time
   - `lord_span° = allot[lord]/108 × C`
   - `lord_start = advance(T, −elapsed_fraction × lord_span°)`  (i.e. run the elongation backwards)
3. **Then walk forward.** Each successive lord (Ashtottari order: Sun → Moon → Mars → Mercury → Saturn
   → Jupiter → Rahu → **Venus**) spans `allot/108 × C` degrees.
4. **Sub-levels subdivide the parent's DEGREE span**, recursively, to 6 levels
   (Maha → Antara → Pratyantara → Sookshma → Prana → **Deha**):
   `child° = allot[child]/108 × parent°`, and each child sequence **starts on the NEXT lord after its
   parent** (`antardhasa_option = 3`).
5. **Re-anchored PER CHART.** Each TP year's dasha is computed from *that* TP instant — it is **not** one
   continuous cycle from birth. Proof: the *same* Venus maha differs between the owner's two charts —
   `2027-04-05 04:29:23 → 2027-06-17 23:25:07` (from the TP-2026 chart) vs
   `2027-04-10 05:44:10 → 2027-06-17 08:04:45` (from the TP-2027 chart).

Allotments (sum 108): **Sun 6 · Moon 15 · Mars 8 · Mercury 17 · Saturn 10 · Jupiter 19 · Rahu 12 · Venus 21.**
Tithi→lord table is `tithi_ashtottari.ashtottari_adhipathi_dict` (Venus owns tithis 6/14/21/29 — the
owner's janma tithi is #6 → **Venus**, which is exactly the lord both his charts start on).

#### Verification (owner's chart: 1976-06-04 05:45:02, Aligarh)

- **TP 2026 (adhika, C = 4680°).** All 8 maha dasas reproduce JHora to within **2–5 seconds**.
  Sub-levels too: Sun AD = 6/108 × 910° = 50.5556° → **1 s**; Moon PD = 7.0216° → **1 s**;
  Mars SD = 0.5201° → **1 s**.
- **TP 2027 (ordinary, C = 4320°).** Measured elongation span of every maha in JHora's table is *exactly*
  `allot/108 × 4320`: Ven **840.00**, Sun **240.00**, Moon **600.00**, Mars **320.00**, Merc **680.00**,
  Sat **400.00**, Jup **760.00**, Rah **480.00**. Predicting the table forward reproduces JHora to within
  **3.5 seconds**.
- **Balance rule.** Birth elongation `E = 70.7497°` → tithi 6 ✓, and `(E mod 12)/12 = 0.8958`. JHora's
  observed elapsed-fraction of the Venus maha at the TP instant is **0.89533** (2026) and **0.89531**
  (2027) — identical across both charts, and matching the degree-based fraction. The engine's *time*-based
  `1 − t_frac = 0.8635` does **not** match.

#### ⚠️ Do NOT use the engine's Tithi Ashtottari functions for this

- `tithi_ashtottari_immediate_children` is **day**-proportional (`child_years = parent_years × Y/H`) →
  puts the Sun AD ~**5 hours** off. §26.6b's "compression propagates for free" is a **trap**: it
  propagates the *wrong* (linear-in-days) subdivision.
- `_ashtottari_dasha_start_date` uses the **time** fraction (`get_fraction`), not the degree fraction.
- The engine is still useful for the **tables only**: `ashtottari_adhipathi_dict` (tithi→lord + allotment)
  and `_ashtottari_next_adhipati` (lord order).
- (Also note `tithi_ashtottari`'s public entry point is `get_dhasa_bhukthi` — PyJHora's own
  `horoscope/main.py` calls a `get_ashtottari_dhasa_bhukthi` that does not exist. Broken upstream.)

#### Implementation sketch (~40 lines)

```python
def _elong(jd, place):                      # Moon - Sun, sidereal, degrees
    u = jd - place.timezone / 24.0
    return (drik.sidereal_longitude(u, const._MOON)
            - drik.sidereal_longitude(u, const._SUN)) % 360.0

def _advance(jd0, deg, place, step=0.05):   # JD where elongation has advanced `deg`
    # accumulate (e - prev) % 360 over coarse steps, then bisect. ~13.2 deg/day.
    ...

ALLOT = {Sun:6, Moon:15, Mars:8, Mercury:17, Saturn:10, Jupiter:19, Rahu:12, Venus:21}  # 108
ORDER = [Sun, Moon, Mars, Mercury, Saturn, Jupiter, Rahu, Venus]

def tithi_ashtottari(chart_jd, place, cycle_deg):        # cycle_deg = N*360, N = lunar months
    E = _elong(chart_jd, place)
    lord = adhipathi(int(E // 12) + 1)                   # tithi -> lord
    span = ALLOT[lord] / 108 * cycle_deg
    start = _advance(chart_jd, -(E % 12) / 12 * span, place)   # wind back the balance
    for _ in range(9):                                   # the running lord + a full cycle
        span = ALLOT[lord] / 108 * cycle_deg
        end = _advance(start, span, place)
        yield lord, start, end, span                     # recurse on (start, span, lord) for children
        start, lord = end, next_lord(lord)

def children(parent_start, parent_deg, parent_lord, place):   # one level down; recurse to 6
    lord = next_lord(parent_lord)                        # antardhasa_option = 3
    cur = parent_start
    for _ in range(8):
        d = ALLOT[lord] / 108 * parent_deg
        end = _advance(cur, d, place)
        yield lord, cur, end, d
        cur, lord = end, next_lord(lord)
```

Expand **lazily** — full depth to Deha is 8⁶ ≈ 262k rows. We already have the expandable-tree UI pattern
on the Dasha page. Filter the top level to the maha dasas overlapping the TP window (JHora shows the
running one from the previous cycle first — the owner's *"3/17 one overlaps with last year's"*).

**Remaining unknown: how JHora decides N (12 vs 13).** Our `get_tithi_pravesha` window span already tells
us (354/355 d → 12; 383/384 d → 13), so `N = round(span_days / 29.530588)` is a sound derivation and
matches both verified charts. Confirm on a third year if it ever looks off.
*(Shipped as `vta.lunar_months_in()`. The 2026 → 2027 step flips 13 → 12 by itself, and both years
reproduce JHora, so the derivation is holding.)*

### 26.9 Build log — what the implementation found that the spec didn't (2026-07-13)

The algorithm in §26.0 was right, but two things only surfaced once it was wired to the real chart:

**1. 🔑 The pravesha instant itself has to be solved in DEGREES.** This was the whole ballgame. The
engine's `vratha.tithi_pravesha` finds the right *day*, but interpolates the time linearly between the
tithi's start and end (`t_time = s_end − t_frac × t_len`) — which lands **~50 minutes early**. Invisible
in a date; fatal in a dasha, because the balance rule winds the elongation back by up to a full maha span
(~910°), **amplifying that error ~50× into a 2.5-day shift of every period**. First run with the engine's
instant put Venus at 2026-03-19 (JHora: 03-17) and *nothing* matched. Refining the instant to the moment
the Moon−Sun elongation actually regains its birth value (`vta.refine_pravesha`) snapped all nine maha
rows onto JHora at once. **The pravesha instant is not a date — treat it as an angle.**

**2. ⚠️ Consequence: the TP chart was being cast at NOON.** `get_lunar_pravesha` used
`swe.julday(ty, tm, td, 12.0)` for the annual rung — so the Tithi Pravesha *chart* (lagna, houses,
Sahams) was cast at midday of the pravesha date, not at the pravesha moment. Now cast at the exact
instant, which is ~50 min ≠ noon → **the TP lagna has changed**. The instant is surfaced on the page
(`window.start_at`) so it can be checked against JHora's own TP chart. *Owner: worth one eyeball.*

**3. ⚠️ The table is hypersensitive to birth SECONDS** — ~**75 seconds of dasha shift per 1 second of
birth time** (the same ~5.7-days-per-degree amplification). `get_lunar_pravesha` was silently dropping
the seconds from `tob`; it now honours them when supplied. This also explains the residual vs JHora:
we land within **~90 s**, which corresponds to ~1 second of difference in the assumed birth instant —
i.e. we are at the floor of what the input precision supports, not carrying a modelling error. (§26.0's
"2–5 seconds" was measured by anchoring on JHora's *own* reported TP instant; computing our own instant
from `tob` is what costs the ~90 s.)

**Verified end-to-end in the browser** against both JHora charts: TP-2026 (adhika, N=13) reproduces all
nine maha rows; TP-2027 (ordinary, N=12) reproduces Venus at `05:45` vs JHora `05:44:10`. Drill-down to
Deha works (each level tiles its parent exactly, ~5 ms per expand). Solar/Mudda table unaffected.

**Also fixed in passing:** `VarshaphalPage`'s `formatDate` parsed bare `YYYY-MM-DD` as *UTC* midnight, so
west of Greenwich every date rendered a day early ("Lunar year begins: May 21" under "Pravesha instant:
May 22"). Date-only strings are now pinned to local midnight.

### 26.1 What JHora actually does (verified numerically from the screenshot)

JHora's panel is titled *"Tithi Ashtottari Dasa of Janma tithi in D-1 (useful especially in Tithi
Pravesha charts)"* and lists **Maha Dasas** whose periods are **days, not years**:

| Lord | JHora span | days | allotment/108 × cycle | diff |
|---|---|---|---|---|
| Ven | 2026-03-17 → 2026-05-30 | 74.0 | 74.61 | −0.6 |
| Sun | 2026-05-30 → 2026-06-20 | 20.87 | 21.32 | −0.45 |
| Moon | 2026-06-20 → 2026-08-12 | 53.49 | 53.29 | +0.20 |
| Mars | 2026-08-12 → 2026-09-09 | 28.36 | 28.42 | −0.06 |
| Merc | 2026-09-09 → 2026-11-09 | 60.43 | 60.40 | +0.03 |
| Sat | 2026-11-09 → 2026-12-15 | 36.48 | 35.53 | +0.96 |
| Jup | 2026-12-15 → 2027-02-20 | 66.97 | 67.50 | −0.53 |
| Rah | 2027-02-20 → 2027-04-05 | 43.31 | 42.63 | +0.67 |
| Ven | 2027-04-05 → 2027-06-17 | (next cycle) | | |

**Conclusion — JHora COMPRESSES the whole 108-"year" Ashtottari cycle into ONE lunar year**, exactly as
**Mudda compresses Vimsottari into the solar year**:
- One full cycle (Ven → … → Rah) = **2026-03-17 → 2027-04-05 = 384 days** = a **13-month adhika-masa
  lunar year** (12-month = 354.4d; 13-month = 383.9d). The 9th row is the *next* cycle's Venus.
- Every maha period = `ashtottari_allotment[lord] / 108 × lunar_year_length`
  (allotments Sun 6, Moon 15, Mars 8, Mercury 17, Saturn 10, Jupiter 19, Rahu 12, Venus 21 = 108).
  Every row matches to within ~1 day.
- The sequence **starts at the TP entry** with a (near-)full Venus — so the start lord is *not* simply
  "whatever is running in the life dasha".

### 26.2 What we shipped in §25.2 (WRONG — replace)

We showed the **antara** periods of the **uncompressed 108-year life dasha**, filtered to the TP window
(`get_tithi_ashtottari(window_start, window_end)` → `dhasa_level_index=3`). That is a *different
construct*: different lords, different spans (owner's chart shows `Saturn › Jupiter › Mercury` where
JHora shows `Ven / Sun / Moon / Mars / …`). It was a reasonable guess at "scope it to the year" but it
is not the technique. **Rip it out and implement the compressed annual dasha.**

### 26.3 Engine reality

- **PyJHora has NO annual/compressed Tithi Ashtottari.** `dhasa/annual/` ships only `mudda.py`
  (Varsha Vimsottari) and `patyayini.py`. So this must be written.
- **`mudda.py` is the exact template to port.** Its compression is
  `duration = const.varsha_vimsottari_days[lord] * year_duration / 360.0`, and its start lord is the
  natal Vimsottari lord **advanced by the year count**: `lord = (lord + years) % 9`.
- The Ashtottari pieces we need already exist in `dhasa/graha/tithi_ashtottari.py`:
  `ashtottari_adhipathi_dict` (lord → [tithi_list, allotment]), `_ashtottari_adhipathi(tithi_index)`
  (janma-tithi → lord), `_ashtottari_next_adhipati(lord)`, `human_life_span_for_ashtottari_dhasa = 108`.
- So: **new `varsha_tithi_ashtottari`** = Mudda's algorithm with the Ashtottari lord table + a **lunar**
  year length (the real TP window: 354 **or 384** days — the adhika-masa case is NOT an edge case, it's
  the owner's actual year), anchored at the TP instant.
- ⚠️ Reminder: `tithi_ashtottari`'s public entry point is `get_dhasa_bhukthi` — PyJHora's own
  `horoscope/main.py` calls a `get_ashtottari_dhasa_bhukthi` that does not exist (broken upstream).

### 26.4 Second owner ask — **TP for today / arbitrary timeframes**

> *"we should have tp for today also, as jhora has that capability … Looks like you give tithi
> ashtottari dasa annually or daily or others option and it gets you dasa for that time frame."*

JHora lets you pick the **pravesha timeframe** and computes the chart + its compressed dasha for *that*
frame. We only expose the **annual** TP (via the year stepper). Wanted:
- **TP for today** — the TP window containing today. NOTE: `get_lunar_pravesha("annual", …)` **already
  auto-selects the window containing `date` when `year` is None** — the Varshaphal page just always
  passes an explicit `year`. So this is mostly a UI affordance (a "Today" button / default), not new math.
- **Other timeframes** — a selector so the TP-style chart + compressed Tithi Ashtottari can be cast for
  a day / month / etc. This mirrors the Tajaka ladder (`years → months → sixty_hours`) that
  `drik.next_solar_date` already exposes on the solar side, and pairs naturally with our lunar ladder
  from §25.1 (tithi → paksha → lunar month → TP year).

### 26.5 Owner's chart + what we PROVED (2026-07-12 investigation)

Owner supplied his birth data so the rule could be reverse-engineered against the screenshot:

**DOB 1976-06-04 · TOB 05:45:02 · Aligarh, UP, India · lat 27.845709, lon 78.333733, TZ +5.5.**
Screenshot is his TP chart for **2026**.

**✅ PROVED — the start lord is the janma-tithi lord, with NO year-advancement.**
His janma tithi is **#6 (Sukla Shasti)**. `tithi_ashtottari.ashtottari_adhipathi_dict` maps tithi 6 →
**Venus** (Venus tithis = 6, 14, 21, 29) — and JHora's table starts on **Venus**. So *unlike* Mudda
(which advances the natal lord by the year count, `(lord+years)%9`), this is simply
`_ashtottari_adhipathi(janma_tithi)`. Rule settled.

**✅ PROVED — the compression is `allot/108 × lunar_year`** (see the table in §26.1; all 8 rows match to
within ~1 day, cycle = 383.7d).

**✅ PROVED — our TP *date* is right; JHora's dasha is NOT anchored to it.** Tithi is ayanamsa-independent
(a Moon–Sun elongation), so these are robust:

| Date | tithi | tamil month | lunar month |
|---|---|---|---|
| Birth 1976-06-04 | **#6** | 1 | 3 |
| **Our** TP-2026 start 2026-05-21 | **#6** ✅ | 1 ✅ | 3 ✅ |
| **JHora's** cycle start 2026-03-17 | #28 ❌ | 11 ❌ | 0 ❌ |

Our TP entry (2026-05-21, Sukla Shasti, Vaikaasi) correctly reproduces the birth tithi + Tamil month +
lunar month. JHora's 2026-03-17 matches **none** of them — it is **not** a Tithi Pravesha instant. So the
compressed dasha is a **continuously-running cycle** that the TP screen merely *displays*; it is not
re-anchored to the TP entry each year. (Also confirmed: 2026 is a genuine **adhika-masa** year — the
engine flags lunar month 3 as leap — which is why the cycle is 384d, not 354d.)

**❌ REFUTED — a continuous cycle from birth with a CONSTANT year length.** Simulating the engine's own
balance rule (`_ashtottari_dasha_start_date`: `start = jd_dob − (1 − t_frac) · allot · Y/108`, then
`+= allot · Y/108` per lord, cycling every `Y`) and solving for the `Y` that lands a Venus period on
2026-03-17 08:32:03 fits **nothing**:

| Y candidate | days | best Venus start near target | error |
|---|---|---|---|
| mean lunar year (12 mo) | 354.367 | 2025-09-28 | −169.9 d |
| adhika lunar year (13 mo) | 383.897 | 2026-09-12 | +179.5 d |
| tropical year | 365.242 | 2026-04-04 | **+17.7 d** (best, still bad) |
| sidereal year | 365.256 | 2026-04-04 | +18.4 d |
| `true_tithi_year(birth)` | 354.500 | 2025-10-05 | −163.2 d |

### 26.6 The one open question (start here next session)

🔴 **What anchors the cycle at 2026-03-17?** The leading hypothesis, given the negative result above and
the fact that the observed cycle is 384d (adhika) rather than 354d: **JHora recomputes the lunar-year
length at each cycle** (true lunar year, alternating ~354 ↔ ~384 as adhika months fall), so a constant
`Y` cannot reproduce the anchor after ~50 years of accumulated cycles. NOTE the engine sets
`year_duration = drik.dhasa_year_duration(jd=…)` **once**, from the birth JD — so if this hypothesis is
right, PyJHora's model is structurally different and we must iterate cycle-by-cycle ourselves.

**Concrete experiment:** iterate forward from birth, recomputing `drik.true_tithi_year(jd, place)` (or
`dhasa_year_duration(..., TRUE_LUNAR_YEAR)`) at the start of *each* cycle, and check whether a Venus
period opens at **2026-03-17 08:32:03**. If it does, the algorithm is settled and we assert our output
byte-matches all 9 rows of the screenshot. If not, try anchoring at a lunar new year (Chaitra Sukla
Pratipada 2026 ≈ 2026-03-19 — suggestively close to 2026-03-17, though the tithi there is 28, i.e. two
days *before* the new moon that opens Chaitra).

Remaining smaller questions:
- **Balance at the first period?** Venus shows 74.0d vs a full 74.61d — genuine balance, or rounding?
  Settled automatically once the anchor is solved.

### 26.6b ✅ Drill-down: owner confirms JHora goes all the way to **Deha-antardasa** — and it's FREE

Owner (2026-07-13): *"it has all the breakup until Deha-antardasas."* The screenshot's maha table is just
the top level. Investigated — this is the **easy** part, and it settles the design:

- **The engine's depth levels line up exactly** (`const.MAHA_DHASA_DEPTH`):
  `1 = Maha · 2 = Antara (Bhukthi) · 3 = Pratyantara · 4 = Sookshma · 5 = Prana · 6 = Deha`.
  `tithi_ashtottari` supports `dhasa_level_index` 1..6, so **Deha is reachable**.
- **🔑 KEY FINDING — compression propagates down the tree for free.**
  `tithi_ashtottari.tithi_ashtottari_immediate_children(parent_lords, parent_start, parent_end, …)`
  returns ONE level of children for a given parent span, and its arithmetic is **scale-free**:

  ```
  parent_years = (end_jd - start_jd) / year_duration
  child_years  = parent_years * (Y / H)          # Y = lord allotment, H = 108
  child_end    = jd_cursor + child_years * year_duration
  ```

  `year_duration` **cancels out** — each child is simply `allot/108 × (parent span)`. So once we compute
  the **compressed maha** periods ourselves, we hand each maha's `(start, end)` to
  `immediate_children` and **every level below (Antara → Deha) is automatically compressed**. No
  per-level compression logic needed, and no `year_duration` fiddling.
  **VERIFIED** against JHora's own compressed Venus maha span from the screenshot (73.92 d): the 8
  children come back exactly proportional (Venus 14.37 / Sun 4.11 / Moon 10.27 / Mars 5.48 /
  Mercury 11.64 / Saturn 6.84 / Jupiter 13.00 / Rahu 8.21) and sum **exactly** to the parent — the helper
  even snaps the last child to the parent end (`children[-1][2] = end_jd`), so there is zero drift.
- **⇒ Build it as a lazy expandable tree, not a flat table.** Full expansion to Deha is 8⁶ ≈ **262,144
  rows** — it must be expand-on-demand. `immediate_children` is purpose-built for that, and we already
  have the UI pattern: the Dasha page's tree + `tools.get_dasha_children(lords_path)`.
  `tithi_ashtottari.get_running_dhasa_for_given_date(current_jd, jd_at_dob, place,
  dhasa_level_index=DEHA)` gives the running chain at all 6 levels for "now" highlighting.
- 🔴 **OPEN — `antardhasa_option`.** It decides where each child sequence *starts*. Engine default is
  `3` = the **next** lord after the parent; option `1` = the **parent** lord itself:

  | option | children of a Venus maha |
  |---|---|
  | 1 | **Venus** → Sun → Moon → Mars → Mercury → Saturn → Jupiter → Rahu |
  | 3 (engine default) | **Sun** → Moon → Mars → Mercury → Saturn → Jupiter → Rahu → Venus |

  Which does JHora use? **A screenshot of any ONE expanded maha in JHora settles this instantly** — if
  the first sub-period repeats the maha lord, it's option 1; if it starts on the next lord, it's 3.

### 26.7 ✅ SHIPPED 2026-07-13 — ± stepper for day / fortnight / month, like the annual one

> *"add that the person can +/- days, fortnight, month just like annual"*
> *"all daily, fortnight, monthly should allow to look ahead and back as well like +/- we have in annual"*

`/varshaphal` had a **year** stepper; the three shorter cadences were hard-wired to *today* and could
only ever show the current window. Each cadence now steps **its own rung of the pravesha ladder**, so
the ± lands on a real window rather than an arbitrary date offset:

| Page | − / + steps by |
|---|---|
| `/daily-digest` | one **calendar day** |
| `/fortnightly-digest` | one **paksha** (~14.8d) |
| `/monthly-digest` | one **month** on the selected basis — Maasa Pravesha (~30.4d) or birth-tithi return (~29.5d) |

**No new math — the backend already took a `date` and snapped it to the window containing it.** The
whole card (opening panchanga, dasha, in-window transit events, the pravesha chart + its Muntha and
Tajaka yogas, and the AI reading) recomputes for whatever window you land on, because `_period_digest`
anchors *everything* to the passed date, not to the wall clock. The **Refresh** button becomes
**Today / Current** whenever you are off the present window.

**Step off the window's own boundaries — never by a nominal length.** Pravesha windows are not a fixed
number of days (a paksha runs 13–16d, a Maasa 29–32d; the observed spans above are all over the place),
so the pages hop using the boundaries the backend just returned: `+` re-anchors to `end_date + 1 day`,
`−` to `start_date − 1 day`. One day past a boundary is always inside the adjacent window whatever its
true length, so the walk stays contiguous with no gaps and no repeats. Verified through the UI: five
consecutive windows on each of the three ladders, ± round-tripping back to the same window.

- 🐛 **Fixed en route — `get_masa_pravesh` could return a window that did not contain the date.**
  It picks the (year, month) index from a *linear* fraction of the tropical year from birth, but the
  true Maasa Pravesha is where the Sun actually reaches natal-longitude + 30°k — which drifts a day or
  two off an even 1/12. For 2026-07-13 it returned `2026-07-15 → 2026-08-15`, a window **starting two
  days after the date being asked about** (so "This Month" was already showing next month), and `−`
  would then re-select that same window and appear stuck. The estimate is now **snapped**: solve the
  window boundaries and walk the month index until the date really falls inside. Both the digest and
  the standalone Maasa Pravesha chart benefit.

### 26.10 ✅ Tithi Ashtottari on **every** rung + the daily lunar basis — SHIPPED 2026-07-13

> *"I do not see any lunar for daily, so does it calculate automatically"* · *"we should add tithi
> ashtottari for each one of them as well"*

**The daily lunar chart was unreachable.** `get_daily_digest(basis="lunar")` has always cast the day's
Tithi Pravesha chart — but `api.js` never sent `basis` and the backend defaults to `"solar"`, so the whole
path was **dead code**. `DailyDigestPage` now carries the same Solar/Lunar toggle the fortnight/month page
has (defaulting to Settings → pravesha basis). The daily *AI* call was missing `basis` too.

**The compressed dasha now runs on all four rungs, not just the annual one** — and the generalization is
free, because the compression is angular. Every rung is a clean fraction or multiple of a turn, since each
is *defined* by an elongation boundary (measured, owner's chart):

| rung | span | elongation swept = `C` |
|---|---|---|
| tithi (day) | 0.85 d | **12°** (one tithi) |
| paksha (fortnight) | 14.41 d | **180°** (half a turn) |
| month | 29.45 d | **360°** (one turn) |
| annual (TP) | 384.03 d | **4680°** (13 turns — adhika) |

So `C` is just **the elongation the window sweeps** (`vta.cycle_degrees`), and the same construction tiles
a day exactly as it tiles a year — verified: one full 8-lord cycle sums to `C` to within 1e-6° on all
four. Sub-annual windows open *on* a tithi boundary, so their balance is zero and the cycle aligns exactly
with the window; only the annual rung carries a running balance from before the window (as JHora shows).

**⚠️ This killed a trap and settled an open question:**
- **`C` is no longer `round(span_days / 29.53) × 360`.** That heuristic is fine for a year but **wrong
  below a month** — it rounds a fortnight's 14.4 days up to *one lunar month*, giving **360° instead of
  180°**, and the dasha would have silently run at **half speed**. Deriving `C` from the sweep is exact at
  every rung. (So do NOT reuse `lunar_months_in` to size a cycle; it is display-only now.)
- It **answers §26.0's last unknown** — *"how does JHora decide N, 12 vs 13?"*. N is simply the whole
  turns the window sweeps: counted, not rounded. Annual still comes out at exactly 4680° / 4320°, and both
  JHora charts still reproduce to the second.

Payload: `get_lunar_pravesha` now returns **`tithi_ashtottari`** on every rung, with `annual_dasha` kept as
an alias on the annual rung so `/varshaphal` reads one key for both the solar (Mudda/Patyayini/Narayana)
and lunar sides. The expandable tree renders on **Daily · Fortnightly · Monthly · Varshaphal**.

### 26.11 ✅ Dedicated Tithi Pravesha page, with the rung selector — SHIPPED 2026-07-13 (**§26 COMPLETE**)

> *"may be can have a dedicated tile and page for TP and user can select daily, fortnight, month and annual"*

**New page `/tithi-pravesha`** (dashboard tile + nav drawer, Moon icon) — one page, four cadences. A
**Window** selector picks the rung (Day / Fortnight / Month / Year) and a ± stepper walks *that* rung one
whole window at a time, hopping off the window's own boundaries (`end + 1d` / `start − 1d`) rather than
adding a nominal length, so the walk stays contiguous whatever the true span. Switching rung **re-anchors
on the current window's start**, so you stay where you are on the timeline instead of being thrown back to
today. Each rung shows: the chart cast at the exact pravesha instant, placements, the compressed Tithi
Ashtottari tree, and an AI reading.

**Owner decisions (2026-07-13):**
1. **The TP page is TP's home — `/varshaphal` is now SOLAR-ONLY.** The Solar/Lunar toggle is gone; the page
   is what its name means (the Tajaka solar return) and links across to the lunar side. No more duplicate
   surface to keep in step.
2. **Muntha, year-lord and the Sahams show on the Year rung only.** They are reckoned from the age in
   *years* — a "year-lord" for a 20-hour window is noise. The AI prompt omits them below annual too.

**Backend was nearly free** (the compute layer already did every rung — see §26.10): one generic endpoint
`POST /api/astrology/lunar-pravesha?rung=` + rung validation. The real work was the **AI prompt**, which was
hard-coded as a *year-ahead* reading: `_build_tithi_pravesha_prompt` is now rung-aware (horizon word, target
length 180→280 words, year-only panels omitted, and it names the **running compressed-dasha lord** — the
sharpest thing to say about a window whose maha periods last hours). Verified live on Ollama: the fortnight
reading came back framed as a fortnight, 232 words against a 220 target.

**⚠️ Don't miss this when moving a page:** saved AI readings carry a **route** (`conversations.py`
`SOURCES`), and `tithi_pravesha` pointed at `/varshaphal`. Left alone, every previously-saved TP reading
would have reopened on a page that no longer renders it. Repointed to `/tithi-pravesha`; the page restores
the rung from the saved context and defaults to annual when absent — which is exactly what those older
readings were. Verified: an existing Paksha reading reopens on the new page with the Fortnight rung and its
original window restored.

### 26.12 ✅ One home per thing — digests decluttered, TP button styled (owner ask 2026-07-13)

> *"read this window on TP is not formatted correctly"* · *"why do we still have Lunar under Annual,
> Monthly, Daily and Fortnight is also there, any reasons"*

**The button.** `Read this window` used `btn btn-primary` — a class that exists in **no stylesheet** (the
app's AI buttons are `ui-btn ui-btn--ai`), so it rendered unstyled. Fixed, and the rest of the new page's
49 classes were audited against the CSS: that was the only invented one. *Lesson: when adding a page, grep
the class names against `styles/*.css` — a bogus class fails silently, it does not error.*

**The Lunar toggles — the honest answer is that "basis" meant two different things:**

| Page | Before | After |
|---|---|---|
| `/varshaphal` (Annual) | Solar/Lunar toggle | **gone** (§26.11 — solar-only) |
| `/daily-digest` | Solar/Lunar toggle | **gone** — it *only* added a chart; a day is the same calendar day on either ladder |
| `/fortnightly-digest` | (lunar by definition) | unchanged — no toggle to remove |
| `/monthly-digest` | Solar/Lunar toggle | **KEPT** — here the basis picks the **window itself** (solar Maasa ~30.4d vs lunar birth-tithi return ~29.5d), a real choice about what the reading covers |

**Owner decision: full cleanup.** The digests are *summaries* ("what's happening"); the TP page is where
*charts* live. So the pravesha chart + Muntha + Tajaka yogas + the Tithi Ashtottari tree came out of all
three digests, which now link across to `/tithi-pravesha`. One home per thing.

**⚠️ The chart card was not the only place it leaked.** After deleting the card, the browser *still* showed
"Muntha" on the fortnight and month pages — it was baked into (1) the backend's **highlight strings**
(`f"…lagna: …; Muntha in …"`) and (2) the digest **AI prompt**, which also fed the model the **year-lord**.
Both removed. And the prompt's *instruction* line still said "what the dasha and the progressed
**Lagna/Muntha** set as the backdrop" — left alone, the model would have been asked for a Muntha reading it
was no longer given, i.e. invited to hallucinate one. *Lesson: removing a panel from the UI does not remove
it from the payload, the highlights, or the prompt — grep all four.*

Why Muntha had to go below the annual rung: it advances **one sign per year of age**, so it is *identical*
for every day, fortnight and month of a given year. Presenting it as insight about "this fortnight" is
dressing a constant up as news. (Tajaka yogas **stay** — they are chart aspects, not age-reckoned.)

The daily page still *sends* the global `praveshaBasis` (it just has no toggle), so the page's narrative
and the scheduled **email** digest — which drives basis from notification prefs — continue to read alike.

**Settings had to follow (owner: *"have we made sure to update our settings page"*).** Settings → General's
pravesha-basis hint still claimed it drove *"the Monthly and **annual** readings"* and that *"pages can
override this"* — both now false: Varshaphal is always solar and the TP page always lunar (neither reads
it), and **only Monthly can override**, because only there does the basis pick the *window*. Rewritten to
say exactly what it does: it casts the **Daily and Monthly** readings, Monthly can override, the Fortnight
is always lunar, and Varshaphal / Tithi Pravesha are untouched by it. Settings → **Notifications** keeps its
own basis (it drives the delivered emails) and was already accurate.
**Follow-up — the Monthly toggle was right, its LABEL was wrong (owner: *"monthly still have solar vs
lunar toggle. Any reason?"*).** It looked like leftover duplication because it was labelled *Basis ·
Solar / Lunar* — word for word the toggle deleted from Daily and Varshaphal. But it is not the same thing.
Measured, for 2026-07-13:

| | window | transit events |
|---|---|---|
| Monthly, solar | **2026-07-06 → 2026-08-06** (Maasa Pravesha) | 7 |
| Monthly, lunar | **2026-06-19 → 2026-07-19** (birth-tithi return) | 6 |
| Daily, solar *vs* lunar | *identical* (same date, same panchanga) | — |

So on Monthly the control answers **"which month are you asking about?"** — two different windows with
different events — while on Daily it only ever attached a chart. Relabelled **Month · Solar month / Lunar
month** (i18n `periodDigest.monthType` / `solarMonth` / `lunarMonth`, replacing the `basis*` keys), so it
reads as the window choice it is. Behaviour unchanged.

Also swept the **18 i18n keys** the removals orphaned (`digest.basis*`, `digest.pravesh*`,
`periodDigest.muntha` / `yearLord` / `pravesh*` / `taHint` …). Four pre-existing orphans in `periodDigest`
(`window`, `yoga`, `ingress`, `station`) were left alone — not mine, and out of scope.

### 26.8 Superseded questions (now answered — kept for context)

- 🔴 **Start-lord rule.** Mudda advances the natal lord by the year count (`(lord + years) % 9`). Is the
  annual Tithi Ashtottari the same with 8 lords (`(lord + years) % 8`), seeded from the **janma tithi**?
  The screenshot starts on **Venus** with a near-full period — **to pin this down exactly we need the
  owner's birth details (dob / tob / place) and the TP year shown**, so we can reverse-engineer the rule
  and assert our output byte-matches the JHora table above.
- 🔴 **Is the first period a true balance?** Venus shows 74.0d vs a full 74.61d — is that a genuine
  (tiny) balance carried from the previous year, or just rounding in our cycle estimate? The birth
  details would settle this too.
- 🔴 **Which year length?** Confirm the compression uses the **actual TP window** (354/384d, which is
  what the data shows) rather than a mean lunar year (354.37d).
- **Keep a drill-down?** Do we want bhukti/antara *within* each compressed maha (JHora's panel shows
  maha only), or is the maha table enough?
- **Which timeframes** should the TP selector offer — today/daily, monthly, annual? Anything else?

## 27. Life Timeline — the flagship dasha–transit view (owner ask 2026-07-15, §5.1 of improvements-2026-07.md) — ✅ SHIPPED
Owner picked the flagship idea from the new review doc (`web/improvements-2026-07.md`). One
horizontal, clickable timeline that composes everything already computed onto a single date axis
around today.

**Backend (`astrology.py`):**
- `_planet_sign_spans(pl_idx, jd_start, jd_end, tz)` — the one new primitive: contiguous same-sign
  spans of a slow graha, daily sample + bisection to the hour (like the Bhrigu ingress scanner). A
  retrograde dip naturally breaks into separate spans (each ingress is real). ~0.4s for the whole
  timeline.
- `get_life_timeline(...,years_before=10,years_after=10)` — Vimsottari maha bands + the running
  maha's bhukti bands (clipped to the window); Saturn **Sade Sati (12/1/2), Ashtama (8), Kantaka
  (4)** phases from the natal Moon, Saturn scanned 3 yr before the window so an in-progress phase's
  true start is caught; Jupiter/Saturn/Rahu **ingress** markers; **eclipses** (reuses `get_eclipses`)
  with the luminary's nakshatra, flagged when it lands on a **natal planet's nakshatra**.
  `_SATURN_PHASE_LABELS` maps house-from-Moon → (kind, phase, description).
- `get_timeline_window_context(...,target_date)` — "what's running" at a clicked date: the Maha +
  Bhukti covering it (resolved from the FULL dasha_sequence so far-future dates still get a bhukti,
  not just the running maha), the Saturn phase, and ingresses/eclipses within ±9 months.
- **KEY gotcha found in verification:** eclipses fail under the FastAPI **TestClient** threadpool
  (`swe.lun_eclipse_when` can't find `seplm48.se1` off the main thread) but work fine under real
  uvicorn — the Almanac eclipse endpoint has the identical behaviour, so it's a harness quirk, not a
  bug. The per-eclipse + outer try/except degrade the eclipse layer to empty without breaking the
  timeline.

**Endpoints (`main.py`):** `POST /api/astrology/life-timeline` (compute) + `.../life-timeline-analysis`
(AI; `TimelineAnalysisRequest` carries `target_date`). AI: `llm_service.analyze_timeline_window` +
`_build_timeline_window_prompt` (~260-word reading of the period — maha/bhukti theme, Saturn's
weather framed calmly, nearest turning-point transit; no fatalism/medical/dates). Saved to history
(source `timeline`).

**Smart-lookup tool (`tools.py`):** `get_life_timeline` (in ALWAYS_TOOLS + _DISPLAY "Timing") — no
date → current overview (maha/bhukti, active Saturn phase, next ingresses/eclipses); with
`target_date` → that window's context.

**Frontend (`TimelinePage.js`, route `/timeline`, `GanttChartSquare` icon, dashboard card + nav):**
a clickable SVG (`viewBox` + explicit CSS height + `preserveAspectRatio="none"` so lanes keep full
height) with stacked lanes — year gridlines, maha band (per-graha colour), bhukti band, Saturn
phases, ingress lollipops, eclipse dots (red-ringed = on a natal nakshatra), a dashed **today** line
and a solid **selected** line. Click anywhere → a "what's running" panel (maha/bhukti chips, Saturn
phase, nearby ingresses/eclipses with natal-nakshatra hits in red) + a **Read this period** on-demand
AI reading. `± 5/10/15/20 year` window picker. `styles/Timeline.css`; i18n `timeline.*` (en full;
hi/sa nav+card). api.js `getLifeTimeline`/`analyzeLifeTimelineAI`.
- **BUG found & fixed in live verification:** `segRect` returned `{x, w, y, h}` spread onto `<rect>`,
  but SVG rects need `width`/`height`, not `w`/`h` — React passed them through as invalid attrs so
  every band rendered **0×0** (invisible). Fixed to return `{x, y, width, height}`. Verified live on
  the owner's chart (Moon→Mars→Rahu maha, Ashtama Shani + Sade Sati-rising phases, eclipses flagged
  on natal Mars/Saturn, click→panel all correct).

**Still open on this feature (v1 limits, non-blocking):** far-future *bhukti* bands aren't drawn on
the chart (only the running maha's are — the panel/AI still resolve them); eclipse markers cluster in
the next ~3 yr (get_eclipses `count` cap); no zoom/pan (window picker only).

## 28. Planet-condition flags + conditional-dasha recommender (§5.2 + §5.4 of improvements-2026-07.md) — ✅ SHIPPED 2026-07-15
Two cheap, high-value follow-ons after the Life Timeline.

**§5.2 Planetary Conditions (`get_planet_conditions`, astrology.py):** the classical point-conditions
that colour a planet but are invisible on a plain chart — **Combust** (`charts.planets_in_combustion`),
**Vargottama** (D1 sign == D9 sign), **Pushkara Navamsa/Bhaga** (`planets_in_pushkara_navamsa_bhaga`),
**Mrityu Bhaga** (`planets_in_mrityu_bhaga` — needs a `drik.Date` + `(h,m,s)` tuple, returns idx or
'Md'/'L'), **Marana Karaka Sthana** (`get_planets_in_marana_karaka_sthana`), **Gandanta** (water→fire
junction: last/first 3°20' of Cancer/Scorpio/Pisces ↔ Leo/Sagittarius/Aries), **Graha Yuddha**
(two tara-grahas sharing a sign within 1°), **Retrograde** (tara-grahas only — Rahu/Ketu are Mean nodes,
perpetually retro = noise; luminaries never retro). Each flag carries a tone
(benefic/challenging/neutral) for UI colour + AI framing. `POST /api/astrology/planet-conditions`
(+`-analysis`; `analyze_planet_conditions`/`_build_planet_conditions_prompt` — honest, no
lifespan/medical, "mrityu bhaga is a degree not a death statement"). Smart-lookup tool
`get_planet_conditions` (ALWAYS_TOOLS + _DISPLAY "Core chart"). Frontend: **Planetary Conditions card
on AdvancedPage** (loads independently like longevity; tone-coloured `.pc-flag` chips per flagged
planet + self-contained AI reading). i18n `conditions.*` (en; hi/sa fall back). Verified live on the
owner's chart: Moon gandanta, Venus combust+vargottama+pushkara, Saturn pushkara bhaga, etc.

**§5.4 Applicable dashas (`get_applicable_dashas`, astrology.py):** wraps
`dhasa.graha.applicability.applicability_check` (BPHS rules) → the conditional nakshatra dashas that
also apply to THIS nativity, each mapped via `_APPLICABLE_DASHA_INFO` to (name, when-it-applies blurb,
DhasaPage picker key | None). `POST /api/astrology/applicable-dashas` (factual, no AI). Frontend:
a **"For this chart, tradition also recommends…" banner** in DhasaPage's `OtherDashaSystems` card —
chips with a picker key deep-link into the system picker (`onChange`), the rest render static.
i18n `dhasa.applicableTitle/applicableNote`. Verified live (owner → Shashtihayani, static; another
chart → ashtottari).

**Verify-skill note:** both were driven in a real browser (Playwright) after the API smoke test — the
Life Timeline (§27) proved that build-green + API-200 is NOT enough for SVG/DOM correctness.

**Still open from §5 of improvements-2026-07.md:** Kundali-hover flag badges + a chart_context.py
conditions block (so every AI reading knows), then §5.1's follow-ons and the rest (strength page,
friendship matrix, avasthas, unknown-birth-time mode, MCP, iCal, …).

## 29. Planet-condition flags — finish the reach (chart_context + Kundali badges) — ✅ SHIPPED 2026-07-15
Completed §5.2's two remaining follow-ons so the flags reach *every* reading, not just the Advanced card.

- **chart_context.py:** new `conditions` section (default-on in `DEFAULT_SECTIONS`) → compact block of
  the flagged planets (planet/sign/house + label/tone per flag). `llm_service._render_context_block`
  renders it as "Planet Conditions (classical flags; …)" so every /ask, /predict etc. reading now
  knows a planet is combust/vargottama/gandanta/… .
- **Tool plumbing fixed:** `get_planet_conditions` moved OUT of `ALWAYS_TOOLS` INTO
  `SECTION_TOOL["conditions"]` so the tri-state seed/tool/off semantics apply (seeded → not also
  exposed as a tool; off → neither). Verified: conditions=tool exposes it, seed/off hide it.
- **Ask page:** added `{ key: "conditions", labelKey: "ask.sectionConditions" }` to `CONTEXT_SECTIONS`
  + `conditions: "tool"` to `DEFAULT_SECTION_STATE`; i18n `ask.sectionConditions`.
- **Kundali-hover badges:** both `NorthIndianChart` (SVG `<title>` + a tone-coloured `●` tspan) and
  `SouthIndianChart` (HTML `title` attr + `.si-cond-dot`) gained an optional `conditions` prop (the
  flagged-planets array; keyed by the planet `fullName` already carried on each item). Tone = worst of
  the planet's flags (challenging > benefic > neutral). BirthChartPage fetches `getPlanetConditions`,
  adds a **"Show conditions"** toggle (persisted `showConditions`, `ShieldAlert` icon, alongside the
  aspects/arudhas toggles) and passes `conditions` to the D1 Kundali. i18n
  `conditions.showOnChart/hideOnChart/hoverHint`.
- Verified live: 5 dots on the owner's D1 with correct colours (Venus #e34234 combust-wins, Moon
  #e34234 gandanta, Saturn/Rahu/Jupiter #2E9E5B), tooltips list the flags; the context block renders
  in the prompt; build + eslint green.

**Still open from §5:** avasthas (§5.3), strength page (§2.2), friendship matrix (§2.5),
unknown-birth-time mode (§5.8), MCP (§2.3), iCal (§5.10), …

## 30. Avasthas — planetary states (§5.3 of improvements-2026-07.md) — ✅ SHIPPED 2026-07-15
Desktop JHora shows the avasthas but the PyJHora engine has NO function for them (the
`deeptaamsa`/`utils.deeptaamsa_range_of_planet` is unrelated Tajaka orb math), so computed web-side
from longitude + dignity — like `_mangal_dosha`/gandanta were.

**`get_avasthas` (astrology.py), seven grahas (Sun..Saturn):**
- **Baladi** (5, by degree): 6° parts → Bala/Kumara/Yuva/Vriddha/Mrita in ODD signs (Aries=0 is the
  1st=odd, i.e. `sign0 % 2 == 0`), **reversed** in even signs. Yuva (prime)=full strength, Mrita=none.
- **Jagradadi** (3, by dignity): own/exalt→Jagrat (awake), friend/neutral→Swapna (dreaming),
  enemy/debilitated→Sushupti (asleep).
- **Deeptadi** (9): dignity base (exalted→Deepta, own→Swastha, friend→Mudita, neutral→Shanta,
  enemy→Deena, debilitated→Dukhita) with **affliction overrides** — combust→Vikala, in graha
  yuddha→Kopa, co-tenant with a malefic (Mars/Saturn/Rahu/Ketu)→Khala. Each state carries a tone.
- Dignity uses `const.planet_relations[planet][sign_lord]` (3=friend/2=neutral/1=enemy/5=self) +
  `EXALTATION_SIGN`; new module consts `_RASI_LORD_IDX`, `_BALADI_*`, `_JAGRADADI_INFO`,
  `_DEEPTADI_INFO`.

**Wiring:** `POST /api/astrology/avasthas`(+`-analysis`; `analyze_avasthas` /`_build_avasthas_prompt` —
frames avasthas as a vitality/mood nuance vs raw Shadbala, no medical/lifespan). Smart-lookup tool
`get_avasthas` in `SECTION_TOOL["avasthas"]` + _DISPLAY "Core chart". Default-on `avasthas` section in
`chart_context.py` (compact Baladi/Jagradadi/Deeptadi line per graha, rendered in
`_render_context_block`) so every AI reading sees it. Frontend: **Avasthas card on AdvancedPage**
(Hourglass icon, 4-col table, Deeptadi as a tone-coloured `.pc-flag` chip, `.av-sub` muted sub-labels,
self-contained AI reading). api.js `getAvasthas`/`analyzeAvasthasAI`; i18n `avasthas.*` (en; hi/sa fall
back). Verified live on the owner's chart: Venus own→Yuva/Jagrat but Vikala (combust), Mars
debilitated→Sushupti/Dukhita, Jupiter co-tenant with Ketu→Khala; context block renders; build green.

**Still open from §5:** strength page (§2.2), friendship matrix (§2.5), unknown-birth-time mode (§5.8),
MCP (§2.3), iCal (§5.10), chart explorer (§5.5), gochara-vedha (§5.6), nakshatra profile (§5.7), …

## 31. Planetary Strength page (§2.2 of improvements-2026-07.md) — ✅ SHIPPED 2026-07-15
Shadbala was computed (Advanced table + remedies + chart_context) but had no dedicated visual.

**`get_strength` (astrology.py)** composes three engine strength measures under one ayanamsa
set/reset (calls `get_shadbala` first — it manages its own ayanamsa — then re-sets for the rest):
- **Shadbala**: reuses `get_shadbala`'s per-planet six-fold (sthana/kaala/dig/cheshta/naisargika/drik,
  in virupa — they sum to total_shashtiamsa = total_rupa×60), total vs required rupa, ratio, rank.
- **Bhava Bala**: `strength.bhava_bala(jd,place)` → `[shashtiamsa, rupas, ratio]`×12; returned with
  house significations (`_BHAVA_SIGNIFICATION`) + rank.
- **Vimsopaka Bala**: `charts.vimsopaka_{shadvarga,sapthavarga,shodhasavarga}_of_planets` → each
  returns `{planet_idx: [count, "varga list", score]}`; the **score (index [2]) is the 0-20 value**
  (NOT the count — the docstrings mislabel it). All 9 planets.

`POST /api/astrology/strength`(+`-analysis`; `analyze_strength`/`_build_strength_prompt` — reads
strongest/weakest grahas + strongest houses, insists "strength ≠ good/bad", points weak planets at
the Remedies page, no medical/lifespan). Smart-lookup tool `get_strength` (ALWAYS_TOOLS + _DISPLAY
"Strengths & afflictions"). Frontend: **`StrengthPage`** (route `/strength`, `Gauge`, dashboard card +
nav drawer) with CSS-bar visualizations (`Strength.css`): ranked Shadbala **ratio bars** (fill vs a 1.0
threshold marker, green sufficient / red below), a **six-fold stacked bar** per planet (6-colour legend),
**Bhava Bala** bars (12 houses), **Vimsopaka** 0-20 bars, + AI reading. api.js `getStrength`/
`analyzeStrengthAI`; i18n `strength.*` (en full; hi/sa nav+card). Verified live on the owner's chart
(Venus #1 ratio 1.65, Saturn #7 0.95 red; H9/H10/H12 weak; Vimsopaka Moon 16.43/Venus 16.18 top).

**Gotcha:** the `planets` derived list must NOT be a `useMemo` after the `if (!selectedProfile) return`
early-return (react-hooks/rules-of-hooks) — made it a plain sorted const.

**Still open from §5/§2:** friendship matrix (§2.5), unknown-birth-time mode (§5.8), MCP (§2.3),
iCal (§5.10), chart explorer (§5.5), gochara-vedha (§5.6), nakshatra profile (§5.7), marriage
workspace (§2.6), Ashtakavarga transit chips (§2.4), Sade-Sati page (§2.1).

## 32. Sade Sati page (§2.1) + "No Profile" bug fix (owner report) — ✅ SHIPPED 2026-07-15
**Bug (owner report):** readings from the new features (timeline/conditions/avasthas/strength) all
saved under "No Profile" even with a profile selected. ROOT CAUSE: `api.js` has a request interceptor
that injects `profile_id` from `localStorage.selectedProfile`, but ONLY for paths in the
`PROFILE_READING_PATHS` allow-list — and the new `*-analysis` endpoints weren't in it. FIX: added
`life-timeline-analysis`, `planet-conditions-analysis`, `avasthas-analysis`, `strength-analysis`,
`saturn-transits-analysis` to the set. Verified live: all three captured request bodies now carry
`profile_id`. **When adding a new AI-reading endpoint, add its path to PROFILE_READING_PATHS** or its
history lands in the wrong bucket.

**Sade Sati (§2.1):** `get_saturn_transits` (astrology.py) reuses `_planet_sign_spans` (the timeline's
daily Saturn sign-scan) over birth→now+37y, maps each span to house-from-Moon:
- **Sade Sati cycles** = spans in houses 12/1/2, grouped into cycles when the gap between qualifying
  spans exceeds 1 year. Per cycle: the three **phase windows** (12=rising, 1=peak, 2=setting) merged
  across retrograde re-entries via `merge_house` (keeps `sub_windows` + a `retrograde_reentry` flag),
  cycle start/end, is_current/is_past, current_phase.
- **Ashtama** (house 8) and **Kantaka** (house 4) periods via `group_periods` (same >1yr-gap grouping).
- **current** = whichever of sade_sati/ashtama/kantaka covers today.
`POST /api/astrology/saturn-transits`(+`-analysis`; `analyze_saturn_transits`/
`_build_saturn_transits_prompt` — calm, growth-not-doom, no misfortune/illness/death, points to
Remedies for Shani upayas). Tool `get_saturn_transits` (ALWAYS_TOOLS + _DISPLAY "Timing"). Frontend
`SadeSatiPage` (route `/sade-sati`, `Aperture` icon — Orbit was taken by Transit): status banner
(active/warn/clear tones), per-cycle cards with a proportional CSS phase bar (`.ss-bar`) + phase rows
(dot, phase, sign, dates, ℞) + current-cycle red outline, Ashtama/Kantaka two-column list with a "now"
tag, AI reading. `SadeSati.css`; i18n `sadeSati.*` (en full; hi/sa nav+card). Verified live on the
owner's Leo Moon: Sade Sati 1976-82 / 2004-12 (past) + 2034-41 (upcoming), currently Ashtama Shani
2025-2028; 9 phase segments, retrograde re-entries flagged.

**Gotcha (again):** derived values used across the JSX must not be `useMemo` AFTER the
`if (!selectedProfile) return null` early-return — plain const/ternary instead (react-hooks/rules).

**Still open from §5/§2:** friendship matrix (§2.5), unknown-birth-time mode (§5.8) — doing these next;
then MCP (§2.3), iCal (§5.10), chart explorer (§5.5), gochara-vedha (§5.6), nakshatra profile (§5.7).

## 33. Friendship matrix + house-lord placements (§2.5) — ✅ SHIPPED 2026-07-15
`get_friendships` (astrology.py) exposes the engine's `house._get_compound_relationships_of_planets(h2p)`
(compound = natural friendship folded with this chart's temporal placement; returns a 9×9 matrix coded
4=Adhimitra/3=Mitra/2=Sama/1=Shatru/0=Adhishatru — diagonal left 0, treated as self):
- **7×7 matrix** (Sun..Saturn, the classical grahas) with per-cell label + tone (4/3 benefic, 2 neutral,
  1/0 challenging), via new `_COMPOUND_REL`.
- **house-lord placements**: for each house 1-12 from the Lagna, its sign lord (`_RASI_LORD_IDX`) and the
  house that lord occupies, with significations.
- **Parivartana**: planet pairs in mutual sign exchange (lord of A's sign == B AND lord of B's sign == A).
`POST /api/astrology/friendships`(+`-analysis`; `analyze_friendships`/`_build_friendships_prompt`).
Tool `get_friendships` in `SECTION_TOOL["friendships"]` (+_DISPLAY "Core chart"). Default-on
`friendships` section in chart_context (compact: house-lord wiring `L{h} in H{lord_house}` + Parivartana;
the matrix is a visual reference, not seeded) rendered in `_render_context_block`. Ask-page
`sectionFriendships` toggle. Frontend: **Friendships card on AdvancedPage** (`Users` icon) — colour-coded
7×7 matrix grid + house-lord table + Parivartana pills + AI reading; `.fr-*` CSS. i18n `friendships.*`.
- **UI gotcha:** `.slice(0,2)` made "Adhimitra" and "Adhishatru" both read "Ad" (only colour
  disambiguated), and "Sama"→"Sa" clashed with Saturn. Fixed with an explicit `REL_ABBR`
  map: AM / Mi / Nu / Sh / AS.
- Verified live (owner's chart: Sun→Moon/Mars/Jupiter Adhimitra, →Venus Adhishatru, →Saturn Sama;
  house lords correct; no Parivartana).

**Remaining of the three requested:** unknown-birth-time mode (§5.8) — doing next.

## 34. Unknown / approximate birth-time mode (§5.8) — ✅ SHIPPED 2026-07-15
Honest handling of the most common real-world problem: no reliable birth time.

- **`BirthDetails.time_accuracy`** (database.py): `"exact"` (default/None) | `"approximate"` | `"unknown"`.
  Since profiles AND every analyze endpoint use `BirthDetails`, adding it here persists it on the
  profile and threads it to the AI in one shot.
- **Profile form** (ProfileSelectionPage): a "Birth time accuracy" `<select>` after the time field;
  added to formData default + edit-populate + both resets + the saved birth_details.
- **`<BirthTimeBanner>`** (new component + CSS): renders nothing for exact; for **unknown** a red
  banner ("Ascendant/houses/vargas/dasha unreliable — read Moon-based only"), for **approximate** a
  softer amber one; both link to `/rectify`.
- **Chandra Lagna re-base** (BirthChartPage): when unknown, the D1 Kundali gets `lagna={moon sign}`
  (the shared North/South chart already takes a `lagna` prop, so houses re-base to the Moon; planets
  keep their signs) and the subtitle becomes "D1 · Chandra Lagna". Moon sign read from
  `result.planets.Moon.house`.
- **AI context**: `build_chart_context` seeds `time_accuracy`; `_render_context_block` injects a strong
  per-accuracy caveat (unknown → "read Moon-referenced, caveat Lagna/houses"; approximate → "tentative,
  suggest rectification") right under Birth Details, so EVERY reading adjusts.
- i18n `profile.timeAccuracy`/`accuracy*` + top-level `birthTime.*` (en; hi/sa fall back).
- Verified live: seeded an `unknown` profile → banner shows, D1 re-based to Chandra Lagna (Leo=H1, As
  at the Moon), context caveat present for approximate+unknown, exact unchanged.

**Note (not done, possible follow-up):** the D9/varga section still renders under the (unreliable) real
Lagna with only the banner warning — could grey it out when unknown. The banner + Chandra-lagna D1 +
AI caveat deliver the honest-disclosure value for v1.

**§2.1 + §2.5 + §5.8 — the three requested — all shipped.** Remaining §5/§2 backlog: MCP (§2.3),
iCal (§5.10), chart explorer (§5.5), gochara-vedha (§5.6), nakshatra profile (§5.7), marriage
workspace (§2.6), Ashtakavarga transit chips (§2.4), life report (§5.11), RAG citations (§5.12).

## 35. Desktop hamburger nav + the entire leftover §5.x backlog (owner ask 2026-07-16) — ✅ SHIPPED

Owner ask: "add a hamburger for desktop (stop having to go back → down → pick another tile),
then implement all leftover 5.x, update the md files, and make sure every functionality is an
AI tool if it should be." All done in one pass; full frontend prod build green, backend imports
clean (156 routes). Details live in `improvements-2026-07.md` §5.5/5.6/5.7/5.9/5.10/5.11/5.12.

- **Desktop hamburger.** `NavDrawer` was already mounted everywhere (in `PageHeader` + the
  Dashboard nav) but CSS hid the toggle above 768px. Removed that restriction → the drawer now
  opens on every screen size, so you can jump between features from any page. Added the new pages'
  links to the drawer (+ Gochara/Nakshatra/Journal/Life-Report).
- **§5.7 Nakshatra profile** — page `/nakshatra`; tool `get_nakshatra_profile`.
- **§5.6 Gochara-phala with vedha** — page `/gochara`; tool `get_gochara_phala`.
  (Both back onto new `reference_data.py` classical tables + methods on `AstrologyCompute`.)
- **§5.5 Interactive chart explorer** — `<PlanetExplorer>` on the Birth Chart page (chip strip →
  slide-in panel, "Ask AI about this placement" deep-link). Frontend-only; no new tool needed
  (existing tools already expose the underlying data).
- **§5.9 Astro-journal + dasha diary** — page `/journal`; `journal.py` + Mongo CRUD; tool
  `get_journal_entries` (pre-fetched + injected onto `bd._journal` to cross the async/sync
  boundary of tool dispatch).
- **§5.10 iCal feed** — `ical.py` (signed token + RFC-5545); Settings → Calendar tab. Read-only
  feed, not an AI tool (it's a calendar-subscription serializer).
- **§5.11 Composed Life Report** — page `/life-report`; 7-chapter sequential generation + save +
  print. A composition of existing context, so no single new tool (it *uses* the whole context).
- **§5.12 RAG with citations** — `rag.py` (Ollama embeddings, disk-cached, graceful-degrade);
  tool `search_classical_texts`; `rag_corpus/` with an honest seed (no fabricated verse numbers)
  + README; AI-Tools page shows citation on/off.

**AI-tool coverage:** every feature that *should* be model-callable is — new tools
`get_nakshatra_profile`, `get_gochara_phala`, `get_journal_entries`, `search_classical_texts`
(all in `ALWAYS_TOOLS` + the `/api/ai/tools` catalog). iCal and Life Report are deliberately not
tools (a calendar serializer and a full-report composition, respectively — neither is a discrete
datum the model fetches). Nakshatra & Gochara readings are registered in `conversations.SOURCE_META`
so their saved readings deep-link correctly from the unified history; Life Report too (`life_report`).

**Still open after this pass:** §2.3 MCP/public API, §2.4 Ashtakavarga transit chips, §2.6 marriage
workspace, §2.7 more chakras; §3.2 golden-value backend tests; todo.md §14 Help/FAQ, §15 compact/tabs.

## 36. Essentials vs Everything — hide the depth from newcomers (owner ask 2026-07-16) — ✅ SHIPPED

Owner feedback: **we have built too much**. A newcomer opened the app to 40+ feature routes
(Jaimini, KP, Pancha-Pakshi, Sarvatobhadra, Bhrigu markers, Tithi Pravesha…) and couldn't tell what
they actually cared about. Shipped a view mode that shows the everyday set by default.

**Owner decisions (settled at ask time):** naming **Essentials / Everything** (not Simple/Advanced —
"Advanced" reads as *the good stuff is hidden from you*); the Essentials set below; **UI only — the
AI is untouched** (same prompt, same tool catalogue: a view toggle must not silently rewrite the
user's model prefs; the layman prompt is its own separate Settings control).

- **The feature registry** — `frontend/src/config/features.js`, the load-bearing piece, done first.
  One declarative list (`{key, path, Icon, tier, group, navOnly, gradient}`) that the NavDrawer, the
  Dashboard tiles and the mode filter all render from. They each used to keep their own hard-coded
  copy and **had already drifted** (the drawer and dashboard disagreed about what existed).
  DashboardPage 367 → 121 lines as a result. Add a route here once; it appears everywhere.
- **The Essentials set (11)**: Dashboard, Birth Chart, Ask AI Astrologer, Today (daily digest),
  Compatibility, Dhasa, Transits, Remedies, Life Report, AI History, Settings. Everything else is
  `tier: "advanced"`.
- **The mode**: `uiMode: "simple" | "advanced"` in `SettingsContext` (localStorage `ui_mode`, in
  `SYNCED_KEYS` → follows the user across devices). Internal values stay simple/advanced; only the
  **labels** are Essentials/Everything.
- **Grandfathering** (`config/uiMode.js`, kept out of SettingsContext so it is unit-testable —
  SettingsContext pulls in axios, which CRA's jest can't transform): new user → Essentials; a
  browser with prior settings → Everything; and on login, an **account with server prefs but no
  `ui_mode`** is promoted to Everything and written back — that covers an existing user on a fresh
  browser, where localStorage is empty and the local heuristic would wrongly say "new".
- **Not gated.** Advanced pages still render on a direct URL (bookmark / shared link / AI history /
  AI suggestion); they show `<AdvancedNotice>` + a one-click "Switch to Everything". Mounted once in
  `PageHeader`, which every feature page already uses. `isFeatureVisible` treats **unregistered**
  routes (login, profile-selection, /share/:token) as visible — otherwise the login page would get
  an "advanced feature" banner.
- **In-page simplification**: `<AdvancedOnly>` collapses depth behind one disclosure in Essentials
  and renders children **plainly** in Everything (zero visual change from before). Applied to Birth
  Chart's divisional/varga charts + Graha Drishti.
- **Toggle** in the NavDrawer (top), the Dashboard footer, and Settings → General — deliberately
  *not* Settings-only, or someone in Essentials never discovers there's more.
- i18n `uiMode.*` + `common.dismiss` + `birthChart.aspectsAdvanced` in en/hi/sa. **en `/advanced`
  relabelled "Chart Deep-Dive"** — with the MODE owning the word "advanced", a page called
  "Advanced Details" meant two different things on screen. (hi/sa already said "detailed
  information"; no collision.)
- Backend: **`ui_mode` added to `user_settings.PREFERENCE_KEYS`** — that tuple is a whitelist, and a
  key missing from it is dropped *silently*.
- Tests: `config/features.test.js` + `config/uiMode.test.js` (41 frontend tests pass; 234 backend).

### Two real bugs this surfaced (both pre-existing traps worth remembering)

1. **`resolveUiMode` must WRITE ITS ANSWER BACK, not re-derive it.** The prior-use evidence is keys
   that *ordinary use goes on to create* — `AskAstrologerPage` writes `ai_model`, and Ask AI is
   itself an Essentials feature. Re-deriving each load silently promoted a brand-new user to
   Everything as soon as they used the app. Decide once, record it; only an explicit choice moves
   it afterwards. Caught by verifying in the browser (`ui_mode` was still `null` after a session);
   regression test added.
2. **`SettingsContext` was calling `authService.putPreferences` / `.getPreferences`, but both live
   on `astrologyService`** — so the whole cross-device preference sync had **never worked**. It
   failed inside a `.catch()` chain and a `setTimeout`, so nothing ever surfaced; the ui_mode push
   tripped over it. Fixed; server round-trip verified (`GET /api/user/preferences` now returns the
   pushed values). The AI model choice syncing across devices — a §12 promise — works for the first
   time.

**Verified live** (Playwright, owner's chart): fresh account → 9 tiles / 11 drawer links in
Essentials vs 37 / 39 in Everything; `/kp` deep-linked in Essentials renders fully with the banner;
the banner CTA and both toggles switch modes; Birth Chart shows exactly 2 disclosures which expand
to the real content; **no uncaught page errors**.

### Follow-up pass — in-page depth across the Essentials pages (owner ask, same day) — ✅ DONE

**Rule established: `<AdvancedOnly>` is for depth on ESSENTIALS-tier pages only.** An advanced-tier
page reached in Essentials already shows `<AdvancedNotice>`; collapsing its body behind a disclosure
too would be doubly annoying. So the Chart Deep-Dive page (`/advanced`) is deliberately untouched.

- **Dhasa** — keeps the current period + the Vimsottari tree; the other 14 dasha systems and the
  three-wheel Sudarshana Chakra collapse into one disclosure.
- **Transits** — the Ashtakavarga bindu column ("AV Support") is hidden in Essentials. It's a table
  *column*, so it takes a `settings.uiMode` conditional, not a wrapper (the `<th>`, the `<td>` and
  the support footnote all key off one `showBindus`).
- **Remedies** — the gemstone/mantra/charity advice stays; the dignity + strength-ratio table (the
  working behind it) collapses.
- **Ask** — answer mode, the per-section seed/tool/off context toggles and the vargas "Charts to
  Consult" picker collapse. **Trap:** `.ask-grid` is a CSS grid, so an `<AdvancedOnly>` *inside* it
  would collapse three cards into one cell — the knobs needed their own second `.ask-grid` under the
  wrapper.
- **Deliberately not touched:** Compatibility (already tab-gated — a tab bar *is* progressive
  disclosure, and Ashtakoot defaults first), Daily Digest (already digest-shaped), Life Report,
  History.

**Ask page: the AI-model tile was spending a whole grid cell on one line of text** (owner ask). Now a
small chip — model name + "View data sent" + "Change in Settings" — **right-aligned directly on top
of the chat area**, in both modes, with the examples getting the tile space back. (First attempt put
it in `PageHeader`'s `right` slot; owner rejected the location — it belongs with the transcript it
describes, not in the page chrome.) Deliberately understated at ~24px tall and 0.69rem: it's a status
readout, not a control the eye should land on. Removed the four CSS rule sets it orphaned
(`.ask-model-summary`, `.ask-model-summary__name`, `.ask-viewdata-btn`, `.ask-link-btn`). Under 700px
"View data sent" falls back to its icon while "Change in Settings" keeps its text — it has no icon,
so hiding its label would leave an empty button.

**Verified live** in both modes: Essentials → exactly 1 disclosure each on Dhasa/Remedies/Ask, no AV
column, model chip in the header; Everything → 0 disclosures, AV Support column + 9 bindu chips back,
content plain. No uncaught page errors. (**Test trap:** poking `localStorage.ui_mode` does NOT switch
the mode — the login sync correctly reasserts the server's value over it. Drive the real toggle.)

## 37. Dark mode / light mode toggle (owner ask 2026-07-16)

Owner ask: let the user switch between **light and dark**. Today `App.css` hard-codes a light
saffron/cream palette in `:root` and 24 stylesheets reference those tokens — plus a long tail of
**hard-coded hex/rgba literals** (charts, badges, chips) that would stay light-on-light in a dark
theme. The work is mostly *auditing the literals*, not writing a dark palette.

- [x] ✅ **Token audit — DONE 2026-07-16.** 625 literals / 251 distinct across 25 stylesheets →
      **~55 semantic tokens** in `App.css :root`. Every CSS colour literal in the app now lives in
      that one block; `src/styles/tokens.test.js` fails the build if one reappears (it also
      asserts no token is referenced-but-undefined). Owner decision: **cluster** near-duplicates
      rather than preserve every literal — measured drift is ≤ 0.04 luminance, largest being
      `#2b2113→#3a2e22` (two near-black browns) and `#999→#8b8fa8` (grey → the indigo-tinted
      muted grey). Light is *imperceptibly* different, not byte-for-byte.

      What the audit turned up, which matters for the palette step:
      - **Clustering was already the author's intent.** `var(--border-color, …)` was written with
        6 different fallback literals, `--card-bg` with 2 — the codebase already treated those
        families as one token.
      - **10 tokens were referenced but never defined** (`--border`, `--card-bg`, `--cream`,
        `--cream-dark`, `--text`, `--ink-light`, `--border-color`, `--indigo`, `--radius-pill`,
        `--gold`), silently rendering their fallback literal — i.e. **invisible to theming**.
        Now defined. (`--lvl-accent` / `--avatar` are legitimately set from JS — see DhasaPage.)
      - **`--indigo` was overloaded**: violet `#5e60ce` in the chakra rules but `#2D3561`
        (= `--text-primary`) on `.now-widget__head`. Split; alias retired for `--indigo-accent`.
      - **Tints keep exact alpha** via channel triples: `rgba(var(--accent-rgb), 0.08)`. The
        saffron tint alone spanned 10 alphas — clustering those would have flattened real depth.
        Dark mode reassigns the *triple*, so every tint follows for free.
      - ⚠️ **Off-brand leftover**: `#667eea → #764ba2` (a bootstrap-ish violet gradient) in
        `Forms.css` + `LocationSearch.css`, tokenised as-is to `--info`/`--info-dark`. It is not
        part of the saffron identity — decide whether to retire it during the palette step.
      - 🗑️ **Two dead duplicate stylesheets deleted** (2026-07-16): `Dashboard.css` (repo root)
        and `web/frontend/Dashboard.css` — leftovers from `b0eb113`, whose extracted CSS landed at
        the wrong path. Nothing imported either (all 39 imports resolve to `src/styles/`), all 48
        of their selectors were duplicated live, and they sat outside `src/` so the token audit
        never reached them. The CSS bundle was byte-identical after removal, hash included.
- [x] ✅ **Dark palette — DONE 2026-07-16.** Night-sky indigo ground (`#12162b`) with the saffron/
      marigold/gold accents, not a grey theme. Every dark token measured AA for body text against
      both `--bg-primary` and `--surface-raised` (lowest: `--text-muted` 4.80 on raised).
      **The spec's premise here was wrong and is corrected in the CSS:** "the light `--saffron-dark`
      will fail contrast" measures *false* — it is 5.8:1 on the dark ground, and plain `--saffron`
      8.4:1, both already AA. Saffron is lifted `#ff9933`→`#ffa64d` for **tone** (the dark ramp
      reads muddy on indigo), not contrast. Don't "restore" it citing contrast.
- [x] ✅ **The setting — DONE 2026-07-16.** `theme: light|dark|system` in `SettingsContext`
      (`SYNCED_KEYS` + `PREFERENCE_KEYS` server-side), default **system**, pre-paint stamp in
      `index.html` that resolves *system* (not the stored literal), `matchMedia` listener for an OS
      flip with the tab open. Toggle in `PageHeader` **and `DashboardPage`** (the Dashboard rolls
      its own `nav-right` and does not use PageHeader — easy to miss) + Settings → General.
      **Fixed a real race while verifying:** the 600ms debounced server push meant a toggle
      followed by a reload inside that window left the server holding the OLD value, and the login
      sync then reasserted it over the correct local one — the click silently reverted. Discrete
      toggles (`theme`, `uiMode`) now push immediately (`IMMEDIATE_KEYS`).
- [x] ✅ **The awkward surfaces — DONE 2026-07-16.** The audit had TWO blind spots, both of which
      left light slabs sitting in the dark theme; each is now covered by a guard test:
      - **CSS colour keywords.** `background: white` ×66 and `color: white` ×47 sailed through the
        hex/rgba audit. This is what kept the Dashboard cards, tiles and chips white.
      - **JS: SVG paint attributes + inline styles.** `fill="white"` on the Kundali rect, the
        VedicClock SVG's whole palette, and `SarvatobhadraPage`'s `CELL_BG` chakra rings — none of
        it is CSS, so no stylesheet audit could ever have seen it.
      - `--cosmic-indigo` **is re-tinted in dark** (`#9a9bef`), unlike the other brand hues: it is
        not used as a hue but as the app's dark *ink* (chart strokes, rasi labels, `--lvl-accent`
        from JS). Re-tinting the token fixed every call site at once, JS included, with zero light
        drift. `--surface-inverse` is overridden separately since a surface must go the other way.
      - `--forest-green` was one more never-defined token living on a fallback; now `--success`.
      - **Print/PDF stays light** via a trick worth keeping: the dark block is wrapped in
        `@media screen`, so print simply never sees it and the light `:root` wins unopposed — no
        duplicated palette to rot. `exportChart.js` additionally forces light *during capture*
        (`withLightTheme` / html2canvas `onclone`), because it inlines **computed** styles: a chart
        captured in dark would otherwise export as dark glyphs onto its white canvas.
      **Verified live** (playwright, real toggle): Dashboard/BirthChart/Settings/Ask/Chakras/Dhasa
      all dark, no page errors; print emulation under `data-theme="dark"` resolves `--surface:#fff`
      and body white; mobile 390px collapses the toggle to an icon with no overflow.
- [x] ✅ Verify every page in both themes, prod build, mobile — done for the pages above.
      **Not yet looked at in dark:** the remaining ~30 feature pages, Kota/Kaala/Tripataki
      canvases, Life Report. The tokens cover them, but "covered" ≠ "looked at".
      (**South Indian chart** cleared in dark on 2026-07-17 under §38 — grid, sign labels,
      centre caption and the aspect overlay all read correctly on the night ground.)

### Owner decision (2026-07-16)

**Three-way: Light / Dark / System, defaulting to System.** So `prefers-color-scheme` is the
first-run behaviour (a user whose machine is already dark never sees the light theme), with a
manual override that sticks. The pre-paint `data-theme` stamp in `index.html` must resolve
*System* too, not just the stored literal — and it must react to the OS flipping while the tab is
open (`matchMedia("(prefers-color-scheme: dark)")` listener), which is the bit that's easy to miss.

## 38. Chart houses label the RASI + the chart's name stops eating the middle (owner feedback 2026-07-17) — ✅ SHIPPED

Owner relayed two pieces of feedback on the North Indian chart:

1. **"The house number 1, 2 … people confuse with Aries, Taurus."** They were right and we were
   wrong. By convention the numeral inside a North Indian house **is the rasi number**
   (1 = Aries … 12 = Pisces) — the house is never numbered, because the geometry fixes it (top
   diamond = 1st house, always). We printed the *house* number in the sign's place and then
   repeated the sign as an abbreviation beside it. JHora, AstroSage and every printed kundali
   number the rasi.
2. **"`Rasi Chart D1 - Natal Indian` is ugly and eats important space."** The title was drawn
   **twice** — once as the card heading and again across the diagram's centre, which is where the
   inner diamond's four houses meet and where the graha-drishti lines converge.

### Shipped

- **The numeral is the sign.** `getSignForVisualHouse()` already computed it; the label just
  stopped rendering `house.num`. Numbers and glyphs are **language-neutral**, which spares the
  in-progress §P3 i18n work from inventing rasi abbreviations that don't exist in hi/sa.
- **Setting: Sign labels** — `config/signLabel.js` (pure module, jest-testable, kept out of
  SettingsContext for the axios reason §36 documents) + `settings.signLabel`, localStorage
  `sign_label`. Four values: **Number / Glyph / Number + glyph / Abbreviation**, default
  `number_glyph`. **One setting with four values, not three toggles** — toggles allow "none", i.e.
  a chart of unlabelled houses; `signLabelParts()` falls back to the default on junk. Both charts
  read it via `useSettings()` directly — do **not** prop-drill it through the ~17 pages the way
  `chartStyle` is. Not in `SYNCED_KEYS` (consistent with `chartStyle`). Hovering a house names the
  sign in full in every mode, so a bare `1` or `♈` is always resolvable.
- **Glyphs coloured by tattva** — fire vermillion, earth emerald, air gold, water indigo, cycling
  from Aries every 4 signs (so trines share a colour). Owner liked the colour of the *emoji*
  rendering; this is the reproducible version of that — emoji badge art is per-platform font
  (Noto vs Apple vs Segoe), so no two users would see the same chart. `rasiTattvaColor()` returns
  `rgb(var(--tattva-*-rgb))`, never a literal.
- **Captions travel with the export.** North: a `<text>` in a `CAPTION_STRIP` band added to the
  viewBox *below* the square — the bottom-right **interior** is a thin wedge shared by houses 8/9
  and would collide once they fill. South: back in the grid's **inner 2x2** (owner: "for south keep
  it in the center") — that space is purpose-built and nothing else can use it. Card heading now
  carries the subtitle as a `.chart-card-sub` chip. North's centre is deliberately empty.

### Traps worth keeping

- **U+2648..U+2653 default to EMOJI presentation.** Bare zodiac glyphs render as colour badges
  wherever an emoji font exists — verified, Chromium/Linux picks Noto Color Emoji and the chart came
  out as little coloured circles. `RASI_GLYPHS` appends **U+FE0E** to force the text form.
  `signLabel.test.js` pins the selector because it is **invisible** — a reformat could drop it and
  nothing else would notice. (SVG glyph *paths* were planned as the robust fix and proved
  unnecessary: VS15 works and exports were verified carrying real glyphs.)
- **`--tattva-*-rgb` alias existing brand triples** rather than defining new hues, which is exactly
  what lets them need **no dark override** — each triple they point at already has one, so the
  elements follow the theme for free (water flips navy → periwinkle on the night ground).
  `tokens.test.js` demanded a dark value for every themed token and failed on them; it now knows the
  general rule that **`--x: var(--y)` inherits its target's dark value** — by *value*, not by name,
  so a literal that later replaces an alias is caught again.
- **The South caption needs `z-index: 3` + a plate behind the text.** `.si-aspect-overlay` is
  `z-index: 2` — declared in `Aspects.css`, not the chart's own stylesheet, which is why a first
  attempt at `z-index: 1` silently lost — and it converges on that exact point. The drishti lines
  ran through the old centre label too, so this is a fix, not a new avoidance.
- **`.settings-row` is a two-child flex** (label | control). A `.settings-hint` *inside* it lands
  **beside** the control and squeezes it (owner caught this: the segment clipped mid-word). Hints go
  as a **sibling after** the row — as every other hint on the page already does.
- **Export bug found and fixed en route**: `elementToPngBlob()` searched a container for a
  descendant `<svg>`, and the South grid nests the aspect-line overlay `<svg>` — so exporting a
  South chart **with aspects shown** produced bare lines on white paper, no chart. Only an element
  that **is** an `<svg>` takes the serializer path now.
- **Screenshot-testing**: `theme` and `uiMode` are in `SYNCED_KEYS`, so writing localStorage is
  futile once logged in — the login sync pulls the server copy and reasserts it; click the control.
  `chartStyle`/`sign_label` are not synced, so localStorage works for those. `showAspects` persists,
  so clicking its toggle is **not idempotent across runs** — set the key, don't click.

**Verified live** (playwright, owner's chart 1976-06-04 Aligarh): Ascendant 25.1° Taurus sits in
house 1 labelled `2 ♉`; all four label modes; North + South in **light and dark**; PNG exports from
both styles with aspects on, carrying glyphs + caption and pinned light. 71 frontend tests, prod
build clean.

## 39. Sign-in resumes your profile instead of always asking (owner ask 2026-07-17) — ✅ SHIPPED

Part 1 of two pieces of owner feedback (§40 is the other: birth-timezone vs. where-you-live-now).

> "When the person logs in it should just load the last profile or the default profile and just
> goes in, or at least gives the user the option to select in settings?"

Right, and it was nearly free: `selectProfile` **already** cached the profile in localStorage and
restored it on mount. The picker wasn't holding state that didn't exist — `LoginPage` just
unconditionally `navigate("/profile-selection")`-ed over it. Most people read one chart, their own,
and the picker was a click between them and it on every single login.

### Shipped

- **`config/startupProfile.js`** — the resolution rule, as a pure function: last-used → default →
  the only profile there is → the picker. Same reasoning as `uiMode.js`/`signLabel.js` for living
  outside `SettingsContext` (which pulls in axios, and with it a module graph jest can't
  transform), so the one rule that can actually strand someone is directly unit-testable.
  **18 tests.**
- **`ProfileContext.resumeProfile()`** — the single entry point: loads profiles, resolves, selects,
  and returns the path to navigate to. Every arrival route goes through it — `LoginPage`,
  `ResetPasswordPage` (the reset signs you straight in), `GoogleSignInButton`, and the new
  `StartupRedirect` at `/`.
- **`StartupRedirect` at `/`** — the root used to hard-`Navigate` to the picker, so *reopening the
  app with a live session* still landed there. Which is the common case: the PWA icon and a
  bookmarked root both hit `/`. Resuming only on login would have fixed the rarer half.
- **Settings → General → "On sign-in"**: *Open my last profile* (default) / *Always ask*. In
  `SYNCED_KEYS`, so the choice follows the user across devices, and in `IMMEDIATE_KEYS` because
  it's a one-click toggle — the 600 ms debounce exists to coalesce typing, and for a toggle it only
  opens the race §37 documents (reload inside the window → login sync reasserts the OLD value →
  the click silently reverts). Whitelisted as `startup_profile` in `user_settings.PREFERENCE_KEYS`,
  which drops unknown keys **silently**.

### Traps

- **The cached profile is a stale snapshot, and must never be resumed into directly.** It can have
  been renamed, edited, or deleted from another device. `resolveStartupProfile` therefore uses the
  cached `_id` only to *look up a fresh record* in the list just fetched from the server, and
  returns an element of **that** list. A deleted profile falls through to the default, then to the
  picker — resuming into a dashboard for a chart the server no longer has is the failure mode this
  exists to prevent.
- **The mode is read from localStorage, not `SettingsContext`.** On login the context is still
  pulling the server copy of the preferences; reading it there would race that fetch and could show
  the picker to a user who chose *resume*. Same shape as `resolveUiMode()` being callable
  standalone.
- **A lone profile opens rather than showing a one-card picker.** Not in the stated precedence, but
  with exactly one saved profile the picker can only be a click on the one card — which is the
  friction the setting exists to remove.
- **`RegisterPage` deliberately still hard-codes the picker.** A new account has no profiles, so
  the picker *is* the destination (it's where the first profile gets created); routing it through
  `resumeProfile` would only buy a wasted fetch to reach the same screen.
- The ~40 `navigate("/profile-selection")` calls on feature pages are **"no profile selected"
  guards**, not arrival routes. They stay.

**Verified**: 90 frontend tests (18 new), eslint clean on every touched file, prod build clean.

## 40. Where you were born vs. where you live now (owner ask 2026-07-17) — ✅ SHIPPED

Part 2 of the owner's two-part feedback (§39 was the first).

> "Person born in India and now living in the US — the timings are off. Notifications and many
> other things are being sent from the Indian timezone but it should be local. Can we store the
> last place where the person logged in as a reference and show info as per that location?"

Confirmed in the code before touching anything. `scheduler.py` took its clock from
`resolve_profiles(...)[0].birth_details.timezone` — the **birth** offset. So a 7am digest for a
US resident fired at 7am **IST**, i.e. 8:30pm the previous evening for them. Reproduced live
against the running DB with the owner's chart:

    no location set    -> 2026-07-17 10:18  (Aligarh)
    location = Chicago -> 2026-07-16 23:48  (Chicago)

Note the **date** differs, not just the hour — so the scheduled digest was about the wrong *day*,
which is the "many other things" half of the report.

### The distinction the whole section rests on

- **Birth details are a constant of the chart.** One instant, one place; the offset in force then
  is true forever. They are **never touched** by any of this. The chart does not move when the
  person does.
- **Current location is a property of the reader**, not of any chart — so it lives on the
  **account**, not per-profile, and there is exactly one.

### Shipped

- **`timezones.py`** — zone lookup (`timezonefinder`, offline) + DST-aware offset/`local_now`
  (`zoneinfo`). **24 tests.**
- **A current location stores an IANA zone name, NEVER an offset.** An offset cannot express a
  DST zone: whichever number you store, you are wrong for half the year. India has no DST, which
  is precisely why a codebase grown on IST never had to learn this. The offset is derived from the
  zone *for the moment it's needed*; `utc_offset` is served alongside the zone so callers needing
  a number (the engine takes hours-as-float) don't each re-derive it and each get it wrong.
- **`user_settings.{get,set,clear}_current_location`** + `GET/PUT/DELETE /api/user/location`
  (3 new routes, snapshot regenerated — the inventory guard caught them, as designed). Structured,
  so deliberately **not** a `preferences` string.
- **The fix**: `scheduler._user_local_now()` paces off the user's zone; `digest.observer_clock()`
  feeds the scheduled digest its `date` (+ `current_time`/`current_tz` for daily) so it's about
  the reader's today.
- **Frontend**: `LocationContext` (server-stored, so `LocationProvider` wraps the app),
  Settings → **Location** tab, and `LocationPrompt` — a detect-**and-confirm** banner on the
  Dashboard. `config/currentLocation.js` holds the rule, **16 tests**.

### Traps

- **The in-app pages were already right; only the scheduled path was broken.** `TransitPage` and
  `DailyDigestPage` already send the browser's own DST-aware offset and date. The scheduler has no
  browser — that asymmetry *is* the bug, and it's why the fix is server-side. Don't "fix" the
  pages.
- **Detection suggests; it never sets.** Silently adopting the browser's zone would let a week in
  London rewrite someone's panchanga and move their digest with no visible cause. Travel is
  ordinary; emigrating is not.
- **The banner links to Settings rather than resolving the location itself.** The browser knows a
  *zone* but not *where* — and a stored location needs real coordinates for the astrology to mean
  anything. Synthesising a representative point for a zone would be a fabrication that later reads
  as fact. Only the user can name their city.
- **For an unset user the prompt compares OFFSETS, not zones** — forced, because a birth profile
  has no zone name, only a number. Coarse (it can't tell Chicago from Mexico City, and it goes
  quiet for half a DST year), but it only decides whether to *ask*, and its answer is never stored.
- **`useLocation` was renamed `useCurrentLocation`** — react-router exports a `useLocation`, and in
  a router-heavy app the collision is a live footgun.
- **`btn-primary`/`btn-secondary` don't exist in this codebase.** Both were invented and rendered
  unstyled until the screenshot showed it; the real class is **`.control-btn`** (`Shared.css`, so
  it's legitimately available outside Settings) with `--ghost`/`--danger` variants in `Settings.css`.
- **`timezonefinder` covers open water** with the nautical `Etc/GMT±N` zones rather than returning
  None, so even a mis-dropped map pin yields a usable zone. (A test asserting None caught this —
  the assumption was wrong, not the code. `Etc/GMT` is sign-inverted: `GMT+2` is UTC-2.)
- **`.settings-row` is a two-child flex**, so a long geocoded place name ("Chicago, South Chicago
  Township, Cook County, Illinois, United States") wraps the **label** unless the value gets
  `min-width: 0`. Same family as the §38 hint-inside-the-row trap.
- **Settings tabs are now derived from one `TAB_ICONS` list** rather than a hand-written array, so
  `?tab=` validation and the tab bar can't drift. Every label was already `settings.tabs.<key>`,
  which is what made the derivation possible.

### Known gap (deliberate, not done)

**Panchanga is still computed at the BIRTH place**, in both the scheduled digest and the in-app
Daily Digest page — `get_daily_digest` hands one `place/lat/lon/tz` to both the natal calc and
`get_panchanga`, so there is no observer place to pass. Sunrise in Aligarh and Chicago differ by
hours, so a US resident's tithi/vaara labels are cast on an Indian sunrise. Fixing it means an
`observer_*` parameter through the digest computes (all three cadences) and the endpoints. Called
out rather than half-done: §40 makes the digest arrive at the right hour, about the right day, but
its panchanga is still the birth place's.

**Verified live** (playwright, owner's chart, browser zones faked to Chicago/London/Kolkata):
scheduler pacing + the date shift above against the real DB; the `Etc/GMT` and DST offsets
(`America/Chicago` → **-5.0** in July, i.e. CDT, where a stored offset would have said -6);
`PUT/GET/DELETE /api/user/location` incl. a junk zone falling back to coordinate derivation; the
real Nominatim search saving `America/Chicago · UTC-5`; the unset/moved/silent prompt cases; a
dismissal surviving reload; and both light and dark. 106 frontend + 261 backend tests, lint and
prod build clean.

## 41. The location banner sets the location (owner feedback 2026-07-17) — ✅ SHIPPED

Owner, on §40 the same day:

> "It does identify my timezone, but when I hit set my location it just takes me to the settings
> page and expects me to type. Should it already set it also? Also it says set my location or
> ignore, for now?"

Both fair, and the first one was **§40 being too cautious**. §40 reasoned: the browser reports a
*zone*, not a *place*, and a stored location needs real coordinates — so rather than invent them it
sent the user to Settings to type. But IANA names every zone after a representative city, so
`America/Chicago` → geocode "Chicago" is a **real lookup**, not a fabrication. Detecting the zone
and then asking the user to type its name back is silly.

### Shipped

- **`POST /api/user/location/from-zone`** — geocodes the zone's representative city and
  **verifies** it: derives the zone back from the geocoded coordinates and refuses unless it matches
  what the browser reported. Without that check a geocoder returning the wrong "Chicago" would be
  stored silently as fact. Every failure is a 4xx the caller falls back from by asking; never a
  silent wrong answer.
- **`timezones.representative_place`** ("America/Argentina/Buenos_Aires" → "Buenos Aires"), with
  `config/currentLocation.js`'s `zoneCity` mirroring it **for the button label only** — the server's
  copy is the one that decides what's stored, and it's the one that verifies.
- **The banner now reads "I'm in Chicago" / "Ignore for now"** — two plain choices. The dismiss was
  an unlabelled ✕ whose only clue was a tooltip; the owner asked for the words. One click, in
  place, no page hop, then a green confirmation (the banner just vanishing is too quiet to read as
  "saved"). A failure to confirm still falls back to Settings.

### Traps

- **The zone's city is not the user's city.** It's the city that *defines* the zone — someone in
  Milwaukee is `America/Chicago`. So the timezone is **exact** (which is what "now" runs on, and the
  entire reported bug) and the coordinates are **metro-accurate**. Owner accepted that trade
  explicitly: panchanga is cast at the birth place anyway today (the §40 gap), so metro coordinates
  cost nothing until that's fixed. Do not present this as a *detected position*.
- **`Etc/GMT±N` names no city** and its POSIX-inverted naming would mislead anyway, so
  `representative_place` returns None for it and the endpoint 422s rather than guessing. Same for
  bare regions and the `SystemV`/`US` legacy aliases.
- **The confirmation shows `zoneCity`, not the stored place.** Nominatim returns the full postal
  address ("Chicago, South Chicago Township, Cook County, Illinois, United States") — a mouthful to
  confirm back at someone. Settings shows the full thing.
- **`.control-btn--ghost` moved `Settings.css` → `Shared.css`**, next to the `.control-btn` base it
  varies. The banner is on the *Dashboard*; it only worked from Settings.css because CRA bundles all
  CSS globally, which is luck, not design.

**Verified live** (playwright): one click from the Dashboard sets it with **no navigation**, the
confirmation renders, and it survives a reload; `Etc/GMT+2` → 422 "names no city", `Mars/Olympus`
→ 400; light and dark. 111 frontend + 272 backend tests, lint and prod build clean.

## 42. Two stylesheets fighting over one input (owner feedback 2026-07-17) — ✅ SHIPPED

Owner, with screenshots of the login field and the Settings language dropdown:

> "can you see why the input text field is weird and dropdowns are larger"

Two unrelated causes, both cosmetic, both from the app having grown **two form systems** that never
got reconciled: the compact `.form-group input/select` in `Forms.css` (10px/12px padding, 14px,
1px border) and the roomier `.form-select` / `.control-input` / `.control-btn` in `Shared.css`
(2px sandalwood border, `--radius-md`).

### The box-in-a-box

The login markup is `.form-group > .input-wrapper > input`: the **wrapper** draws the border and the
input is meant to sit bare inside it. But `.form-group input` is a *descendant* selector, so it
matched the wrapped input too — and at **exactly the same specificity** as `.input-wrapper input`
(0,1,1: one class, one element). A tie, so the winner was whichever file CRA happened to bundle
later. `Forms.css` won, the input painted its own 6px-radius border and background *inside* the
wrapper's, and the extra 12px of horizontal padding pushed it past the wrapper's right edge.

Fixed in `Auth.css` by adding `.form-group .input-wrapper input` (0,2,1) alongside the original
selector, plus a `:focus` reset — `.form-group input:focus` was also outranking `.input-wrapper
input`, so focusing drew a second ring inside the wrapper's.

### The oversized dropdown

`.form-select` used `padding: var(--space-md)` (16px on all four sides) and `font-size: 1rem`, while
its own siblings in `Shared.css` — `.control-input`, `.control-btn` — already used `var(--space-sm)
var(--space-md)` and `0.9375rem`. It was the odd one out **within its own system**, not just against
`Forms.css`, so it was aligned to the siblings it shares rows with rather than restyled to a new
scale. 41px tall now, in line with the segmented toggles beside it in Settings → General.

### Traps

- **Specificity ties are decided by bundle order, and bundle order is not a design.** This is the
  same hazard §41 noted from the other side ("CRA bundles all CSS globally, which is luck, not
  design"). A rule that *looks* like it wins locally can lose to a file it has never heard of. When
  a component styles its own children, it needs specificity that survives being bundled next to
  anything — not a coin flip.
- **`.form-group input` reaches further than it reads.** It's a descendant selector, so it claims
  every input anywhere under a `.form-group`, including ones a component deliberately wrapped. Any
  new wrapped control under a `.form-group` will hit this.
- **`Forms.css` duplicates its own `.form-group select` block** (lines ~74 and ~334, near-identical).
  Left alone here — noting it because the second copy silently wins and editing the first has no
  effect.

**Verified live** (playwright, dark theme, the owner's screenshots reproduced): the login input
computes to `borderWidth: 0px`, transparent background, no box-shadow, focused *and* unfocused;
`.form-select` computes to `8px 16px` / `15px` / 41px tall. 111 frontend tests pass.

## 42. The banner names your TIMEZONE, not a city (owner feedback 2026-07-17) — ✅ SHIPPED

Owner, on §41's "I'm in Chicago" button, same day:

> "It should just say which timezone I am in and not the city, as the user would be confused."

Right, and sharper than it first looks. **"I'm in Chicago" claims a city the user may not be in.**
The zone's representative city *defines* the zone — someone in Milwaukee is also America/Chicago —
so §41's own documented caveat ("the zone's city is not the user's city") had leaked into the copy
and was being asserted back at the user as fact. It stated the one thing the flow doesn't know. The
timezone is the part it knows **exactly**, and the part everything about "now" actually runs on.

### Shipped

- **`zoneDisplayName` / `zoneLabel`** (`config/currentLocation.js`, 12 tests) — "America/Chicago" →
  **"Central Time (UTC−5)"**. The raw IANA name is no better than the city for this: it *is* a city
  name, and a developer-facing identifier. `Intl` `timeZoneName: "longGeneric"` gives the name
  people recognise, and unlike `"long"` it's **stable across DST** ("Central Time", not Central
  Daylight for half the year and Central Standard for the other). Intl localises it, so hi/sa get it
  with **no translation table of ours** (verified: `sa` → "उत्तर अमेरिका: मध्य समयः").
  `America/Indiana/Indianapolis` → **"Eastern Time"**, which is the right answer and one the city
  name could never have given.
- **Copy**: "You seem to be on Central Time (UTC−5), not your birth timezone. Use it for “today” and
  your digests?" → **Use this timezone** / **Ignore for now**. Confirmation: "Your times now follow
  Central Time (UTC−5)."
- **`source: "zone" | "place"` on the stored location**, and Settings tells the truth with it: the
  **timezone leads** (it's what the user chose), the place is secondary and reads **"near Chicago
  (approximate)"** when it came from a zone, plain when they searched it. Without this the banner
  would carefully avoid naming a city and then Settings would assert "your location is Chicago,
  South Chicago Township, Cook County, Illinois, United States" one screen over — the same confusion,
  relocated.
- The zone path now stores the **plain city** ("Chicago") rather than the geocoder's full postal
  address: street-level precision is a lie about a metro-level guess, and it only ever renders
  inside "near X (approximate)".

### Traps

- **Don't reach for the IANA name when avoiding the city.** `America/Chicago` fails for exactly the
  reason "Chicago" fails.
- **`longGeneric`, not `long`.** `long` flips with DST and makes the banner look like it changed its
  mind twice a year. A test pins that the label contains neither "Daylight" nor "Standard".
- **`Etc/GMT±N` has no friendly name** — Intl returns "GMT-02:00", which is fine, and
  `representative_place` still refuses it server-side, so it can't be set anyway.
- The offset uses a real **minus sign (U+2212)**, not a hyphen — pinned by a test, because a hyphen
  beside a digit reads as a dash in most UI fonts.
- `zoneCity` (frontend) is **gone** — replaced by `zoneDisplayName`. The server's
  `representative_place` still exists and still does the real work; it's the geocoding input, never
  a label.

**Verified live** (playwright, browser faked to America/Chicago): banner and confirmation name only
the timezone; Settings shows "Central Time (UTC−5)" + "near Chicago (approximate)"; then searching
**Milwaukee** — the exact case the wording exists for — yields the same Central Time with an exact,
unmarked place. 116 frontend + 272 backend tests, lint and prod build clean.

## §44 Admin console — deployer-only cross-account view + moderation (SHIPPED 2026-07-18)

**Ask:** the deployer wanted a page to see all data across every account. The
original idea was "a vague URL + a shared secret token only I hold." Rejected as
security-by-obscurity (leaks via logs/history/Referer, not tied to a person, no
audit trail). Built a real, auditable admin surface instead.

### Identity — env allowlist is the source of truth
- `ADMIN_USERNAMES` (`.env`, comma-separated; matches a user by **username OR
  email**, case-insensitive) is authoritative. `reconcile_admins()` runs at
  startup (main.py lifespan) and mirrors it onto a new `users.is_admin` flag —
  granting listed accounts, **revoking** de-listed ones. So an operator grants
  admin by editing the deploy secret and redeploying, **never** by touching
  Mongo (which is pod-internal). This directly answered the deployer's question
  "how do I flip a DB flag when the DB is only reachable inside the pod?".
- `get_admin_user` (deps.py) requires a normal session (real login/JWT) **and**
  admin identity. Non-admins get **404, not 403**, so a logged-in probe can't
  confirm the console exists. `is_admin_user()` checks the env list live (works
  before the next reconcile) then the DB flag.
- The admin logs in with their **own** password — no shared token anywhere.

### Data scope — metadata always, content is "break glass"
- Always available: user list + per-user counts, deployment aggregates
  (total/new-7d/30d/suspended/admins/google), stored-record totals.
- Drilling into a user's **actual private content** (readings/chats/journal/
  birth data) is gated behind `ADMIN_CONTENT_ACCESS` (default **false**;
  `require_content_access` → 403). Flip it + redeploy only when something is
  genuinely wrong; every content view is **audit-logged** (`admin_audit`).

### Moderation (Read + moderate, per owner)
- Suspend/unsuspend (blocks login + refresh via `assert_not_suspended` on the
  login/google/refresh routes — takes effect within one access-token lifetime).
- Cascade delete: `admin.py`'s `USER_COLLECTIONS` map (collection → user-key
  field; most `user_id`, but api_tokens/refresh_tokens/password_reset_tokens use
  `username`) drives both the counts and a full delete across all 13 per-user
  collections + the `users` doc.
- Guardrails: can't suspend/delete yourself or another admin; delete requires
  typing the username to confirm.

### Surface
- Backend: `admin.py` (logic), `routes/admin.py` (8 endpoints under
  `/api/admin/*`), wired in main.py; `/api/user/profile` now returns `is_admin`.
- Frontend: `AdminPage.js` (Overview / Users / Audit tabs; detail + delete
  modals), `styles/Admin.css` (all colours via theme tokens — dark/light safe),
  `adminService` in api.js, `/admin` route, and a **conditional** NavDrawer entry
  shown only when `user.is_admin`.
- Tests: `tests/test_admin.py` (allowlist parsing, identity, content toggle,
  the 404 gate, `/me`) — DB-free paths only, hermetic like the other smoke
  tests. Route snapshot regenerated (8 new routes appended).

**Verified:** 98 backend tests pass, token-literal guard passes, prod build
clean. Grant an admin by setting `ADMIN_USERNAMES` and redeploying.

## 45. iPhone layout fixes + Life Report that survives the phone sleeping (owner ask 2026-07-18)

Four owner-reported issues, all shipped.

### 45.1 Navbar icons invisible on iPhone
The settings gear rendered as an empty box and the logout button showed only its
text. Root cause was **not** colour: lucide icons are flex children, and once
`.nav-right` overflowed at phone width they shrank to zero. `.theme-toggle > svg`
was the only icon in the app with a `flex-shrink: 0` guard, which is exactly why
the theme toggle was the only visible one.
- [x] `flex-shrink: 0` on every `.nav-right` / `.navbar-brand` svg (and on
      `.logout-btn` itself) — applies to **all** pages, since `PageHeader` reuses
      the same `.navbar` classes.
- [x] New ≤640px block: tighter navbar padding/gaps, smaller brand, and
      **icon-only** actions (`.logout-btn span` hidden) to reclaim the width.
      Added `title`/`aria-label` to the logout button so the icon-only form keeps
      an accessible name.
- [x] Brand pinned to one line **scoped to `.dashboard-container`** — a blanket
      `white-space: nowrap` on `.navbar h1` would have overflowed long PageHeader
      titles like "Birth Time Rectification".

### 45.2 Profile name tile reformatted for phones
`.profile-avatar-large` had no `flex-shrink: 0` (circle squashed to an oval) and
`.profile-meta` was a nowrap flex row (the three birth fields crushed into narrow
columns).
- [x] `flex-shrink: 0` on the avatar at all widths; `min-width: 0` +
      `overflow-wrap` on `.profile-info` so long names/places wrap instead of
      widening the banner past the viewport.
- [x] ≤640px: avatar (56px) left with the name beside it, birth details stacked
      one per line, bullet separators hidden. **Owner picked this layout** over a
      centered card / compact single row.

### 45.3 Life Report no longer dies when the phone sleeps
Generation was a **client-side loop** of 7 sequential chapter requests. iOS
suspends a backgrounded page's JavaScript and kills in-flight fetches, so locking
the screen stopped the run — and since the report was only persisted once *every*
chapter finished, everything generated so far was lost.

**Owner chose the server-side background job** (over "client loop + resume", which
would only stop losing work rather than keep going).
- [x] New `life_report.py`: job documents in `life_report_jobs`, per-chapter
      persistence, cancel, and a **staleness reaper** — a run whose heartbeat is
      >15 min old (pod restart mid-job) is flipped to error so the UI can't spin
      forever and a restart isn't blocked.
- [x] 3 endpoints: `POST life-report/start` (idempotent — re-attaches to a run
      already going for that profile, so a reconnect can't start a second one),
      `GET life-report/job`, `POST life-report/cancel`. Run via FastAPI
      `BackgroundTasks`; the resolved model config (incl. API key) is passed in
      memory and never written to the job doc.
- [x] Frontend polls every 4s and **also refreshes on `visibilitychange`** — iOS
      freezes timers while the screen is off, so this gives an instant catch-up
      the moment you unlock. Client loop + the save-on-complete effect deleted;
      orphaned `generateLifeReportChapter`/`saveLifeReport` service wrappers
      removed (the endpoints themselves stay as public API).
- [x] A "this keeps running, you can leave" note while generating, plus a Stop
      button.

### 45.4 Report persists and stays in AI history
- [x] The page loads the latest job for the profile on open, so it shows your
      last report instead of a blank slate; **Regenerate** starts a fresh run.
- [x] **Owner chose "keep old versions"** — a regenerate never overwrites: each
      finished run files its own reading in the unified AI history (`source:
      "life_report"`), so previous reports stay browsable there.

**Verified:** 328 backend tests (11 new in `tests/test_life_report.py`, DB-free)
+ 116 frontend tests pass, prod build clean, route snapshot regenerated (3 new
routes, nothing lost or changed). Also driven end-to-end against live Mongo with
a stubbed LLM: full run → 7/7 chapters + history entry; regenerate → 2 jobs and
2 history entries (old kept); **interrupted run → the 2 chapters already done
survive** (the actual bug); cancel, cross-user cancel rejection, and the stale
reaper all behave.
