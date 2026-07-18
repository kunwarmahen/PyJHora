"""Life Report background-job tests (§45).

Covers the DB-free core of the server-side job: assembling the finished markdown
from per-chapter state, the staleness reaper that stops an interrupted run from
wedging the UI on a spinner forever, and the serialized shape the polling client
depends on (progress counts, partial markdown).

The Mongo-backed helpers (create/cancel/run) are exercised in the deployment, not
here — these tests keep to the pure functions so they stay hermetic like the rest
of the suite (no live Mongo).
"""
from datetime import datetime, timedelta, timezone

import life_report


def _chapters():
    return [
        {"key": "personality", "title": "Personality & Self", "status": "done", "text": "  First.  "},
        {"key": "career", "title": "Career & Vocation", "status": "done", "text": "Second."},
        {"key": "wealth", "title": "Wealth & Resources", "status": "active", "text": ""},
        {"key": "health", "title": "Health", "status": "pending", "text": ""},
    ]


# ── Assembling the report ────────────────────────────────────────────────────

def test_assemble_uses_only_completed_chapters():
    md = life_report.assemble_markdown(_chapters())
    assert "## Personality & Self" in md
    assert "## Career & Vocation" in md
    # Not yet generated — must not leak an empty heading into the report.
    assert "Wealth & Resources" not in md
    assert "Health" not in md


def test_assemble_strips_and_orders():
    md = life_report.assemble_markdown(_chapters())
    assert md == "## Personality & Self\n\nFirst.\n\n## Career & Vocation\n\nSecond."


def test_assemble_empty_when_nothing_done():
    pending = [{"key": "a", "title": "A", "status": "pending", "text": ""}]
    assert life_report.assemble_markdown(pending) == ""


def test_assemble_skips_done_chapter_with_no_text():
    odd = [{"key": "a", "title": "A", "status": "done", "text": ""}]
    assert life_report.assemble_markdown(odd) == ""


# ── Staleness reaper ─────────────────────────────────────────────────────────

def _job(status, age_sec):
    ts = datetime.now(timezone.utc) - timedelta(seconds=age_sec)
    return {"status": status, "updated_at": ts, "created_at": ts}


def test_fresh_running_job_is_not_stale():
    assert life_report._is_stale(_job("running", 10)) is False


def test_long_running_job_is_stale():
    assert life_report._is_stale(_job("running", life_report.STALE_AFTER_SEC + 60)) is True


def test_finished_jobs_are_never_stale():
    # A done/error job is terminal; age must not reclassify it.
    assert life_report._is_stale(_job("done", 10 ** 6)) is False
    assert life_report._is_stale(_job("error", 10 ** 6)) is False


def test_running_job_without_timestamps_is_stale():
    # Nothing to prove it is alive, so don't let it block a restart forever.
    assert life_report._is_stale({"status": "running"}) is True


def test_naive_timestamps_are_treated_as_utc():
    # Mongo returns naive datetimes; a naive "just now" must not read as ancient.
    naive = datetime.now(timezone.utc).replace(tzinfo=None)
    assert life_report._is_stale({"status": "running", "updated_at": naive}) is False


# ── Serialized shape the client polls ────────────────────────────────────────

def test_serialize_reports_progress_and_partial_markdown():
    out = life_report._serialize({
        "_id": "abc123",
        "status": "running",
        "profile_id": "p1",
        "person_name": "Ravi",
        "chapters": _chapters(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    assert out["job_id"] == "abc123"
    assert out["status"] == "running"
    assert (out["done_count"], out["total"]) == (2, 4)
    # Partial markdown lets the page show finished chapters while the rest run.
    assert "## Career & Vocation" in out["markdown"]
    assert [c["status"] for c in out["chapters"]] == ["done", "done", "active", "pending"]


def test_serialize_tolerates_missing_fields():
    out = life_report._serialize({"_id": "x"})
    assert out["chapters"] == []
    assert (out["done_count"], out["total"]) == (0, 0)
    assert out["markdown"] == ""
    assert out["created_at"] and out["updated_at"]
