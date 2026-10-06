"""Record real API responses for the page harness's "realistic" mode (§83.7).

The harness (src/pages/pages.smoke.test.js) mounts every page against failing
APIs. This records what the routes actually send for the owner's reference chart,
so the harness can also mount every page against a real, successful payload:

  1. registers a throwaway user and seeds the harness's own profile
     (the owner's chart — the one `mockProfile` describes),
  2. opens every route the harness mounts (read from KEY_BY_COMPONENT, so the
     two lists can't drift) in Everything mode, as the harness does,
  3. keeps the first successful JSON response per "METHOD /path".

AI calls, auth, profiles and the user's own records are left out: a mount never
needs a model reply, and the harness stubs the contexts those feed.

Needs the app running (`./dev.sh start`) and Playwright in a scratch venv:

    python3 -m venv /tmp/pw && /tmp/pw/bin/pip install playwright && /tmp/pw/bin/playwright install chromium
    cd web/frontend && /tmp/pw/bin/python scripts/record_page_fixtures.py

Writes src/pages/__fixtures__/realistic.json. Re-record when a route's payload
changes shape; the realistic test fails loudly on a page that crashes on it.
"""
import json
import os
import random
import re
import sys
import urllib.request
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.join(HERE, "..", "src", "pages", "pages.smoke.test.js")
OUT = os.path.join(HERE, "..", "src", "pages", "__fixtures__", "realistic.json")
APP = os.environ.get("APP_URL", "http://localhost:3000")
API = os.environ.get("API_URL", "http://localhost:8000")

# Never recorded: model output, credentials, the machine's own LLM setup, and
# per-user records the harness stubs through its contexts anyway.
SKIP = re.compile(
    r"^/api/(auth|ai|admin|profiles|user|history|journal|notifications|onboarding|api-tokens|llm)\b|^/health$"
    r"|-analysis$|/predict$|/ask$|/quiz/|/rectify-birth-time/(chat|explain|events)|/life-report/chapter"
)


def harness_routes():
    src = open(HARNESS, encoding="utf-8").read()
    block = src[src.index("const KEY_BY_COMPONENT = {"):]
    block = block[: block.index("};")]
    return sorted(set(re.findall(r':\s*"(/[^"]*)"', block)))


def harness_profile():
    src = open(HARNESS, encoding="utf-8").read()
    block = src[src.index("const mockProfile = {"):]
    block = block[: block.index("};")]

    def field(name, cast=str):
        m = re.search(rf'{name}:\s*"?([^",\n]+)"?', block)
        return cast(m.group(1))

    return {
        "name": field("name"), "dob": field("dob"), "tob": field("tob"),
        "place": field("place"), "latitude": field("latitude", float),
        "longitude": field("longitude", float), "timezone": field("timezone", float),
    }


def post(path, body, token=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main():
    user = f"fixture_{random.randint(10000, 99999)}"
    password = "Fixture!2345"
    token = post("/api/auth/register", {"username": user, "email": f"{user}@example.com",
                                        "password": password, "name": "Fixture"})["access_token"]
    birth = harness_profile()
    post("/api/profiles/save", {"profile_name": "Owner", "birth_details": birth,
                                "is_default": True}, token)

    responses = {}

    def keep(resp):
        url = resp.url
        if not url.startswith(API) or resp.status != 200:
            return
        path = url[len(API):].split("?")[0]
        key = f"{resp.request.method} {path}"
        if SKIP.search(path) or key in responses:
            return
        try:
            responses[key] = resp.json()
        except Exception:
            pass

    routes = harness_routes()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("response", keep)
        page.goto(f"{APP}/login")
        page.evaluate("localStorage.setItem('lang','en')")
        page.fill('input[type="text"]', user)
        page.fill('input[type="password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_timeout(4000)
        page.evaluate("localStorage.setItem('ui_mode','advanced')")
        for route in routes:
            page.goto(APP + route)
            page.wait_for_timeout(int(os.environ.get("SETTLE_MS", "7000")))
            print(f"{route:28s} {len(responses)} endpoints so far", file=sys.stderr)
        browser.close()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "recorded": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "chart": birth,
            "note": "Real responses for the owner's chart; see scripts/record_page_fixtures.py.",
            "responses": dict(sorted(responses.items())),
        }, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"{len(responses)} endpoints -> {OUT} ({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    main()
