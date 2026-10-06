# Jyotir AI — Architecture & development

## Project Structure

```
pyjhora-web/
├── backend/
│   ├── config.py            # Configuration settings
│   ├── database.py          # MongoDB models and connection
│   ├── auth.py              # Authentication utilities (password hashing, JWT access tokens)
│   ├── refresh_tokens.py    # Long-lived, revocable, rotating refresh tokens (silent re-auth)
│   ├── main.py              # App wiring only: lifespan, CORS, router mounting
│   ├── models.py            # Pydantic request models
│   ├── deps.py              # Shared deps: auth, rate limit, model-config, persistence
│   ├── routes/              # 11 APIRouter modules (all ~160 handlers)
│   ├── astrology/           # PyJHora wrapper — engine.py + 14 concern mixins + core.py
│   ├── llm_service.py       # Multi-provider LLM layer (composes the llm/ mixins) + streaming
│   ├── llm/                 # base.py (enums/config), providers/{ollama,openai,gemini}.py, prompts.py
│   ├── chart_context.py     # Builds the structured chart context sent to the AI
│   ├── claim_check.py       # Checks a finished reading against the chart it came from (§69) — extract, verify, regenerate once, annotate
│   ├── claim_reports.py     # Daily claim-check counters + the admin triage queue
│   ├── events.py            # The chart's forward calendar (§70): store, refresh, claim, deliver
│   ├── tools.py             # Tool registry for agentic mode (wraps AstrologyCompute) + GET /api/ai/tools catalog
│   ├── tool_traces.py       # Lazy side-storage for smart-lookup tool results
│   ├── conversations.py     # Unified AI history: chat threads + one-shot readings (source registry, save_reading, retention cap)
│   ├── outcomes.py          # "Did this land?" verdicts on saved readings — snapshot, track record, fed back to the prompt
│   ├── life_report.py       # Server-side Life Report job: runs the 7 chapters in the background so a sleeping phone can't interrupt it
│   ├── user_settings.py     # Per-user encrypted API keys
│   ├── ratelimit.py         # Per-user rate limiting for AI endpoints
│   ├── shares.py            # Read-only shareable chart links
│   ├── api_tokens.py        # Per-user hashed API tokens for the public API + MCP
│   ├── rag.py               # Classical-text retrieval + citations (local Ollama embeddings)
│   ├── rag_corpus/          # The corpus itself: *.jsonl + import_text.py (see its README)
│   ├── tests/               # Golden-value + endpoint smoke tests (./dev.sh test)
│   ├── pytest.ini           # Test config
│   ├── requirements.txt     # Python dependencies
│   ├── Dockerfile           # Docker image for backend
│   └── .env.example         # Environment template
├── frontend/
│   ├── src/
│   │   ├── pages/           # Page components
│   │   ├── components/      # Reusable components
│   │   ├── contexts/        # React contexts
│   │   ├── services/        # API service
│   │   ├── styles/          # CSS files
│   │   ├── App.js           # Main app component
│   │   └── index.js         # Entry point
│   ├── public/
│   │   └── index.html       # HTML template
│   ├── package.json         # Node dependencies
│   ├── Dockerfile           # Docker image for frontend
│   └── .env.example         # Environment template
├── mcp/                     # Standalone MCP server (its own venv) — see mcp/README.md
│   ├── server.py            # Wraps the public API tool catalog for MCP clients
│   └── requirements.txt     # MCP SDK deps (kept separate from the backend)
├── docker-compose.yml       # Docker Compose configuration
└── README.md               # This file
```

## Development Notes

### Backend Architecture

The backend uses a layered architecture (the three big modules were split by
concern in §4 — pure file moves, no behaviour change):

