"""The claim-check switch and the admin report layer (§68.1).

DB-free, like `test_admin.py`: everything here is the parts that decide *whether*
a check runs and *what shape* its record takes, which are the parts a deploy can
get wrong silently. The Mongo reads/writes themselves are exercised in the
deployment.
"""
import asyncio

import claim_reports
import runtime_config
from config import settings


# ── The switch: env default, console override ───────────────────────────────

def test_env_sets_the_default(monkeypatch):
    monkeypatch.setattr(settings, "CLAIM_CHECK_MODE", "annotate")
    assert runtime_config.defaults()["claim_check_mode"] == "annotate"


def test_a_typo_in_the_deploy_secret_cannot_stop_the_app(monkeypatch):
    """A bad env value falls back rather than raising — the same rule the digest
    narrative style follows, and for the same reason."""
    monkeypatch.setattr(settings, "CLAIM_CHECK_MODE", "verfiy")
    assert runtime_config.defaults()["claim_check_mode"] == \
        runtime_config.DEFAULT_CLAIM_CHECK_MODE


def test_off_is_reachable_from_the_env(monkeypatch):
    """The capability must be switchable off without a code change."""
    monkeypatch.setattr(settings, "CLAIM_CHECK_MODE", "off")
    assert runtime_config.defaults()["claim_check_mode"] == "off"


def test_the_console_can_only_set_a_known_mode():
    coerce = runtime_config.FIELDS["claim_check_mode"][1]
    assert coerce("LOG") == "log"
    for bad in ("", "yes", "true", "verify!"):
        try:
            coerce(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} was accepted as a mode")


def test_every_mode_the_console_offers_is_one_the_guard_implements():
    """Two lists that must agree: the console renders `CLAIM_CHECK_MODES` and the
    guard branches on `claim_check.MODES`. Drift here is a dead option in a
    dropdown — the §52 failure in miniature."""
    import claim_check
    assert set(runtime_config.CLAIM_CHECK_MODES) == set(claim_check.MODES)


def test_mode_falls_back_to_the_env_when_the_database_is_unreachable(monkeypatch):
    """A Mongo hiccup must not silently turn the checker off."""
    monkeypatch.setattr(settings, "CLAIM_CHECK_MODE", "annotate")

    async def boom():
        raise RuntimeError("no database")

    monkeypatch.setattr(runtime_config, "get", boom)
    assert asyncio.run(claim_reports.mode()) == "annotate"


# ── The report's shape ──────────────────────────────────────────────────────

def test_triage_states_are_closed_sets():
    assert claim_reports.STATUSES[0] == "open"
    # "checker" closes the loop back onto the rules themselves: the reading was
    # right and the check was wrong. Without it, tuning has no signal.
    assert "checker" in claim_reports.VERDICTS


def test_model_ids_are_key_safe():
    """Mongo forbids dots in field names and every model id has one, so a
    by-model counter would fail the write and lose the whole day's stats."""
    assert "." not in claim_reports._key("gemma3:4b-it-q4_K_M")
    assert "." not in claim_reports._key("gpt-4.1-mini")


def test_the_two_rates_answer_different_questions():
    """`flagged_rate` is how often the model contradicted its own chart (measured
    before the retry — the quality signal). `unresolved_rate` is how often that
    reached a reader (whether the guard is working). Collapsing them into one
    number hides either the model's error rate or the guard's value."""
    summary = asyncio.run(claim_reports.summary(days=1))
    assert "flagged_rate" in summary and "unresolved_rate" in summary
    assert "flagged_readings" in summary["totals"]
    assert "unresolved_readings" in summary["totals"]


def test_recording_never_raises_without_a_database():
    """This runs on the path about to return a real answer to a real reader; a
    logging failure must not cost them the answer."""
    report = {"claims": 3, "checked": 3, "contradictions": [{"kind": "lordship"}]}
    assert asyncio.run(claim_reports.record(
        report, username="u", source="ask", model="m")) is None
