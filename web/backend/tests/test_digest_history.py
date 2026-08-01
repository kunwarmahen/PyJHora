"""Delivered digests in the reading history, and the caution layer.

Two reports drove this. First: the digest that arrives by email every morning
appeared nowhere in the app — only an in-app digest was ever saved — so the one
reading a user actually reads daily was the one they could never look back at.
Second: those digests were monotonous and never mentioned anything difficult,
because nothing in the payload was capable of saying a day was hard.

The tests below pin the two properties that make each fix hold: digests are
retained *separately* so they cannot evict chat history, and the caution list
gives today's signal priority over a months-long backdrop.
"""
import pytest

import digest_history
from astrology import compute_digests as cd
from config import settings


# ── Storage identity ────────────────────────────────────────────────────────

def test_digest_ids_are_distinguishable_from_conversation_ids():
    # The conversation endpoints route on this prefix, so a digest id must never
    # look like an ai_conversations ObjectId.
    assert digest_history.is_digest_id("dg_64b7f0c2e1a2b3c4d5e6f708")
    assert not digest_history.is_digest_id("64b7f0c2e1a2b3c4d5e6f708")
    assert not digest_history.is_digest_id("")
    assert not digest_history.is_digest_id(None)


def test_history_max_is_independent_of_the_ai_history_cap(monkeypatch):
    # The whole reason digests live in their own collection: a daily send across
    # several profiles must not be able to push out someone's chat threads.
    import conversations as convo

    monkeypatch.setattr(settings, "DIGEST_HISTORY_MAX", 30)
    monkeypatch.setenv("AI_HISTORY_MAX", "100")
    assert digest_history.history_max() == 30
    assert convo.history_max() == 100
    assert digest_history.COLLECTION != convo.COLLECTION


def test_history_max_falls_back_on_garbage(monkeypatch):
    monkeypatch.setattr(settings, "DIGEST_HISTORY_MAX", "lots")
    assert digest_history.history_max() == 120


def test_cadence_meta_routes_each_cadence_to_its_page():
    for cadence, route in (("daily", "/daily-digest"),
                           ("fortnightly", "/fortnightly-digest"),
                           ("monthly", "/monthly-digest")):
        assert digest_history.CADENCE_META[cadence]["route"] == route
    # An unknown cadence must still land somewhere sensible rather than 404.
    assert digest_history._meta("nonsense")["route"] == "/daily-digest"


# ── The stored body ─────────────────────────────────────────────────────────

def _block(**over):
    b = {
        "name": "Asha", "date": "2026-08-01",
        "narrative": "A steady day.",
        "highlights": ["Rahu Mahadasha, Saturn Bhukti"],
        "cautions": [{"text": "Sun transits the 8th — gochara: Unfavourable",
                      "scope": "today"}],
        "changes": ["Saturn has turned retrograde"],
    }
    b.update(over)
    return b


def test_render_includes_narrative_changes_and_cautions():
    text = digest_history.render_text(_block())
    assert "A steady day." in text
    assert "Saturn has turned retrograde" in text
    assert "gochara: Unfavourable" in text
    assert "Rahu Mahadasha" in text


def test_render_keeps_a_digest_whose_narrative_failed():
    # A thinner digest is still what the user was sent; a history that quietly
    # omits those days would misrepresent what they received.
    text = digest_history.render_text(_block(narrative=None))
    assert "Rahu Mahadasha" in text
    assert text.strip()


def test_render_is_empty_only_when_there_is_nothing_at_all():
    assert digest_history.render_text(
        {"narrative": None, "highlights": [], "cautions": [], "changes": []}) == ""


