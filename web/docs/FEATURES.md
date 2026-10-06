# Jyotir AI — Features

What the app does, organised the way the app itself is: by **hub** (§79). Each hub
is one entry in the drawer and on the dashboard; its pages share a section strip.
Setup lives in [SETUP.md](SETUP.md), code layout in [ARCHITECTURE.md](ARCHITECTURE.md),
endpoints in [API.md](API.md).

- [Overview](#overview)
- [Cross-cutting features](#cross-cutting-features) — the AI, view modes, the dashboard, settings, help, digests
- Feature reference by hub: [My Chart](#my-chart) · [Your Periods](#your-periods) · [Other Systems](#other-systems) · [Reports](#reports) · [Dasha & Timeline](#dasha--timeline) · [Transits](#transits) · [Sky & Panchanga](#sky--panchanga) · [Relationships](#relationships) · [My Notebook](#my-notebook) · [Standalone tools](#standalone-tools) · [Account & platform](#account--platform)

## Overview

This is a full-stack web application for Vedic Astrology calculations using PyJHora library. It includes:

- **Backend**: FastAPI with MongoDB for data persistence and JWT authentication
- **Frontend**: React SPA with responsive UI
- **Authentication**: User registration and login with JWT tokens
- **Features**: Birth Chart (Rasi D1 + Navamsa D9), divisional charts D1–D60, Panchanga,
  Yogas/Doshas, dedicated Raja Yogas, Graha Drishti (aspects, with strength-weighted lines
  on the chart), Vimsottari Dhasa (+ 18 other dasha systems — including the **Sudarshana Chakra
  dasha**, a 12-year wheel read from the Lagna, Moon and Sun at once — & Sudarsana Chakra charts),
  Transits (Gochara — each transiting graha **weighted by its Ashtakavarga bindus** for the
  sign it occupies, with a supported/neutral/rough chip, and counted from the **bhava
  arudhas** as well as the Lagna and Moon: AL/UL columns and labels on the chart, all
  twelve padas in a grid, steppers from a minute to a year, and a **nakshatra-gochara**
  layer reading the same transits one level finer — which of the 27 stars each graha is
  crossing, the dates it entered and leaves, and that star's **tarabala** counted from
  your birth star),
  an Ephemeris & transit calendar (daily sidereal grid + sign-ingress dates),
  a Bhava / house-cusp chart (Sripati / Placidus / KP / Equal),
  a print-ready Full Report (Save-as-PDF),
  Varshaphal / Tajaka annual horoscope (with year-ahead AI reading),
  an Almanac (planetary hours, eclipses, festival/vratha dates, a Drik ⇄ Surya-Siddhanta
  engine toggle, the Hijri date, and an AI day-guide),
  Pancha Pakshi Sastra (bird-cycle day timing, with AI day-guide),
  Muhurta / electional astrology (auspicious windows for an activity, **scored against your own
  chart** — Tara Bala, Chandra Bala, your running dasha lords and per-window lagna shuddhi (§71) —
  with AI rationale, plus day sub-tools: Choghadiya, Panchaka, Tarabala & Chandrabala),
  Prashna / horary (a chart for the moment you ask, with a horary AI reading),
  personalized daily / fortnightly / monthly readings, each anchored to a real progressed (pravesha)
  chart on the solar (Tajaka) or lunar (tithi) ladder — "Today", "This Fortnight" (Paksha Pravesha) and
  "This Month" (Maasa Pravesha or the birth-tithi return) — plus Tithi Pravesha, the annual lunar
  return; all with AI readings and per-cadence email & push notifications,
  a Life Timeline (`/timeline`) — one clickable SVG axis around today with the Vimsottari
  maha/bhukti bands, the Sade Sati / Ashtama / Kantaka Saturn phases, the Jupiter/Saturn/Rahu
  ingresses and the eclipses (flagged on natal nakshatras); click any point for a "what's
  running" panel + on-demand AI reading, and a **"What's coming"** tab — the same layers read as a
  dated list of what *changes* (period changes, Saturn phases beginning and ending, sign changes,
  retrograde stations, eclipses), each counted from your own Lagna, Moon and Arudha Lagna, with
  optional **event alerts** by email/push when one arrives (§70),
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
  a **Chart of the Moment** (the current sky as a chart in its own right, not overlaid on a
  birth chart — a full `/now` page with panchanga, hora & AI reading, plus a Dashboard
  mini-kundali widget; both Everything-mode only. It is cast for your Settings → Location,
  falling back to your birth place, and always names which it used, since a four-minute
  shift of meridian is a whole degree of ascendant. The AI can fetch it from any page via
  the `get_now_chart` tool),
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

> The build log and open work are in [`../todo.md`](../todo.md).

## Using the AI astrologer

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

# Cross-cutting features

### Ask AI Astrologer

- **Interactive Chat Interface**: Multi-turn conversation with memory about your birth chart
- **Provider & model selection**: Ollama (local, auto-detected models), any OpenAI-compatible
  local server (LM Studio / llama.cpp / vLLM), Google Gemini, or OpenAI — pick the exact model.
  Chosen in the new **Settings** page (see below); the Ask page shows the active model with a
  "Change in Settings" link. A **Max response length** slider (also in Settings, 512–32768 tokens)
  caps how many tokens a model may *generate* per answer — the output budget, not the context
  window, which the app never touches and leaves at the provider's own setting. Its **Auto**
  default sends no cap at all, so the model stops when it is done. The setting applies across
  **every** AI feature (Ask, predictions, compatibility, quiz, and the per-page plain-language
  analyses), not just the Ask page.
- **Classical citations** (§5.12 / §73): a reading can quote the shastra rather than assert on
  its own authority. `backend/rag_corpus/` ships **315 passages** — **246 real verses of the
  *Brihat Jataka*** (N. Chidambaram Iyer, 1885, public domain) with genuine chapter/verse
  references, plus 69 general principles labelled *"General principle"* so a paraphrase is never
  dressed up as a shloka. Retrieval is local (Ollama embeddings, no new cloud service) and the
  AI reaches it through the `search_classical_texts` tool. Add your own out-of-copyright editions
  with `rag_corpus/import_text.py`; if the corpus or Ollama is unavailable, readings simply carry
  no citations. See `backend/rag_corpus/README.md`.
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
  [`docs/AI_TOOL_CALLING_DESIGN.md`](../docs/AI_TOOL_CALLING_DESIGN.md)
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
- **AI activity** (§77): answers are written by server-side jobs that survive a dropped
  connection, a locked phone or a closed tab. A pill in every page header shows what the AI is
  writing for you (and History lists it under **"In progress"**); when it's done the pill says so
  and opens the saved answer on its own page.
  With browser push on, an answer that finishes after you've left also sends a **"your answer is
  ready"** notification that opens it (Settings → Notifications, on by default).
- **"Did this land?"**: every saved reading takes an **outcome** — it happened / partly / too early
  to tell / it didn't — with what actually came about in your own words, optionally logged to your
  astro-journal in the same step. Settled verdicts are fed back into later readings, so the AI can
  see which of your chart's indications you confirmed and which you told it were wrong. The History
  page tallies them into a **track record** (hit rate over settled outcomes; "too early to tell" is
  excluded, a partial counts as half). Verdicts outlive the readings they judge, so the tally is not
  reset when older readings age out. The Ask page's **Context sections** card carries a "your own
  record" line showing how many outcomes and journal entries the AI can see for this profile —
  outcomes go up with the chart in **both** answer modes, journal entries need **Smart lookup**
  (Full context sends no tools). Neither is a section of the chart, so neither has a toggle row
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
  details" disclosure: the Birth Chart's divisional charts + Graha Drishti, Dasha's other 18 systems
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
  Dashboard tiles and the mode filter all render from. Add the route there (with a `tier`, a
  `group` and, if it belongs with others, a `hub`) and it appears everywhere; there is no second list to update.

### How the Dashboard is laid out — sections and hubs (§79)

Two levels. **Sections** put things in the order a reading actually proceeds; inside them,
**hubs** collapse pages that are one idea into a single tile and drawer row:

| Section | Entries (hubs in bold, members in brackets) |
| --- | --- |
| **Start here** | **My Chart** (Birth Chart · Bhava Chart · Nakshatra Profile · Planetary Strength · Chart Deep-Dive · Sensitive Points) · Ask AI Astrologer · **Your Periods** (Today · This Fortnight · This Month · Varshaphal · Tithi Pravesha) |
| **Read the chart** | **Other Systems** (Jaimini · KP · Nadi Karakas · Bhrigu Markers · Chakras) · **Reports** (Life Report · Full Report) |
| **Timing** | **Dasha & Timeline** (Dasha Periods · Life Timeline) · **Transits** (Transits · Gochara-phala · Sade Sati · Ephemeris) |
| **Calendar & muhurta** | **Sky & Panchanga** (Almanac · Vedic Clock · Pancha Pakshi · Chart of the Moment) · Muhurta |
| **Relationships** | **Relationships** (Compatibility · Compare Charts) |
| **Remedies & practice** | Remedies · Prashna · **My Notebook** (AI History · Astro-Journal) · Learn the Chart · Birth-Time Rectification |

- **Every page keeps its own URL.** A hub is a shared entry plus a section strip (`components/HubNav.js`,
  mounted by `PageHeader`) listing its members; nothing redirects, so readings, digests, notifications
  and bookmarks that link to `/gochara` or `/varshaphal` still land. The strip is route links with
  `aria-current`, not a second tablist, so it never fights a page's own `?tab=` bar.
- **One registry.** Sections are `FEATURE_GROUPS`, hubs are `HUBS` in `config/features.js`, and a page
  joins a hub with `hub: "<key>"` on its own entry — members are derived, there is no member list to
  drift. `navEntries(uiMode)` is what the drawer and the dashboard render.
- **Browsing shows hubs, searching shows pages**: typing "gochara" lands on Gochara-phala itself.
- **Essentials**: a hub appears if any member is `simple` and opens the first such member (Your Periods →
  Today); the strip hides advanced members unless you are on one. Empty sections disappear.
- Labels: `nav.hubs.<key>` (drawer + strip) and `dashboard.hubs.<key>.{title,description}` (tile).
  `features.test.js` → "hubs" pins that every hub has ≥2 members, labels, and that every visible page is
  reachable from the drawer or a strip.

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

It is no longer only the digest's concern. `deps.viewer_tz` resolves the offset — request value,
then the stored zone, then the birth offset — and `deps.viewer_place` the full place, and between
them they decide what "today" means everywhere: the transit and gochara snapshots, the running
dasha, the date every AI reading is told it is, and the sunrise a Pancha Pakshi day is divided
from. Before that, each of those quietly used the *server's* clock or the *birth* place, which is
how one evening in Cary produced three different wrong days (§57).

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
  AI endpoints; no account/profile mutation is exposed. Two tools in the catalog read **your own
  recorded data** rather than the ephemeris — `get_journal_entries` and `get_reading_outcomes` —
  scoped to the token's owner, and explicit when you have nothing recorded rather than answering
  with an empty list.
- **Personal API tokens**: create/revoke long-lived tokens under **Settings → API access**
  (shown once, stored hashed, prefixed `jyd_`). Authenticate with `Authorization: Bearer jyd_…`.
- **MCP server** (`web/mcp/`): a standalone [Model Context Protocol](https://modelcontextprotocol.io)
  server that wraps the same catalog so **Claude Desktop** (or any MCP client) can compute charts,
  dashas, panchanga, transits, KP, Jaimini, muhurta and more against your profiles — over stdio
  or streamable-HTTP. It talks to the public API with your token; setup is in
  [`web/mcp/README.md`](../mcp/README.md).

#### What a position looks like (and what changed in Sept 2026)

Every graha, lagna and sensitive point comes back in one shape, and the two
sign-ish numbers mean different things:

| key | meaning |
| --- | --- |
| `sign_name` | the sign, spelled out — `"Cancer"` |
| `house` | the **bhava**, counted whole-sign from *that chart's own* lagna (a varga's houses come off the varga's lagna, not the D1's) |
| `sign_num` | the **1-based sign** (Aries 1 … Pisces 12) — a drawing coordinate for a Kundali cell, not a placement |
| `degrees` | degrees within the sign |

A transit carries no plain `house`: it is read from several references at once,
so each is named — `house_from_lagna`, `house_from_moon`, `house_from_al`,
`house_from_ul`.

**Breaking change (§63/§65, Sept 2026)** for anything parsing these payloads:

- `house` used to be the sign cell (the 1-based sign) on chart payloads. It is
  now the bhava. If you were reading it as a sign, read `sign_num`.
- `rasi` — the 0-based twin — is **gone** from chart payloads. `sign_num` is
  `rasi + 1`.
- Tool results served through `/api/v1` and MCP are sanitized for LLM use: the
  drawing coordinates (`sign_num`, `rasi`, and bare integer `sign` fields that sit
  beside a `*_name`) are stripped, because a coordinate reads as a house number to
  a model and outranks the truth. Read `sign_name` and `house` there. The REST
  chart endpoints the web UI uses keep `sign_num`, since they have a chart to draw.

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

# Feature reference by hub

## My Chart

Also here: **Nakshatra Profile** (`/nakshatra`) — your birth star with its classical attributes and a 27-day tarabala strip, plus every graha's own nakshatra; **Planetary Strength** (`/strength`) — Shadbala, Bhava Bala and Vimsopaka Bala as ranked bars, with an AI reading.

### Birth Chart Calculator

- Calculate Rasi (D1) and Navamsa (D9) charts from birth details
- Divisional (varga) charts D1–D60 with a picker
- North / South Indian chart styles, selectable ayanamsa
- **Sign labels** follow the classical convention — the numeral in a house is the **rasi**
  number (1 = Aries … 12 = Pisces; `sign_num` in the API), not the house number, which the
  chart's geometry already fixes. Settings → General chooses Number / Glyph / Number + glyph / Abbreviation; glyphs are
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

### Bhava / House-Cusp Chart (`/bhava`)

- A **Bhava Chalit / cuspal chart**: unlike the Rasi chart (where each sign _is_ a
  house), it divides the ecliptic by **house cusps**, so a graha near a sign boundary can
  fall in a different bhava than its sign
- **House systems**: Sripati (Porphyry — matches Jagannatha Hora's Bhava Chalit),
  Placidus, KP (Krishnamurti), and Equal (KN Rao)
- Renders the Bhava Chalit Kundali (North / South style) plus a **house-cusp table** —
  each bhava with its sign, cusp (bhava madhya as `d°mm' Sign`), and the grahas in it

### Advanced Details (`/advanced`)

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

### Sensitive Points (`/sensitive-points`)

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

## Your Periods

Also here: **This Fortnight** (`/fortnightly-digest`, Paksha Pravesha) and **This Month** (`/monthly-digest`, Maasa Pravesha or the birth-tithi return), and **Tithi Pravesha** (`/tithi-pravesha`) — the lunar-return year chart with its compressed Tithi Ashtottari.

### Today — Daily Digest & Notifications (`/daily-digest`)

- A personalized **daily card**: today's Panchanga + your running Vimsottari dasha (flagging a
  Bhukti change within 30 days) + headline transits (Sade-Sati, Jupiter-from-Moon, retrogrades,
  next Jupiter/Saturn ingress), plus an **AI reading**
- **"Working in your favour" and "Take care with"** — the two sides of the day, each in its own
  card and its own section of the email. Sources: **Tara Bala** (the count from your birth star to
  today's star — the tradition's own "is today good *for me*", and the one signal that differs every
  single day), **Chandra Bala** (the Moon's sign from your natal Moon, turning every ~2¼ days),
  the **Sarvatobhadra chakra** (a graha sitting on or facing your birth star / Moon sign),
  classical gochara verdicts measured from your birth Moon (`Favourable` / `Unfavourable`, or a
  favourable one cancelled by **vedha**), **Ashtama** / **Ardhashtama Sani**, the **Vishti (Bhadra)**
  karana, and the periods traditionally kept clear for anything newly begun (Rahu Kalam, Yamaganda,
  Gulika). Every entry is tagged **today** (what is different about this morning) or **ongoing**
  (a backdrop lasting weeks or months). That tag is what stops a 2½-year Saturn transit being
  announced as fresh news every day — at most four entries per side, of which at most two may be
  backdrop, so the day-variable signal always gets through.
  These are independent measures and **may disagree** — a day can be excellently starred and still
  carry a hard transit. The AI is explicitly told not to average them into "a mixed day" but to name
  each and say which to act on
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
- **Narrative style** (§67): two prompts write the reading, chosen by
  `DIGEST_NARRATIVE_STYLE` or the **Admin › Settings** picker (runtime, no redeploy).
  **Focused** (the default) leads on whichever signal is genuinely strongest that day,
  reads the natal chart — the house the running dasha lord occupies and the houses it
  rules — so it can name *which part of a life* the day touches, rotates how it opens
  from one day to the next, and is given the last note it sent so it does not re-argue
  it. Its email drops the bullet lists it was written from and keeps a short **At a
  glance** of what a 220-word note cannot carry (clock times, dates, the next ingress).
  **Classic** is the original prompt, kept so a deployment can be put back with one
  click. A section whose narrative fails falls back to the full bullet lists either way.
- **Scheduler**: an opt-in in-process scheduler (`DIGEST_SCHEDULER_ENABLED`, or the runtime
  switch in **Admin › Settings**) delivers each user's
  digest once a day at **or after** their preferred local hour — using "at or after" (not only the
  exact hour) means a target hour missed because the process was down/restarting still delivers
  later the same day instead of skipping it. Multi-worker-safe via an atomic DB claim
  (`notifications.last_sent_date`). Or leave it off and point your own cron at
  `POST /api/notifications/digest/send` per user (both share `digest.send_digest_for_user`).
  **It defaults to `false`, and forgetting it is silent** — see
  [Troubleshooting → No digest emails or notifications](#no-digest-emails-or-notifications-arrive)

#### Fortnightly & Monthly readings (`/fortnightly-digest`, `/monthly-digest`)

Both carry the same two-sided treatment as the daily card, plus the one thing a long-window
reading can offer that a transit list cannot: **dated Tara Bala days**. Every day of the window is
charted from your birth star, and the well-starred days and the ones to keep light are named with
their dates ("Tue 4 Aug, Thu 6 Aug"). Days already past are dropped — a Maasa Pravesha month opens
on the solar ingress, which can be weeks before you read the digest.

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

### Varshaphal / Annual Horoscope (`/varshaphal`)

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

## Other Systems

Also here: **Jaimini** (`/jaimini`) — Chara Karakas, Karakamsa/Swamsa with rasi drishti, argala; **KP System** (`/kp`) — planet and cuspal sub-lords, four-fold significators, ruling planets, KP horary 1–249; **Nadi Karakas** (`/nadi`) — the chart read through planetary significators, events timed by their transits.

### Sarvatobhadra Chakra (`/chakras`)

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

### Bhrigu / Nadi Yearly Markers (`/bhrigu-markers`)

- Two clearly-labelled traditional predictive devices for a birth chart:
  - **Nadi annual progression** — the one-sign-per-year advance from the natal Moon (age 0 = Moon
    sign); each year's marker sign + its lord + the natal planets sitting there (Bhrigu-Bindu and
    Moon-sign years flagged)
  - **Bhrigu Bindu activations** — the natal Bhrigu Bindu (the Rahu–Moon midpoint, with its sign /
    degree / house from the Lagna) plus the next **Jupiter & Saturn** transits into the Bhrigu-Bindu
    and Moon signs — the turning-point trigger dates
- Horizon picker (8 / 12 / 20 / 30 years) + an **AI reading**. Framed as an indicative aid, not a
  fated forecast

## Reports

Also here: **Life Report** (`/life-report`) — see *Life Report* under Cross-cutting features above.

### Horoscope & Predictions

- General horoscope predictions
- Health predictions
- Career predictions
- Current transits (Gochara)
- Optional AI enhancement with Qwen

### Full Report (print-ready PDF) (`/report`)

- A single **print-ready document** assembling the whole chart: masthead
  (name / born / place / ayanamsa / generated date), vitals (Lagna, Moon sign, birth
  nakshatra, Sun sign), Rasi (D1) + Navamsa (D9) charts, planetary-positions table,
  Vimsottari mahadasha timeline, yogas, doshas, and current transits
- **Print / Save as PDF** button (`window.print()`); a print stylesheet strips the app
  chrome and paginates cleanly so the browser's "Save as PDF" yields a tidy report
- Sources are fetched independently, so one unavailable section degrades gracefully
  instead of blanking the report

## Dasha & Timeline

Also here: **Life Timeline** (`/timeline`) — one clickable axis with the Vimsottari bands, Saturn phases, ingresses and eclipses, and a **What's coming** tab with optional event alerts (§70).

### Dhasa Periods

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
  True Chitra moves every period by a couple of days over a 60-year cycle. This
  line described the intent rather than the behaviour until 2026-09: `get_dashas`
  and `get_dasha_children` took no ayanamsa argument at all, so the Vimsottari
  page always answered in the default and changing the setting did nothing
  visible. Now wired through and guarded by a test that a new chart-derived
  compute must accept an ayanamsa *and* that the value changes the answer.
- **Vimsottari agrees with Jagannatha Hora at every level**, verified against a
  JHora printout for the reference chart: all nine maha boundaries to ~25-40 s
  across 120 years, and the Antardasha / Pratyantardasha / Sookshma chain to
  under a second. Two things are load-bearing for that. The dasha year is the
  **true sidereal** year (`DHASA_YEAR_DURATION.JHORA_DEFAULT`) — a mean year is
  ~16 h out on every maha boundary. And sub-periods divide the parent's **solar
  arc**, not its elapsed time: a period of N dasha-years is exactly N x 360 deg
  of the Sun's sidereal travel, and since the Sun runs fastest near January
  perihelion, equal arcs are deliberately *unequal* spans of time. PyJHora's own
  `vimsottari_immediate_children` sizes children from elapsed time instead, which
  hands each one 2.07% too much and leaves the last 13.8% short. See todo.md §62.
- Shashtihayani additionally routes past a PyJHora balance-at-birth bug (it
  divides by one nakshatra where its contiguous star-blocks require the whole
  block); corrected, it matches Jagannatha Hora to the day. See todo.md §52.1.
- **Sudarsana Chakra**: a collapsible section showing the three wheels read from the
  Lagna, Moon and Sun as ascendants for a chosen solar-return year (± year stepper),
  rendered as three Kundalis in the selected chart style.

## Transits

Also here: **Gochara-phala** (`/gochara`) — Moon-referenced transit results with vedha; **Sade Sati** (`/sade-sati`) — Saturn's 7½-year cycles over the natal Moon with phases, Ashtama and Kantaka Shani.

### Transits (Gochara)

- Current planetary positions for the present moment (anchored to the viewer's local
  time and timezone) or any chosen date/time, drawn over the natal chart
- Date + time pickers plus ±1 steppers (minute / hour / day / year) and a "Now" reset
  to walk the transit moment forwards or backwards
- House counted from both the natal Lagna and natal Moon, retrograde flagged
- Key upcoming sign-ingress dates for Jupiter and Saturn
- North / South Indian chart styles, respects the selected ayanamsa

**Nakshatra gochara** (same page, below the transit table) reads those transits at star
level rather than sign level — a sign holds a slow graha for years, a nakshatra for
months, so this is where a transit becomes timing:

- **Dated star windows** for every graha but the Moon: when it entered the star it is in,
  when it leaves, and the stars ahead — including the ones it turns *back* into while
  retrograde, which are flagged as re-entries rather than shown as ordinary ingresses
- **Tarabala** — the transit star counted from your own birth star, giving one of the nine
  Taras (Sampat, Vipat, Kshema … Vadha). This is the column added to the transit table, and
  it is the only one on that table that is about you rather than about the sky
- Each graha's house from Lagna and Moon, the houses it owns, whether it or the star's lord
  is your running dasha lord, and whether it is crossing a star a natal graha occupies
- A computed **supportive / mixed / pressured** verdict, from tarabala and the graha's own
  nature — and *only* those. Each star's deity, symbol and theme are shown too, labelled
  **Imagery (not a rule)**: the classical texts give no table of results for "graha X in
  star Y", so nothing here pretends one exists
- An AI reading of the star windows, and a `get_nakshatra_gochara` tool so Ask can answer
  "how long does this Saturn transit last" with dates

### Ephemeris & Transit Calendar (`/ephemeris`)

- A **daily sidereal ephemeris**: for each day in the window every graha's sign,
  degree-in-sign, nakshatra and retrograde state (taken at local noon), rendered as a
  dense dates × grahas grid (`deg° SignAbbr`, ℞ for retrograde), with today's row
  highlighted
- A **sign-ingress calendar** — the sign changes inside the window (planet, from → to
  sign, date, ℞) as a card grid
- Selectable window span (30 / 60 / 92 days), prev/next paging and a "Today" jump;
  respects the selected ayanamsa

## Sky & Panchanga

Also here: **Chart of the Moment** (`/now`) — the current sky cast as a chart for your Settings → Location.

### Almanac (`/almanac`)

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

### Pancha Pakshi Sastra (`/pancha-pakshi`)

- The **bird-cycle daily-timing system** (Tamil Siddha tradition): assigns you a
  **birth bird** from your birth star + paksha, then rates the day's windows by that
  bird's state — **Ruling / Eating / Walking / Sleeping / Dying** (strongest to weakest)
- A **colour-coded day timeline** — 10 main periods (5 from sunrise, 5 from sunset), each
  split into 5 sub-windows, tinted by strength with a legend, and the currently-running
  window outlined
- **Best** and **quieter** window summaries (top/bottom by effect) for "good time for X"
  planning, a date picker + "Today" reset
- The **timings are on your own clock**: the birth bird is fixed from the nativity, but
  the periods divide sunrise→sunset *where you are now*, taken from your current
  location and falling back to the birth place. The pill names the place they're in —
  a window you can't act in isn't a timing (§57.4)
- Optional **plain-language AI day-guide** (uses the model picked in Ask AI Astrologer),
  and a smart-lookup **tool** (`get_pancha_pakshi`) so the AI can pull today's timing

### Vedic Clock & Retrograde (`/vedic-clock`)

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

## Relationships

Also here: **Compare Charts** (`/compare`) — two saved profiles side by side with a neutral AI comparison.

### Marriage Compatibility

- Ashtakoot (Guna Milan) score out of 36, computed from each person's Moon nakshatra+pada
- Per-koota breakdown with correct maxima (Varna 1, Vashya 2, Tara 3, Yoni 4, Graha Maitri 5,
  Gana 6, Bhakoot 7, Nadi 8) and a verdict
- Side-by-side kundalis (North/South) for visual comparison
- On-demand "Get detailed AI analysis" using the model picked in Ask AI Astrologer

## My Notebook

Also here: **Astro-Journal** (`/journal`) — log life events against the dasha and transits running at the time; the AI can read it.

### AI History (`/history`)

- Reachable from a **dashboard tile** (desktop) and the **nav drawer** (mobile)
- **Every AI output is saved automatically** — the Ask/Transit chats _and_ every one-shot reading
  (Varshaphal, Muhurta, Prashna, Remedies, Bhrigu, Daily digest, Sensitive points, Vedic clock,
  Almanac, Pancha Pakshi, Sarvatobhadra, Compatibility, Compare, Rectification, Predictions)
- **Delivered digests too** — every digest actually sent (email/push), for each profile it
  covered, is filed and reopens on its own page exactly as it was sent. They live in their own
  `digest_readings` collection under `DIGEST_HISTORY_MAX`, *not* the shared `AI_HISTORY_MAX` pile:
  a daily send across several profiles would otherwise evict a user's chat threads within weeks
- **Global History page** grouped by profile (+ a **"No profile"** bucket for location-driven tools),
  filterable by chat vs. reading vs. digest; each item has a source badge, preview, and individual
  delete
- **Reopen = exact snapshot**: clicking an item returns to the tool that produced it, restores the
  inputs, and re-shows the saved reading verbatim (no re-computation)
- **Per-page "Recent readings"** control on each tool page for reopening a past reading in place
- Readings pile up (each generation is its own item); retention capped by `AI_HISTORY_MAX`
  (default 100, pruned on write). The Learn-the-Chart quiz keeps its own separate history
- **Outcomes** — a "did this land?" verdict on any item (reading or delivered digest), on the
  History page and in each tool page's own "Recent readings" panel. Optionally writes the matching
  astro-journal entry in the same request, and snapshots the Vimsottari period that was running when
  it landed. Stored in their own `reading_outcomes` collection with a copy of what they judged, so a
  verdict **survives its reading being pruned** by `AI_HISTORY_MAX` — deleting a reading by hand
  does take its verdict, the retention cap does not. Settled verdicts reach later readings through
  the prompt context and the `get_reading_outcomes` tool

## Standalone tools

Also here: **Learn the Chart** (`/learn`) — the AI quizzes you on your own chart and explains each answer.

### Muhurta / Electional Astrology (`/muhurta`) — personal to your chart (§71)

- Find **auspicious time windows** for an activity (general, marriage, travel, new business,
  housewarming, education, medical) over a date range, computed at your profile's place
- Each day is scored from its Panchanga — per-activity favourable **nakshatra**, **weekday**,
  **tithi** (Rikta/Amavasya penalised) and **yoga** (the nine inauspicious yogas penalised)
- …and then from **your own chart** (on by default; the "Score against my chart" switch turns it
  off to show the plain almanac underneath). Four classical personal checks: **Tara Bala** (the
  day's star counted from your birth star), **Chandra Bala** (the transiting Moon from your natal
  Moon), your running Vimsottari **Mahadasha and Bhukti lords' gochara** from that Moon, and —
  per window, because the rising sign turns over every ~2 hours — **lagna shuddhi**, the sign rising
  during that window counted from your janma rasi and janma lagna. Two people in the same city no
  longer get the same answer
- Qualifying days yield concrete **windows**: the Abhijit muhurta + the benefic planetary **horas**
  (Moon/Mercury/Jupiter/Venus) that avoid Rahu-Kalam / Yamaganda / Gulika
- A window barred by lagna shuddhi (the classical 8th-from-janma bar) is **flagged and ranked last,
  not hidden** — same treatment as the kaala-vela flag, so you can see why the obvious midday slot
  isn't the pick
- Ranked best-windows list + a day-by-day rating grid (with Tara / Chandra chips) + an **AI
  rationale** that names the personal reasons, and a smart-lookup **tool** (`get_muhurta`) so the
  astrologer can answer "when is a good time to…" from *this* chart
- **Day sub-tools** (a "Day tools" section, pick any day): the **Choghadiya** table (8 day + 8
  night parts, each good/neutral/bad with a "now" marker), the **Panchaka** status, and — using
  your profile's natal Moon — your personal **Tarabala** (the tara from your birth star to the
  day's star) and **Chandrabala** (the transit Moon counted from your natal Moon)

### Prashna / Horary (`/prashna`)

- Ask a question and cast a chart for the **exact moment you ask** — no birth data needed
- Uses your browser location (with permission; falls back to the profile place) at the current
  instant; renders the moment-chart via the shared North/South Kundali
- A Prashna-style **AI reading**: Ascendant = querent, Moon = mind/matter, house & lord = outcome,
  with a likely-yes / no / mixed answer and a sense of timing

### Remedies (`/remedies`)

- Traditional **remedial suggestions per weak / afflicted planet**. A planet is flagged when it is
  **debilitated**, **shadbala-deficient** (six-fold strength ratio < 1.0), or in a **dusthana**
  (6th/8th/12th from the Lagna)
- For each flagged graha: the classical **gemstone**, **beeja mantra** (+ japa count), presiding
  **deity**, **weekday**, **charity (daana)** and **colour**, plus a per-planet dignity & strength
  overview and an **AI reading**
- Clearly labelled **traditional guidance & devotional practice — not medical, legal or financial
  advice**; gemstones should be worn only after qualified consultation

### Birth-Time Rectification (`/rectify`) — experimental

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

## Account & platform

### Authentication

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

### Export & Share

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

### LLM Integration (Optional)

- Enhanced predictions with a local Ollama model or any configured provider
- Contextual astrological interpretations
- Personalized analysis
- **Privacy with hosted models (§78):** the chart is computed here, so a hosted
  provider (Gemini, OpenAI, OpenRouter, a cloud OpenAI-compatible host) is sent the
  computed chart, the profile name and your own text — but by default **not** the
  birth date (replaced by the age), time or place/coordinates. Each can be allowed
  per user in Settings → AI → "What hosted AI models may see". A self-hosted model
  always gets everything; a local model falling back to a hosted one is redacted.
  Redaction happens at the send points in `llm_service.py` (`llm/privacy.py`), so no
  prompt builder has to remember it. Note: Gemini's free tier may use prompts for
  training — use a paid key if that matters.

### Admin console (`/admin`) — deployer only

Not a user feature: a superuser surface for operating the deployment. Access is the
`ADMIN_USERNAMES` env allowlist (matching username **or** email), reconciled onto each account's
`is_admin` flag at startup — so you grant and revoke admin by editing the deploy secret, never by
opening Mongo. A logged-in non-admin probing any console route gets **404, not 403**, so the
console's existence is not confirmed to them.

- **Overview** — deployment totals, new users over 7/30 days, per-collection record counts, and AI requests by provider over 30 days (how many left the server, how many had birth details withheld — counts only)
- **Users** — every account with headline counts; suspend (blocks login, Google sign-in and token
  refresh) and cascade-delete. You cannot touch yourself or another admin
- **Activity** — what the deployment has been doing: signups, AI readings and chats, delivered
  digests, journal entries, reading outcomes, quizzes, shares. **Derived on read** from the collections themselves
  rather than logged, which is why it covers everything that ever happened, including data written
  long before any of this existed. Metadata only (titles, kinds, counts — never what someone wrote),
  so it stays readable without `ADMIN_CONTENT_ACCESS`. Filter by kind and by username
- **Audit log** — *events*, in two categories. **Moderation**: what an admin did here (suspend,
  delete, break-glass content view, config change). **Security**: what the deployment did on its own
  (register, login, failed/blocked/suspended login, Google sign-in, logout-all, password change,
  reset requested/completed, email change, API token issued/revoked, self-delete, console opened).
  Filter by category, action, actor, target and age; pruned past `ADMIN_AUDIT_RETENTION_DAYS`.
  A quiet log here is the *good* outcome — for ordinary use, read Activity instead
- **Settings** — the runtime knobs, stored in the database and re-read by the scheduler every tick,
  so a change takes effect within one cycle with **no redeploy and no pod shell**: the digest
  scheduler switch, its tick interval, how many **minutes** a digest may be held back waiting for a
  busy model, which prompt writes the narrative, and the **claim-checking mode** (§69: verify /
  annotate / log / off). Env vars remain the defaults; **Reset** clears an override and returns a
  field to its deployed value
- **Claim checks** (§69) — the reading-quality report. Every AI reading is checked against the chart
  it was generated from before it is shown; this tab is what you act on afterwards. Two rates,
  because they answer different questions: **model got it wrong** counts the *first* answer (how
  often the model contradicts its own chart — what prompt work has to move), and **reached the
  reader** counts what survived the retry. Below them, a breakdown by claim kind and by model, and a
  **triage queue**: one row per reading that still disagreed, each closed with a verdict naming what
  was actually at fault — the *prompt*, the *code*, the *model*, or the *checker* itself. A run of
  "code" verdicts means a payload is lying to the model again; a run of "checker" means the rules
  need tuning, not the app. The evidence quotes one identifiable person's chart, so it is redacted to
  bare claim kinds without `ADMIN_CONTENT_ACCESS` (the rate and the triage still work), and reading
  it is audit-logged
- **Content drill-down** into a user's actual readings/chats/journal/birth data is gated behind
  `ADMIN_CONTENT_ACCESS` (default **false** — metadata and counts only). It is a deliberate
  "break glass" step, and every such view is audit-logged regardless
