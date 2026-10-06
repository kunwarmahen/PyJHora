# Jyotir AI — Vedic Astrology Web App

> **Branding.** The product is **Jyotir AI** (configurable via `REACT_APP_SITE_TITLE` /
> backend `SITE_NAME`). **PyJHora** names the underlying `jhora` calculation library /
> fork (`github.com/kunwarmahen/PyJHora`), which is unchanged.

A full-stack Vedic astrology app: a **FastAPI + MongoDB** backend that computes everything
with PyJHora, a **React** frontend, and an **AI astrologer** (local Ollama, Gemini, OpenAI or
OpenRouter) that reads your actual chart through tool calls, checks its own claims against
it, and keeps every reading you generate.

## Quick start

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
./dev.sh start          # backend :8000, frontend :3000 (local processes)
./dev.sh test all       # backend + frontend tests  (./dev.sh up = containers)
```

Or `docker-compose up --build`. Then open http://localhost:3000, register, and add a birth
profile. Full instructions: **[docs/SETUP.md](docs/SETUP.md)**.

## What's in it

The app is organised into **hubs** — related pages behind one menu entry, with a strip under
the page title to move between them (§79). Every page keeps its own URL.

| Hub | Pages |
| --- | --- |
| **My Chart** | Birth Chart (D1/D9, all vargas, yogas & doshas, aspects, panchanga) · Bhava Chart · Nakshatra Profile · Planetary Strength · Chart Deep-Dive · Sensitive Points |
| **Your Periods** | Today · This Fortnight · This Month · Varshaphal (solar year) · Tithi Pravesha (lunar return) — each with AI readings and email/push digests |
| **Other Systems** | Jaimini · KP System · Nadi Karakas · Bhrigu Markers · Chakras (Sarvatobhadra, Kota, Kaala, Tripataki) |
| **Reports** | Life Report (chaptered reading) · Full Report (print-ready PDF) |
| **Dasha & Timeline** | Dasha Periods (Vimsottari + 18 other systems) · Life Timeline (+ What's coming & event alerts) |
| **Transits** | Transits (with Ashtakavarga support + nakshatra gochara) · Gochara-phala · Sade Sati · Ephemeris |
| **Sky & Panchanga** | Almanac · Vedic Clock & Retrograde · Pancha Pakshi · Chart of the Moment |
| **Relationships** | Compatibility (Ashtakoot, Dashakoota, Mangal dosha, 7th house, marriage timeline) · Compare Charts |
| **My Notebook** | AI History (with "Did this land?") · Astro-Journal |

Standalone: **Ask AI Astrologer**, Muhurta (scored against your chart), Prashna, Remedies,
Learn the Chart, Birth-Time Rectification, Settings, Help & FAQ, and a deployer-only Admin
console. Also: a read-only REST API (`/api/v1`) and an MCP server ([`mcp/`](mcp/README.md)),
an iCal feed, offline mode, Hindi/Sanskrit UI, light/dark themes.

## Documentation

| Doc | What's in it |
| --- | --- |
| [docs/FEATURES.md](docs/FEATURES.md) | Every feature, by hub — what it computes and how it's wired |
| [docs/SETUP.md](docs/SETUP.md) | Install, `.env` configuration, AI model setup, deployment, troubleshooting |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Project structure, backend/frontend architecture, testing |
| [docs/API.md](docs/API.md) | REST endpoints (live docs at `/docs` on the backend) |
| [docs/LOCATION_SEARCH.md](docs/LOCATION_SEARCH.md) | How places become coordinates and timezones |
| [docs/I18N_DATA_LAYER_DESIGN.md](docs/I18N_DATA_LAYER_DESIGN.md) | Translating engine-returned names — read before touching it |
| [docs/AI_TOOL_CALLING_DESIGN.md](docs/AI_TOOL_CALLING_DESIGN.md) | How the AI astrologer reads the chart through tools |
| [mcp/README.md](mcp/README.md) | The MCP server (its own venv) |
| [todo.md](todo.md) | Build log + open work, by numbered section (§N); the code cites these numbers |

## Support and contributing

Issues and contributions: the PyJHora fork, https://github.com/kunwarmahen/PyJHora.

## License

Check the JyotirAI license for terms of use.