def test_serialize_reads_as_a_one_turn_thread():
    # The reading-restore path (useRestoreReading) takes the last assistant
    # message; a digest has to serialise into that exact shape or the History
    # page would need a special case for it.
    doc = {"_id": "abc", "cadence": "daily", "title": "Daily digest — 2026-08-01",
           "text": "A steady day.", "created_at": "2026-08-01T06:00:00+00:00",
           "model": "gemma", "provider": "ollama", "profile_id": "p1"}
    out = digest_history.serialize(doc)
    assert out["id"] == "dg_abc"
    assert out["route"] == "/daily-digest"
    assert out["kind"] == "digest"
    assert [m["role"] for m in out["messages"]] == ["user", "assistant"]
    assert out["messages"][-1]["content"] == "A steady day."
    assert out["messages"][-1]["model"] == "gemma"


def test_list_item_matches_the_conversation_list_shape():
    # The History page renders both from one list, so the keys must line up.
    import conversations as convo

    doc = {"_id": "abc", "cadence": "monthly", "title": "Monthly digest",
           "narrative": "x" * 400, "created_at": "2026-08-01T06:00:00+00:00",
           "profile_id": "p1", "delivered": {"email": True}}
    item = digest_history._list_item(doc)
    for key in ("id", "profile_id", "title", "source", "kind", "route", "label",
                "preview", "created_at", "updated_at"):
        assert key in item
    assert item["source"] in convo.SOURCE_META
    assert len(item["preview"]) <= 160
    assert item["delivered"]["email"] is True


def test_digest_readings_are_cascade_deleted_with_the_account():
    # Filed under the user, so account deletion has to take them with it.
    import admin as admin_service

    assert admin_service.USER_COLLECTIONS["digest_readings"] == "user_id"


# ── Cautions: the difficult side of a digest ────────────────────────────────

def _gochara(*rows):
    return {"status": "success", "results": list(rows)}


def _row(planet, house, tone, obstructed_by=()):
    return {"planet": planet, "house_from_moon": house, "tone": tone,
            "obstructed_by": list(obstructed_by)}


def test_unfavourable_gochara_becomes_a_caution_in_the_classical_wording():
    lines = cd._gochara_cautions(_gochara(_row("Saturn", 8, "bad")))
    assert len(lines) == 1
    assert "gochara: Unfavourable" in lines[0]["text"]
    assert "8th" in lines[0]["text"]


def test_vedha_obstruction_is_reported_and_explained():
    lines = cd._gochara_cautions(
        _gochara(_row("Jupiter", 9, "caution", obstructed_by=["Ketu"])))
    text = lines[0]["text"]
    assert "vedha" in text
    assert "Ketu" in text
    # The classical phrase alone means nothing to a reader — it must be unpacked.
    assert "checked, not delivered" in text


def test_favourable_transits_never_produce_a_caution():
    assert cd._gochara_cautions(_gochara(_row("Jupiter", 9, "good"))) == []


def test_fast_inner_planets_are_left_out():
    # Mercury/Venus verdicts churn without saying much.
    assert cd._gochara_cautions(_gochara(_row("Mercury", 8, "bad"))) == []
    assert cd._gochara_cautions(_gochara(_row("Venus", 8, "bad"))) == []


def test_slow_grahas_are_tagged_standing_and_fast_ones_today():
    lines = cd._gochara_cautions(
        _gochara(_row("Saturn", 8, "bad"), _row("Moon", 8, "bad")))
    by_planet = {("Saturn" if "Saturn" in c["text"] else "Moon"): c["scope"]
                 for c in lines}
    assert by_planet["Saturn"] == "standing"
    assert by_planet["Moon"] == "today"


def test_skip_planets_prevents_saying_the_same_transit_twice():
    # Saturn in the 4th is already reported as Ardhashtama Sani; repeating it as a
    # bare gochara verdict wastes one of only four caution slots.
    rows = _gochara(_row("Saturn", 4, "bad"), _row("Sun", 8, "bad"))
    assert len(cd._gochara_cautions(rows)) == 2
    assert len(cd._gochara_cautions(rows, skip_planets={"Saturn"})) == 1


