"""Did this land? — the loop from a prediction back to what happened (§68.7).

The point of this feature is not the widget; it is that the app finally has an
evaluation signal at all. So these tests pin the parts that would silently
corrupt that signal rather than fail loudly:

  * the hit rate must not count predictions whose window hasn't closed,
  * a partial hit must not be promoted to a full one,
  * an outcome must survive the reading it judges being pruned away, and
  * what reaches the model must be labelled as the *user's report* and must
    never include an unsettled verdict.

Test the class, not the instance: the verdict vocabulary is swept rather than
spot-checked, so a fifth verdict added next year fails here instead of quietly
falling out of the summary and the prompt.
"""
import asyncio

import pytest

import admin as admin_service
import outcomes
import tools as tool_registry
from llm.prompts import PromptsMixin


class _Prompts(PromptsMixin):
    pass


def _row(verdict, **kw):
    base = {"verdict": verdict, "label": "Ask Astrologer", "source": "astrologer",
            "title": "Career in 2025", "reading_date": "2025-01-04T10:00:00+00:00"}
    base.update(kw)
    return base


# ── The vocabulary ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("verdict", outcomes.VERDICTS)
def test_every_verdict_normalizes_and_has_a_phrase(verdict):
    """A verdict the API accepts but the prompt can't put into words would reach
    the model as a bare enum. Sweep, don't spot-check."""
    assert outcomes.normalize_verdict(verdict) == verdict
    assert outcomes.normalize_verdict(verdict.upper()) == verdict
    assert outcomes._VERDICT_PHRASE.get(verdict)


def test_unknown_verdict_is_rejected():
    for bad in ("maybe", "", None, "up"):
        assert outcomes.normalize_verdict(bad) is None


def test_settled_is_every_verdict_except_too_early():
    # The one rule the whole hit rate rests on.
    assert set(outcomes.SETTLED) == set(outcomes.VERDICTS) - {"not_yet"}


# ── The hit rate ────────────────────────────────────────────────────────────

def test_unsettled_outcomes_are_excluded_from_the_rate():
    s = outcomes.summarize([_row("happened"), _row("not_yet"), _row("not_yet")])
    assert s["total"] == 3
    assert s["settled"] == 1
    assert s["hit_rate"] == 100  # not 33 — two of these have not happened *yet*


def test_partial_hits_count_as_half_not_whole():
    s = outcomes.summarize([_row("happened"), _row("partly")])
    assert s["hit_rate"] == 75


def test_rate_is_none_when_nothing_has_settled():
    s = outcomes.summarize([_row("not_yet")])
    assert s["hit_rate"] is None
    assert s["counts"]["not_yet"] == 1


def test_summary_counts_every_verdict_key_even_at_zero():
    s = outcomes.summarize([])
    assert set(s["counts"]) == set(outcomes.VERDICTS)
    assert s["total"] == 0 and s["settled"] == 0 and s["hit_rate"] is None


def test_by_source_splits_the_record_per_tool():
    s = outcomes.summarize([_row("happened"), _row("didnt", label="Muhurta")])
    assert s["by_source"]["Ask Astrologer"]["happened"] == 1
    assert s["by_source"]["Muhurta"]["didnt"] == 1


# ── The snapshot: an outcome outlives its reading ───────────────────────────

def test_snapshot_captures_what_was_judged():
    """`AI_HISTORY_MAX` prunes readings continuously. Without this snapshot the
    track record would erase itself on the user's 101st reading."""
    reading = {
        "source": "astrologer", "label": "Ask Astrologer", "kind": "reading",
        "title": "Career in 2025", "created_at": "2025-01-04T10:00:00+00:00",
        "messages": [{"role": "user", "content": "will I move?"},
                     {"role": "assistant", "content": "A change of city is likely."}],
    }
    snap = outcomes.snapshot_of(reading)
    assert snap["title"] == "Career in 2025"
    assert snap["reading_date"] == "2025-01-04T10:00:00+00:00"
    assert "change of city" in snap["excerpt"]


def test_snapshot_excerpt_is_capped():
    snap = outcomes.snapshot_of(
        {"messages": [{"role": "assistant", "content": "x" * 5000}]})
    assert len(snap["excerpt"]) == outcomes.EXCERPT_CHARS


def test_snapshot_survives_a_reading_with_no_answer():
    snap = outcomes.snapshot_of({"title": "Empty"})
    assert snap["excerpt"] == "" and snap["title"] == "Empty"


def test_outcomes_are_registered_for_cascade_delete():
    # Belt and braces over tests/test_admin.py's registry sweep: this collection
    # deliberately outlives the readings it points at, so it can only be cleaned
    # up from here.
    assert admin_service.USER_COLLECTIONS[outcomes.COLLECTION] == "user_id"


