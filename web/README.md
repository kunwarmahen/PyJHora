# Jyotir AI — Vedic Astrology Web App (Setup & Deployment Guide)

> **Branding.** The product is **Jyotir AI** (configurable via `REACT_APP_SITE_TITLE` /
> backend `SITE_NAME`). References to **PyJHora** below name the underlying `jhora`
> calculation library / fork (`github.com/kunwarmahen/PyJHora`), which is unchanged.

## Overview

This is a full-stack web application for Vedic Astrology calculations using PyJHora library. It includes:

- **Backend**: FastAPI with MongoDB for data persistence and JWT authentication
- **Frontend**: React SPA with responsive UI
- **Authentication**: User registration and login with JWT tokens
- **Features**: Birth Chart (Rasi D1 + Navamsa D9), divisional charts D1–D60, Panchanga,
  Yogas/Doshas, dedicated Raja Yogas, Graha Drishti (aspects, with strength-weighted lines
  on the chart), Vimsottari Dhasa (+ 14 other dasha systems — including the **Sudarshana Chakra
  dasha**, a 12-year wheel read from the Lagna, Moon and Sun at once — & Sudarsana Chakra charts),
  Transits (Gochara — each transiting graha **weighted by its Ashtakavarga bindus** for the
  sign it occupies, with a supported/neutral/rough chip),
  an Ephemeris & transit calendar (daily sidereal grid + sign-ingress dates),
  a Bhava / house-cusp chart (Sripati / Placidus / KP / Equal),
  a print-ready Full Report (Save-as-PDF),
  Varshaphal / Tajaka annual horoscope (with year-ahead AI reading),
  an Almanac (planetary hours, eclipses, festival/vratha dates, a Drik ⇄ Surya-Siddhanta
  engine toggle, the Hijri date, and an AI day-guide),
  Pancha Pakshi Sastra (bird-cycle day timing, with AI day-guide),
  Muhurta / electional astrology (auspicious windows for an activity, with AI rationale,
  plus day sub-tools: Choghadiya, Panchaka, Tarabala & Chandrabala),
  Prashna / horary (a chart for the moment you ask, with a horary AI reading),
  personalized daily / fortnightly / monthly readings, each anchored to a real progressed (pravesha)
  chart on the solar (Tajaka) or lunar (tithi) ladder — "Today", "This Fortnight" (Paksha Pravesha) and
  "This Month" (Maasa Pravesha or the birth-tithi return) — plus Tithi Pravesha, the annual lunar
  return; all with AI readings and per-cadence email & push notifications,
  a Life Timeline (`/timeline`) — one clickable SVG axis around today with the Vimsottari
  maha/bhukti bands, the Sade Sati / Ashtama / Kantaka Saturn phases, the Jupiter/Saturn/Rahu
  ingresses and the eclipses (flagged on natal nakshatras); click any point for a "what's
  running" panel + on-demand AI reading,
  Bhrigu / Nadi-style yearly markers (the Moon-based annual progression + Bhrigu Bindu
  activations, with AI reading),
  Planetary Conditions — the classical point-flags (combustion, vargottama, pushkara, mrityu
  bhaga, marana karaka, gandanta, planetary war, retrograde) shown as a card on the Advanced
  page, as tone-coloured hover badges on the birth chart, and fed into every AI reading; plus
  a "tradition also recommends" banner of the conditional dashas that apply to the chart,
  Avasthas — the planetary states (Baladi age / Jagradadi wakefulness / Deeptadi temperament)
  as a card on the Advanced page and in every AI reading,
  a Planetary Strength page (`/strength`) visualizing Shadbala (six-fold strength + composition),
  Bhava Bala (house strength) and Vimsopaka Bala (varga dignity) as ranked bars, with an AI reading,
  a Sade Sati page (`/sade-sati`) — Saturn's 7½-year transits over the natal Moon, the cycles with
  their rising/peak/setting phases and retrograde re-entries, the Ashtama & Kantaka Shani periods,
  the current status, and a calm AI reading,
  planetary friendships (the compound-relationship matrix + house-lord placements + Parivartana) on
  the Advanced page, fed into every AI reading,
  and honest unknown/approximate birth-time handling — a per-profile time-accuracy flag that, when the
  time is unknown, re-bases the chart to the Moon (Chandra Lagna), warns that Lagna/house/varga results
  are unreliable, and tells the AI to read Moon-referenced,
  Remedies (traditional gemstone / mantra / deity suggestions per weak planet),
  Sensitive Points (Special lagnas & upagrahas, Sphutas, the 36 Sahams, and Argala —
  with AI reading),
  a Vedic Clock & Retrograde page (a live ghati/vighati clock + vakra-gathi retrograde
  loops, with AI reading),
  a **KP (Krishnamurti Paddhati)** page (planet & cuspal sub-lords, four-fold house
  significators, ruling planets, and KP horary 1–249, with AI readings),
  a **Jaimini** deep-dive (Chara Karakas, Karakamsa/Swamsa with rasi-drishti aspects, and
  argala, with AI reading),
  a **Chart of the Moment** (the current sky as a chart — a Dashboard mini-kundali widget
  plus a full `/now` page with panchanga & AI reading),
  a **Chakras** page (`/chakras`, tabbed) — four classical chakras for any chosen moment, each
  with a plain-language AI reading: **Sarvatobhadra** (transits + vedha), the **Kota Chakra**
  (the fort — transiting malefics marked as they breach the inner enclosures, the classical
  health/protection reading, plus Kota Swami/Paala), the **Kaala Chakra** (the wheel of
  directions — which compass direction each graha colours, for travel/orientation), and the
  **Tripataki Chakra** (vedha on the Moon + Lagna, readable on the transit **or** the
  Varshaphal annual chart),
  Compatibility — now a **marriage/relationship
  workspace** (tabbed: Guna Milan with side-by-side **D1 + D9** charts + Ashtakoot **+ Dashakoota
  10-porutham + Mangal/Kuja-dosha with cancellation nuances**; a **7th-house deep-dive** for both
  partners — lord, occupants, Venus/Jupiter karakas, Upapada; and a **dasha-overlap timeline** with
  a shared Saturn/Sade-Sati outlook, plus a marriage-aware couple AI reading), an Advanced page
  (Ashtakavarga, Arudha, Karakas, Special Lagnas, Upagrahas, Shadbala, Ayu/longevity), and
  experimental Birth-Time Rectification (BV Raman śuddhi methods, with before/after charts)
- **AI Integration**: Multi-model LLM support (Ollama/local, OpenAI-compatible, Gemini, ChatGPT)
- **Interactive Q&A**: Chat with AI Astrologer for personalized insights

> **Modernization in progress.** See [`todo.md`](todo.md) for the redesign plan and
> feature backlog. Charts are computed using the birth location's actual timezone,
> and the Birth Chart page now renders both the Rasi (D1) and Navamsa (D9) charts.

## What's New - AI-Powered Features 🆕

### Ask AI Astrologer

- **Interactive Chat Interface**: Multi-turn conversation with memory about your birth chart
- **Provider & model selection**: Ollama (local, auto-detected models), any OpenAI-compatible
  local server (LM Studio / llama.cpp / vLLM), Google Gemini, or OpenAI — pick the exact model.
  Chosen in the new **Settings** page (see below); the Ask page shows the active model with a
  "Change in Settings" link. A **Max response length** slider (also in Settings) raises the output
  cap if answers get cut off — it applies across **every** AI feature (Ask, predictions,
  compatibility, quiz, and the per-page plain-language analyses), not just the Ask page.
- **Streaming answers**: responses stream token-by-token (SSE) with a **Stop** button
- **Per-answer token usage**: each answer shows the provider-reported token count
  (prompt + completion breakdown on hover), captured from Ollama, OpenAI/-compatible
  and Gemini streams
- **Rich, transparent context**: D1 + chosen divisional charts (vargas), the running
  Vimsottari dasha chain, yogas, doshas, graha drishti (aspects), arudha padas
  (AL/UL), current transits, Sarva Ashtakavarga and Shadbala strengths — view the
  exact data sent (and in Smart-lookup mode the AI can fetch each on demand)
- **Two answer modes** (per conversation): **Full context** pre-sends the whole chart,
  or **Smart lookup** sends a small seed and lets the model fetch what it needs on demand
  — with a **per-section Seed / Tool / Off** control over what is pre-sent vs fetched
  (dasha, yogas, doshas, transits, vargas, ashtakavarga, shadbala, panchanga) — the
  tool-call steps show inline in the transcript. See
  [`docs/AI_TOOL_CALLING_DESIGN.md`](docs/AI_TOOL_CALLING_DESIGN.md)
- **Saved history**: every Q&A is stored per profile and can be revisited or deleted
- **Unified AI History** (`/history`): _every_ AI output across the whole app — not just the Ask
  chat, but every one-shot reading (Varshaphal, Muhurta, Prashna, Remedies, Bhrigu, Daily digest,
  Sensitive points, Vedic clock, Almanac, Pancha Pakshi, Sarvatobhadra, Compatibility, Compare,
  KP, KP horary, Jaimini, Chart of the moment, Rectification, Predictions) — is saved automatically.
  The History page groups items by profile
  (plus a **"No profile"** bucket for location-driven tools) and filters by chat vs. reading;
  clicking any item **returns to the tool that produced it and re-shows the exact saved reading**
  (a snapshot — no re-computation). Every tool page also has its own collapsible **"Recent readings"**
  control (filtered to that tool) for reopening a past reading in place. Readings pile up; each is
  individually deletable. Retention is capped by `AI_HISTORY_MAX` (default 100, pruned on write).
  (The Learn-the-Chart quiz keeps its own dedicated history and is not stored here.)
- **Answer affordances**: copy, **regenerate** (with the same model, or pick a
  _different_ provider/model from the split-button menu), thumbs up/down, and
  **export the whole conversation to Markdown or PDF**
- **Per-user API keys (encrypted)**: each user stores their own provider keys — managed in the
  **Settings → API Keys** tab — no shared `.env` key required
- **Rate limiting**: per-user per-minute + per-day quotas on the AI endpoints
- **Safety disclaimer**: clear "guidance, not professional advice" footer

### Essentials vs Everything (the view mode)

The app grew to ~40 feature routes, which is a wall for anyone who doesn't already know Jyotish.
A **view mode** decides how much of it is advertised:

- **Essentials** (the default for new users) shows the 11 things most people actually want —
  Dashboard, Birth Chart, Ask AI Astrologer, Today, Compatibility, Dhasa Periods, Transits,
  Remedies, Life Report, AI History, Settings — and collapses in-page depth behind a "Show advanced
  details" disclosure: the Birth Chart's divisional charts + Graha Drishti, Dhasa's other 14 systems
  + Sudarshana Chakra, Remedies' dignity table, and Ask's answer-mode / context / vargas knobs.
  Transits hides its Ashtakavarga bindu column. (`<AdvancedOnly>` is for Essentials-tier pages only —
  advanced-tier pages get the banner instead and render in full.)
- **Everything** shows all of it — KP, Jaimini, Chakras, Prashna, Muhurta, Varshaphal, Pancha
  Pakshi, and the rest.
- **Nothing is gated.** An advanced page reached by URL — a bookmark, a shared link, saved AI
  history, an AI suggestion — still renders in full; it just shows a banner explaining it's an
  advanced feature, with a one-click switch. Deep links never dead-end.
- **It is a view preference only.** It deliberately does not touch the AI: same prompt, same tool
  catalogue, same model. The layman/answer-mode controls are separate, on Settings → AI and Ask.
- **Where to switch**: the nav drawer (top), the Dashboard footer, or Settings → General. The
  choice syncs server-side per user, so it follows you across devices.
- **Existing users are grandfathered into Everything** (evidenced by prior settings in the browser,
  or by an account that already has server-side preferences) — the split never silently takes pages
  away from someone already using them.
- **Adding a feature**: `frontend/src/config/features.js` is the single registry the nav drawer, the
  Dashboard tiles and the mode filter all render from. Add the route there (with a `tier` and a
  `group`) and it appears everywhere; there is no second list to update.

### How the Dashboard is laid out

The tiles are not one flat grid — they are clustered into six sections, in the order a reading
actually proceeds, so features an astrologer reaches for in the same breath sit next to each other:

