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
