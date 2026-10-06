# Jyotir AI — Setup, configuration & deployment

> Absorbs the old `QUICKSTART.md` (now in `archive/`). The fastest path is *Installation → Option 2: Docker Compose*.

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
./dev.sh test          # backend golden-value + endpoint + determinism tests (1,029)
./dev.sh test web      # frontend jest (232) + prettier --check + eslint, incl. jsx-a11y
./dev.sh test all      # both
./dev.sh test engine   # also smoke-run PyJHora's own ~1,500-test suite
```

`test web` is the guard on everything the compiler cannot see: the `jsx-a11y` rules (§73) that
stop another icon-only control shipping without a name, the formatter, and `npm ci --dry-run`
under the build image's own npm (see *Adding a dependency* below — a host npm writes lockfiles
that `npm ci` refuses). It must report **0 problems** — a warning left standing is how the rule
set becomes decoration.

Still open (todo.md §68.2/§68.3): none of this runs in CI, and no page has ever been *rendered*
in a test — every frontend suite covers a pure config or util module.

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
anything. Everything below runs over a single SSH ControlMaster connection.

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

**Passwords are asked once, up front.** There are two of them, and they are two
different credentials: the **SSH login** (unless you've installed a key on the
NAS with `ssh-copy-id`) and the NAS's own **`sudo`** password, since every remote
command is `sudo docker …`. Both are collected back to back *before* the image
builds start, so a deploy never stops for input once it's under way.

On a NAS they are usually the same account and the same password, so the second
prompt offers the first as its default — **bare Enter reuses the SSH password**,
or type a different one:

```
==> connecting to admin@nas.local ...
SSH password for admin@nas.local:
sudo password for admin@nas.local [Enter = same as the SSH password]:
✓ sudo accepted the SSH password — the rest of the deploy runs unattended
```

If they turn out to differ, you're told so and re-prompted (three attempts) —
not left to discover it after the transfer. Nothing is asked at all when the NAS
grants passwordless sudo. An empty answer to the SSH prompt is fine too: it just
means "authenticate however you normally would", so key users can hit Enter — and
once a key has worked, `dev.sh` records that in `web/.run/nas-auth` and stops
asking. It deliberately does **not** probe key auth live: a probe that fails is a
failed login attempt on every `nas` command, and a NAS that auto-blacklists will
ban this machine after a handful of them (see the troubleshooting note below).

Mechanically: `ssh` has no "read the password from here" flag, so `dev.sh` hands
it a tiny **askpass helper** (`SSH_ASKPASS_REQUIRE=force`, OpenSSH 8.4+). The
helper holds no secret — it prints an environment variable exported for the `ssh`
child alone, so the password never reaches disk. ControlMaster then covers the
SSH side for the rest of the run. For sudo, `dev.sh` authenticates the remote
credential once and holds it open with a keepalive for as long as the remote
script runs (a cold `docker load` can outlast sudo's five-minute cache). That
password travels over ssh's **stdin** — never on the remote command line, where
the NAS's own `ps` would show it — and no PTY is allocated, so nothing echoes it
back to your terminal.

`./dev.sh nas shell` is the one exception: an interactive shell needs its own
PTY, and sudo's `tty_tickets` means a credential primed on a ttyless session
doesn't count for it, so sudo still prompts there.

**"Connection reset by peer" / `kex_exchange_identification` on connect** is not
a bad password — the NAS is closing the connection *before* authentication, and
`dev.sh` says so rather than blaming the password. On ASUSTOR ADM the usual cause
is **ADM Defender's auto-blacklist** after repeated failed logins; `ssh -v` shows
the giveaway banner `Not allowed at this time`. Clear it in the ADM web UI
(`http://<NAS_HOST>:8000`) → **Settings → ADM Defender → Black List**, and remove
this machine's IP.

For a fully unattended run, `export NAS_SSH_PASSWORD=…` and/or
`NAS_SUDO_PASSWORD=…` in your shell. They are deliberately **not** read from
`web/.env`: that file is scp'd to the NAS on every deploy, so a password living
in it would be shipped to the very box it unlocks. Better still, install your key
(`ssh-copy-id <NAS_USER>@<NAS_HOST>`) and the SSH prompt disappears for good.

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

