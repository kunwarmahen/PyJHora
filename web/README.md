# PyJHora Web Application - Setup & Deployment Guide

## Overview

This is a full-stack web application for Vedic Astrology calculations using PyJHora library. It includes:

- **Backend**: FastAPI with MongoDB for data persistence and JWT authentication
- **Frontend**: React SPA with responsive UI
- **Authentication**: User registration and login with JWT tokens
- **Features**: Birth Chart (Rasi D1 + Navamsa D9), divisional charts D1–D60, Panchanga,
  Yogas/Doshas, dedicated Raja Yogas, Graha Drishti (aspects, with strength-weighted lines
  on the chart), Vimsottari Dhasa (+ 13 other dasha systems & Sudarsana Chakra), Transits,
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
  a personalized daily digest ("Today" — panchanga + dasha + transits, with email & push
  notifications),
  Bhrigu / Nadi-style yearly markers (the Moon-based annual progression + Bhrigu Bindu
  activations, with AI reading),
  Remedies (traditional gemstone / mantra / deity suggestions per weak planet),
  Sensitive Points (Sphutas, the 36 Sahams, and Argala — with AI reading),
  a Vedic Clock & Retrograde page (a live ghati/vighati clock + vakra-gathi retrograde
  loops, with AI reading),
  Sarvatobhadra Chakra (with layman AI reading), Compatibility, an Advanced page
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
- **Unified AI History** (`/history`): *every* AI output across the whole app — not just the Ask
  chat, but every one-shot reading (Varshaphal, Muhurta, Prashna, Remedies, Bhrigu, Daily digest,
  Sensitive points, Vedic clock, Almanac, Pancha Pakshi, Sarvatobhadra, Compatibility, Compare,
  Rectification, Predictions) — is saved automatically. The History page groups items by profile
  (plus a **"No profile"** bucket for location-driven tools) and filters by chat vs. reading;
  clicking any item **returns to the tool that produced it and re-shows the exact saved reading**
  (a snapshot — no re-computation). Every tool page also has its own collapsible **"Recent readings"**
  control (filtered to that tool) for reopening a past reading in place. Readings pile up; each is
  individually deletable. Retention is capped by `AI_HISTORY_MAX` (default 100, pruned on write).
  (The Learn-the-Chart quiz keeps its own dedicated history and is not stored here.)
- **Answer affordances**: copy, **regenerate** (with the same model, or pick a
  *different* provider/model from the split-button menu), thumbs up/down, and
  **export the whole conversation to Markdown or PDF**
- **Per-user API keys (encrypted)**: each user stores their own provider keys — managed in the
  **Settings → API Keys** tab — no shared `.env` key required
- **Rate limiting**: per-user per-minute + per-day quotas on the AI endpoints
- **Safety disclaimer**: clear "guidance, not professional advice" footer

### Settings (single source of truth)
- **One place for preferences**: a dedicated **Settings** page (gear icon in the Dashboard
  navbar + nav drawer, or `/settings`) with tabs — **General** (language, chart style North/South,
  ayanamsa), **AI** (provider / model / endpoint, answer-mode default, **Max response length**
  slider, links to API Keys + AI Capabilities), **API Keys**, **Almanac** (Drik / Surya-Siddhanta
  engine), **Notifications** (daily-digest opt-in, target profile + preferred hour, email + browser-
  push toggles, "send test now"), and **Account** (account overview, update email, change password,
  log out other devices, and a danger-zone **Delete account**)
- **Consolidated controls**: the per-page dropdowns/toggles that used to live on individual pages
  (ayanamsa, chart style, almanac engine, AI model/keys) were removed — pages now read these from
  Settings via a `SettingsContext` (backed by the same `localStorage` keys). Language is changed
  here too (the old per-page language switcher was removed)
- **Per-question controls kept on Ask**: answer mode, the per-section Seed/Tool/Off context
  toggles, and the vargas "Charts to Consult" picker remain on the Ask page (they're
  question-specific)

### AI Capabilities page
- **Tool catalog / capability disclosure**: the **AI Capabilities** page (reached from
  **Settings → AI → "View AI capabilities"**, or `/ai-tools`) lists every tool the AI astrologer
  can call while answering — grouped by Core chart / Timing / Strengths & afflictions, each
  with a plain-language description and an optional **Show technical schema** toggle for its
  inputs
- **Always in sync**: rendered live from `GET /api/ai/tools`, which is derived from the same
  `tools.py` registry the model actually uses, so it never drifts from the real toolset

### Transit chat (in-context gochara reading)
- **Ask about *these* transits, right on the Transits page**: an embedded chat below
  the gochara chart, seeded with *only* the current transits + your running dasha
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

## Project Structure

