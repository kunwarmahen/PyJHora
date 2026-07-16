"""Route-surface contract for main.py (§4b guard).

`main.py` carries ~160 routes but only a handful are exercised by the functional
smoke tests — so a mechanical refactor (splitting handlers into APIRouter
modules) had almost no safety net. This pins the whole surface instead: for every
route, its **method + path + parameters + request model**. Anything dropped,
renamed, re-verbed, moved to a different prefix, or given a different body model
fails here.

That's exactly the class of breakage a route split can cause, and it costs one
snapshot file rather than 160 hand-written request tests. It deliberately does
NOT assert behaviour — the golden/endpoint tests cover that.

If a route is added or intentionally changed, regenerate the snapshot:

    python -c "import json,main; \
        spec=main.app.openapi(); ..."   # see tests/README or the git history

and review the diff in the PR — the point is that the change is *deliberate*.
"""
import json
import os

import pytest

SNAPSHOT = os.path.join(os.path.dirname(__file__), "routes_snapshot.json")


def _current_surface():
    """The live route surface, in the same shape as the snapshot."""
    import main

    spec = main.app.openapi()
    snap = {}
    for path, ops in spec.get("paths", {}).items():
        for method, op in ops.items():
            if method.upper() in ("HEAD", "OPTIONS"):
                continue
            key = f"{method.upper()} {path}"
            params = sorted(
                f"{p.get('in')}:{p.get('name')}{'*' if p.get('required') else ''}"
                for p in op.get("parameters", []) or []
            )
            try:
                ref = op["requestBody"]["content"]["application/json"]["schema"].get("$ref", "")
                ref = ref.rsplit("/", 1)[-1]
            except Exception:
                ref = ""
            snap[key] = {"params": params, "body": ref}
    return snap


@pytest.fixture(scope="module")
def surface():
    return _current_surface()


@pytest.fixture(scope="module")
def pinned():
    with open(SNAPSHOT) as f:
        return json.load(f)


def test_no_routes_lost_or_added(surface, pinned):
    """Every pinned route still exists, and no route appeared unannounced."""
    missing = sorted(set(pinned) - set(surface))
    added = sorted(set(surface) - set(pinned))
    assert not missing, f"routes disappeared: {missing}"
    assert not added, (
        f"new routes not in the snapshot: {added} — regenerate tests/routes_snapshot.json "
        "if this is intentional"
    )


def test_route_signatures_unchanged(surface, pinned):
    """Each route keeps its parameters and request model."""
    drift = []
    for key, want in sorted(pinned.items()):
        got = surface.get(key)
        if got is None:
            continue  # covered by the missing-routes test
        if got["params"] != want["params"]:
            drift.append(f"{key}: params {got['params']} != {want['params']}")
        if got["body"] != want["body"]:
            drift.append(f"{key}: body {got['body']!r} != {want['body']!r}")
    assert not drift, "route signature drift:\n" + "\n".join(drift)


def test_surface_is_substantial(pinned):
    """Guard against the snapshot itself being emptied/regenerated to nothing."""
    assert len(pinned) >= 150, f"only {len(pinned)} routes pinned — snapshot looks truncated"
    # The astrology surface is the bulk of the app.
    astro = [k for k in pinned if "/api/astrology/" in k]
    assert len(astro) >= 100, f"only {len(astro)} astrology routes pinned"
