"""FastAPI route smoke tests (§3.2).

Hits each pure-compute `/api/astrology/*` route with the auth dependency
overridden and asserts a 200 plus the expected top-level keys — catching
route/serialization regressions that the direct-call golden tests can't see
(wrong response model, a renamed field, a broken query-param binding).

Auth is bypassed in the `client` fixture; the app lifespan is never entered, so
no Mongo connection is required (these routes never touch the database).
"""
from tests.conftest import CHART1, CHART2


def _post(client, path, chart, **params):
    return client.post(f"/api/astrology/{path}", json=chart, params=params)


class _FakeInsertResult:
    inserted_id = "test-chart-id"


class _FakeCollection:
    async def insert_one(self, _doc):
        return _FakeInsertResult()


class _FakeDB:
    def __getitem__(self, _name):
        return _FakeCollection()


def test_birth_chart(client, monkeypatch):
    # The birth-chart route persists the chart to Mongo; stub the collection so
    # the test stays hermetic (no live DB) while still exercising the full route.
    import database
    monkeypatch.setattr(database, "database", _FakeDB())
    r = _post(client, "birth-chart", CHART1)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["lagna"]["sign_name"] == "Taurus"
    assert "planets" in body and "d9_chart" in body


def test_dhasa(client):
    r = _post(client, "dhasa", CHART1)
    assert r.status_code == 200, r.text
    assert "dasha_sequence" in r.json()


def test_panchanga(client):
    r = client.get("/api/astrology/panchanga", params={
        "place": "Aligarh", "lat": 27.88, "lon": 78.08, "tz": 5.5,
        "date": "2026-07-16",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    for limb in ("tithi", "nakshatra", "yoga", "karana", "vaara"):
        assert limb in body


def test_transit(client):
    r = _post(client, "transit", CHART1)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "planets" in body
    # §2.4: the bindu annotation is present on the wire.
    assert "bindu_strength" in body["planets"]["Saturn"]


def test_ashtakavarga(client):
    r = _post(client, "ashtakavarga", CHART1)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["sarva"]) == 12
    assert body["sarva_total"] == 337


def test_chart_details(client):
    r = _post(client, "chart-details", CHART1)
    assert r.status_code == 200, r.text


def test_doshas(client):
    r = _post(client, "doshas", CHART1)
    assert r.status_code == 200, r.text


def test_yogas(client):
    r = _post(client, "yogas", CHART1)
    assert r.status_code == 200, r.text


def test_compatibility(client):
    payload = {
        "male_dob": CHART1["dob"], "male_tob": CHART1["tob"], "male_place": CHART1["place"],
        "male_latitude": CHART1["latitude"], "male_longitude": CHART1["longitude"],
        "male_timezone": CHART1["timezone"],
        "female_dob": CHART2["dob"], "female_tob": CHART2["tob"], "female_place": CHART2["place"],
        "female_latitude": CHART2["latitude"], "female_longitude": CHART2["longitude"],
        "female_timezone": CHART2["timezone"],
    }
    r = client.post("/api/astrology/compatibility", json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["total_score"] == 27.0


def test_marriage_workspace(client):
    payload = {
        "male_details": CHART1,
        "female_details": CHART2,
    }
    r = client.post("/api/astrology/marriage-workspace", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "success"
    assert body["seventh_house"]["male"]["seventh_lord"] == "Mars"


def test_nadi(client):
    r = _post(client, "nadi", CHART1, gender=0)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "success"
    assert len(body["karakas"]) == 9
    assert body["spouse_karaka"] == "Venus"
    kb = {k["planet"]: k for k in body["karakas"]}
    assert kb["Venus"]["sign_name"] == "Taurus"
    assert set(kb["Venus"]["conjunct"]) == {"Sun", "Mercury"}
    assert len(body["themes"]) == 9
