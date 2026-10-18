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

Two of the tools read **your own recorded data** rather than the ephemeris:
`get_journal_entries` (your dated life events, each stamped with the dasha that
was running) and `get_reading_outcomes` (your "did this land?" verdicts on past
readings — see [todo.md §72](../todo.md)). They are scoped to the token's owner,
and honest when empty: with nothing recorded, `get_reading_outcomes` returns a
note saying so rather than an empty list, so a client can't narrate a track
record that doesn't exist.

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

## Hosted endpoint — connect by URL, no code needed

The NAS deployment serves the MCP server at **`https://www.jyotirai.win/mcp`**
(its own `jyotirai-mcp` container, routed by nginx). Nothing to install: give your
client the URL plus your token as a header.

```bash
# Claude Code
claude mcp add --transport http jyotir-ai https://www.jyotirai.win/mcp \
  --header "Authorization: Bearer jyd_your_token"
```

```json
// Any client that takes a URL + headers (Cursor, Claude Desktop via mcp-remote, …)
{
  "mcpServers": {
    "jyotir-ai": {
      "url": "https://www.jyotirai.win/mcp",
      "headers": { "Authorization": "Bearer jyd_your_token" }
    }
  }
}
```

The hosted server holds **no token of its own**. Each request's
`Authorization: Bearer jyd_…` is forwarded to `/api/v1` unchanged, so every
caller acts as themselves. A request with no token gets a 401 before any MCP
handling. Never set `JYOTIR_API_TOKEN` on that container: it is the fallback for
a caller who sends none, and on a shared endpoint it would let anyone act as you.
The compose service deliberately has no `env_file` for that reason.

Ships with the rest of the stack: `./dev.sh nas deploy` (or `./dev.sh nas deploy mcp`
for just this image).

claude.ai's custom connectors want OAuth rather than a static header, so they
can't use this endpoint yet. Claude Code, Claude Desktop (through `mcp-remote`),
Cursor and SDK agents can.

**Running `server.py` locally against the remote site** still works too:
`JYOTIR_API_URL=https://www.jyotirai.win` (no `/api` suffix) and a token created
on that site. Tokens live in each deployment's own Mongo, so one made on your
local dev stack won't work against the NAS.

## What the tools return

Positions come back naming the sign, not numbering it — a model reading a
coordinate as a house number is the whole reason these payloads are shaped the
way they are (`web/todo.md` §63):

```json
"Sun": { "sign_name": "Cancer", "degrees": 0.03, "house": 12 }
```

`house` is the **bhava**, counted whole-sign from *that chart's own* lagna — a
varga's houses come off the varga's lagna, not the D1's, and each chart result
carries a `house_system` line naming the sign that is house 1. Transits carry no
plain `house` (they are read from several references at once) but name each count:
`house_from_lagna`, `house_from_moon`, `house_from_al`, `house_from_ul`.

Drawing coordinates — the 1-based `sign_num`, the 0-based `rasi`, and bare integer
`sign` fields that sit beside a spelled-out name — are stripped from every tool
result before it leaves the API. They are cell references for a Kundali, not
placements, and they were being read as house numbers.

## Config (env)

| Var | Default | Meaning |
|---|---|---|
| `JYOTIR_API_URL` | `http://localhost:8000` | Base URL of the web backend |
| `JYOTIR_API_TOKEN` | — (required for stdio) | Your Settings → API access token. Over http it's only a fallback for callers that send none; leave it unset on a shared endpoint |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `http` (streamable-HTTP) |
| `MCP_HTTP_HOST` | `127.0.0.1` | HTTP bind host |
| `MCP_HTTP_PORT` | `8765` | HTTP bind port |

## Security

- The token is a bearer credential; treat it like a password. Revoke it any time
  under Settings → API access.
- The server only ever calls the read-only `/api/v1/*` surface.
