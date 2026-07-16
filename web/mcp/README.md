# Jyotir AI — MCP server

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes
the Jyotir AI astrology engine to any MCP client (Claude Desktop, etc.). It wraps
the same tool catalog the web app uses — natal chart, dashas (Vimsottari + 14 other
systems), panchanga, transits (with Ashtakavarga weighting), the chakras
(Sarvatobhadra / Kota / Kaala / Tripataki), KP, Jaimini, muhurta, and ~30 more — and
runs them against **your saved profiles** or inline birth data.

The catalog is fetched from the API at startup, so tools added to the web app show
up here automatically — nothing to update in this server.

Everything is **read-only compute**. The public API exposes no account or profile
mutation, so nothing here can change your data.

## How it works

```
MCP client  ──stdio/http──►  mcp/server.py  ──HTTPS + API token──►  Jyotir AI  /api/v1/*
```

The server fetches the tool catalog from `GET /api/v1/tools` at startup, registers
each tool natively (so your client sees them with schemas), and forwards each call
to `POST /api/v1/tools/{name}`. A `list_profiles` tool surfaces your saved charts.

## Setup

1. **Create an API token**: in the web app, go to **Settings → API access** and
   create a token. Copy it (it's shown once) — it looks like `jyd_…`.

2. **Install** (its own venv — the MCP SDK needs newer deps than the backend):

   ```bash
   cd web/mcp
   python3 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ```

3. **Run** (stdio, for testing):

   ```bash
   JYOTIR_API_URL=http://localhost:8000 \
   JYOTIR_API_TOKEN=jyd_your_token \
   ./venv/bin/python server.py
   ```

   Or streamable-HTTP: add `MCP_TRANSPORT=http` (serves at `http://127.0.0.1:8765/mcp`).

## Claude Desktop

Add to `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "jyotir-ai": {
      "command": "/absolute/path/to/web/mcp/venv/bin/python",
      "args": ["/absolute/path/to/web/mcp/server.py"],
      "env": {
        "JYOTIR_API_URL": "http://localhost:8000",
        "JYOTIR_API_TOKEN": "jyd_your_token"
      }
    }
  }
}
```

Restart Claude Desktop; the Jyotir AI tools appear in the tools menu. Ask it to
"list my profiles", then "run the natal chart for <profile>".

## Config (env)

| Var | Default | Meaning |
|---|---|---|
| `JYOTIR_API_URL` | `http://localhost:8000` | Base URL of the web backend |
| `JYOTIR_API_TOKEN` | — (**required**) | Your Settings → API access token |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `http` (streamable-HTTP) |
| `MCP_HTTP_HOST` | `127.0.0.1` | HTTP bind host |
| `MCP_HTTP_PORT` | `8765` | HTTP bind port |

## Security

- The token is a bearer credential; treat it like a password. Revoke it any time
  under Settings → API access.
- The server only ever calls the read-only `/api/v1/*` surface.
