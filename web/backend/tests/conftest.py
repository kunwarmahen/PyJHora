"""Shared fixtures for the web-backend test suite (§3.2).

Adds the backend directory to `sys.path` so `import astrology` / `import main`
resolve when pytest is run from the repo root, and provides the two fixed charts
the golden tests pin plus an auth-bypassed FastAPI TestClient.
"""
import os
import sys

import pytest

# tests/ lives inside web/backend — put the backend dir on the path.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


# ── The two fixed reference charts ──────────────────────────────────────────
# Chart 1 is the owner's chart (1976-06-04 05:45:02, Aligarh), JHora-verified to
# the arc-minute in todo §26 with the app's matched defaults (True Chitra
# ayanamsa + mean nodes). Chart 2 is a second, independent chart used for the
# Ashtakoot pair and the determinism (order-independence) guard.
CHART1 = {
    "name": "Owner",
    "dob": "1976-06-04", "tob": "05:45:02", "place": "Aligarh",
    "latitude": 27.88, "longitude": 78.08, "timezone": 5.5,
}
CHART2 = {
    "name": "Partner",
    "dob": "1990-01-15", "tob": "14:30:00", "place": "Chennai",
    "latitude": 13.0827, "longitude": 80.2707, "timezone": 5.5,
}


def _compute_args(chart):
    """Map a BirthDetails-shaped dict to AstrologyCompute's positional kwargs."""
    return {
        "dob": chart["dob"], "tob": chart["tob"], "place": chart["place"],
        "lat": chart["latitude"], "lon": chart["longitude"], "tz": chart["timezone"],
    }


@pytest.fixture
def chart1():
    return dict(CHART1)


@pytest.fixture
def chart2():
    return dict(CHART2)


@pytest.fixture
def args1():
    return _compute_args(CHART1)


@pytest.fixture
def args2():
    return _compute_args(CHART2)


class MainThreadASGIClient:
    """A minimal sync HTTP client that drives the ASGI app on the *calling*
    (main) thread via `asyncio.run` + `httpx.ASGITransport`.

    Why not `fastapi.testclient.TestClient`? It runs `async def` handlers on a
    separate anyio portal thread. AstrologyCompute's `_set_ayanamsa` calls Swiss
    Ephemeris' `set_ayanamsa_mode`, which corrupts swe's process-global C state
    when invoked off the main thread (documented at astrology.py:103 — every
    later `swe.calc_ut` then gets `jd -0.001010 outside Moshier range`). Running
    the app on the main thread's event loop reproduces the real (uvicorn) setup,
    where every endpoint is `async def` and therefore runs on the main thread.
    """

    def __init__(self, app):
        self._app = app

    def _run(self, method, url, **kwargs):
        import asyncio
        import httpx

        async def _go():
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
                return await ac.request(method, url, **kwargs)

        return asyncio.run(_go())

    def get(self, url, **kwargs):
        return self._run("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._run("POST", url, **kwargs)


@pytest.fixture(scope="session")
def client():
    """ASGI client with auth bypassed, driven on the main thread.

    Does not enter the app lifespan, so no Mongo connection is opened — the smoke
    tests hit only the pure-compute astrology endpoints. The birth-chart route
    (which persists to Mongo) is covered with a stubbed collection.
    """
    import main

    main.app.dependency_overrides[main.get_current_user] = lambda: "test-user"
    # The public API v1 (§2.3) authenticates with get_api_user (API token); bypass
    # it the same way so the v1 smoke tests don't need a real token in Mongo.
    main.app.dependency_overrides[main.get_api_user] = lambda: "test-user"
    return MainThreadASGIClient(main.app)
