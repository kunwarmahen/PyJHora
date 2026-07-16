"""Shared LLM constants, enums and config (§4c split).

The module-level block of the old single-file llm_service.py, moved verbatim:
SITE_NAME, tool-loop limits, SYSTEM_PROMPT, ProviderType/LLMProvider and
ModelConfig. The provider + prompt mixins import from here.

`__all__` deliberately includes single-underscore names the moved bodies
reference by bare name.
"""
"""
Unified LLM service supporting multiple providers and models:
  - ollama            : local models served by Ollama (auto-discovered)
  - openai-compatible : any local/remote server exposing the OpenAI /v1 schema
                        (LM Studio, llama.cpp server, vLLM, text-generation-webui)
  - gemini            : Google Gemini API
  - openai            : OpenAI ChatGPT API

Each request is described by a ModelConfig (provider_type + model + optional
base_url + api_key). Legacy provider strings ("qwen"/"gemini"/"chatgpt") are
still accepted and mapped onto the new model so older clients keep working.
"""
import asyncio
import httpx
import json
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, AsyncGenerator
from enum import Enum

import tools as tool_registry

# Product/brand name surfaced to the model as the source of the chart data.
# Overridable via the SITE_NAME env var (kept in sync with the frontend brand).
SITE_NAME = os.getenv("SITE_NAME", "Jyotir AI")

# Agentic ("tool-call") mode tuning.
MAX_TOOL_ROUNDS = 6
# Cap on how many times the SAME tool may be re-executed (identical name + args)
# within one answer; beyond this the model gets a nudge to use what it has.
MAX_DUP_TOOL_CALLS = 3

# Streaming retry tuning. A stream that fails *before emitting any content* with a
# transient error (provider unreachable, 5xx/429, timeout) is retried from scratch;
# once real tokens have been sent we can't cleanly retry, so we don't.
MAX_STREAM_RETRIES = 2
STREAM_RETRY_BACKOFF = 1.0  # seconds, multiplied by the attempt number
_TRANSIENT_STREAM_MARKERS = (
    "cannot connect", "connection", "timed out", "timeout", "temporarily",
    "read error", "reset by peer", "502", "503", "504", "500", "429",
)


def _is_transient_stream_error(text: Optional[str]) -> bool:
    """Heuristic: does this first-chunk error string look retryable? The provider
    `_stream_*` methods yield a single error string (no content) when they fail at
    connect time, so we inspect that to decide whether a retry is worthwhile."""
    t = (text or "").lower()
    if not t.startswith("error"):
        return False
    return any(m in t for m in _TRANSIENT_STREAM_MARKERS)
TOOL_MODE_NOTE = (
    "Some chart sections may be omitted from the context above. Use the available "
    "tools to fetch any additional data you need — dasha periods, yogas, doshas, "
    "current transits, divisional (varga) charts, ashtakavarga, shadbala, panchanga "
    "— before answering. Fetch only what is relevant to the question, then give a "
    "specific, well-reasoned final answer that cites the chart factors behind every "
    "claim. Do not ask the user for more information; fetch it yourself."
)

SYSTEM_PROMPT = (
    "You are an expert Vedic (Jyotish) astrologer. Reason from classical Parashari "
    "principles and make your reasoning explicit, citing the chart factors behind "
    "every claim.\n\n"
    "Apply these rules when interpreting the chart provided:\n"
    "1. HOUSES (bhavas): judge a life area by its house, the house lord's placement "
    "and dignity, and planets occupying or aspecting it. Key significations — "
    "1st: self/body; 2nd: wealth/family/speech; 3rd: courage/siblings/effort; "
    "4th: home/mother/happiness; 5th: children/intellect/purva-punya; 6th: "
    "enemies/debt/disease; 7th: marriage/partnership; 8th: longevity/upheaval/"
    "occult; 9th: fortune/dharma/father; 10th: career/status/karma; 11th: gains/"
    "fulfilment; 12th: loss/expense/moksha.\n"
    "2. KARAKAS (significators): Sun=soul/father/authority, Moon=mind/mother, "
    "Mars=energy/siblings/property, Mercury=intellect/speech, Jupiter=wisdom/"
    "children/wealth, Venus=spouse/comfort, Saturn=longevity/discipline/karma, "
    "Rahu=ambition/foreign, Ketu=detachment/moksha. Weigh the natural karaka "
    "alongside the relevant house.\n"
    "3. DIGNITY: note exaltation, debilitation, own-sign, moolatrikona and "
    "friend/enemy signs — a strong lord empowers its house; a weak or afflicted "
    "lord undermines it.\n"
    "4. ASPECTS (drishti): all planets aspect the 7th from themselves; Mars also "
    "aspects 4th & 8th, Jupiter the 5th & 9th, Saturn the 3rd & 10th. Benefic "
    "aspects support, malefic aspects stress.\n"
    "5. YOGAS & DOSHAS: factor in the named yogas/doshas supplied; explain how a "
    "yoga's planets produce its result, and qualify doshas rather than alarming.\n"
    "6. TIMING: use the running Vimsottari dasha chain and current transits "
    "(gochara) to time events; a result manifests when promised by the natal "
    "chart AND activated by the dasha/transit.\n"
    "7. DIVISIONAL CHARTS (vargas): corroborate with the relevant varga — D9 for "
    "marriage/dharma, D10 for career, D7 for children, etc.\n"
    "8. ARUDHA PADAS: when supplied, use the Arudha Lagna (AL) for the *perceived* "
    "self — image, reputation, status and material manifestation (maya), as distinct "
    "from the actual Lagna (the real self); use the Upapada (UL) for the spouse and "
    "marriage. Contrast AL vs Lagna when a question is about how one is seen.\n\n"
    "Be specific to THIS chart, balanced and constructive (never fatalistic), and "
    "offer practical guidance and classical remedies where appropriate."
)


class ProviderType(str, Enum):
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai-compatible"
    GEMINI = "gemini"
    OPENAI = "openai"


class LLMProvider(str, Enum):
    """Legacy provider identifiers kept for backward compatibility."""
    QWEN = "qwen"
    GEMINI = "gemini"
    CHATGPT = "chatgpt"


# Legacy string -> new provider type
_LEGACY_MAP = {
    "qwen": ProviderType.OLLAMA,
    "ollama": ProviderType.OLLAMA,
    "gemini": ProviderType.GEMINI,
    "chatgpt": ProviderType.OPENAI,
    "openai": ProviderType.OPENAI,
    "openai-compatible": ProviderType.OPENAI_COMPATIBLE,
}


@dataclass
class ModelConfig:
    provider_type: ProviderType
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Optional per-request output cap. When set (from the user's Settings), it
    # overrides the per-call default at every provider payload site, so a user
    # whose answers get cut off can raise it. None = use the method default.
    max_tokens: Optional[int] = None


__all__ = [_n for _n in dir() if not _n.startswith('__')]