| Section | What's in it |
| --- | --- |
| **Start here** | Birth Chart · Ask AI Astrologer · Today |
| **Read the chart** | Bhava · Nakshatra · Planetary Strength · Chart Deep-Dive · Sensitive Points · Jaimini · KP · Nadi Karakas · Bhrigu Markers · Life Report · Full Report |
| **Timing** | Dhasa · Life Timeline · Transits · Gochara-phala · Sade Sati · Varshaphal · Tithi Pravesha |
| **Calendar & muhurta** | This Fortnight · This Month · Almanac · Muhurta · Pancha Pakshi · Chakras · Vedic Clock · Chart of the Moment · Ephemeris |
| **Relationships** | Compatibility · Compare Charts |
| **Remedies & practice** | Remedies · Prashna · Astro-Journal · AI History · Learn the Chart · Birth-Time Rectification |

- The sections are `FEATURE_GROUPS` in `config/features.js`; each feature names one via `group`.
  Headings and their one-line hints come from `nav.groups.<key>` / `nav.groups.<key>Hint`.
- The **nav drawer uses the same sections in the same order**, so the two surfaces teach one layout.
- **Empty sections disappear.** Essentials advertises nothing from Calendar & Muhurta, so that
  heading simply isn't drawn; the same happens per-section while filtering.
- **Search results stay grouped** — a match appears in the section it lives in when browsing, rather
  than being relocated to a flat result list.

### Settings (single source of truth)

- **One place for preferences**: a dedicated **Settings** page (gear icon in the Dashboard
  navbar + nav drawer, or `/settings`) with tabs — **General** (**view mode** Essentials/Everything,
  appearance light/dark/system, **on sign-in** resume-last-profile / always-ask,
  language, chart style North/South, **sign labels**, ayanamsa, **pravesha basis**),
  **Location** (**where you live now** — see below), **AI** (provider / model / endpoint, answer-mode default, **Max response length**
  slider, links to API Keys + AI Capabilities — the LLM/model choice is saved **server-side per user
  so it follows you across devices** and is what the scheduled daily digest renders with),
  **API Keys**, **Almanac** (Drik / Surya-Siddhanta
  engine), **Notifications** (daily-digest opt-in, target profiles — a subset or "all" — AI-reading
  toggle + preferred hour, email + browser-push toggles, "send test now"; **each profile can also carry
  its own delivery email** (Profiles → edit → *Digest email*) — see
  [How digest email delivery works](#how-digest-email-delivery-works) below), and **Account** (account overview, update email, change password,
  log out other devices, and a danger-zone **Delete account**)
- **Consolidated controls**: the per-page dropdowns/toggles that used to live on individual pages
  (ayanamsa, chart style, almanac engine, AI model/keys) were removed — pages now read these from
  Settings via a `SettingsContext` (backed by the same `localStorage` keys). Language is changed
  here too (the old per-page language switcher was removed)
- **Per-question controls kept on Ask**: answer mode, the per-section Seed/Tool/Off context
  toggles, and the vargas "Charts to Consult" picker remain on the Ask page (they're
  question-specific)

### How digest email delivery works

Every saved profile has an optional **Digest email** field (Profiles → edit). At send time each
profile is sorted by that field into one of two deliveries — and the two never compete:

- **You (the account owner) always get one combined email** covering *every* profile, at your own
  account address. This is unconditional.
- **Any profile whose Digest email is someone else's address also gets its own personal email** with
  just that person's section — *and* still appears in your combined copy.

So the mental model is: **your combined email = everyone, always; a per-profile email = an extra,
opt-in copy for someone who lives elsewhere or wants their own.** Nobody ever drops out of your view.

A worked example — your account is `you@example.com`:

| Profile | Digest email | Who receives that profile's reading |
| --- | --- | --- |
| Mahendra (you) | *(blank)* | You, in your combined email |
| Naina | `naina@…` | You (combined) **and** Naina (her own email) |
| Anoushka | `anoushka@…` | You (combined) **and** Anoushka (her own email) |
| Akansha | *(blank)* | You, in your combined email |

**Consent (why a newly-added address may not receive anything yet).** An *external* address is
**double opt-in**: saving the profile emails that person a one-time confirmation, and their daily
digest does **not** start until they click **Confirm**. Until then their status is *pending* — but
they are still in your combined copy the whole time. Every digest they do receive carries a one-click
**unsubscribe**, which stops their personal emails (again, without removing them from your combined
copy). The profile card shows the state: **invite pending / confirmed / unsubscribed** — that pill is
the first place to look if someone "isn't getting emails" (usually they just haven't confirmed).

**Two edge cases.** A profile whose Digest email is *your own* account address counts as "you" — it
goes in the combined copy only, no confirmation, no duplicate. And **browser push is always
owner-only**: a non-account family member has no logged-in device to push to, so they only ever get
email.

### Current location — where you were born vs. where you live

Two different questions, and the app keeps two different answers:

- **Birth details** (per profile): the moment and place you were born. A constant of the
  chart — they carry a fixed UTC offset (`+5.5`) and **never change**, not even if you move.
- **Current location** (per account, **Settings → Location**): where you live *now*. Used for
  everything about "now" — which day your digest is about, and the hour it's sent.

Someone born in India and living in the US has a birth offset of `+5.5` and a life that runs on
`America/Chicago`. Before this existed, everything was paced off the birth profile, so a "7am"
daily digest arrived at 8:30pm the previous evening — and was about the wrong day.

Each daily digest also carries **the next auspicious Choghadiya window** ("Favourable window today:
Labh 07:18–09:00"), a **"Since your last digest"** line calling out only what actually moved (a graha
newly retrograde/direct, a dasha or bhukti change, Sade-Sati starting or lifting), and per-person
**Open / Ask** buttons that deep-link straight to that chart. A profile can be set to **weekly**
(Profiles → edit → *Digest frequency*) so it rides the daily digest only on Mondays — handy for
family members whose day-to-day rarely changes.

A digest covering several profiles uses **one clock for the whole message**, so a family read
together never straddles two calendar days. The reader's current location wins; failing that the
first profile's birth offset is borrowed as a shared fallback (before this, each profile derived its
own "today" from its own birth timezone, so members born in different zones could land on different
days). A profile can also carry **its own "lives now" location** (Profiles → edit → *Lives now*) — a
family member studying abroad then gets a digest about *their* today, in *their* zone, while everyone
else stays on the owner's clock. Like the account location it stores an IANA zone (derived from the
coordinates), never an offset, so it is DST-correct. And the facts that are the same for everyone on that day — the panchanga headline, the
retrograde list, upcoming ingresses — are printed **once** under an "Across the sky today" header
rather than repeated under every name; each person's section then carries only what is specific to
their chart.

Current location stores an **IANA zone name**, never an offset, because an offset can't carry
DST: a stored `-6.0` for Chicago is an hour wrong for half the year (India has no DST, which is
why this went unnoticed for so long). The zone is derived from the coordinates offline with
`timezonefinder`; the offset is computed from the zone *for the moment it's needed*.