def test_todays_signal_always_survives_the_cap():
    # The anti-monotony property. Slow grahas are the most "significant" and would
    # otherwise fill every slot every day for months, leaving nothing that
    # distinguishes this morning from yesterday's.
    standing = [{"text": f"slow-{i}", "scope": "standing"} for i in range(6)]
    today = [{"text": f"fast-{i}", "scope": "today"} for i in range(3)]
    picked = cd._pick_cautions(standing + today)
    assert len(picked) == cd._MAX_CAUTIONS
    assert sum(1 for c in picked if c["scope"] == "today") >= 2
    assert sum(1 for c in picked if c["scope"] == "standing") <= cd._MAX_STANDING_CAUTIONS


def test_backdrop_still_gets_through_when_today_is_quiet():
    picked = cd._pick_cautions([{"text": "slow", "scope": "standing"}])
    assert [c["text"] for c in picked] == ["slow"]


def test_no_cautions_are_invented_from_an_empty_day():
    assert cd._pick_cautions([]) == []
    assert cd._gochara_cautions(None) == []
    assert cd._gochara_cautions({"status": "failed"}) == []


def test_ashtama_and_ardhashtama_sani_are_named():
    # Saturn's 4th and 8th from the Moon had no representation at all before —
    # they were reported in the same neutral tone as any other transit.
    assert cd._SANI_FROM_MOON[8][0] == "Ashtama Sani"
    assert cd._SANI_FROM_MOON[4][0] == "Ardhashtama Sani"
    # Sade-Sati's own houses stay out of this table — they're reported separately.
    for house in (12, 1, 2):
        assert house not in cd._SANI_FROM_MOON


def test_avoid_windows_are_the_classical_trio():
    panch = {"rahu_kalam": {"start": "09:00", "end": "10:30"},
             "yamaganda": {"start": "13:00", "end": "14:30"},
             "gulika": {"start": "06:00", "end": "07:30"}}
    windows = cd._avoid_windows(panch)
    assert [w["name"] for w in windows] == ["Rahu Kalam", "Yamaganda", "Gulika Kalam"]


def test_avoid_windows_skips_anything_the_engine_could_not_compute():
    assert cd._avoid_windows({"rahu_kalam": {}}) == []
    assert cd._avoid_windows(None) == []


@pytest.mark.parametrize("n,want", [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"),
                                    (8, "8th"), (11, "11th"), (12, "12th")])
def test_ordinals_read_naturally(n, want):
    assert cd._ordinal(n) == want


# ── End to end through the real engine ──────────────────────────────────────

def test_daily_digest_carries_cautions_and_avoid_windows(args1):
    d = cd.AstrologyCompute.get_daily_digest(**args1, date="2026-08-01")
    assert d["status"] == "success"
    # Structure, not content: which transits are unfavourable on a given day is
    # the engine's business, but the fields must always be present and shaped.
    assert isinstance(d["cautions"], list)
    assert all({"text", "scope"} <= set(c) for c in d["cautions"])
    assert all(c["scope"] in ("today", "standing") for c in d["cautions"])
    assert len(d["cautions"]) <= cd._MAX_CAUTIONS
    assert d["avoid_windows"] and d["avoid_windows"][0]["name"] == "Rahu Kalam"
    assert any(h.startswith("Avoid for anything new:") for h in d["highlights"])


def test_period_digest_carries_cautions(args1):
    d = cd.AstrologyCompute.get_monthly_digest(**args1, date="2026-08-01")
    assert d["status"] == "success"
    assert isinstance(d["cautions"], list)
    assert all({"text", "scope"} <= set(c) for c in d["cautions"])


def test_avoid_line_is_shared_sky_not_personal():
    # It depends only on the date and place, so a family digest must print it once
    # rather than repeating it under every name.
    import digest as digest_service

    sky, personal = digest_service._split_highlights(
        ["Avoid for anything new: Rahu Kalam 09:00–10:30",
         "Rahu Mahadasha, Saturn Bhukti"])
    assert sky == ["Avoid for anything new: Rahu Kalam 09:00–10:30"]
    assert personal == ["Rahu Mahadasha, Saturn Bhukti"]
