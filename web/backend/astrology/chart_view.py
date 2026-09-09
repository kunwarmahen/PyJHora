"""LLM-safe chart shapes.

The compute layer speaks the *renderer's* language: `rasi` is the 0-based sign
index and `house` is that index + 1 — i.e. the 1-based SIGN number whose cell a
Kundali component draws the planet in. Neither is a bhava.

Handed to a model unchanged, a row like::

    "Sun": {"rasi": 3, "house": 4, "sign_name": "Cancer"}

reads as "Sun in the 4th house", which is only ever true for an Aries lagna —
and the 0-based `rasi` is off by one against every convention the model knows
(Cancer is rasi 4 in the books, not 3). Both numbers then out-argue the truth,
because there are two of them and no lagna in sight.

So nothing reaches a prompt with those keys. `chart_positions` replaces them
with the real whole-sign house counted from that chart's own Lagna (a varga's
houses are counted from the varga's Lagna, not the D1's), and `strip_layout`
drops them from payloads that already carry their own `house_from_*` counts.

A bare integer `sign` is the same disease under another name, and worse: it is
0-based in most payloads (`special_lagnas`, `upagrahas`, `varnadas`, `muntha`,
`lagna_sign`) but 1-based in the arudhas, so the model cannot even learn one
rule for it. Every one of those rows already carries `sign_name`, and most a
real `house` too, so `sanitize` drops the integer wherever a name sits beside
it — deep, over any payload shape, from `tools.dispatch`, which makes it the
default for tools that do not yet exist.
"""
from .engine import ZODIAC_NAMES

# Keys that mean "which sign cell to draw this in", not "which bhava".
LAYOUT_KEYS = ("rasi", "house")


def _redundant_sign_int(key, value, siblings):
    """True for an integer sign index that a `*_name` sibling already spells out.

    `sign` next to `sign_name`, `lagna_sign` next to `lagna_sign_name`. The
    integer is ambiguous (0- or 1-based, depending on the payload) and the name
    is not, so the name wins and the number goes.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    if key == "rasi":
        return True
    if key == "sign":
        return "sign_name" in siblings
    return key.endswith("_sign") and f"{key}_name" in siblings


def sign_index(pos):
    """0-based sign of a compute-layer position dict, or None."""
    if not isinstance(pos, dict):
        return None
    if pos.get("rasi") is not None:
        return int(pos["rasi"]) % 12
    if pos.get("house") is not None:
        return (int(pos["house"]) - 1) % 12
    name = pos.get("sign_name")
    if name in ZODIAC_NAMES:
        return ZODIAC_NAMES.index(name)
    return None


def strip_layout(pos):
    """A copy of one position dict without the drawing-only sign numbers."""
    return {k: v for k, v in pos.items() if k not in LAYOUT_KEYS}


def sanitize(payload):
    """Deep-clean a payload of sign integers that read as house numbers.

    Drops `rasi` and any redundant integer sign anywhere in the structure, and
    leaves `house` alone — by the time a payload reaches here its `house` is a
    real bhava, either because the compute already counted it (sphutas, sahams,
    KP, Muntha, transits) or because `chart_positions` did.
    """
    if isinstance(payload, dict):
        return {k: sanitize(v) for k, v in payload.items()
                if not _redundant_sign_int(k, v, payload)}
    if isinstance(payload, list):
        return [sanitize(v) for v in payload]
    return payload


def strip_layout_all(positions):
    """Same, over a {name: position} map. For payloads that already carry their
    own house counts (transits: house_from_lagna / _moon / _al / _ul)."""
    return {name: strip_layout(pos) for name, pos in (positions or {}).items()}


def chart_positions(lagna, planets):
    """Reshape one chart (its lagna + planets) for the LLM.

    Returns ``{"house_system", "lagna", "planets"}`` where every `house` is the
    whole-sign bhava counted from `lagna` — 1 for the Lagna's own sign — and the
    layout keys are gone.
    """
    lagna = lagna or {}
    asc = sign_index(lagna)
    asc_name = lagna.get("sign_name") or (ZODIAC_NAMES[asc] if asc is not None else "?")

    def counted(pos):
        out = strip_layout(pos)
        sign = sign_index(pos)
        if asc is not None and sign is not None:
            out["house"] = ((sign - asc) % 12) + 1
        return out

    return {
        "house_system": (
            f"Whole-sign houses counted from THIS chart's own Lagna in {asc_name}, "
            f"so {asc_name} is house 1. Each planet's \"house\" below is already "
            "counted — use it as given, do not re-derive it from the sign."
        ),
        "lagna": counted(lagna),
        "planets": {name: counted(pos) for name, pos in (planets or {}).items()},
    }
