"""Determinism / order-independence guard (§3.3).

`astrology.py` sets global engine state per request (ayanamsa, node type) and
resets it in a `finally`. That reset is load-bearing: if it ever regresses,
one chart's computation would leak settings into the next. This interleaves two
different charts and asserts each is bit-identical to computing it alone.
"""
from astrology import AstrologyCompute as A
from tests.conftest import _compute_args, CHART1, CHART2


def _fingerprint(result):
    return (
        result["lagna"]["sign_name"],
        result["lagna"]["degrees"],
        tuple((n, p["sign_name"], p["degrees"]) for n, p in sorted(result["planets"].items())),
    )


def test_interleaved_charts_are_order_independent():
    a1 = _compute_args(CHART1)
    a2 = _compute_args(CHART2)

    solo1 = _fingerprint(A.calculate_birth_chart(**a1))
    solo2 = _fingerprint(A.calculate_birth_chart(**a2))

    # Interleave with an explicit non-default ayanamsa on the second chart to
    # prove the per-request reset actually restores the default afterwards.
    A.calculate_birth_chart(**a2, ayanamsa="RAMAN")
    inter1 = _fingerprint(A.calculate_birth_chart(**a1))
    A.calculate_birth_chart(**a2, ayanamsa="KP")
    inter2 = _fingerprint(A.calculate_birth_chart(**a2))

    assert inter1 == solo1, "Chart 1 changed after computing Chart 2 — state leaked"
    assert inter2 == solo2, "Chart 2 not reproducible after an interleaved run"