Setting one is optional and detection is only ever a **suggestion** — a banner offers ("You seem to
be on Central Time (UTC−5)… Use this timezone / Ignore for now"), the user confirms. Nothing is
adopted silently, or a fortnight abroad would quietly move your digest. Confirming is **one click**:
the server geocodes the zone's representative city and *verifies* the result lands back in that zone
before saving, so it's a real lookup with a check rather than an invented position.

**The UI speaks in timezones, never cities.** Naming the city would claim something we don't know:
the zone's city *defines* the zone, but someone in Milwaukee is also `America/Chicago`. So a
zone-derived location has an **exact timezone** and only **metro-accurate coordinates**, and says so
— Settings shows "Central Time (UTC−5)" with "near Chicago (approximate)" beneath it. Search your
city there to pin the exact spot. (The friendly zone name comes from `Intl` `longGeneric`, so it's
stable across DST and localised for free; the raw IANA name is a developer identifier.)

Leaving it unset falls back to the birth profile, which stays correct for anyone who still lives
where they were born.

### Help & FAQ

- **`/help`** (also `/faq`): 60 plain-language questions for someone who has never
  read a chart — what a birth chart is, why the exact birth time matters, what the
  square diagram actually shows, a one-line tour of every feature, what the AI can
  see and how far to trust it, and what's stored about you
- **Reachable from anywhere**: a "?" in every page header and on the dashboard,
  plus an entry in the nav-drawer footer
- **Maintainable**: structure in `config/help.js`, words in the `help.*` i18n
  block keyed by id — adding a question is one id plus two strings, and
  `config/help.test.js` fails if the two ever drift apart. The glossary is
  rendered from `constants/glossary.js`, the same table the hover definitions use
- Answers collapse by default and are searchable; `#id` deep-links a single
  answer (e.g. `/help#aiModes`)
- **The "?" is contextual**: it opens the answer about the page you're on, not
  the top of the FAQ. The anchor is derived from the route
  (`helpAnchorForPath`), so no page declares it and a new feature gets a
  specific "?" as soon as it joins the tour. A page explained in several places
  (`/settings`) falls back to the top rather than jumping arbitrarily

### Life Report (long-form, generated on the server)

- **Seven composed chapters** — personality, career, wealth, relationships, health, dharma and the
  current outlook — assembled into one document you can read, print or save as PDF
- **Generation runs on the server, not in the browser.** The page starts a job and then only polls
  it, so you can lock your phone, switch apps or close the tab and the report keeps being written.
  (It used to be a loop in the browser: an iPhone locking its screen suspended the JavaScript, killed
  the in-flight request, and — because nothing was saved until *every* chapter finished — threw away
  all the work done so far.)
- **Every chapter is persisted the moment it lands**, so partial progress survives an interrupted
  run, and a job abandoned by a server restart is reaped rather than spinning forever
- **The page opens on your latest report** for that profile instead of a blank slate; **Regenerate**
  starts a fresh run and **keeps the previous reports** — every finished one is filed in the unified
  AI history and stays browsable

### AI Capabilities page

- **Tool catalog / capability disclosure**: the **AI Capabilities** page (reached from
  **Settings → AI → "View AI capabilities"**, or `/ai-tools`) lists every tool the AI astrologer
  can call while answering — grouped by Core chart / Timing / Strengths & afflictions, each
  with a plain-language description and an optional **Show technical schema** toggle for its
  inputs
- **Always in sync**: rendered live from `GET /api/ai/tools`, which is derived from the same
  `tools.py` registry the model actually uses, so it never drifts from the real toolset

### Transit chat (in-context gochara reading)

- **Ask about _these_ transits, right on the Transits page**: an embedded chat below
  the gochara chart, seeded with _only_ the current transits + your running dasha
  (`pass_all` mode) so the AI interprets exactly what you're looking at — no redundant
  recompute, no drift from the displayed chart
- **Smart suggestion chips from the live sky**: surfaces questions from what's actually
  on screen — Sade Sati when Saturn transits the 12th/1st/2nd from your natal Moon,
  retrograde grahas, and upcoming slow-mover ingresses
- **Reuses the configured provider/model** from "Ask AI Astrologer" (keys resolved
  server-side); streams token-by-token with a **Stop** button; keeps its own saved
  conversation thread

### Enhanced Predictions

- **AI-Powered Analysis**: All prediction endpoints now support AI enhancement
- **Comprehensive Data**: Uses complete planetary positions, nakshatras, and chart details
- **Compatibility Analysis**: Deep AI analysis of relationship compatibility beyond just scores

### Public API & MCP server

- **Token-authed public API** (`/api/v1/*`): a stable, **read-only** surface for scripts and
  automation. `GET /api/v1/tools` lists the full astrology tool catalog (schemas included);
  `POST /api/v1/tools/{name}` runs any tool against one of your saved profiles (`profile_id`)
  or inline `birth_details`; `GET /api/v1/profiles` lists your charts. Rate-limited like the
  AI endpoints; no account/profile mutation is exposed.
- **Personal API tokens**: create/revoke long-lived tokens under **Settings → API access**
  (shown once, stored hashed, prefixed `jyd_`). Authenticate with `Authorization: Bearer jyd_…`.
- **MCP server** (`web/mcp/`): a standalone [Model Context Protocol](https://modelcontextprotocol.io)
  server that wraps the same catalog so **Claude Desktop** (or any MCP client) can compute charts,
  dashas, panchanga, transits, KP, Jaimini, muhurta and more against your profiles — over stdio
  or streamable-HTTP. It talks to the public API with your token; setup is in
  [`web/mcp/README.md`](mcp/README.md).

### Public landing page

`/` serves a public **marketing landing page** to signed-out visitors (glowing
North/South Indian charts that crossfade, cosmic starfield hero, feature and
"how it works" sections, and Log in / Get started free calls-to-action top-right).
Signed-in users still resume straight into the app (`StartupRedirect`), so the
landing page never gets in a returning user's way — the `/` route branches on auth
in `components/RootRoute.js`. The page ships its own theme-aware styles scoped under
`.landing` and reuses the app's Light/Dark/System toggle. An optional pricing
section (Free / Pro / Practitioner) is hidden by default and shown only when
`REACT_APP_SHOW_PRICING=true`; tier numbers are placeholders in
`pages/LandingPage.js` until you finalize them.

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
│   ├── tools.py             # Tool registry for agentic mode (wraps AstrologyCompute) + GET /api/ai/tools catalog
│   ├── tool_traces.py       # Lazy side-storage for smart-lookup tool results
│   ├── conversations.py     # Unified AI history: chat threads + one-shot readings (source registry, save_reading, retention cap)
│   ├── life_report.py       # Server-side Life Report job: runs the 7 chapters in the background so a sleeping phone can't interrupt it
│   ├── user_settings.py     # Per-user encrypted API keys
│   ├── ratelimit.py         # Per-user rate limiting for AI endpoints
│   ├── shares.py            # Read-only shareable chart links
│   ├── api_tokens.py        # Per-user hashed API tokens for the public API + MCP
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

## Prerequisites

### Option 1: Local Development

- Python 3.9+
- Node.js 16+ and npm
- MongoDB 5.0+ (or use Docker)
- PyJHora fork: `pip install git+https://github.com/kunwarmahen/PyJHora.git`

### Option 2: Docker (Recommended)

- Docker 20.10+
- Docker Compose 2.0+

## Installation

### Option 1: Local Development Setup

#### Backend Setup

```bash
cd backend

# Copy environment file
cp .env.example .env

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install PyJHora from fork
pip install git+https://github.com/kunwarmahen/PyJHora.git

# Edit .env with your settings
# IMPORTANT: Change SECRET_KEY to something secure

# Run backend
uvicorn main:app --reload
```

Backend will be available at `http://localhost:8000`

#### Frontend Setup

```bash
cd frontend

# Copy environment file
cp .env.example .env

# Install dependencies
npm install

# Start development server
npm start
```

Frontend will be available at `http://localhost:3000`

#### Running the tests

The backend has a golden-value + endpoint smoke suite (pinned to two JHora-verified
charts) that catches drift from a PyJHora bump or an `astrology.py` refactor:

```bash
./dev.sh test          # backend golden-value + endpoint + determinism tests
./dev.sh test engine   # also smoke-run PyJHora's own ~1,500-test suite
```

#### MongoDB Setup

Start MongoDB locally or use Docker:

```bash
docker run -d \
  -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=admin123 \
  mongo:7.0
```

### Option 2: Docker Compose (Recommended for Simplicity)

```bash
# Copy environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Build and start all services
docker-compose up --build

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# MongoDB: localhost:27017
```

To stop:

```bash
docker-compose down
```

#### Via `dev.sh` (auto-detects docker / podman)

The `dev.sh` helper also drives the container workflow, so you don't have to
remember the engine-specific commands:

```bash
./dev.sh build            # build image(s)
./dev.sh up               # build + deploy (detached)
./dev.sh ps               # container status
./dev.sh clogs            # follow container logs (add a target: clogs backend)
./dev.sh down             # stop & remove containers

# build/deploy a single service
./dev.sh up backend

# force a specific engine (default order: docker compose → docker-compose → podman)
DEV_COMPOSE="podman compose" ./dev.sh up
```

It also builds and serves an **optimized production frontend** (via
`npm run build`) without containers — handy for testing the real bundle or
serving over the LAN:

```bash
./dev.sh build-web        # build the optimized bundle -> frontend/build
./dev.sh serve            # serve that build on :3000 with SPA routing
                          #   (builds first if frontend/build is missing)
./dev.sh stop frontend    # stop the served build
```

Unlike `./dev.sh start` (the hot-reloading `npm start` dev server), `serve`
runs the minified production build, so it reflects exactly what ships.

#### NAS deploy (`./dev.sh nas …`)

Builds both images **locally** and loads them on the NAS — the NAS never builds
anything. Everything below runs over a single SSH ControlMaster connection, so
you're asked for a password once.

```bash
./dev.sh nas deploy              # build, ship what changed, restart the stack
./dev.sh nas deploy backend      # only the backend image (or: web)
./dev.sh nas deploy --force      # re-ship even if the NAS already has this image ID
./dev.sh nas deploy --skip-build # ship the images already built locally
./dev.sh nas logs [svc]          # tail NAS logs
./dev.sh nas ps | down | up | shell [svc]
```

The deploy is **incremental**. After each successful load, `dev.sh` records the
image IDs in `.deployed-images` on the NAS (plain text, no `sudo` needed to read
it). The next deploy compares that against what it just built and skips the whole
save → compress → transfer → load chain for any image that didn't change — which
is usually one of the two, since most edits touch either the backend or the
frontend, not both. `--force` bypasses the check if the NAS state ever drifts
(e.g. you removed an image there by hand).

Images are **streamed** — `podman save | <codec> | ssh` — with no intermediate
tarball on either side. The codec is negotiated at deploy time to the fastest one
*both* ends have: `zstd -T0` → `pigz` → `gzip`. Override with
`NAS_TRANSFER_CODEC=gzip ./dev.sh nas deploy` if you ever need to pin it. The two
image builds run in parallel, and the backend image carries no compiler toolchain
(see `web/backend/Dockerfile`), so there is a lot less to ship in the first place.

The deploy no longer runs `compose down` before `up`: compose recreates exactly
the containers whose image ID changed, so Mongo and the Cloudflare tunnel stay up
across a redeploy. For a hard reset use `./dev.sh nas down && ./dev.sh nas up`.

## Configuration

### Which `.env` file does what

There are three real env files (plus their committed `.example` templates). All
three are gitignored — only the templates are tracked.

| File | Read by | Used when |
|---|---|---|
| `web/backend/.env` | the backend process, via pydantic-settings (`config.py` → `env_file = ".env"`, resolved from `web/backend/` as cwd) | **local dev only** — `./dev.sh start`, or running `python main.py` by hand |
| `web/frontend/.env` | create-react-app, which inlines `REACT_APP_*` at build/start time | **local dev only** — `./dev.sh start` / `npm start` / `npm run build` |
| `web/.env` | `docker compose` (variable interpolation) and `dev.sh` (via `env_val`) | **Docker + NAS deploy** — `./dev.sh up`, `./dev.sh nas deploy`. Template: `.env.nas.example` |

Rules of thumb:

- **Running locally (`./dev.sh start`)** → edit `backend/.env` and `frontend/.env`.
  `web/.env` is *mostly* ignored here, with one exception: `dev.sh` pulls
  `GOOGLE_CLIENT_ID` / `REACT_APP_GOOGLE_CLIENT_ID` out of it and exports them
  into both processes, so Google sign-in works in local dev without duplicating
  the client ID. That's the only bridge between the two worlds.
- **Running in local Docker (`./dev.sh up`)** → `docker-compose.yml` hardcodes the
  backend/frontend settings in its `environment:` blocks and only interpolates the
  two Google vars from `web/.env`. Compose auto-loads `web/.env` because it sits
  next to the compose file. Note `environment:` wins over anything in the
  bind-mounted `backend/.env`, so editing that file has no effect under Docker.
- **Deploying to the NAS (`./dev.sh nas deploy`)** → **everything** comes from
  `web/.env`. `dev.sh` reads `NAS_*` and `REACT_APP_*` from it to build and ship the
  images, then `scp`s the file to the NAS where `docker-compose.nas.yml` consumes it
  both as `env_file:` for the backend and for `${VAR}` interpolation.
  `backend/.env` never reaches the image — the repo-root `.dockerignore` excludes
  `**/.env`. `frontend/.env` *is* copied into the frontend build context (no `.env`
  entry in `web/frontend/.dockerignore`), but every var the deploy cares about is
  passed as a `--build-arg` → `ENV`, and CRA's dotenv loader won't override a var
  already in the environment. Only vars `dev.sh` doesn't pass (currently just
  `REACT_APP_API_TIMEOUT`) fall through from your local `frontend/.env` into the
  production bundle — worth remembering if you add a new `REACT_APP_*` var.

So the same key (e.g. `SECRET_KEY`, `CORS_ORIGINS`, `APP_BASE_URL`, `DATABASE_NAME`)
lives in `backend/.env` for local dev and again in `web/.env` for production — they
are independent, and the values *should* differ.

> `src/jhora/ui/.env` is unrelated to the web app: it's a stray editor/launch-config
> fragment for the desktop PyQt UI, not a dotenv file. Nothing loads it.

### Backend (.env)

```env
# MongoDB
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=jyotirai_db

# Security (CHANGE IN PRODUCTION)
SECRET_KEY=your-secret-key-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
# Refresh-token lifetimes (days). "Keep me signed in" picks the long TTL; a plain login the short.
REFRESH_TOKEN_EXPIRE_DAYS=30
REFRESH_TOKEN_SHORT_DAYS=1

# LLM providers (endpoints + default models; keys are optional — users can also
# store their own per-user keys in the app). See backend/.env.example for the full list.
# OLLAMA_DEFAULT_MODEL is the server-side default: it drives the AI model shown in
# Settings › AI (as the "server default" when the model field is left blank) and the
# model reported in Settings › System, so a fresh deployment picks it up automatically
# — no per-browser setting to redo after each redeploy.
OLLAMA_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=qwen2.5:14b
OPENAI_COMPATIBLE_URL=http://localhost:1234/v1
GEMINI_API_KEY=         # optional global fallback
OPENAI_API_KEY=         # optional global fallback
OPENROUTER_API_KEY=     # optional global fallback (openrouter.ai/keys)

# Sharing the GPU with other workloads (§54). If the machine serving Ollama also
# runs training jobs, inference will periodically have nowhere to load the model.
# LOCAL_LLM_CONCURRENCY  in-flight requests per local host (1 = serialise; two
#                        readings on a contended GPU are slower than one after
#                        the other, and likelier to OOM)
# LOCAL_LLM_QUEUE_WAIT   seconds to wait for a slot before saying "busy"
# LOCAL_LLM_COOLDOWN     seconds a host is treated as out-of-capacity after an
#                        OOM, so 20 queued digests fail fast instead of each
#                        waiting out its own 300s timeout
# LOCAL_LLM_GATE=0       disables both of the above
# LLM_FALLBACK_ORDER     cloud providers to try when the local model can't answer
#                        (only ones that actually have a key are used)
# OLLAMA_CPU_URL         a second, CPU-only Ollama (`CUDA_VISIBLE_DEVICES= ollama
#                        serve` on another port) as the last resort: slow, but it
#                        never competes for the GPU
LOCAL_LLM_CONCURRENCY=1
LOCAL_LLM_QUEUE_WAIT=120
LOCAL_LLM_COOLDOWN=300
LLM_FALLBACK_ORDER=gemini,openrouter,openai
OLLAMA_CPU_URL=

# Per-user API-key encryption (keys users save in the UI are encrypted with this;
# falls back to SECRET_KEY if unset — set a stable value in production)
API_KEY_ENCRYPTION_KEY=change-this-to-a-long-random-string

# Per-user rate limits on the AI endpoints
AI_RATE_LIMIT_PER_MIN=20
AI_RATE_LIMIT_PER_DAY=300

# Public frontend URL — used to build links in outbound email (password reset)
APP_BASE_URL=http://localhost:3000

# Transactional email (SMTP) — provider-agnostic (Gmail app-password / SendGrid /
# Mailgun / SES SMTP). Leave SMTP_HOST blank to disable real sending (the reset
# link is logged to the console instead). Port 587 = STARTTLS, 465 = implicit SSL.
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=PyJHora <no-reply@example.com>
SMTP_USE_TLS=true
PASSWORD_RESET_TTL_MINUTES=30

# Web Push (PWA daily-digest notifications) via VAPID. Generate once with
# `python -m notifications genkeys`. Leave blank to disable browser push (email +
# in-app digest still work). NOTE: even with keys set, browsers only allow push on
# a secure context — an HTTPS page or http://localhost. Over plain-HTTP LAN
# hostnames the Settings toggle shows "unavailable" (a browser rule, not this key).
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:admin@example.com

# Daily-digest scheduler (opt-in): deliver each opted-in user's digest once a day
# at their preferred local hour. Safe with multiple workers (an atomic DB claim
# prevents double-sends).
#
# LEAVING THIS FALSE MEANS NOTHING IS EVER DELIVERED ON A SCHEDULE — no digest
# emails, no push. It fails *silently*: scheduler.start() returns immediately and
# no error is logged, so the backend looks healthy. Worse, Settings › "Send test
# now" keeps working (it calls POST /api/notifications/digest/send directly and
# bypasses the scheduler), which makes the feature look correctly configured.
# Set it true unless you are driving that endpoint from your own cron.
DIGEST_SCHEDULER_ENABLED=false
DIGEST_SCHEDULER_INTERVAL_MINUTES=15
# How many ticks a scheduled digest may be held back while the AI narrative is
# unavailable for a reason that may clear (the GPU is busy). Past this it sends
# with rule-based highlights and no narrative — late beats never. 6 × 15 min ≈ 1½ h.
DIGEST_AI_MAX_DEFERRALS=6

# Admin console (deployer-only /admin page: all accounts, usage, moderation).
# ADMIN_USERNAMES is the source of truth — comma-separated usernames/emails; the
# app reconciles each user's is_admin flag from it at startup, so you grant/revoke
# admin by editing this and redeploying, never by touching Mongo. Empty = no admins.
# ADMIN_CONTENT_ACCESS is a "break glass" switch: false (default) shows metadata +
# counts only; true also lets an admin open a user's private content (audit-logged).
ADMIN_USERNAMES=
ADMIN_CONTENT_ACCESS=false

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]