# Birth-detail privacy (§78). Hosted models are not sent the birth date, time or
# place unless the user allows it in Settings → AI; self-hosted ones get
# everything. "Self-hosted" = an Ollama / OpenAI-compatible endpoint on loopback,
# a private/Tailscale IP, a single-label or .local/.lan/.internal name. List any
# other host that is really yours (e.g. a Tailscale MagicDNS name):
# SELF_HOSTED_LLM_HOSTS=nas.tailnet-1234.ts.net

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
# emails, no push. It fails *quietly*: the scheduler loop runs but does nothing,
# and Settings › "Send test now" keeps working (it calls
# POST /api/notifications/digest/send directly and bypasses the scheduler), which
# makes the feature look correctly configured.
# Set it true unless you are driving that endpoint from your own cron.
#
# NOTE these three are the *defaults* for the runtime settings an admin can edit
# live in Admin › Settings (stored in Mongo, re-read every tick — no redeploy).
# Changing them here changes what a deployment starts from and what "Reset"
# returns to; an existing override in the database wins until it is cleared.
DIGEST_SCHEDULER_ENABLED=false
DIGEST_SCHEDULER_INTERVAL_MINUTES=15
# How many ticks a scheduled digest may be held back while the AI narrative is
# unavailable for a reason that may clear (the GPU is busy). Past this it sends
# with rule-based highlights and no narrative — late beats never. 6 × 15 min ≈ 1½ h.
# The console edits this as a *duration* (digest_ai_max_delay_minutes, default
# 6 × 15 = 90) because a retry count silently changes meaning with the interval.
DIGEST_AI_MAX_DEFERRALS=6
# Which prompt writes the digest narrative — "focused" (leads on the day's single
# strongest signal, reads the birth chart to name the area of life it touches, and
# does not repeat yesterday's note) or "classic" (covers every signal in the order
# the data lists them). Both ship; this is only the default, and Admin › Settings
# switches a live deployment either way without a redeploy.
DIGEST_NARRATIVE_STYLE=focused
# How many delivered digests are kept per user in their reading history. Digests
# are stored separately from chats/readings under their own cap, precisely so a
# daily send across several profiles can never evict AI_HISTORY_MAX conversations.
DIGEST_HISTORY_MAX=120

# Claim checking (§69). Before a reading is shown it is checked against the chart
# it was generated from: placements, house lords, signs, nakshatras, retrogression
# and exaltation are extracted from the finished text and compared with the very
# context the model was handed. Four shipped bugs were the model contradicting its
# own chart and a human catching it afterwards, so this is on by default.
#   verify   — check, re-ask once naming the error, annotate only what survives
#              the retry. Costs a second call when a reading is wrong.
#   annotate — check and annotate; never a second call.
#   log      — record for Admin › Claim checks; the reader sees nothing.
#   off      — no checking.
# Like the digest knobs above this is only the *default*: Admin › Settings switches
# a live deployment without a redeploy. An unrecognised value falls back to verify
# rather than raising, so a typo here cannot stop the app booting.
CLAIM_CHECK_MODE=verify
# How long a *triaged* claim-check row is kept. Open ones are never pruned — an
# unread work item ageing out is how a bug gets forgotten.
CLAIM_CHECK_RETENTION_DAYS=90

# Admin console (deployer-only /admin page: all accounts, usage, moderation).
# ADMIN_USERNAMES is the source of truth — comma-separated usernames/emails; the
# app reconciles each user's is_admin flag from it at startup, so you grant/revoke
# admin by editing this and redeploying, never by touching Mongo. Empty = no admins.
# ADMIN_CONTENT_ACCESS is a "break glass" switch: false (default) shows metadata +
# counts only; true also lets an admin open a user's private content (audit-logged).
ADMIN_USERNAMES=
ADMIN_CONTENT_ACCESS=false
# How long the audit log keeps rows (pruned on write). It records moderation
# actions AND security events (sign-ins, failed sign-ins, resets, API tokens),
# and logins arrive far faster than moderation does — hence a horizon.
ADMIN_AUDIT_RETENTION_DAYS=90

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
- **Max response length** defaults to **Auto** — no cap, the model stops when it is done.
  Set a value only to rein in a model that runs on past the point of being useful.
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
on any cadence, on either channel. Nothing errors, so the logs look clean.

Since the scheduler's pacing became runtime-editable, the loop **always starts** and checks
the switch on each tick — so it now announces its own state at boot and whenever it changes:

```
[scheduler] digest scheduler idle (every 15 min, patience 90 min)
```

`idle` is the tell. A deployer can flip it without a redeploy in **Admin › Settings**, which
writes a database override that wins over the env var until it is cleared.

Two things make this easy to misdiagnose as a regression:

- Settings › **"Send test now"** keeps working. It calls
  `POST /api/notifications/digest/send` directly and shares only the *delivery* code
  (`digest.send_digest_for_user`), not the scheduler — so the feature looks configured.
- On the NAS, `web/.env` is the only env source and is `scp`'d over the remote copy on
  **every** deploy, so a value hand-edited on the NAS does not survive. Set it in your local
  `web/.env` (template: `.env.nas.example`).

Confirm from the log. The state line prints at startup **and again whenever the state
changes**, so you must replay the whole log — the default 100-line tail will have scrolled
past it on a container that has been up any length of time:

```bash
./dev.sh nas logs backend all | grep '\[scheduler\]'
# want:    [scheduler] digest scheduler running (every 15 min, patience 90 min)
# problem: [scheduler] digest scheduler idle (every 15 min, patience 90 min)
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
