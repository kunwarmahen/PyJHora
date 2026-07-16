"""The astrology package — split out of the old 8k-line astrology.py (§4).

Import surface is unchanged: `from astrology import AstrologyCompute,
DEFAULT_AYANAMSA, SUPPORTED_AYANAMSAS, SUPPORTED_VARGAS, SUPPORTED_DASHAS, ...`
all still resolve, so no caller needed editing.
"""
from .engine import *  # noqa: F401,F403  (constants, tables, helpers)
from .engine import __all__ as _engine_all
from .core import AstrologyCompute  # noqa: F401

__all__ = list(_engine_all) + ["AstrologyCompute"]