```
pyjhora-web/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── database.py          # MongoDB models and connection
│   ├── auth.py              # Authentication utilities (password hashing, JWT access tokens)
│   ├── refresh_tokens.py    # Long-lived, revocable, rotating refresh tokens (silent re-auth)
│   ├── astrology.py         # PyJHora wrapper
│   ├── llm_service.py       # Multi-provider LLM layer (Ollama/OpenAI-compatible/Gemini/OpenAI) + streaming
│   ├── chart_context.py     # Builds the structured chart context sent to the AI
│   ├── tools.py             # Tool registry for agentic mode (wraps AstrologyCompute) + GET /api/ai/tools catalog
│   ├── tool_traces.py       # Lazy side-storage for smart-lookup tool results
│   ├── conversations.py     # Unified AI history: chat threads + one-shot readings (source registry, save_reading, retention cap)
│   ├── user_settings.py     # Per-user encrypted API keys
│   ├── ratelimit.py         # Per-user rate limiting for AI endpoints
│   ├── shares.py            # Read-only shareable chart links
│   ├── qwen_predictor.py    # Legacy Qwen LLM integration
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

## Configuration

### Backend (.env)

```env
# MongoDB
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=pyjhora_db

# Security (CHANGE IN PRODUCTION)
SECRET_KEY=your-secret-key-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
# Refresh-token lifetimes (days). "Keep me signed in" picks the long TTL; a plain login the short.
REFRESH_TOKEN_EXPIRE_DAYS=30
REFRESH_TOKEN_SHORT_DAYS=1

# LLM providers (endpoints + default models; keys are optional — users can also
# store their own per-user keys in the app). See backend/.env.example for the full list.
OLLAMA_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=qwen2.5:14b
OPENAI_COMPATIBLE_URL=http://localhost:1234/v1
GEMINI_API_KEY=         # optional global fallback
OPENAI_API_KEY=         # optional global fallback

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
# in-app digest still work).
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:admin@example.com

# Daily-digest scheduler (opt-in): deliver each opted-in user's digest once a day
# at their preferred local hour. Off by default (cron POST /notifications/digest/send
# instead). Safe with multiple workers (an atomic DB claim prevents double-sends).
DIGEST_SCHEDULER_ENABLED=false
DIGEST_SCHEDULER_INTERVAL_MINUTES=15

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

### Frontend (.env)

```env
# Optional — when unset, the app calls the same host it was served from on :8000
# (so it works over the LAN from a phone with no per-device config). Set to pin it.
REACT_APP_API_URL=http://localhost:8000
REACT_APP_API_TIMEOUT=30000
```

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
- User registration with username, email, password (with a live password-strength hint)
- JWT-based login with a **"Keep me signed in"** option, and a per-IP **brute-force rate-limit**
  (default 10 failed attempts / 15 min → HTTP 429; env `LOGIN_RATE_MAX_FAILS` / `LOGIN_RATE_WINDOW_SEC`)
- **Refresh tokens**: a short-lived access token is silently refreshed in the background using a
  long-lived, revocable, **rotating** refresh token, so you stay signed in across access-token
  expiry (no more being logged out every ~30 minutes). Refresh tokens are stored hashed and are
  revoked on logout and on password change
- **Account management** (Settings → Account): account overview (username + member-since),
  **update email**, **change password** (verifies the current password, signs out other devices),
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
- **Vimsottari**: full drill-down tree Maha Dasha → Bhukti → Antara → Sookshma.
  Maha + Bhukti load up front; deeper levels lazy-load on expand (computed at full
  precision from the natal chart). The currently running period auto-expands the
  whole live chain and is highlighted.