# Sign in with Google (optional). OAuth 2.0 Client ID (type: Web application) from
# https://console.cloud.google.com/apis/credentials — add http://localhost:3000 and
# your public domain as "Authorized JavaScript origins" (no redirect URIs needed).
# The backend verifies Google's ID token against this; the frontend needs the SAME
# value as REACT_APP_GOOGLE_CLIENT_ID. Blank = feature disabled, password auth
# unaffected. A first Google sign-in with an email that matches an existing account
# links to it; otherwise a new account is created with the email as the username.
GOOGLE_CLIENT_ID=
```

### Frontend (.env)

```env
# Brand name + tagline — white-label the app (nav bar, dashboard, auth pages,
# browser tab) without touching source. Optional; SITE_TITLE defaults to
# "PyJHora" and the tagline falls back to a translated default when unset.
REACT_APP_SITE_TITLE=Jyotir AI
REACT_APP_SITE_TAGLINE=Where Vedic Wisdom Meets AI

# Optional — when unset, the app calls the same host it was served from on :8000
# (so it works over the LAN from a phone with no per-device config). Set to pin it.
REACT_APP_API_URL=http://localhost:8000
REACT_APP_API_TIMEOUT=30000

# Sign in with Google (optional) — MUST equal the backend GOOGLE_CLIENT_ID. When set,
# a "Continue with Google" button appears on the login/register pages; when blank the
# button is hidden. `./dev.sh` passes this through from web/.env for local testing.
REACT_APP_GOOGLE_CLIENT_ID=
```

The brand mark next to the title uses the built app icon (`public/icon-192.png`),
rendered via the shared `BrandLogo` component. The **backend** has a matching
`SITE_NAME` setting (`backend/.env`) used in outbound email and the API docs title —
keep it in sync with `REACT_APP_SITE_TITLE`. Note: "PyJHora" is retained wherever it
names the underlying `jhora` calculation library (engine comments, error strings,
DB name), which is deliberate.

## Quick Start Guide

### Getting Started with AI Astrologer

1. **Register/Login**: Create an account at http://localhost:3000
2. **Choose AI Model**: Set up at least one AI model (Qwen recommended for free local use)
3. **Navigate to "Ask AI Astrologer"** from the dashboard
4. **Enter Birth Details**: Date, time, and place of birth
5. **Ask Questions**: Use example questions or ask your own
6. **Get Insights**: Receive detailed, personalized astrological analysis

### Example Questions to Ask

- "What are my key strengths and weaknesses?"
- "Which career path is most suitable for me?"
- "When should I consider marriage?"
- "What do my planetary positions reveal about my personality?"
- "How can I overcome current challenges in my life?"
- "What remedies would be beneficial for me?"

## Features

### 1. Authentication

- User registration with **name**, username, email, password (with a live password-strength hint).
  The name is shown in the dashboard greeting, Settings → Account, and the nav drawer, and is editable
  in Settings. Google sign-in pulls the name from the Google profile automatically.
- **Sign in with Google** (optional): a "Continue with Google" button on the login/register pages
  using Google Identity Services. The verified Google email becomes the username; signing in with an
  email that already exists **links** to that account (same verified email = same account), so a
  password user can later log in either way. Google-only accounts have no password; Settings →
  Account offers **"Set a password"** (no current password required) so they can also sign in with
  their email. Enabled by setting `GOOGLE_CLIENT_ID` + `REACT_APP_GOOGLE_CLIENT_ID` (see
  Configuration); the button is hidden when unset, leaving password auth unchanged.
- JWT-based login with a **"Keep me signed in"** option, and a per-IP **brute-force rate-limit**
  (default 10 failed attempts / 15 min → HTTP 429; env `LOGIN_RATE_MAX_FAILS` / `LOGIN_RATE_WINDOW_SEC`)
- **Refresh tokens**: a short-lived access token is silently refreshed in the background using a
  long-lived, revocable, **rotating** refresh token, so you stay signed in across access-token
  expiry (no more being logged out every ~30 minutes). Refresh tokens are stored hashed and are
  revoked on logout and on password change
- **Account management** (Settings → Account): account overview (name + username + member-since),
  **update name**, **update email**, **change password** (verifies the current password, signs out other devices;
  Google-only accounts see **"Set a password"** instead, which needs no current password),
  **log out other devices** (revokes every other session, keeps this one), and a danger-zone
  **delete account** — password-confirmed and irreversible, cascade-purging all of the user's data
  (birth profiles, saved charts, AI conversations + tool traces, shared-chart links, quiz sessions,
  settings and refresh tokens)
- **Forgot / reset password** (`/forgot-password`, `/reset-password`): request a reset by username
  or email; a single-use, TTL'd, hashed token is emailed as a link (via the provider-agnostic SMTP
  layer — see Configuration). The forgot endpoint always returns the same generic response (no
  account enumeration) and is IP-throttled; completing the reset revokes all sessions and signs you
  straight in. When SMTP is unconfigured the link is logged server-side so local dev still works.
- Protected routes; tokens in localStorage (access + refresh)

### 2. Birth Chart Calculator

- Calculate Rasi (D1) and Navamsa (D9) charts from birth details
- Divisional (varga) charts D1–D60 with a picker
- North / South Indian chart styles, selectable ayanamsa
- **Sign labels** follow the classical convention — the numeral in a house is the **rasi**
  number (1 = Aries … 12 = Pisces), not the house number, which the chart's geometry already
  fixes. Settings → General chooses Number / Glyph / Number + glyph / Abbreviation; glyphs are
  tinted by **tattva** (fire, earth, air, water). Hovering a house names the sign in full
- Yogas & Doshas surfaced as cards
- **Raja Yogas** card — the fundamental Kendra–Trikona raja yogas (a quadrant lord
  associated with a trine lord, each with a coarse strength) plus the named special
  types (Dharma-Karmadhipati, Vipareeta, Neecha-Bhanga) with descriptions
- Graha Drishti (aspects) card + optional aspect lines drawn on the Rasi chart
  (per-graha colour, **width/opacity weighted by aspect strength**); a show/hide
  toggle, and hover a graha to focus just its aspects
- **Arudha padas on the charts** — an optional "Show arudhas" toggle overlays the
  bhava arudhas (**AL** Arudha Lagna, **UL** Upapada, and A2–A11) as italic
  temple-gold markers in each rasi's cell, in both the North and South styles
  (off by default). Shown on the **Rasi (D1) and every divisional (varga) chart** —
  each chart's arudhas are computed on its own positions, so they differ per varga
- **AI reading of the arudhas** — with the overlay on, a panel below the chart
  reads the *projected* chart (how each area of life appears, as against how it
  is). You pick which arudhas to read from a chip row (**AL, UL, A10, A11**
  pre-ticked; any of the twelve can be toggled). The reading is grounded in more
  than the sign: each arudha's **lord and where it sits relative to its own
  arudha**, its **occupants**, the planets casting **rasi drishti**, plus the
  houses counted *from* AL and UL that classical practice actually reads —
  2nd/10th/11th/12th from AL and 2nd/7th from UL. Saved to the AI history and
  reopenable (the chips restore to the selection the reading was generated with)
- Panchanga (daily almanac) panel: tithi, vaara, nakshatra, yoga, karana plus
  sunrise/sunset and rahu kalam / yamaganda / gulika / abhijit / durmuhurtam,
  with a date picker and a Birth-place / Current-location (geolocation) toggle
- Store charts in MongoDB
- Display planetary positions

### 3. Horoscope & Predictions

- General horoscope predictions
- Health predictions
- Career predictions
- Current transits (Gochara)
- Optional AI enhancement with Qwen

### 4. Marriage Compatibility

- Ashtakoot (Guna Milan) score out of 36, computed from each person's Moon nakshatra+pada
- Per-koota breakdown with correct maxima (Varna 1, Vashya 2, Tara 3, Yoni 4, Graha Maitri 5,
  Gana 6, Bhakoot 7, Nadi 8) and a verdict
- Side-by-side kundalis (North/South) for visual comparison
- On-demand "Get detailed AI analysis" using the model picked in Ask AI Astrologer

### 5. Dhasa Periods

- **Vimsottari**: full drill-down tree Mahadasha → Antardasha (Bhukti) →
  Pratyantardasha → Sookshma. (Note: "Antardasha" and "Bhukti" are synonyms for
  level 2 — level 3 is the Pratyantardasha, matching Jagannatha Hora's naming.)
  Maha + Antardasha load up front; deeper levels lazy-load on expand (computed at full
  precision from the natal chart). The currently running period auto-expands the
  whole live chain and is highlighted.
- **Other systems** (17 total): Ashtottari, Yogini, Shodasottari, Dwadasottari,
  Panchottari, Shatabdika, Shashtihayani (Shashti-sama), Chaturaaseeti Sama,
  Dwisatpathi (graha) and Narayana, Kalachakra, Kendradhi-Rasi, Sudasa,
  Drig, Chara, Sthira, Trikona (raasi) — pick one from the "Other Dasha Systems" card
  for a maha-period table.
- **Applicable-dasha chips**: the engine's `applicability_check` tests the chart
  against each conditional system's classical precondition (Sun in the Lagna →
  Shashtihayani, 10th lord in the 10th → Chaturaaseeti Sama, …) and every system it
  can recommend is also one the picker can open — clicking a chip loads its periods.
  The AI has the same view via the `get_applicable_dashas` tool.
- All of these honour the **selected ayanamsa** — a nakshatra dasha's balance at
  birth is read off the Moon's sidereal longitude, so the ~1' between Lahiri and
  True Chitra moves every period by a couple of days over a 60-year cycle.
  Shashtihayani additionally routes past a PyJHora balance-at-birth bug (it
  divides by one nakshatra where its contiguous star-blocks require the whole
  block); corrected, it matches Jagannatha Hora to the day. See todo.md §52.1.
- **Sudarsana Chakra**: a collapsible section showing the three wheels read from the
  Lagna, Moon and Sun as ascendants for a chosen solar-return year (± year stepper),
  rendered as three Kundalis in the selected chart style.

### 6. Transits (Gochara)

- Current planetary positions for the present moment (anchored to the viewer's local
  time and timezone) or any chosen date/time, drawn over the natal chart
- Date + time pickers plus ±1 steppers (minute / hour / day / year) and a "Now" reset
  to walk the transit moment forwards or backwards
- House counted from both the natal Lagna and natal Moon, retrograde flagged
- Key upcoming sign-ingress dates for Jupiter and Saturn
- North / South Indian chart styles, respects the selected ayanamsa

### 6a. Ephemeris & Transit Calendar (`/ephemeris`)

- A **daily sidereal ephemeris**: for each day in the window every graha's sign,
  degree-in-sign, nakshatra and retrograde state (taken at local noon), rendered as a
  dense dates × grahas grid (`deg° SignAbbr`, ℞ for retrograde), with today's row
  highlighted
- A **sign-ingress calendar** — the sign changes inside the window (planet, from → to
  sign, date, ℞) as a card grid
- Selectable window span (30 / 60 / 92 days), prev/next paging and a "Today" jump;
  respects the selected ayanamsa

### 6b. Bhava / House-Cusp Chart (`/bhava`)

- A **Bhava Chalit / cuspal chart**: unlike the Rasi chart (where each sign _is_ a
  house), it divides the ecliptic by **house cusps**, so a graha near a sign boundary can
  fall in a different bhava than its sign
- **House systems**: Sripati (Porphyry — matches Jagannatha Hora's Bhava Chalit),
  Placidus, KP (Krishnamurti), and Equal (KN Rao)
- Renders the Bhava Chalit Kundali (North / South style) plus a **house-cusp table** —
  each bhava with its sign, cusp (bhava madhya as `d°mm' Sign`), and the grahas in it

