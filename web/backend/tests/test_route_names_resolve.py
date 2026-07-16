"""Every route handler's global references must actually resolve (§4b guard).

The §4b split moved ~160 handlers out of main.py into routes/* modules that pull
shared helpers in via `from deps import *`. That import silently skips
underscore-prefixed names, so a handler calling `_enforce_rate_limit(...)` would
import fine and only blow up with NameError *when that route is first hit* —
and only 16 of the 160 routes have functional tests.

Star imports also defeat pyflakes' static undefined-name analysis, so this closes
the gap at runtime: for every route handler (and any nested function inside it),
disassemble the code object, collect every LOAD_GLOBAL, and assert the name
resolves in the handler's own module globals or builtins.

This is cheap, needs no DB/LLM, and covers the whole surface.
"""
import builtins
import dis
import types

import pytest


def _code_objects(code):
    """The handler's code object plus every nested one (inner defs, lambdas,
    comprehensions) — a NameError can hide in any of them."""
    yield code
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            yield from _code_objects(const)


def _global_loads(func):
    """Names the function (and its nested code) loads from module globals."""
    names = set()
    for code in _code_objects(func.__code__):
        for ins in dis.get_instructions(code):
            if ins.opname in ("LOAD_GLOBAL", "LOAD_NAME"):
                nm = ins.argval
                if isinstance(nm, str):
                    names.add(nm)
    return names


def _endpoints():
    import main

    out = []
    for r in main.app.routes:
        fn = getattr(r, "endpoint", None)
        if fn is None or not hasattr(fn, "__code__"):
            continue
        path = getattr(r, "path", "?")
        methods = ",".join(sorted(getattr(r, "methods", []) or []))
        out.append((f"{methods} {path}", fn))
    return out


def test_endpoints_discovered():
    eps = _endpoints()
    assert len(eps) >= 150, f"only {len(eps)} endpoints found — discovery looks broken"


@pytest.mark.parametrize("label,fn", _endpoints(), ids=lambda v: v if isinstance(v, str) else "")
def test_handler_globals_resolve(label, fn):
    """No handler references a global that isn't importable in its module."""
    g = fn.__globals__
    missing = sorted(
        n for n in _global_loads(fn)
        if n not in g and not hasattr(builtins, n)
    )
    assert not missing, (
        f"{label} ({fn.__module__}.{fn.__name__}) references undefined globals: "
        f"{missing} — likely a helper not exported by `from deps import *`"
    )
