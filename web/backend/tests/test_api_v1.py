"""Public API v1 smoke tests (§2.3).

Exercises the token-authed, read-only `/api/v1/*` surface that the MCP server and
scripts consume: the discovery root, the tool catalog, and running a tool with
inline birth details (profile-id resolution needs Mongo and is covered by the
manual/integration path). Auth is bypassed in the `client` fixture.
"""
from tests.conftest import CHART1


def test_v1_index_is_public(client):
    r = client.get("/api/v1")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == "1"
    assert body["read_only"] is True
    assert "run_tool" in body["endpoints"]


def test_v1_tools_catalog(client):
    r = client.get("/api/v1/tools")
    assert r.status_code == 200, r.text
    tools = r.json()["tools"]
    names = {t["name"] for t in tools}
    assert "get_natal_chart" in names
    # Each entry carries the fields a client/MCP server needs.
    sample = next(t for t in tools if t["name"] == "get_natal_chart")
    for key in ("name", "label", "category", "description", "parameters"):
        assert key in sample


def test_v1_run_tool_inline_birth_details(client):
    r = client.post("/api/v1/tools/get_natal_chart",
                    json={"birth_details": CHART1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tool"] == "get_natal_chart"
    # get_natal_chart returns the D1 summary; chart 1 is a Taurus lagna.
    assert body["result"]["lagna"]["sign_name"] == "Taurus"


def test_v1_run_tool_with_args(client):
    r = client.post("/api/v1/tools/get_divisional_chart",
                    json={"birth_details": CHART1, "args": {"varga_factor": 9}})
    assert r.status_code == 200, r.text
    assert r.json()["result"].get("status") != "failed"


def test_v1_unknown_tool_400(client):
    r = client.post("/api/v1/tools/get_not_a_tool",
                    json={"birth_details": CHART1})
    assert r.status_code == 400, r.text


def test_v1_missing_birth_data_400(client):
    r = client.post("/api/v1/tools/get_natal_chart", json={})
    assert r.status_code == 400, r.text


# ── profile_id resolution (§72) ─────────────────────────────────────────────

def test_profile_id_resolution_can_actually_build_an_objectid():
    """`_resolve_birth_details` wraps `ObjectId(profile_id)` in a bare
    `except Exception` and reports the failure as "Invalid profile_id".

    `ObjectId` was not imported into `deps.py` after the §4 split, so that line
    raised NameError for *every* caller and the public API rejected every saved
    profile — with a message that blamed the caller's input. The convenience the
    whole `profile_id` parameter exists for (don't paste birth data into an MCP
    client) was gone, and nothing failed.

    A bare `except` around a name lookup can only be pinned from outside, so this
    checks the name resolves and that a well-formed id survives the call.
    """
    import deps
    from bson import ObjectId

    assert hasattr(deps, "ObjectId"), \
        "deps.ObjectId is missing — every profile_id resolves to 'Invalid profile_id'"
    assert deps.ObjectId is ObjectId
    # A real 24-hex id must construct without raising.
    assert str(deps.ObjectId("6aa2ebf3ec73ec3936f48e5b")) == "6aa2ebf3ec73ec3936f48e5b"


# ── birth-detail privacy (§90) ──────────────────────────────────────────────
# The §78 redaction sits where OUR model calls leave. /api/v1 is the other way
# out: an MCP client pulls the JSON into a model we can't see — almost always a
# hosted one — so the caller's Settings → AI choices apply to every response.

def test_v1_tool_result_withholds_birth_details_by_default(client):
    # No database in the fixture → no preferences → the default: withhold all.
    r = client.post("/api/v1/tools/get_saturn_transits",
                    json={"birth_details": CHART1})
    assert r.status_code == 200, r.text
    assert CHART1["dob"] not in r.text
    assert "[birth date withheld]" in r.text


def test_v1_tool_result_honours_the_users_opt_in(client, monkeypatch):
    import user_settings

    async def allow_all(_user):
        return {"ai_share_birth_date": "true", "ai_share_birth_time": "true",
                "ai_share_birth_place": "true"}
    monkeypatch.setattr(user_settings, "get_preferences", allow_all)
    r = client.post("/api/v1/tools/get_saturn_transits",
                    json={"birth_details": CHART1})
    assert r.status_code == 200, r.text
    assert CHART1["dob"] in r.text
    assert "withheld" not in r.text


def test_profile_listing_is_redacted_but_keeps_nickname_and_id():
    from llm.privacy import PrivacyPolicy, WITHHELD
    bd = {k: CHART1[k] for k in ("name", "dob", "tob", "place")}
    policy = PrivacyPolicy()
    policy.remember([{"profile_name": "Me", "birth_details": bd}])
    out = policy.redact_payload([{"id": "abc", "profile_name": "Me", **bd}])[0]
    # The full name is shown as the profile's nickname.
    assert out["id"] == "abc" and out["name"] == "Me" and out["profile_name"] == "Me"
    assert out["dob"] == WITHHELD["date"]
    assert out["tob"] == WITHHELD["time"]
    assert out["place"] == WITHHELD["place"]


def test_redact_payload_catches_labelled_lines_in_nested_strings():
    from llm.privacy import PrivacyPolicy, WITHHELD
    out = PrivacyPolicy().redact_payload(
        {"summary": "Time of Birth: 05:45:02\nLagna: Taurus"})
    assert out["summary"] == f"Time of Birth: {WITHHELD['time']}\nLagna: Taurus"