### 6c. Full Report (print-ready PDF) (`/report`)

- A single **print-ready document** assembling the whole chart: masthead
  (name / born / place / ayanamsa / generated date), vitals (Lagna, Moon sign, birth
  nakshatra, Sun sign), Rasi (D1) + Navamsa (D9) charts, planetary-positions table,
  Vimsottari mahadasha timeline, yogas, doshas, and current transits
- **Print / Save as PDF** button (`window.print()`); a print stylesheet strips the app
  chrome and paginates cleanly so the browser's "Save as PDF" yields a tidy report
- Sources are fetched independently, so one unavailable section degrades gracefully
  instead of blanking the report

### 7. Sarvatobhadra Chakra (`/sarvatobhadra`)

- The authentic **9×9 "auspicious-in-every-direction" grid** — 28 nakshatras (incl.
  Abhijit), the 50 aksharas, 12 rasis, and the central tithi-group / weekday block —
  with **today's grahas mapped onto it** (each placed on both its nakshatra and rasi cell)
- Highlights the native's **sensitive points**: birth star (Janma Nakshatra), Moon sign,
  birth tithi group, birth weekday, plus an optional **name star** (pick the nakshatra of
  your name's first syllable from a dropdown)
- Flags **occupation** (a graha sitting on a sensitive cell) and **saamne/frontal vedha**
  (a graha facing it across the chakra), toned supportive (benefic) vs stressful (malefic),
  with a same-tithi-group / same-weekday coincidence read for the chosen day
- Date/time picker (defaults to now), respects the selected ayanamsa, and an on-demand
  **plain-language AI reading** of what to expect — uses the model picked in Ask AI Astrologer

### 8. Varshaphal / Annual Horoscope (`/varshaphal`)

- The **Tajaka annual (solar-return) chart** for a chosen year — cast for the moment
  the Sun returns to its natal longitude — with a **year stepper** (floored at the
  birth year) and North / South chart styles, exportable, respecting the selected ayanamsa
- **Muntha** (progressed point, advances one sign per year) and **year-lord (Varsheshwara)**
- **Sahams** (sensitive points, akin to Arabic parts): Punya/Vidya/Yasas/Mitra/Karma/Roga/
  Vivaha/Puthra — each as sign + degree + house
- Present **Tajaka yogas** (Ishkavala/Induvara + Ithasala/Eesarpha planet pairs)
- **Annual dasha** with a system picker — **Mudda (Varsha Vimsottari)** and **Patyayini**
  (planet-ruled) or **Varsha Narayana** (sign-ruled) — the year's sub-periods, current one highlighted
- On-demand **plain-language AI year-ahead reading** grounded in the above, using the model
  picked in Ask AI Astrologer
- Also published as a smart-lookup **tool** (`get_varshaphal`) so the AI astrologer can pull
  an annual snapshot when asked "how is _&lt;year&gt;_ for me?"
- **Solar only.** Its lunar counterpart — **Tithi Pravesha** — has its own page (`/tithi-pravesha`),
  which also carries the shorter rungs of the lunar ladder (day / fortnight / month). The two annual
  charts are read side by side; the page links across.

### 9. Almanac (`/almanac`)

- A location-driven almanac (not birth-chart bound) with a **shared location toggle**
  — birth place vs the device's current location (browser geolocation) — feeding four
  self-contained sections:
- **Today**: the daily **Panchanga** (five limbs + sunrise/sunset + Rahu Kalam/Yamaganda/
  Gulika/Abhijit/Durmuhurtam), reusing the existing panel under the shared location control
- **Planetary Hours (Hora)**: the day's 24 horas — 12 daytime (sunrise→sunset) + 12
  nighttime — each ruled by a graha starting with the weekday lord, tagged benefic (gold)
  or malefic (vermillion), with the running daytime hora highlighted; per-day date picker
- **Eclipses**: the next solar and lunar eclipses (global visibility) with type and the
  begin / maximum / end instants in the location's local time
- **Festivals & Vrathas**: a **date-range picker** + toggleable type chips (Ekadashi,
  Pradosham, Purnima, Amavasya, Sankashti, Vinayaka Chaturthi, Krishna Ashtami) listing
  every tithi-driven occurrence in the range, sorted by date
- **Conjunctions (Graha Yuddha)**: date-range scan of the five tara grahas (Mars, Mercury,
  Jupiter, Venus, Saturn — Sun/Moon/nodes excluded by tradition); each event shows the
  closest approach (min separation + date) and flags a **planetary war** when under 1°
- **Engine toggle & Hijri date**: the Today/Panchanga panel switches between the modern
  **Drik** engine and the classical **Surya-Siddhanta** ayanamsa, and shows the day's
  **Hijri (Islamic) date** alongside the five limbs
- **AI day-guide**: an optional plain-language reading of the day's panchanga + planetary
  hours (Abhijit/benefic-hora good windows, Rahu Kalam/Yamaganda/Gulika to avoid), using
  the model picked in Ask AI Astrologer
- Same current-DST timezone caveat as the rest of the almanac (fine for picking a day)

### 10. Pancha Pakshi Sastra (`/pancha-pakshi`)

- The **bird-cycle daily-timing system** (Tamil Siddha tradition): assigns you a
  **birth bird** from your birth star + paksha, then rates the day's windows by that
  bird's state — **Ruling / Eating / Walking / Sleeping / Dying** (strongest to weakest)
- A **colour-coded day timeline** — 10 main periods (5 from sunrise, 5 from sunset), each
  split into 5 sub-windows, tinted by strength with a legend, and the currently-running
  window outlined
- **Best** and **quieter** window summaries (top/bottom by effect) for "good time for X"
  planning, a date picker + "Today" reset
- Optional **plain-language AI day-guide** (uses the model picked in Ask AI Astrologer),
  and a smart-lookup **tool** (`get_pancha_pakshi`) so the AI can pull today's timing

### 11. Advanced Details (`/advanced`)

- **Ashtakavarga**: Bhinna (per-contributor) + Sarva (combined) bindu tables, with
  a Sarva heatmap (grand total 337)
- **Chart factors**: Arudha padas (A1–A12), Chara karakas (Jaimini), Special lagnas
  (Sree/Indu/Bhrigu Bindu/Pranapada/Kunda), Upagrahas (Gulika/Maandi + the 5 solar)
- **Shadbala**: six-fold planetary strength (sthana/kaala/dig/cheshta/naisargika/drik)
  with total rupa, required rupa, ratio and rank for Sun–Saturn
- **Graha Drishti (aspects)**: per-graha table of the houses & planets each graha
  aspects (incl. the Mars 4/8, Jupiter 5/9, Saturn 3/10 special aspects) plus rasi
  drishti, with the Parashari sphuta strength (0–100%)
- **Ayu / vitality indication**: a gentle, conditional longevity band — **Alpa** (short) /
  **Madhya** (medium) / **Purna** (long) — from the classical sign-pair method, with its
  contributing factors. Framed as one signal among many, never a death date or age
- Each section loads independently and respects the selected ayanamsa

### 12. Birth-Time Rectification (`/rectify`) — experimental

Three approaches, chosen with a mode toggle:

- **By rule (śuddhi)** — classical BV Raman checks: **Nakshatra Śuddhi** (default;
  self-serve — no extra input), **Lagna Śuddhi**, and **Janma Śuddhi** (needs a
  gender selection). Searches ±30 min and suggests the nearest time that satisfies
  the check
- **By life events** — you enter known dated events (marriage, children, career,
  illness, relocation, a parent's passing, …); the app scans candidate birth times
  and picks the one whose **Vimsottari dasha** (the maha/bhukti running at each
  event) plus **Jupiter/Saturn transits** best match each event's classical
  significators. Deterministic and **auditable** — a per-event table shows _why_
  each time fits (which period lord rules/occupies the event's houses, or is its
  karaka), with a rough **fit %** that strengthens as you add events
- **Conversational** — an AI astrologer **interviews you in chat**, asking about one
  dated life event at a time and extracting them as it goes; when it has enough it
  invites you to run the (same deterministic) rectification. The AI only _collects_
  the events — the engine still decides the time, so the result stays auditable
- Both show the **signed shift**, a **what-moved** before→after summary (Moon
  star/pada + rising sign), the **before/after charts side by side**, an optional
  **"why this time fits"** AI explanation (model from Ask AI Astrologer), and an
  **"Apply suggested time to this profile"** button (with confirm) so the corrected
  time flows into every other chart
- **Clearly framed as experimental** — a suggestion to verify against known life
  events, never an authoritative correction (PyJHora flags these methods experimental)

### 13. Sensitive Points (`/sensitive-points`)

- The chart's **supporting sensitive points**, on one page:
- **Special Points** — the full non-planetary table, matching the one Jagannatha Hora
  prints:
  - **Special lagnas** — the four time-based *kaala lagnas* (**Bhava**, **Hora**,
    **Ghati**, **Vighati**) plus **Sree**, **Indu**, **Bhrigu Bindu**, **Pranapada**,
    **Kunda** and **Varnada**. The three that carry real predictive rules are read as a
    trio: **Hora Lagna** for wealth and income (judge the 2nd and 11th from it),
    **Ghati Lagna** for power and authority (the 10th from it), **Bhava Lagna** for the
    body. Vighati Lagna moves a full sign every four minutes and is only meaningful with
    a second-accurate birth time
  - **Upagrahas** — the six **kaala-velas** (Gulika, Maandi, Kaala, Mrityu, Artha Prahara,
    Yama Ghantaka) and the five **solar** upagrahas (Dhuma, Vyatipata, Parivesha,
    Indrachapa, Upaketu)
  - **Varnada V1..V12** — the Varnada of each house. Four published derivations disagree;
    the method is a **Settings → Almanac** choice, defaulting to **Sanjay Rath**, the one
    that reproduces Jagannatha Hora exactly
  - Only the rule-bearing points (Bhava/Hora/Ghati/Varnada Lagna + Gulika) are fed to the
    AI as interpretable. The rest are shown as reference data, with the prompt explicitly
    told not to invent verdicts for them
- **Sphutas** — 14 sensitive longitudes derived from the natal chart (Tri/Chatur/Pancha/
  Prana/Deha/Mrityu/Sookshma Tri/Beeja/Kshetra/Tithi/Yoga/Rahu Tithi/Yogi/Avayogi), each
  as a sign + degree + house
- **Sahams** — the **36 natal Sahams** (Arabic-part-like points), each tied to a life
  theme (Punya/Vidya/Karma/Artha/Vivaha/Puthra/Rajya/Laabha…), placed by sign + house
- **Argala & Virodhargala** — per bhava, which houses receive strong planetary
  **intervention** (argala) vs **obstruction** (virodhargala), with a net verdict
- Optional **AI reading** (model from Ask AI Astrologer) + smart-lookup **tools**
  (`get_special_points`, `get_sphuta`, `get_sahams`, `get_argala`). The special lagnas are
  also **seeded into the chat context by default** (the `special_points` section chip)
- The **kaala-velas** additionally appear as *time* windows in the panchanga
  (`kaala_velas`) and annotate Muhurta candidates. They are a **caution, not an
  exclusion** — they are eighth-parts of the same day as Rahu Kalam / Yamaganda / Gulika
  Kalam and often coincide with them, so barring all of them would rule out most of every
  day

### 14. Vedic Clock & Retrograde (`/vedic-clock`)

- A **live Vedic day-clock** (SVG): a 60-ghati dial with a shaded day arc and a hand that
  ticks client-side (advancing the snapshot ghati by real elapsed seconds — timezone-
  independent), a digital **ghati:vighati** readout, the running **hora lord**, and the
  current panchanga limbs
- A **Vakra-gathi retrograde plot** (SVG): the geocentric apparent-path loop for a chosen
  planet (Mars/Mercury/Jupiter/Venus/Saturn), reimplemented server-side with numpy (no
  pyqtgraph)
- A **retrograde status table**: which grahas are retrograde now + the next station
  (direction-change) dates (Rahu/Ketu flagged perpetually retrograde)
- Optional **AI reading** of the current sky + smart-lookup **tools** (`get_vedic_clock`,
  `get_retrograde`)

### 15. Muhurta / Electional Astrology (`/muhurta`)

- Find **auspicious time windows** for an activity (general, marriage, travel, new business,
  housewarming, education, medical) over a date range, computed at your profile's place
- Each day is scored from its Panchanga — per-activity favourable **nakshatra**, **weekday**,
  **tithi** (Rikta/Amavasya penalised) and **yoga** (the nine inauspicious yogas penalised)
- Qualifying days yield concrete **windows**: the Abhijit muhurta + the benefic planetary **horas**
  (Moon/Mercury/Jupiter/Venus) that avoid Rahu-Kalam / Yamaganda / Gulika
- Ranked best-windows list + a day-by-day rating grid + an **AI rationale**, and a smart-lookup
  **tool** (`get_muhurta`) so the astrologer can answer "when is a good time to…"
- **Day sub-tools** (a "Day tools" section, pick any day): the **Choghadiya** table (8 day + 8
  night parts, each good/neutral/bad with a "now" marker), the **Panchaka** status, and — using
  your profile's natal Moon — your personal **Tarabala** (the tara from your birth star to the
  day's star) and **Chandrabala** (the transit Moon counted from your natal Moon)

### 16. Prashna / Horary (`/prashna`)

- Ask a question and cast a chart for the **exact moment you ask** — no birth data needed
- Uses your browser location (with permission; falls back to the profile place) at the current
  instant; renders the moment-chart via the shared North/South Kundali
- A Prashna-style **AI reading**: Ascendant = querent, Moon = mind/matter, house & lord = outcome,
  with a likely-yes / no / mixed answer and a sense of timing

### 17. Today — Daily Digest & Notifications (`/daily-digest`)

- A personalized **daily card**: today's Panchanga + your running Vimsottari dasha (flagging a
  Bhukti change within 30 days) + headline transits (Sade-Sati, Jupiter-from-Moon, retrogrades,
  next Jupiter/Saturn ingress), plus a warm **AI reading**
- **± day stepper** — look ahead or back a day at a time, like the Varshaphal year stepper. The whole
  card recomputes for the day you land on; **Refresh** becomes **Today** while you are off the present day
- **Solar / Lunar basis toggle** (defaults to Settings → pravesha basis). On **Lunar**, the day also
  carries its **Tithi Pravesha chart** — cast at the exact instant the running tithi opens — and that
  tithi's **compressed Tithi Ashtottari**, the same expandable tree the annual page shows, one rung down:
  maha periods of a few hours, drillable to sub-periods of minutes
- **Multiple profiles per digest**: pick a subset of your saved charts (or tick **All my profiles**
  to always include every one, plus any you add later). The delivered email/push is a **single
  combined message** with one section per chart. Each section leads with an AI **"how the day looks"**
  narrative (toggle **Include AI reading**) and falls back to the rule-based highlights when the LLM
  is unconfigured or unreachable, so a scheduled send never fails on the AI
- **Delivery channels** (opt-in, in **Settings → Notifications**): in-app always; **email** digest
  (via SMTP); **browser push** (Web Push / VAPID). A "send me a test now" button and per-user
  profiles/hour preferences
  - **Browser push requires a secure context.** Service Workers and the Push API only exist on
    HTTPS pages or `http://localhost` / `127.0.0.1`. Opened over a plain-HTTP LAN hostname (e.g.
    `http://host.lan:3000`) the toggle shows **"unavailable"** with a tooltip/hint explaining why —
    this is a browser rule, not a server problem (email + in-app digest still work). Serve the app
    over HTTPS, or use `localhost`, to enable push. The badge distinguishes three cases: server not
    configured (no VAPID keys), insecure page (needs HTTPS/localhost), or an unsupported browser.
- **Scheduler**: an opt-in in-process scheduler (`DIGEST_SCHEDULER_ENABLED`) delivers each user's
  digest once a day at **or after** their preferred local hour — using "at or after" (not only the
  exact hour) means a target hour missed because the process was down/restarting still delivers
  later the same day instead of skipping it. Multi-worker-safe via an atomic DB claim
  (`notifications.last_sent_date`). Or leave it off and point your own cron at
  `POST /api/notifications/digest/send` per user (both share `digest.send_digest_for_user`).
  **It defaults to `false`, and forgetting it is silent** — see
  [Troubleshooting → No digest emails or notifications](#no-digest-emails-or-notifications-arrive)

#### Fortnightly & Monthly readings (`/fortnightly-digest`, `/monthly-digest`)

The same idea over longer horizons, on **independent per-cadence opt-ins**. Every period reading is
anchored to a real **progressed (pravesha) chart** — not an invented window.

**Why these cadences, and not "weekly".** Vedic astrology has two pravesha ladders, and a 7-day week
sits on neither. This is also why Jagannatha Hora offers daily / fortnightly / monthly / annually:

| Cadence     | Solar basis (Tajaka)            | Lunar basis (tithi)             |
|-------------|---------------------------------|----------------------------------|
| Daily       | — *(no rung; sixty-hour ≈ 2.5d)* | **Tithi** (~0.98d)               |
| Fortnightly | — *(no rung)*                   | **Paksha Pravesha** (~14.8d)     |
| Monthly     | **Maasa Pravesha** (~30.4d)     | **Birth-tithi return** (~29.5d)  |
| Annual      | **Varshaphal** (~365d)          | **Tithi Pravesha** (~354d)       |

- **This Fortnight** (`/fortnightly-digest`) — the running **paksha** (Shukla or Krishna, ~14.8 days)
  with its **Paksha Pravesha** chart (Lagna / Muntha / Tajaka yogas), the running dasha, the transit
  events inside the window (all-graha **sign-ingresses** and **retrograde stations**), and an AI
  reading. Lunar-only — there is no solar fortnight.
- **This Month** (`/monthly-digest`) — the month on **either ladder**, switchable on the page:
  **Solar** = the **Maasa Pravesha** (Tajaka monthly solar return, the monthly analogue of Varshaphal);
  **Lunar** = the **birth-tithi return** (your natal tithi recurring). Either way **the "month" is that
  pravesha window (e.g. "Jun 15 → Jul 17"), not a calendar month.**
- **± window stepper** — both pages look ahead and back one **whole pravesha window** at a time (a
  paksha; a Maasa / lunar month on whichever basis is selected), and the reading — panchanga, dasha,
  in-window transit events, the pravesha chart and the AI text — recomputes for the window you land on.
  Because the windows are **not** a fixed length (13–16d for a paksha, 29–32d for a month), the step
  re-anchors off the *current window's own boundaries* (`end + 1d` / `start − 1d`) rather than adding a
  nominal span, which keeps the walk contiguous. **Refresh** becomes **Current** while you are away
  from the present window.
- **The digests are summaries, not chart views.** The progressed (pravesha) chart that backs each window —
  with its Muntha, its aspects and its compressed Tithi Ashtottari — lives on the
  **[Tithi Pravesha page](#tithi-pravesha--the-lunar-return-tithi-pravesha)**, which shows every rung of the
  lunar ladder; each digest links across rather than drawing the same chart twice.
- **Chart basis** — Settings → General has a global **Solar / Lunar** default (`praveshaBasis`), used for
  both the pages and the scheduled emails. Only **Monthly** offers a per-reading override, and only because
  there the basis picks the **window itself** (a solar Maasa Pravesha ~30.4d vs the lunar birth-tithi return
  ~29.5d) — a real choice about what the reading covers. The fortnight is lunar by definition (there is no
  solar fortnight), and a *day* is the same calendar day on either ladder, so neither offers the choice.
- **Muntha and the year-lord appear in annual readings only.** Both advance one sign per *year of age*, so
  they hold the same value for every day, fortnight and month of a given year — surfacing them in a
  fortnightly reading dresses a constant up as news. They are omitted from the sub-annual digests' highlights
  and from their AI prompts.
- **Per-cadence delivery**: **Settings → Notifications** has separate **daily / fortnightly / monthly**
  toggles. Daily takes an hour; monthly takes a day-of-month + hour; **fortnightly takes only an hour —
  the paksha boundary *is* the schedule**, so it fires once when each new lunar fortnight opens. The
  channels (email/push), profile selection ("all" or a subset), AI-reading toggle and chart basis are
  **shared** across cadences. Each cadence has its own atomic once-per-window claim
  (`last_sent_fortnightly` = the running paksha's start, `last_sent_monthly` = year-month); cron users
  can hit `POST /api/notifications/digest/send?cadence=fortnightly|monthly`.
- All readings are saved to the **unified AI history** (sources `fortnightly_digest` /
  `monthly_digest`) and exposed to Ask-Astrologer as `get_fortnightly_digest` / `get_monthly_digest`
  tools.

#### Tithi Pravesha — the lunar return (`/tithi-pravesha`)

The **lunar** counterpart of Varshaphal, on its own page. Where Varshaphal times a year from the Sun's
return to its natal longitude, this times a window from the **Moon–Sun relationship at birth** — and it is
read *alongside* the solar chart, not instead of it. (It used to be a Solar/Lunar toggle on `/varshaphal`;
it outgrew that once the shorter rungs arrived, so `/varshaphal` is now purely the solar Tajaka chart.)

**One page, four cadences.** A **Window** selector picks the rung of the lunar pravesha ladder, and a ±
stepper walks that rung one whole window at a time:

| Rung | Window | Cast when |
|---|---|---|
| **Day** | ~1 day | the running **tithi** opens |
| **Fortnight** | ~14.8 days | the current **paksha** opens |
| **Month** | ~29.5 days | your **birth tithi recurs** |
| **Year** | ~354d (384 in an adhika-masa year) | your **natal tithi *and* lunar month** recur — the **TP chart** proper |

Changing rung keeps your place on the timeline: if the window on screen is the one **running now**, the new
rung shows its *current* window too (the Year rung opened on your natal tithi, possibly months back — it
would be wrong to drop you into the tithi that year *began* with). Step off the present, and the window's
own start carries across to the rung you switch to.

Every rung is cast at the **exact pravesha instant** — solved to the moment the Moon−Sun elongation
regains its birth value, not rounded to the day (the page shows the instant). Each carries its window's
**Varsha Tithi Ashtottari**: a tithi-reckoned dasha for a tithi-reckoned chart, which is the pairing
Jagannatha Hora shows. The Tajaka annual dashas (Mudda/Patyayini/Narayana) are solar-return constructs and
are not offered here.

**Varsha Tithi Ashtottari** is the *compressed* form: the whole 108-unit Ashtottari cycle squeezed into the
pravesha window, exactly as Mudda compresses Vimsottari into the solar year. The compression is in
**Moon−Sun elongation, not in days** — the cycle is the elongation the window *sweeps*, each lord takes
`allotment/108` of it, and the running lord and its balance come from the chart's own elongation. Because
that is angular, it serves every rung: each is a clean fraction or multiple of a turn (a tithi sweeps
**12°**, a fortnight **180°**, a lunar month **360°**, a pravesha year **12 or 13 × 360°**), so a day is
tiled exactly as a year is. Rendered as an **expandable tree**, six levels deep (Maha → Antara →
Pratyantara → Sookshma → Prana → Deha), each level computed on expand — the full depth is 8⁶ ≈ 262k
periods, and the deepest last under a minute. Verified against Jagannatha Hora on two charts (an adhika and
an ordinary year). PyJHora ships no compressed Tithi Ashtottari, so it lives in
`backend/varsha_tithi_ashtottari.py`; the engine's own Tithi Ashtottari functions subdivide proportionally
in *days* and cannot be used.

**Muntha, the year-lord and the 8 Sahams appear on the Year rung only.** They are reckoned from the age in
*years*, so they carry no meaning for a single tithi — showing them on a day would be inventing precision.

**The Tajaka yogas are shown as what they are on a lunar chart: applying and separating aspects.** The
backend block is shared with Varshaphal, so the lunar return inherits Ishkavala / Induvara (planets confined
to kendras+panapharas, or to apoklimas) and Ithasala / Eesarpha (an aspect closing in, or pulling apart, by
degree). Those four judge the **geometry of the chart in front of them** — Tajika Neelakanthi itself applies
Ithasala in Prashna, on charts that are no one's annual return — so they hold on a TP chart. What does *not*
carry over is the year-reckoned apparatus: a Muntha advancing one sign per **solar** year sits oddly on a
~354-day window, and the TP lineage judges this chart with Parashari / Jaimini tools plus Tithi Ashtottari
anyway. So the page (and the AI prompt) calls the section **Applying & Separating Aspects**, and the API
key stays `tajaka_yogas` for the solar side's sake.
The AI reading is likewise scaled to the window it is cast for (a day gets near-term, concrete suggestions;
a year gets the year-ahead treatment), and it names the running compressed-dasha lord.

The same tree also appears on **Today**, **This Fortnight** and **This Month** on their lunar basis (see
the Daily / Period digests). Exposed to Ask-Astrologer as the `get_tithi_pravesha` tool.

### 18. Bhrigu / Nadi Yearly Markers (`/bhrigu-markers`)

- Two clearly-labelled traditional predictive devices for a birth chart:
  - **Nadi annual progression** — the one-sign-per-year advance from the natal Moon (age 0 = Moon
    sign); each year's marker sign + its lord + the natal planets sitting there (Bhrigu-Bindu and
    Moon-sign years flagged)
  - **Bhrigu Bindu activations** — the natal Bhrigu Bindu (the Rahu–Moon midpoint, with its sign /
    degree / house from the Lagna) plus the next **Jupiter & Saturn** transits into the Bhrigu-Bindu
    and Moon signs — the turning-point trigger dates
- Horizon picker (8 / 12 / 20 / 30 years) + an **AI reading**. Framed as an indicative aid, not a
  fated forecast

### 19. Remedies (`/remedies`)

- Traditional **remedial suggestions per weak / afflicted planet**. A planet is flagged when it is
  **debilitated**, **shadbala-deficient** (six-fold strength ratio < 1.0), or in a **dusthana**
  (6th/8th/12th from the Lagna)
- For each flagged graha: the classical **gemstone**, **beeja mantra** (+ japa count), presiding
  **deity**, **weekday**, **charity (daana)** and **colour**, plus a per-planet dignity & strength
  overview and an **AI reading**
- Clearly labelled **traditional guidance & devotional practice — not medical, legal or financial
  advice**; gemstones should be worn only after qualified consultation

### 20. Export & Share

- **Export** any chart as **PNG** or **PDF** (buttons on each chart card) — on Birth
  Chart, Compare, Transit and the shared view
- **Share** a chart as a **public, read-only link** (`/share/:token`) — no login needed
  to view; offers a "create a free account" CTA
- **Export / import birth profiles** (Profile selection screen) — download your saved
  profiles (name, DOB, time, place, coordinates, timezone) as a portable JSON file, and
  import that file back into any account. **Export** lets you **pick which profiles** to
  include (all pre-selected; toggle individually or select-all/none) — or export everything.
  Imports **skip duplicates** (same profile name + date + time of birth), so re-importing
  the same file is safe, and never override the account's current default profile
- **Default profile** — mark one saved profile as your default with the ⭐ toggle on its card
  (a "Default" badge shows which one). At most one profile is default at a time; clicking the
  star again clears it. The **daily digest** uses this default when no specific profile is
  chosen in notification preferences (falling back to your first saved profile if none is set).
  Editing a profile no longer changes which one is the default

### 21. LLM Integration (Optional)

- Enhanced predictions with a local Ollama model or any configured provider
- Contextual astrological interpretations
- Personalized analysis

### 22. AI History (`/history`)

- Reachable from a **dashboard tile** (desktop) and the **nav drawer** (mobile)
- **Every AI output is saved automatically** — the Ask/Transit chats _and_ every one-shot reading
  (Varshaphal, Muhurta, Prashna, Remedies, Bhrigu, Daily digest, Sensitive points, Vedic clock,
  Almanac, Pancha Pakshi, Sarvatobhadra, Compatibility, Compare, Rectification, Predictions)
- **Global History page** grouped by profile (+ a **"No profile"** bucket for location-driven tools),
  filterable by chat vs. reading; each item has a source badge, preview, and individual delete
- **Reopen = exact snapshot**: clicking an item returns to the tool that produced it, restores the
  inputs, and re-shows the saved reading verbatim (no re-computation)
- **Per-page "Recent readings"** control on each tool page for reopening a past reading in place
- Readings pile up (each generation is its own item); retention capped by `AI_HISTORY_MAX`
  (default 100, pruned on write). The Learn-the-Chart quiz keeps its own separate history

## AI Models Setup (Optional but Recommended)

### Option 1: Qwen 2.5 via Ollama (Recommended - Free & Local)

Install and run Qwen 2.5 locally using Ollama:

```bash
# 1. Install Ollama
curl https://ollama.ai/install.sh | sh

# 2. Start Ollama service
ollama serve

# 3. Pull Qwen 2.5 model
ollama pull qwen2.5

# 4. Update backend/.env
OLLAMA_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=qwen2.5:14b

# 5. Restart backend
```

**Advantages**: Free, private, no API costs, runs offline

### Option 2: Google Gemini

Use Google's Gemini AI (requires API key):

```bash
# 1. Get API key from: https://aistudio.google.com/app/apikey

# 2. Add to backend/.env
GEMINI_API_KEY=your-gemini-api-key-here

# 3. Restart backend
```

**Advantages**: Cloud-based, no local resources needed, free tier available

### Option 3: OpenAI ChatGPT

Use ChatGPT for AI predictions (requires API key):

```bash
# 1. Get API key from: https://platform.openai.com/api-keys

# 2. Add to backend/.env
OPENAI_API_KEY=your-openai-api-key-here

# 3. Restart backend
```

**Advantages**: Very high quality responses, well-tested

### Option 4: OpenRouter

One key, hundreds of hosted models from every major vendor (Anthropic, OpenAI,
Google, Meta, DeepSeek, …) behind the OpenAI schema:

```bash
# 1. Get API key from: https://openrouter.ai/keys

# 2. Add to backend/.env
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_DEFAULT_MODEL=google/gemini-2.5-flash   # optional

# 3. Restart backend
```

The model dropdown is populated live from OpenRouter's public catalogue (cached
for 15 minutes), so new models appear without a code change. Model ids are
`vendor/model`, e.g. `anthropic/claude-sonnet-4.5`. Agentic tool mode works —
pick a model that supports tool calling. Users can store their own OpenRouter key
under **Settings → API Keys** instead of using the server-wide one.

**Advantages**: One key and one bill for every vendor; easy model comparison;
free-tier models available (ids ending in `:free`)

### Switching Between AI Models

Users can select their preferred provider **and model** in the frontend:

- Go to **Settings → AI**
- Pick a provider (Ollama / OpenAI-compatible / Gemini / OpenAI / OpenRouter) and a specific model
- Optionally raise the **Max response length** if answers get cut off
- Each model will provide different perspectives on your chart

Model dropdowns are populated live from each vendor (Ollama's installed models,
the OpenAI-compatible server's `/models`, and — as soon as a key is present —
Gemini's ListModels, OpenAI's `/v1/models` and OpenRouter's catalogue), cached
for `LLM_MODEL_CACHE_TTL` seconds. A model released after this code was written
shows up on its own; no hardcoded list to update. Without a key, Gemini and
OpenAI fall back to a short static list so the picker is never empty.

### Per-user API keys (no shared `.env` key needed)

Instead of (or in addition to) the global `.env` keys above, each user can store
their own provider keys from the app: open **Settings → API Keys** and paste a
Gemini / OpenAI / OpenAI-compatible key. Keys are encrypted at rest, shown back only
masked, and used ahead of any global env key for that user's requests.

## API Endpoints

### Authentication

- `POST /api/auth/register` - Register new user (returns access + refresh token)
- `POST /api/auth/login` - Login user (`remember_me` picks the refresh-token TTL)
- `POST /api/auth/google` - Sign in / register with a Google Identity Services ID token (find-or-create by verified email, returns access + refresh token; 503 when `GOOGLE_CLIENT_ID` is unset)
- `POST /api/auth/refresh` - Exchange a refresh token for a fresh access token (rotates the refresh token)
- `POST /api/auth/logout` - Revoke a refresh token
- `PUT /api/auth/name` - Update the current user's display name (auth)
- `POST /api/auth/change-password` - Change password (auth; revokes other sessions, returns a fresh pair; for a password-less Google account it sets the first password without requiring a current one)
- `GET /api/user/profile` - Get current user profile

### Astrology

- `POST /api/astrology/birth-chart` - Calculate birth chart
- `GET /api/astrology/birth-chart/{chart_id}` - Retrieve stored chart
- `GET /api/astrology/vargas` - List supported divisional charts
- `POST /api/astrology/divisional-chart?varga=N` - Calculate a divisional (varga) chart
- `GET /api/astrology/ayanamsas` - List supported ayanamsa options
- `GET /api/astrology/panchanga?date=&latitude=&longitude=&timezone=` - Daily almanac (panchanga)
- `GET /api/astrology/almanac/hora?date=&place=&latitude=&longitude=&timezone=` - Planetary hours (24 horas, benefic/malefic, current flagged)
- `GET /api/astrology/almanac/eclipses?place=&latitude=&longitude=&timezone=&from_date=&count=` - Next N solar + lunar eclipses (local time)
- `GET /api/astrology/almanac/festivals?place=&latitude=&longitude=&timezone=&start=&end=&types=` - Tithi-driven festival / vratha dates in a range (`types` = comma-separated keys)
- `GET /api/astrology/almanac/conjunctions?place=&latitude=&longitude=&timezone=&start=&end=&max_sep=` - Planetary conjunctions (Graha Yuddha) among Mars–Saturn, with closest approach + war flag (<1°)
- `POST /api/astrology/horoscope` - Get horoscope predictions
- `POST /api/astrology/doshas` - Calculate doshas
- `POST /api/astrology/yogas` - Get yogas
- `POST /api/astrology/dhasa` - Calculate Vimsottari Dhasa periods (Maha + Bhukti)
- `POST /api/astrology/dhasa/children?lords=Venus,Saturn` - Lazily fetch the child
  periods (Pratyantardasha/Sookshma) of a Vimsottari node for the drill-down tree
- `GET /api/astrology/dasha-systems` - List the other (non-Vimsottari) dasha systems
- `POST /api/astrology/dasha-periods?dhasa_type=` - Maha-level periods for ashtottari/
  yogini/narayana/kalachakra
- `POST /api/astrology/transit?current_date=&current_time=&current_tz=&ayanamsa=` - Current transits (Gochara); `current_time`/`current_tz` anchor the snapshot to the viewer's present moment and timezone (default: their local now)
- `POST /api/astrology/sarvatobhadra?name_nakshatra=&current_date=&current_time=&current_tz=&ayanamsa=` - Sarvatobhadra Chakra (9×9 grid) with the current transits + occupation/vedha on the native's sensitive stars
- `POST /api/astrology/sarvatobhadra-analysis` - Plain-language AI reading of the Sarvatobhadra transit picture (`SarvatobhadraAnalysisRequest`; model-config aware, rate-limited)
- `POST /api/astrology/ashtakavarga?ayanamsa=` - Bhinna + Sarva Ashtakavarga tables
- `POST /api/astrology/chart-details?ayanamsa=` - Arudha padas, Chara karakas,
  Special lagnas, Upagrahas
- `POST /api/astrology/arudha-analysis` - AI reading of the bhava arudhas
  (`ArudhaAnalysisRequest`). `selected` is the list of arudha short codes to read
  (`["AL","UL","A10","A11"]` when omitted); unknown codes are filtered out, never
  interpolated into the prompt. Computes the enriched arudha payload internally —
  lords, occupants, rasi drishti and the houses derived from AL/UL
- `POST /api/astrology/planetary-nakshatras-analysis` - AI reading of the star each
  graha occupies (`NakshatraProfileAnalysisRequest`, the same body as the janma-star
  reading). Distinct from `nakshatra-profile-analysis`, which reads only the Moon's
  birth star
- `POST /api/astrology/shadbala?ayanamsa=` - Six-fold planetary strength (Shadbala)
- `POST /api/astrology/share` - Create a read-only share token for a chart
- `GET /api/astrology/share/{token}` - **Public** (no auth): recompute a shared chart
- `POST /api/astrology/compatibility` - Check marriage compatibility

### AI Q&A (New) 🆕

- `GET /api/llm/providers` - List AI providers, reachability, and available models (reflects per-user keys)
- `POST /api/astrology/ask` - Ask a question about the birth chart (multi-turn, rich context)
- `POST /api/astrology/ask/stream` - Same, streamed token-by-token over SSE
- `GET /api/ai/conversations?profile_id=` - List saved conversations for a profile
- `GET /api/ai/conversations/{id}` - Fetch a full conversation thread
- `DELETE /api/ai/conversations/{id}` - Delete a conversation
- `POST /api/ai/conversations/{id}/feedback` - Thumbs up/down on an answer
- `POST /api/astrology/predict` - Generate AI-powered predictions (general, health, career, relationships)
- `POST /api/astrology/compatibility-analysis` - Get detailed AI compatibility analysis
- `POST /api/astrology/compare-analysis` - Get a neutral AI comparison of two charts (not marriage matching)
- `GET /api/astrology/life-report/chapters` - The ordered Life Report chapter list
- `POST /api/astrology/life-report/start` - Start a server-side Life Report run (re-attaches to one already running for the profile)
- `GET /api/astrology/life-report/job?profile_id=` - Progress while generating, the finished report afterwards (the page polls this)
- `POST /api/astrology/life-report/cancel?job_id=` - Stop a running report

### Saved Profiles

- `POST /api/profiles/save` - Save a new birth profile
- `GET /api/profiles/list` - List all saved profiles for the current user
- `PUT /api/profiles/{profile_id}` - Update an existing birth profile
- `PUT /api/profiles/{profile_id}/default` - Mark a profile as the default (or clear it); at most one default per user
- `DELETE /api/profiles/{profile_id}` - Delete a saved profile
- `GET /api/profiles/export` - Export all of the current user's profiles as a portable JSON envelope
- `POST /api/profiles/import` - Bulk-import profiles from an exported file (skips duplicates)

### User

- `GET /api/user/charts` - Get user's saved charts
- `GET /api/user/api-keys` - Per-provider key status (masked; never the raw key)
- `PUT /api/user/api-keys/{provider}` - Store (encrypted) your API key for a provider
- `DELETE /api/user/api-keys/{provider}` - Remove a stored API key

### Health

- `GET /health` - Health check endpoint

## Frontend Pages

- `/login` - Login page
- `/register` - Registration page
- `/dashboard` - Main dashboard with feature overview
- `/birth-chart` - Birth chart calculator
- `/ask-astrologer` - **NEW**: Interactive AI chat for personalized astrology insights 🆕
- `/compatibility` - Marriage compatibility checker
- `/dhasa` - Dhasa periods: Vimsottari drill-down tree + other systems
- `/transit` - Transits (Gochara) over the natal chart
- `/almanac` - Almanac: planetary hours (hora), upcoming eclipses, tithi-driven festival / vratha dates, and planetary conjunctions (Graha Yuddha), with a birth-place vs current-location toggle
- `/sarvatobhadra` - Sarvatobhadra Chakra: today's transits on the 9×9 star grid + occupation/vedha on your sensitive stars, with a layman AI reading
- `/advanced` - Advanced details: Ashtakavarga, Arudha, Karakas, Special Lagnas, Upagrahas, Shadbala
- `/nakshatra` - Nakshatra profile: your **birth star** (janma-nakshatra) with its classical attributes and a 27-day tarabala strip, plus **every graha's own nakshatra** (star, pada, star lord, theme) — each with its own AI reading
- `/compare` - Compare two saved profiles side by side (charts, placements table + on-demand neutral AI comparison)
- `/share/:token` - **Public, read-only** shared chart view (no login required)
- `/predictions` - Horoscope and predictions generator
- `/settings` - **NEW**: Settings (single source of truth) — language, chart style, sign labels, ayanamsa, AI provider/model + **max response length**, API keys, almanac engine, and change password
- `/ai-tools` - AI Capabilities catalog (reached from Settings → AI)

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
- **tools.py**: the AI tool registry (43 tools) — also what `/api/v1/tools` and the
  MCP server publish

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
- **Mobile/PWA**: responsive rules in `src/styles/Responsive.css`; installable PWA via
  `public/manifest.json` + icons + `public/sw.js` (registered in production only; the
  service worker never caches `/api`)
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

## Production Deployment

### Before Going Live

1. **Change SECRET_KEY** in backend/.env to a secure random string
2. **Set CORS_ORIGINS** to your production domain
3. **Use production MongoDB**: Update MONGODB_URL
4. **Enable SSL/HTTPS**: Use reverse proxy (nginx, traefik)
5. **Point OLLAMA_URL** at your local model host (or leave the AI providers unset to run without local AI)
6. **Add environment variables** for production database credentials

### Docker Production Build

```bash
# Build production images
docker-compose -f docker-compose.yml build

# Push to registry and deploy
docker-compose up -d
```

### Using Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
    }
}
```

## Troubleshooting

### MongoDB Connection Issues

```bash
# Check if MongoDB is running
docker ps | grep mongodb

# View MongoDB logs
docker-compose logs mongodb
```

**Mongo container crashes on startup with `Illegal instruction`** — MongoDB 5.0+
requires a CPU with **AVX** support (SERVER-54407). Low-power hosts (many NAS boxes,
older Atom/Celeron chips) don't have it. Check with `grep -qw avx /proc/cpuinfo`; if
missing, pin the last AVX-free release, **`mongo:4.4`** (its healthcheck must use the
legacy `mongo` shell, not `mongosh`, which only exists in 5.0+).

**Auth fails against a bundled Mongo** — a literal `@` in `MONGO_PASSWORD` breaks the
`mongodb://user:pass@host` URL parsing. Avoid `@` (or percent-encode it as `%40`).

### Backend API Errors

```bash
# Check backend logs
docker-compose logs backend

# Ensure PyJHora is installed
pip list | grep PyJHora
```

### Frontend Not Loading

```bash
# Check if frontend is built
ls -la frontend/build/

# Check REACT_APP_API_URL configuration
cat frontend/.env
```

### Digest Emails & Notifications

#### No digest emails or notifications arrive

Almost always **`DIGEST_SCHEDULER_ENABLED` is unset or `false`**. It defaults to `false`
(`config.py`), so a deployment that never sets it has *never* delivered a scheduled digest —
on any cadence, on either channel. The failure is completely silent: `main.py`'s lifespan
calls `scheduler.start()`, which returns at the first line without starting the loop and
without logging anything. Nothing errors, so the logs look clean.

Two things make this easy to misdiagnose as a regression:

- Settings › **"Send test now"** keeps working. It calls
  `POST /api/notifications/digest/send` directly and shares only the *delivery* code
  (`digest.send_digest_for_user`), not the scheduler — so the feature looks configured.
- On the NAS, `web/.env` is the only env source and is `scp`'d over the remote copy on
  **every** deploy, so a value hand-edited on the NAS does not survive. Set it in your local
  `web/.env` (template: `.env.nas.example`).

Confirm by the boot log line — its **absence** is the tell. It prints **once, at startup**,
so you must replay the whole log; the default 100-line tail will have scrolled past it on a
container that has been up any length of time, and the grep comes back empty either way:

```bash
./dev.sh nas logs backend all | grep '\[scheduler\]'
# expect: [scheduler] daily-digest scheduler started (every 15 min)
```

If it *is* running but nothing arrives, the quiet log prefixes carry the reason — they read
as normal chatter on a skim: `[email:noop]` (no `SMTP_HOST` — mail is logged, not sent),
`[email:error]` (SMTP rejected/throttled the send; note Gmail app passwords cap around 500
recipients/day), `[push] pywebpush not installed`, `[digest] …`.

```bash
./dev.sh nas logs backend all | grep -E '\[scheduler\]|\[email:|\[push\]|\[digest\]'
```

> **If none of those prefixes ever appear, suspect the logs, not the code.** Every one of
> them is a bare `print()`, and Python block-buffers stdout whenever it isn't a TTY — which
> is exactly the case under `docker logs`. Uvicorn's own lines go through the `logging`
> module to stderr and appear immediately, so the container looks like it is logging fine
> while our diagnostics sit in an 8KB buffer for hours. `ENV PYTHONUNBUFFERED=1` in
> `web/backend/Dockerfile` is what prevents this; if you are running an image built before
> that was added, rebuild (`./dev.sh nas deploy backend`) before trusting an empty grep.

The decisive state is `notifications.last_sent_date` on the user's `user_settings` doc.
The scheduler *claims* the day atomically **before** sending (`scheduler.py`), so a recent
date with no email means the scheduler ran and delivery failed downstream — and that day is
burnt, since the claim is not rolled back. Missing or stale means it never ran. Mongo 4.4
ships the legacy `mongo` shell, not `mongosh`:

```bash
sudo docker exec jyotirai-mongodb mongo -u admin -p '<MONGO_PASSWORD>' \
  --authenticationDatabase admin jyotirai_db --quiet \
  --eval 'db.user_settings.find({},{user_id:1,notifications:1}).forEach(printjson)'
```

#### A profile's `notify_email` recipient never receives anything

By design. An address that isn't the account owner's is a third party, so it goes through
**double opt-in** (`digest_recipients.py`): saving the profile emails them an invite, and
until they click *Confirm* they sit in `pending` and are **skipped silently** at send time.
`unsubscribed` is permanent — re-saving the profile never re-invites, so a standing opt-out
is never overwritten.

This does not affect the owner's own copy, which always covers every profile. The
per-recipient state shows as a chip on the **Profiles** page (pending / confirmed /
unsubscribed) — note it is *not* surfaced on Settings › Notifications. To inspect it:

```bash
sudo docker exec jyotirai-mongodb mongo -u admin -p '<MONGO_PASSWORD>' \
  --authenticationDatabase admin jyotirai_db --quiet \
  --eval 'db.digest_recipients.find({},{email:1,status:1}).forEach(printjson)'
```

If the invite itself never arrived, check the `[email:` lines above — a failed invite is
caught and logged rather than failing the profile save.

### AI Provider / Ollama Issues

**"Ollama responded with status 307"** — a trailing slash on `OLLAMA_URL`
(`http://host:11434/`) produces a `//api/tags` double slash, which Ollama answers with a
307 redirect that the client won't follow. Drop the trailing slash. (The backend now
`rstrip("/")`s it defensively, but keep configured URLs clean.) A remote Ollama must also
bind `0.0.0.0` (`OLLAMA_HOST=0.0.0.0:11434`) to accept connections from the backend host,
and the model named in `OLLAMA_DEFAULT_MODEL` must be pulled (`ollama list`).