- **main.py**: app wiring only — lifespan, CORS, mounting the routers
- **routes/**: the ~160 handlers as 11 `APIRouter` modules (astrology, astrology_ai,
  auth, ai, v1, quiz, user, profiles, journal, notifications, misc)
- **models.py** / **deps.py**: pydantic request models / shared dependencies
  (auth, rate limiting, model-config resolution, reading persistence)
- **config.py**: Configuration management
- **database.py**: MongoDB models and async connection
- **auth.py**: JWT and password utilities
- **astrology/**: PyJHora wrapper — `engine.py` (jhora bootstrap, JHora-matched
  defaults, constants, helpers) + 14 concern mixins + `core.py`, composed into the
  same `AstrologyCompute` facade
- **llm_service.py** + **llm/**: unified LLM service (Ollama / OpenAI-compatible /
  Gemini / OpenAI) — the tool loop stays in `llm_service.py`; provider adapters are
  `llm/providers/*`, prompt builders + the context renderer are `llm/prompts.py`
- **tools.py**: the AI tool registry (50 tools) — also what `/api/v1/tools` and the
  MCP server publish
- **events.py**: the forward calendar of a chart's own events (§70) — dasha
  changes, Saturn's phases, ingresses, retrograde stations, eclipses — stored per
  (user, profile, stable key) so it can be recomputed freely without ever
  re-alerting. Claiming is per *event*, not per window, which is what makes the
  alerts idempotent across ticks and workers
- **claim_check.py** + **claim_reports.py**: the claim checker (§69). `claim_check`
  is pure and database-free — it extracts the checkable assertions from a finished
  reading and tests them against the same context the model was given, then
  `guard()` regenerates once and annotates what survives. `claim_reports` holds the
  daily counters and the admin triage queue, and resolves the runtime mode

### Frontend Architecture

The frontend uses React with:

- **React Router**: Navigation between pages
- **Context API**: Global authentication state
- **Axios**: HTTP client for API calls
- **Responsive CSS**: Mobile-friendly design
- **Protected Routes**: Authentication checks
- **Shared primitives**: `PageHeader`, `ProfileBanner`, `Card`, `Button`, `DataField`,
  `ErrorBanner`, `LoadingState`, `NavDrawer` (mobile feature drawer), `GlossaryTerm`
  (Sanskrit-term tooltips, data in `src/constants/glossary.js`) — in `src/components/`,
  styled in `src/styles/Shared.css`
- **One feature registry** (`src/config/features.js`): `FEATURES` (one per routed page, with
  `tier`, `group` and optional `hub`), `FEATURE_GROUPS` (dashboard/drawer sections) and `HUBS`
  (§79). The drawer and dashboard render `navEntries(uiMode)` — hubs collapsed — and
  `PageHeader` mounts `HubNav`, the section strip that links a hub's members. Help's "?" button
  resolves through `config/help.js`. See FEATURES.md → *How the Dashboard is laid out*.
- **Mobile/PWA**: responsive rules in `src/styles/Responsive.css`; installable PWA via
  `public/manifest.json` + icons + `public/sw.js` (registered in production only; the
  service worker never caches `/api`). Navigations are network-first with the cached shell as
  the fallback — fixed in §74.4, where it turned out `fetch(request, { cache: "reload" })` on a
  navigation request is a synchronous `TypeError`, so that branch had never run and the app
  could not be opened offline at all
- **Code splitting** (§74): `App.js` loads every page through `React.lazy` — nothing but the
  shell, the contexts and the shared chrome is in the initial bundle (166 KB gzipped, down
  from 487 KB). `leaflet` lives in `components/MapCanvas.js` and arrives when the map picker
  is opened; `react-markdown` in `components/Markdown.js`; only `en.json` is bundled, with
  `hi`/`sa` fetched by `i18n/index.js`'s `ensureLanguage()` on selection. Consequences worth
  knowing: a page must be opened once online before it is available offline (four core routes
  are warmed at idle), and `RouteErrorBoundary` covers a chunk that fails — reloading once for
  a stale tab after a deploy, and explaining itself when offline. `src/bundleSplit.test.js`
  guards all of it; **do not add a static `import` of a page or a heavy library to `App.js`**
- **Offline reading** (§73): the shell alone was useless, since every number is computed
  server-side. `src/services/offlineCache.js` keeps each **deterministic** API response in
  IndexedDB — keyed on a hash of *user + method + path + params + body*, because the core
  payloads are POSTs and the Cache API cannot store those — and replays it when a request
  fails with no response at all. `OfflineBanner` then says when the copy was saved. AI
  readings, jobs and streams are never cached (they are in the history instead), and the
  store is dropped on logout and whenever a different account signs in on this browser.
- **Accessibility** (§73): every feature page wraps its content in `<main id="page-content">`
  with a skip link past the ~40-entry drawer; the drawer is `inert` when closed and closes on
  Escape; tab bars are one tab stop with arrow-key movement. The kundali is a complex image
  with a **full text alternative** — `src/config/chartDescription.js` names the ascendant and
  then every sign/house with its occupants, so a screen reader reads the chart rather than
  the word "image". Controls that cannot be a `<button>` get the keyboard contract from
  `src/utils/a11y.js`. The `jsx-a11y` lint rules are on; `./dev.sh test web` runs them.
- **Adding a dependency — regenerate the lockfile with the build image's npm.**
  `frontend/Dockerfile.nas` builds on `node:18-alpine`, whose **npm is 10.8.2**, and it runs
  `npm ci`, which refuses a lockfile that disagrees with `package.json`. A newer local npm
  (11.x) prunes nested entries that npm 10 still requires — it dropped
  `tailwindcss/node_modules/yaml`, and the NAS build died with *"Missing: yaml@2.9.0 from
  lock file"* even though the install had worked locally. So run the install through the
  same image rather than the host npm:

  ```bash
  cd web/frontend
  podman run --rm -v "$PWD":/app:Z -w /app node:18-alpine \
    npm install --package-lock-only <pkg>
  ```

  **This is now checked for you** — it had bitten twice, and a paragraph in a README is
  not a guard. `./dev.sh test web` and `build_web_image` (so `./dev.sh nas deploy` and
  `./dev.sh build`) both run the equivalent of

  ```bash
  podman run --rm -v "$PWD":/app:Z -w /app node:18-alpine npm ci --dry-run
  ```

  in ~2s, on a scratch copy of `package.json` + `package-lock.json` only, so nothing can
  write into the repo. The node tag is read out of `Dockerfile.nas` rather than hardcoded,
  so it cannot drift from what actually builds. With no podman/docker on the machine it
  warns and skips; `SKIP_LOCKFILE_CHECK=1` skips it deliberately. A failure prints the
  regenerate command above.

- **Tooling**: `npm run lint` (ESLint) and `npm run format` / `format:check` (Prettier).
  When `REACT_APP_API_URL` is unset, `src/services/api.js` defaults to the **same host** the
  page was served from (on port 8000) — so the app works from any device on the LAN with no
  per-device config (desktop via localhost, a phone via the machine's IP). Set it explicitly
  to override. `API_URL` is exported from `api.js` and reused everywhere (LocationSearch,
  MapPicker, ProfileContext) so the host can't drift to a hardcoded `localhost`.

### Important: PyJHora Installation

For **local development**, the backend imports the PyJHora library directly from the
repo's `../../src` (relative to `web/backend/`), so a clone is enough — no separate
install needed. (You can alternatively `pip install git+https://github.com/kunwarmahen/PyJHora.git`.)

For **Docker/Podman**, the backend image's build context is the **repository root**
(`docker-compose.yml`: `context: ..`, `dockerfile: web/backend/Dockerfile`) so the
image can vendor `src/` to `/src` — exactly where `astrology.py`'s `../../src` import
resolves inside the container. A repo-root `.dockerignore` keeps the `.git` dir and dev
junk out of the build context. No code changes are needed for the container to import
PyJHora. The stack also builds and runs under **Podman** (`podman compose up --build`).

## Testing

| Suite | Run | What it covers |
| --- | --- | --- |
| Backend | `./dev.sh test` (or `cd backend && venv/bin/python -m pytest tests`) | ~1,170 tests: golden chart values vs Jagannatha Hora, endpoints (main-thread ASGI client, no Mongo), registries, the claim checker, prompts |
| Frontend | `./dev.sh test web` (or `CI=true npx react-scripts test --watchAll=false`) | ~580 tests: config/registry modules, **every page mounted** (down / rejected / realistic) (`src/pages/pages.smoke.test.js`), chart cell placement (`src/components/chartPlacement.test.js`) |
| Engine | `./dev.sh test engine` | PyJHora's own ~8,000 (slow; manual) |
| CI | `.github/workflows/web-ci.yml` | backend + frontend (format, lint, tests) on every push/PR touching `web/` or `src/jhora/`; engine via manual dispatch |

**The page harness** (`pages.smoke.test.js`) discovers every `*Page.js`, so a new page is covered
the moment it exists. It mounts each one with the API **down** and with every call **rejected** (a 400 with
a `detail`, which is what routes send when a calculation fails) and asserts it doesn't throw or loop
on requests; every hub member must also render its hub strip. Traps it documents: CRA's `resetMocks`
wipes `jest.fn` implementations between tests (stubs are plain functions); context stubs must be
*stable* objects or effects that depend on them re-run forever; `react-markdown` is ESM-only, so the
`Markdown` wrapper is stubbed.

A third mode, **realistic** (§83.7), mounts every page against what the routes really send: the *real*
`services/api.js` functions run (URLs, params, interceptors) with axios's adapter and `fetch` answering
from `src/pages/__fixtures__/realistic.json` — 47 endpoints recorded from the running app for the owner's
chart by `frontend/scripts/record_page_fixtures.py` (reads the harness's own route list and profile;
skips AI, auth, the user's records and the LLM setup). Unrecorded paths get the 400. Re-record when a
payload changes shape. Two things make it work: `package.json` `"jest"` maps `axios` to its CJS build
(CRA's Jest doesn't transform axios's ESM — before the mapping, every realistic call threw and the pages
swallowed it, so the mode "passed" without serving anything), and the `realistic mode is real` test fails
unless the Birth Chart page is answered from the recordings and shows the recorded degrees.

**The chart test** renders a chart whose `house` fields are deliberately wrong for their signs: a renderer
that reads `house` instead of `sign_num` (the §65/§66 bug) fails it. Cells carry `data-house`/`data-sign`.

### Manual API Testing

Use curl or Postman:

```bash
# Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"testpass"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}'

# Calculate birth chart (use token from login)
curl -X POST http://localhost:8000/api/astrology/birth-chart \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "name":"John Doe",
    "dob":"1990-01-15",
    "tob":"14:30:00",
    "place":"Chennai, India",
    "latitude":13.0827,
    "longitude":80.2707
  }'
```

See also: [I18N_DATA_LAYER_DESIGN.md](I18N_DATA_LAYER_DESIGN.md) (read before touching engine-name translation), [AI_TOOL_CALLING_DESIGN.md](AI_TOOL_CALLING_DESIGN.md), [LOCATION_SEARCH.md](LOCATION_SEARCH.md).
