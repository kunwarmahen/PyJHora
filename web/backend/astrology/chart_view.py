"""LLM-safe chart shapes.

`house` now means the bhava everywhere in the compute layer, and the Kundali's
drawing coordinate — the 1-based sign whose cell a graha is painted in — is
`sign_num` (§65). Before that rename the coordinate *was* called `house`, and a
row read::

    "Sun": {"rasi": 3, "house": 4, "sign_name": "Cancer"}

which says "Sun in the 4th house" to anything that reads it, and is only ever
true for an Aries lagna. Two numbers, no lagna in sight, and the key literally
named `house`.

`sign_num` is unambiguous but still not something a model should reason from —
it is a coordinate, not a placement — so it is stripped at the AI boundary along
with any `rasi` a payload still carries.

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
# `house` is deliberately NOT here: since §65 it is always a real bhava.
LAYOUT_KEYS = ("rasi", "sign_num")


def _redundant_sign_int(key, value, siblings):
    """True for an integer sign index that a `*_name` sibling already spells out.

    `sign` next to `sign_name`, `lagna_sign` next to `lagna_sign_name`. The
    integer is ambiguous (0- or 1-based, depending on the payload) and the name
    is not, so the name wins and the number goes.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    if key in ("rasi", "sign_num"):
        return True
    if key == "sign":
        return "sign_name" in siblings
    return key.endswith("_sign") and f"{key}_name" in siblings


def sign_index(pos):
    """0-based sign of a compute-layer position dict, or None.

    Never derived from `house` — that is a bhava, and reading a sign out of it
    is the whole mistake this module exists to undo.
    """
    if not isinstance(pos, dict):
        return None
    if pos.get("sign_num") is not None:
        return (int(pos["sign_num"]) - 1) % 12
    if pos.get("rasi") is not None:
        return int(pos["rasi"]) % 12
    name = pos.get("sign_name")
    if name in ZODIAC_NAMES:
        return ZODIAC_NAMES.index(name)
    return None


def strip_layout(pos):
    """A copy of one position dict without the drawing-only sign numbers."""
    return {k: v for k, v in pos.items() if k not in LAYOUT_KEYS}


def sanitize(payload):
    """Deep-clean a payload of sign integers that read as house numbers.

    Drops `rasi`, `sign_num` and any redundant integer sign anywhere in the
    structure, and leaves `house` alone — it is a real bhava, counted by the
    compute layer itself.
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