**Local AI shows "Off" / no model in Settings › System, or the AI model is blank after
a redeploy** — the System tab and the AI model field are driven by the server's live
Ollama status (`/health` probes `OLLAMA_URL` and reports `OLLAMA_DEFAULT_MODEL`), not by a
per-browser setting. If it reads "Off": the backend can't reach `OLLAMA_URL` — check the
endpoint is correct and reachable *from the backend container* (on the NAS, point it at the
host, e.g. `http://host.docker.internal:11434` or the LAN IP, not `localhost`). Once
reachable, the configured model shows automatically in Settings › AI as the "server
default" — you no longer need to type it in per browser, so it survives redeploys.

### Port Already in Use

```bash
# Change ports in docker-compose.yml or kill process
# On macOS/Linux:
lsof -i :3000  # Find process on port 3000
kill -9 <PID>

# On Windows:
netstat -ano | findstr :3000
taskkill /PID <PID> /F
```

## Future Enhancements

- [ ] Real-time chart visualization with SVG/Canvas
- [ ] Advanced prediction algorithms
- [ ] Multi-language support
- [ ] Mobile app with React Native
- [ ] Advanced Qwen integration for remedies
- [ ] Chart sharing and collaboration
- [ ] Subscription plans and analytics
- [ ] Integration with other astrology APIs

## Support and Contributing

For issues or contributions, please refer to the PyJHora fork:
https://github.com/kunwarmahen/PyJHora

## License

Check the JyotirAI license for terms of use.