- **Other systems** (14 total): Ashtottari, Yogini, Shodasottari, Dwadasottari,
  Panchottari, Shatabdika (graha) and Narayana, Kalachakra, Kendradhi-Rasi, Sudasa,
  Drig, Chara, Sthira, Trikona (raasi) — pick one from the "Other Dasha Systems" card
  for a maha-period table.
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
- A **Bhava Chalit / cuspal chart**: unlike the Rasi chart (where each sign *is* a
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
  an annual snapshot when asked "how is *&lt;year&gt;* for me?"

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
  significators. Deterministic and **auditable** — a per-event table shows *why*
  each time fits (which period lord rules/occupies the event's houses, or is its
  karaka), with a rough **fit %** that strengthens as you add events
- **Conversational** — an AI astrologer **interviews you in chat**, asking about one
  dated life event at a time and extracting them as it goes; when it has enough it
  invites you to run the (same deterministic) rectification. The AI only *collects*
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
- **Sphutas** — 12 sensitive longitudes derived from the natal chart (Tri/Chatur/Pancha/
  Prana/Deha/Mrityu/Beeja/Kshetra/Tithi/Yoga/Yogi/Avayogi), each as a sign + degree + house
- **Sahams** — the **36 natal Sahams** (Arabic-part-like points), each tied to a life
  theme (Punya/Vidya/Karma/Artha/Vivaha/Puthra/Rajya/Laabha…), placed by sign + house
- **Argala & Virodhargala** — per bhava, which houses receive strong planetary
  **intervention** (argala) vs **obstruction** (virodhargala), with a net verdict
- Optional **AI reading** (model from Ask AI Astrologer) + smart-lookup **tools**
  (`get_sphuta`, `get_sahams`, `get_argala`)

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
- **Delivery channels** (opt-in, in **Settings → Notifications**): in-app always; **email** digest
  (via SMTP); **browser push** (Web Push / VAPID). A "send me a test now" button and per-user
  profile/hour preferences
- **Scheduler**: an opt-in in-process scheduler (`DIGEST_SCHEDULER_ENABLED`) delivers each user's
  digest once a day at their preferred local hour — multi-worker-safe via an atomic DB claim
  (`notifications.last_sent_date`). Or leave it off and point your own cron at
  `POST /api/notifications/digest/send` per user (both share `digest.send_digest_for_user`)

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

### 21. LLM Integration (Optional)
- Enhanced predictions with a local Ollama model or any configured provider
- Contextual astrological interpretations
- Personalized analysis

### 22. AI History (`/history`)
- Reachable from a **dashboard tile** (desktop) and the **nav drawer** (mobile)
- **Every AI output is saved automatically** — the Ask/Transit chats *and* every one-shot reading
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

# 4. Update backend/.env (QWEN_API_URL is still honored as a fallback)
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

### Switching Between AI Models

Users can select their preferred provider **and model** in the frontend:
- Go to **Settings → AI**
- Pick a provider (Ollama / OpenAI-compatible / Gemini / OpenAI) and a specific model
- Optionally raise the **Max response length** if answers get cut off
- Each model will provide different perspectives on your chart

### Per-user API keys (no shared `.env` key needed)

Instead of (or in addition to) the global `.env` keys above, each user can store
their own provider keys from the app: open **Settings → API Keys** and paste a
Gemini / OpenAI / OpenAI-compatible key. Keys are encrypted at rest, shown back only
masked, and used ahead of any global env key for that user's requests.

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user (returns access + refresh token)
- `POST /api/auth/login` - Login user (`remember_me` picks the refresh-token TTL)
- `POST /api/auth/refresh` - Exchange a refresh token for a fresh access token (rotates the refresh token)
- `POST /api/auth/logout` - Revoke a refresh token
- `POST /api/auth/change-password` - Change password (auth; revokes other sessions, returns a fresh pair)
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
  periods (Antara/Sookshma) of a Vimsottari node for the drill-down tree
- `GET /api/astrology/dasha-systems` - List the other (non-Vimsottari) dasha systems
- `POST /api/astrology/dasha-periods?dhasa_type=` - Maha-level periods for ashtottari/
  yogini/narayana/kalachakra
- `POST /api/astrology/transit?current_date=&current_time=&current_tz=&ayanamsa=` - Current transits (Gochara); `current_time`/`current_tz` anchor the snapshot to the viewer's present moment and timezone (default: their local now)
- `POST /api/astrology/sarvatobhadra?name_nakshatra=&current_date=&current_time=&current_tz=&ayanamsa=` - Sarvatobhadra Chakra (9×9 grid) with the current transits + occupation/vedha on the native's sensitive stars
- `POST /api/astrology/sarvatobhadra-analysis` - Plain-language AI reading of the Sarvatobhadra transit picture (`SarvatobhadraAnalysisRequest`; model-config aware, rate-limited)
- `POST /api/astrology/ashtakavarga?ayanamsa=` - Bhinna + Sarva Ashtakavarga tables
- `POST /api/astrology/chart-details?ayanamsa=` - Arudha padas, Chara karakas,
  Special lagnas, Upagrahas
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

### Saved Profiles
- `POST /api/profiles/save` - Save a new birth profile
- `GET /api/profiles/list` - List all saved profiles for the current user
- `PUT /api/profiles/{profile_id}` - Update an existing birth profile
- `DELETE /api/profiles/{profile_id}` - Delete a saved profile

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
- `/compare` - Compare two saved profiles side by side (charts, placements table + on-demand neutral AI comparison)
- `/share/:token` - **Public, read-only** shared chart view (no login required)
- `/predictions` - Horoscope and predictions generator
- `/settings` - **NEW**: Settings (single source of truth) — language, chart style, ayanamsa, AI provider/model + **max response length**, API keys, almanac engine, and change password
- `/ai-tools` - AI Capabilities catalog (reached from Settings → AI)

## Development Notes

### Backend Architecture

The backend uses a layered architecture:

- **main.py**: FastAPI routes and endpoints
- **config.py**: Configuration management
- **database.py**: MongoDB models and async connection
- **auth.py**: JWT and password utilities
- **astrology.py**: PyJHora wrapper functions
- **qwen_predictor.py**: LLM integration for enhanced predictions

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
5. **Set USE_QWEN to false** if not using local LLM
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

Check the PyJHora license for terms of use.
