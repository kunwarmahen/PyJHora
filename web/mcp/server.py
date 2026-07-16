"""Jyotir AI MCP server (§2.3) — a thin bridge from any MCP client (Claude
Desktop, etc.) to the Jyotir AI public API.

It wraps the same `tools.py` catalog the web app already exposes: at startup it
fetches `GET /api/v1/tools`, registers each as a native MCP tool (so the client
sees them individually, with schemas), and forwards every call to
`POST /api/v1/tools/{name}` — authenticated with the user's API token. A
`list_profiles` tool lets the client discover the user's saved charts to pass as
`profile_id`.

Everything is **read-only compute**; the public API exposes no account/profile
mutation, so nothing here can change the user's data.

Config (env):
  JYOTIR_API_URL     base URL of the web backend (default http://localhost:8000)
  JYOTIR_API_TOKEN   a token from Settings → API access (required)
  MCP_TRANSPORT      "stdio" (default, for Claude Desktop) or "http"
  MCP_HTTP_HOST      bind host for http transport (default 127.0.0.1)
  MCP_HTTP_PORT      bind port for http transport (default 8765)

Run:
  JYOTIR_API_TOKEN=jyd_… python server.py            # stdio
  JYOTIR_API_TOKEN=jyd_… MCP_TRANSPORT=http python server.py
"""
import contextlib
import json
import os
import sys
from typing import Any, Dict, List

import httpx
import mcp.types as types
from mcp.server.lowlevel import Server

API_URL = os.environ.get("JYOTIR_API_URL", "http://localhost:8000").rstrip("/")
API_TOKEN = os.environ.get("JYOTIR_API_TOKEN", "").strip()
TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()

SERVER_NAME = "jyotir-ai"

# Birth-data sub-schema surfaced on every tool as an alternative to profile_id.
_BIRTH_DETAILS_SCHEMA = {
    "type": "object",
    "description": "Inline birth data (use this OR profile_id).",
    "properties": {
        "name": {"type": "string"},
        "dob": {"type": "string", "description": "Date of birth, YYYY-MM-DD."},
        "tob": {"type": "string", "description": "Time of birth, HH:MM (24h)."},
        "place": {"type": "string"},
        "latitude": {"type": "number"},
        "longitude": {"type": "number"},
        "timezone": {"type": "number", "description": "UTC offset in hours, e.g. 5.5."},
    },
    "required": ["dob", "tob"],
}


def _auth_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


def _merged_input_schema(tool: Dict[str, Any]) -> Dict[str, Any]:
    """Build the MCP inputSchema for a catalog tool: the birth-data selectors
    (profile_id / birth_details / ayanamsa) plus the tool's own parameters."""
    own = tool.get("parameters") or {}
    props: Dict[str, Any] = {
        "profile_id": {
            "type": "string",
            "description": "Id of one of your saved profiles (see list_profiles). "
                           "Provide this OR birth_details.",
        },
        "birth_details": _BIRTH_DETAILS_SCHEMA,
        "ayanamsa": {
            "type": "string",
            "description": "Optional ayanamsa key; defaults to True Chitra (JHora-matched).",
        },
    }
    props.update(own.get("properties") or {})
    # The tool's own required params stay required; profile_id/birth_details are
    # validated server-side (either is accepted), so they aren't marked required.
    return {"type": "object", "properties": props, "required": own.get("required", [])}


async def _fetch_catalog(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    r = await client.get(f"{API_URL}/api/v1/tools", headers=_auth_headers())
    r.raise_for_status()
    return r.json().get("tools", [])


def build_server(catalog: List[Dict[str, Any]]) -> Server:
    server: Server = Server(SERVER_NAME)
    by_name = {t["name"]: t for t in catalog}

    # A synthetic tool for profile discovery, plus every catalog tool.
    profiles_tool = types.Tool(
        name="list_profiles",
        description="List your saved birth profiles (id + name + birth summary). "
                    "Use a returned id as `profile_id` when running any other tool.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    )

    @server.list_tools()
    async def list_tools() -> List[types.Tool]:
        tools = [profiles_tool]
        for t in catalog:
            tools.append(types.Tool(
                name=t["name"],
                description=t.get("description", t.get("label", t["name"])),
                inputSchema=_merged_input_schema(t),
            ))
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if name == "list_profiles":
                r = await client.get(f"{API_URL}/api/v1/profiles", headers=_auth_headers())
                payload = _safe_json(r)
            elif name in by_name:
                args = dict(arguments or {})
                body: Dict[str, Any] = {}
                for k in ("profile_id", "birth_details", "ayanamsa"):
                    if k in args:
                        body[k] = args.pop(k)
                body["args"] = args
                r = await client.post(
                    f"{API_URL}/api/v1/tools/{name}",
                    headers=_auth_headers(), json=body)
                payload = _safe_json(r)
            else:
                payload = {"error": f"Unknown tool '{name}'"}
        return [types.TextContent(type="text", text=json.dumps(payload, indent=2, default=str))]

    return server


def _safe_json(r: httpx.Response) -> Any:
    try:
        data = r.json()
    except Exception:
        data = {"error": f"HTTP {r.status_code}: {r.text[:500]}"}
    if r.status_code >= 400 and isinstance(data, dict):
        data.setdefault("error", f"HTTP {r.status_code}")
    return data


async def _run_stdio(server: Server) -> None:
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def _run_http(server: Server) -> None:
    """Streamable-HTTP transport, mounted on a minimal Starlette app at /mcp."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    manager = StreamableHTTPSessionManager(app=server, json_response=False, stateless=True)

    async def handle(scope, receive, send):
        await manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with manager.run():
            yield

    app = Starlette(routes=[Mount("/mcp", app=handle)], lifespan=lifespan)
    host = os.environ.get("MCP_HTTP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_HTTP_PORT", "8765"))
    print(f"[{SERVER_NAME}] streamable-HTTP on http://{host}:{port}/mcp", file=sys.stderr)
    uvicorn.run(app, host=host, port=port, log_level="warning")


async def _amain() -> None:
    if not API_TOKEN:
        print("ERROR: JYOTIR_API_TOKEN is not set (create one under Settings → API access).",
              file=sys.stderr)
        sys.exit(2)
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            catalog = await _fetch_catalog(client)
        except Exception as e:
            print(f"ERROR: could not reach the Jyotir AI API at {API_URL}: {e}", file=sys.stderr)
            sys.exit(1)
    print(f"[{SERVER_NAME}] loaded {len(catalog)} tools from {API_URL}", file=sys.stderr)
    server = build_server(catalog)
    await _run_stdio(server)


def main() -> None:
    import anyio
    if TRANSPORT == "http":
        # HTTP transport still needs the catalog; fetch synchronously first.
        if not API_TOKEN:
            print("ERROR: JYOTIR_API_TOKEN is not set.", file=sys.stderr)
            sys.exit(2)

        async def _load():
            async with httpx.AsyncClient(timeout=30.0) as client:
                return await _fetch_catalog(client)

        try:
            catalog = anyio.run(_load)
        except Exception as e:
            print(f"ERROR: could not reach the Jyotir AI API at {API_URL}: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"[{SERVER_NAME}] loaded {len(catalog)} tools from {API_URL}", file=sys.stderr)
        _run_http(build_server(catalog))
    else:
        anyio.run(_amain)


if __name__ == "__main__":
    main()