# ── What the model is told ──────────────────────────────────────────────────

def test_for_ai_withholds_unsettled_verdicts(monkeypatch):
    rows = [_row("happened", note="Moved to Pune", outcome_date="2025-06-01",
                 dasha={"maha": "Jupiter", "bhukti": "Saturn"}),
            _row("not_yet", title="Marriage in 2030")]

    async def fake_list(user_id, profile_id=None, verdict=None):
        return rows

    monkeypatch.setattr(outcomes, "list_for_user", fake_list)
    out = asyncio.run(outcomes.for_ai("u"))
    assert len(out) == 1
    row = out[0]
    assert row["user_reported"] == "confirmed this happened"
    assert row["in_their_words"] == "Moved to Pune"
    assert row["running_then"] == "Jupiter/Saturn"
    assert row["read_on"] == "2025-01-04"


def test_track_record_renders_as_testimony_not_chart_data():
    ctx = {"today": "2026-09-10", "birth_details": {}, "lagna": {}, "moon_sign": {},
           "sun_sign": {}, "planetary_positions": {},
           "track_record": [{"reading": "Ask Astrologer: Career in 2025",
                             "read_on": "2025-01-04",
                             "user_reported": "confirmed this happened",
                             "happened_on": "2025-06-01",
                             "running_then": "Jupiter/Saturn",
                             "in_their_words": "Moved to Pune"}]}
    block = _Prompts()._render_context_block(ctx)
    assert "HOW EARLIER READINGS TURNED OUT" in block
    # It must be flagged as the user's report — a model handed these among the
    # ephemeris lines will otherwise treat them as computed facts.
    assert "NOT chart data" in block
    assert "Moved to Pune" in block and "Jupiter/Saturn" in block
    # And it must not invite the model to advertise its own accuracy.
    assert "Never cite it as proof" in block


def test_context_block_omits_the_section_when_nothing_is_recorded():
    ctx = {"today": "2026-09-10", "birth_details": {}, "lagna": {}, "moon_sign": {},
           "sun_sign": {}, "planetary_positions": {}}
    assert "HOW EARLIER READINGS TURNED OUT" not in _Prompts()._render_context_block(ctx)


# ── The AI tool ─────────────────────────────────────────────────────────────

def test_tool_says_so_when_there_is_no_track_record():
    """"Success with nothing in it" is the shape a dead feature takes — and here
    it is also the shape of a model inventing a track record. Say it out loud."""
    r = tool_registry._reading_outcomes({}, "TRUE_CITRA")
    assert r["count"] == 0
    assert "Do not claim a track record" in r["note"]


def test_tool_serves_what_the_endpoint_injected():
    bd = {"_outcomes": [{"reading": "Muhurta: 12 Jan", "user_reported": "says this did NOT happen"}]}
    r = tool_registry._reading_outcomes(bd, "TRUE_CITRA")
    assert r["count"] == 1 and r["outcomes"] == bd["_outcomes"]


def test_tool_is_discoverable_by_the_model():
    # A tool the model can't know exists is a tool that never runs.
    assert "get_reading_outcomes" in tool_registry.ALWAYS_TOOLS
    names = [t["name"] for t in tool_registry.tool_catalog()]
    assert "get_reading_outcomes" in names


# ── The injection every tool path must do ───────────────────────────────────

def test_every_tool_running_path_hangs_the_user_rows_on_birth_details():
    """The "Your data" tools (`get_journal_entries`, `get_reading_outcomes`) read
    Mongo, and `tools.dispatch` is synchronous — so the *route* has to pre-fetch
    the rows onto `birth_details` before running the loop.

    A route that forgets returns `{"count": 0, "entries": []}`: a 200, no log, no
    failing test, and a tool that has been dead since the day it shipped. That is
    exactly what happened to `get_journal_entries` on the non-streaming
    `/api/astrology/ask` — the injection was inline in the streaming handler and
    nowhere else. This pins the class rather than those two routes: any module
    that runs a tool must also call the shared fetch.
    """
    import os
    import re

    routes_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "routes")
    RUNS_TOOLS = re.compile(r"\b(?:tool_registry\.dispatch|run_tool_loop)\s*\(")
    offenders = []
    for fname in sorted(os.listdir(routes_dir)):
        if not fname.endswith(".py"):
            continue
        src = open(os.path.join(routes_dir, fname)).read()
        if RUNS_TOOLS.search(src) and "attach_user_feedback" not in src:
            offenders.append(fname)
    assert not offenders, (
        "route modules that run AI tools without pre-fetching the user's own rows "
        "(the Your-data tools answer empty there): " + ", ".join(offenders))
