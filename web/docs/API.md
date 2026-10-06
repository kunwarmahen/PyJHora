# Jyotir AI — REST API

Interactive docs: `http://localhost:8000/docs` (FastAPI/Swagger) — always current. The token-authed public API (`/api/v1`) and the MCP server are described in [FEATURES.md → Public API & MCP server](FEATURES.md#public-api--mcp-server).

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
- `GET /api/ai/conversations?profile_id=&digests=` - List saved conversations for a profile; `digests=true` also folds in delivered digests
- `GET /api/ai/conversations/{id}` - Fetch a full conversation thread (a `dg_`-prefixed id returns a delivered digest in the same one-turn shape)
- `DELETE /api/ai/conversations/{id}` - Delete a conversation (or a delivered digest)
- `POST /api/ai/conversations/{id}/feedback` - Thumbs up/down on an answer
- `PUT /api/ai/conversations/{id}/outcome` - Record "did this land?" on a saved reading or delivered digest (`ReadingOutcomeRequest`: `verdict` = `happened`|`partly`|`not_yet`|`didnt`, `note`, `outcome_date`; an optional `journal` block writes the matching astro-journal entry **in the same request** and links it). Snapshots what it judged, and the Vimsottari period running on the outcome date. Re-recording replaces the verdict — one answer per reading
- `DELETE /api/ai/conversations/{id}/outcome` - Un-judge a reading (a linked journal entry is left alone — it is a record of a life, not of an opinion about a reading)
- `GET /api/ai/personal-context?profile_id=` - Counts of what the AI can read about this person **beyond their chart**: `journal_entries` and `settled_outcomes`. Backs the "your own record" line in the Ask page's Context sections card, so the capability is visible rather than silent
- `GET /api/ai/outcomes?profile_id=` - Every recorded verdict plus the track-record `summary` (counts per verdict, `hit_rate` over **settled** outcomes only — `not_yet` excluded, `partly` counts as half — and a per-tool breakdown). Rows whose reading has since been pruned by `AI_HISTORY_MAX` are still here: each carries its own snapshot
- `POST /api/astrology/predict` - Generate AI-powered predictions (general, health, career, relationships)
- `POST /api/astrology/compatibility-analysis` - Get detailed AI compatibility analysis
- `POST /api/astrology/compare-analysis` - Get a neutral AI comparison of two charts (not marriage matching)
- `GET /api/astrology/life-report/chapters` - The ordered Life Report chapter list
- `POST /api/astrology/life-report/start` - Start a server-side Life Report run (re-attaches to one already running for the profile)
- `GET /api/astrology/life-report/job?profile_id=` - Progress while generating, the finished report afterwards (the page polls this)
- `POST /api/astrology/life-report/cancel?job_id=` - Stop a running report
- `POST /api/astrology/muhurta?activity=&start_date=&end_date=&place=&latitude=&longitude=&timezone=&ayanamsa=` - Auspicious windows for an activity over a date range. **The body is an optional `BirthDetails`** (§71): send it and every day and window is also scored against that chart (Tara Bala, Chandra Bala, the running Vimsottari lords' gochara, per-window lagna shuddhi) and the result carries `personalized: true` + `personal_basis`; omit it and the answer is the location-only almanac. Coordinates are **required** — a muhurta without a place is refused, not answered for a default city
- `POST /api/astrology/muhurta/subtools` - Choghadiya + Panchaka for a day (`MuhurtaSubtoolsRequest`), plus personal Tarabala / Chandrabala when `birth_details` is sent. Honours `ayanamsa`: the janma star, the day's star and the Panchaka lagna are all sidereal (only the Choghadiya is exempt — it divides sunrise to sunset and knows nothing about the zodiac)
- `POST /api/astrology/muhurta-analysis` - AI rationale for the recommended windows (`MuhurtaAnalysisRequest`; names the personal reasons when `birth_details` is sent, and says the answer is the public almanac's when it is not)

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

### Admin (deployer only — 404 for non-admins)

- `GET /api/admin/me` - "Am I an admin?" — the one route every logged-in user may call
- `GET /api/admin/stats` - Deployment totals and per-collection record counts
- `GET /api/admin/users?q=&limit=` - All accounts with headline counts
- `GET /api/admin/users/{username}` - One account's detail
- `GET /api/admin/users/{username}/content/{kind}` - Break-glass content drill-down (needs `ADMIN_CONTENT_ACCESS`; audit-logged)
- `POST /api/admin/users/{username}/suspend` - Suspend / unsuspend an account
- `DELETE /api/admin/users/{username}` - Cascade-delete an account and all its data
- `GET /api/admin/activity?kinds=&username=&limit=` - The derived activity feed
- `GET /api/admin/audit?category=&action=&actor=&target=&since_days=&limit=` - Audit events + summary
- `GET /api/admin/config` - Runtime settings: effective values, deployed defaults, which are overridden
- `PUT /api/admin/config` - Update runtime settings (`clear: [...]` returns a field to its default)
- `GET /api/notifications/events?profile_id=&kinds=&refresh=` - The chart's forward calendar (§70)
- `POST /api/notifications/events/send` - Deliver any due event alerts now (claims real events)
- `GET /api/admin/claim-checks/summary?days=` - Claim-check rates, and the breakdown by kind and model
- `GET /api/admin/claim-checks?status=&kind=&source=&limit=` - The triage queue (redacted without `ADMIN_CONTENT_ACCESS`)
- `PATCH /api/admin/claim-checks/{id}` - Triage one row (`status`, `verdict`, `note`)

### Health

- `GET /health` - Health check endpoint. Also reports `engine_version` (PyJHora's
  own version string) and `default_ayanamsa`. Both answer questions that only
  arise after a deploy and otherwise need a shell inside the container: an engine
  upgrade moves real numbers, and the default ayanamsa sets every nakshatra
  dasha's balance at birth, so two pods on different values print different dasha
  dates while both report healthy. Settings › System shows the version.
