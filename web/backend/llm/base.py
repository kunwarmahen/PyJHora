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
  - gemini            : Google Gemini API (an AI Studio key is a Gemini key)
  - openai            : OpenAI ChatGPT API
  - openrouter        : OpenRouter — one key, hundreds of hosted models

Each request is described by a ModelConfig (provider_type + model + optional
base_url + api_key). Legacy provider strings ("qwen"/"gemini"/"chatgpt") are
still accepted and mapped onto the new model so older clients keep working.
"""
import asyncio
import httpx
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, AsyncGenerator
from enum import Enum

from fastapi import HTTPException

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

# A local model that cannot get the GPU is a *capacity* failure, not a plain
# outage: the server is up and answering, it just has nowhere to put the weights
# (another process — say a training run — holds the VRAM). It is worth
# distinguishing because the remedy differs: an outage is retried, whereas
# hammering a box whose GPU is busy only makes every caller wait out the full
# 300s timeout. These strings are what Ollama/llama.cpp/CUDA actually emit.
_CAPACITY_MARKERS = (
    "out of memory", "outofmemory", "oom", "cuda error", "cuda_error",
    "no available gpu", "insufficient memory", "not enough memory",
    "requires more system memory", "requires more memory",
    "failed to allocate", "unable to allocate", "cannot allocate",
    "vram", "gpu memory", "model requires more", "no slots available",
    "server busy", "unable to load model",
)

# Provider errors that no amount of retrying fixes — the operator must change
# something. Surfaced as 400 rather than 503 so the UI can say "fix your
# settings" instead of "try again later".
_CONFIG_MARKERS = (
    "api key", "api_key", "unauthorized", "401", "403", "not set",
    "no base url", "no model specified", "invalid_api_key",
)


def classify_error_text(text: Optional[str]) -> Optional[str]:
    """Classify a provider's error string: "capacity" | "transient" | "config" |
    "fatal", or None when `text` is not an error at all.

    The provider adapters report failure by *returning* a string that starts with
    "Error" (they predate this module and several call sites still want the text
    rather than an exception). Everything downstream — retry, fallback, the
    circuit breaker, the HTTP status — keys off this one classification, so the
    markers live here rather than being re-guessed at each site.
    """
    t = (text or "").strip().lower()
    if not t.startswith("error"):
        return None
    return classify_failure(text)


def classify_failure(text: Optional[str]) -> str:
    """Same verdict as `classify_error_text`, for text already known to describe a
    failure — an exception message, say, which carries no "Error" prefix. Always
    returns a class; "fatal" is the fallback."""
    t = (text or "").lower()
    if any(m in t for m in _CAPACITY_MARKERS):
        return "capacity"
    if any(m in t for m in _CONFIG_MARKERS):
        return "config"
    if any(m in t for m in _TRANSIENT_STREAM_MARKERS):
        return "transient"
    return "fatal"


class LLMUnavailable(HTTPException):
    """The model could not produce an answer — and saying so beats inventing one.

    Subclasses HTTPException on purpose. ~50 route handlers already end with
    `except HTTPException: raise` / `except Exception as e: raise
    HTTPException(500, str(e))`, so raising this from the LLM layer arrives at the
    client with the right status and message without editing a single handler —
    and, critically, `except Exception` blocks that mean "degrade gracefully"
    (digest narratives) start firing, which they never did while failure was a
    perfectly ordinary return value.

    `kind` is the `classify_error_text` verdict; `retryable` tells a background
    caller whether waiting is worth it.
    """

    _STATUS = {"capacity": 503, "transient": 503, "config": 400, "fatal": 502}

    # What a capacity failure means in words the reader can act on. The provider's
    # own text ("model requires more system memory (12.1 GiB)...") is true but
    # reads as a crash; it stays on `provider_message` for the logs.
    _CAPACITY_MESSAGE = (
        "The model has no spare capacity right now — the machine it runs on is "
        "busy with another workload. Nothing is broken; please try again in a few "
        "minutes.")

    def __init__(self, message: str, *, kind: str = "fatal",
                 provider: Optional[str] = None, model: Optional[str] = None,
                 retry_after: Optional[int] = None,
                 provider_message: Optional[str] = None):
        self.kind = kind
        self.provider = provider
        self.model = model
        self.retry_after = retry_after
        self.raw_message = message
        # What the provider actually said — for logs and the admin, not the user.
        self.provider_message = provider_message or message
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(status_code=self._STATUS.get(kind, 502),
                         detail=message, headers=headers)

    @property
    def retryable(self) -> bool:
        return self.kind in ("capacity", "transient")

    @classmethod
    def from_error_text(cls, text: str, cfg: Optional["ModelConfig"] = None,
                        retry_after: Optional[int] = None) -> "LLMUnavailable":
        kind = classify_error_text(text) or "fatal"
        return cls(cls._CAPACITY_MESSAGE if kind == "capacity" else text,
                   kind=kind,
                   provider=(cfg.provider_type.value if cfg else None),
                   model=(cfg.model if cfg else None),
                   retry_after=retry_after, provider_message=text)

    @classmethod
    def from_exception(cls, exc: BaseException,
                       cfg: Optional["ModelConfig"] = None) -> "LLMUnavailable":
        """Wrap a provider exception. Timeouts and connect errors are classified by
        *type* rather than message — `str(httpx.ReadTimeout())` is often empty, and
        a timeout is exactly the symptom of a GPU that is busy elsewhere."""
        if isinstance(exc, LLMUnavailable):
            return exc
        if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError,
                            httpx.NetworkError, asyncio.TimeoutError)):
            kind = "transient"
            message = str(exc) or exc.__class__.__name__
        else:
            message = str(exc) or exc.__class__.__name__
            kind = classify_failure(message)
        return cls(cls._CAPACITY_MESSAGE if kind == "capacity"
                   else f"Error: {message}", kind=kind,
                   provider=(cfg.provider_type.value if cfg else None),
                   model=(cfg.model if cfg else None),
                   provider_message=f"Error: {message}")
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
    OPENROUTER = "openrouter"


# Providers that speak the OpenAI /v1/chat/completions schema. Dispatch sites
# test membership here rather than listing types inline, so an added
# OpenAI-shaped provider is wired into completion, streaming and tool mode in
# one edit instead of five.
OPENAI_STYLE_PROVIDERS = (
    ProviderType.OPENAI,
    ProviderType.OPENAI_COMPATIBLE,
    ProviderType.OPENROUTER,
)

# Env var holding the global fallback key, per provider that needs one. Used for
# the "no key" error text so the message names the variable the user must set.
_KEY_ENV_VAR = {
    ProviderType.OPENAI: "OPENAI_API_KEY",
    ProviderType.OPENROUTER: "OPENROUTER_API_KEY",
    ProviderType.GEMINI: "GEMINI_API_KEY",
}

# Local servers are slow to first token, and OpenRouter routes to models
# (reasoning/large) that regularly exceed two minutes; OpenAI proper is fast.
_SLOW_PROVIDERS = (ProviderType.OPENAI_COMPATIBLE, ProviderType.OPENROUTER)


def _request_timeout(provider_type) -> float:
    return 300.0 if provider_type in _SLOW_PROVIDERS else 120.0


def _missing_key_error(provider_type) -> Optional[str]:
    """Error text when a key-requiring provider has no key, else None."""
    env = _KEY_ENV_VAR.get(provider_type)
    if not env:
        return None
    return (f"Error: no API key for this provider. Add one in Settings → API Keys "
            f"(or set {env} in the server environment).")


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
    "openrouter": ProviderType.OPENROUTER,
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
    # Configs to try, in order, when this one fails retryably (the GPU is busy
    # with something else, the local box is down). Built where the user's stored
    # keys are readable — `deps._resolve_cfg` for requests, `digest._digest_cfg`
    # for scheduled work — because the LLM layer has no database. Empty is the
    # normal case and means "fail on this config's own terms".
    fallbacks: List["ModelConfig"] = field(default_factory=list)


# Providers served off this machine (or the LAN box next to it), whose capacity
# is shared with everything else on that host — notably a training run holding
# the GPU. These are the ones the gate serialises and trips the breaker for; a
# hosted API has its own elastic capacity and needs neither.
LOCAL_PROVIDERS = (ProviderType.OLLAMA, ProviderType.OPENAI_COMPATIBLE)

# Local-LLM gate tuning (see llm/gate.py).
#   CONCURRENCY  how many requests may be in flight per local host. 1 by default:
#                two readings sharing a contended GPU are slower than the same
#                two run back to back, and far likelier to OOM.
#   QUEUE_WAIT   how long to wait for a slot before giving up. Bounded so an
#                interactive question fails fast instead of hanging behind a
#                five-minute digest.
#   COOLDOWN     how long a host stays "no capacity" after a capacity failure,
#                so the remaining N profiles of a digest run fail in microseconds
#                rather than each waiting out its own 300s timeout.
LOCAL_LLM_CONCURRENCY = max(1, int(os.getenv("LOCAL_LLM_CONCURRENCY", "1")))
LOCAL_LLM_QUEUE_WAIT = float(os.getenv("LOCAL_LLM_QUEUE_WAIT", "120"))
LOCAL_LLM_COOLDOWN = float(os.getenv("LOCAL_LLM_COOLDOWN", "300"))
LOCAL_LLM_GATE_ENABLED = os.getenv("LOCAL_LLM_GATE", "1").lower() not in ("0", "false", "no")

# Fallback chain tuning (see LLMService.build_fallbacks). Order is a preference
# list of provider types to try when the configured one cannot answer.
LLM_FALLBACK_ENABLED = os.getenv("LLM_FALLBACK", "1").lower() not in ("0", "false", "no")
LLM_FALLBACK_ORDER = tuple(
    p.strip() for p in os.getenv("LLM_FALLBACK_ORDER",
                                 "gemini,openrouter,openai").split(",") if p.strip())

# Optional CPU-only Ollama endpoint used as the last link of the fallback chain
# (`CUDA_VISIBLE_DEVICES= ollama serve` on another port). Slow, but it never
# competes for the GPU — so a digest still gets written while training runs.
OLLAMA_CPU_URL = (os.getenv("OLLAMA_CPU_URL", "") or "").rstrip("/")


__all__ = [_n for _n in dir() if not _n.startswith('__')]
