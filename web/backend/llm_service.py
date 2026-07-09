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


class LLMService:
    """Unified interface for multiple LLM providers and models"""

    def __init__(self):
        # API keys
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_compat_key = os.getenv("OPENAI_COMPATIBLE_API_KEY", "")

        # Endpoints. rstrip("/") so a trailing slash can't produce a "//api/tags"
        # double slash, which Ollama answers with a 307 redirect httpx won't follow.
        self.ollama_url = (
            os.getenv("OLLAMA_URL") or "http://localhost:11434"
        ).rstrip("/")
        self.openai_compat_url = os.getenv(
            "OPENAI_COMPATIBLE_URL", "http://localhost:1234/v1"
        ).rstrip("/")

        # Default models per provider
        self.ollama_default_model = os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5:14b")
        self.gemini_default_model = os.getenv("GEMINI_DEFAULT_MODEL", "gemini-1.5-flash")
        self.openai_default_model = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")
        self.openai_compat_model = os.getenv("OPENAI_COMPATIBLE_MODEL", "")

    # ------------------------------------------------------------------ #
    # Config resolution
    # ------------------------------------------------------------------ #
    def resolve_config(self,
                       provider_type: Optional[str] = None,
                       model: Optional[str] = None,
                       base_url: Optional[str] = None,
                       api_key: Optional[str] = None,
                       legacy_provider: Optional[str] = None) -> ModelConfig:
        """Build a ModelConfig from explicit fields or a legacy provider string."""
        # Determine provider type
        raw = (provider_type or legacy_provider or "ollama").lower()
        pt = _LEGACY_MAP.get(raw)
        if pt is None:
            try:
                pt = ProviderType(raw)
            except ValueError:
                pt = ProviderType.OLLAMA

        # Defaults per provider type
        if pt == ProviderType.OLLAMA:
            return ModelConfig(pt, model or self.ollama_default_model,
                               base_url or self.ollama_url, None)
        if pt == ProviderType.OPENAI_COMPATIBLE:
            return ModelConfig(pt, model or self.openai_compat_model,
                               base_url or self.openai_compat_url,
                               api_key or self.openai_compat_key)
        if pt == ProviderType.GEMINI:
            return ModelConfig(pt, model or self.gemini_default_model,
                               None, api_key or self.gemini_api_key)
        # OPENAI
        return ModelConfig(pt, model or self.openai_default_model,
                           "https://api.openai.com/v1", api_key or self.openai_api_key)

    # ------------------------------------------------------------------ #
    # Provider / model discovery
    # ------------------------------------------------------------------ #
    async def list_providers(self, user_keys: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """Return configured providers, their availability, and model lists.

        `user_keys` is the calling user's stored per-provider keys; when present
        they count toward availability (and are flagged so the UI can show the
        source), so a user who saved their own key sees the provider as ready
        even if no global env key is set.
        """
        user_keys = user_keys or {}
        return [
            await self._ollama_status(),
            await self._openai_compat_status(user_keys.get("openai-compatible")),
            self._gemini_status(user_keys.get("gemini")),
            self._openai_status(user_keys.get("openai")),
        ]

    async def _ollama_status(self) -> Dict[str, Any]:
        info = {
            "type": ProviderType.OLLAMA.value,
            "label": "Ollama (Local)",
            "base_url": self.ollama_url,
            "default_model": self.ollama_default_model,
            "requires_key": False,
            "editable_base_url": True,
            "models": [],
            "available": False,
            "reason": None,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.ollama_url}/api/tags")
                if resp.status_code == 200:
                    models = [m.get("name") for m in resp.json().get("models", [])
                              if m.get("name")]
                    info["models"] = sorted(models)
                    info["available"] = True
                    if models and self.ollama_default_model not in models:
                        info["default_model"] = models[0]
                    if not models:
                        info["reason"] = "Ollama is running but no models are installed (ollama pull <model>)."
                else:
                    info["reason"] = f"Ollama responded with status {resp.status_code}."
        except Exception:
            info["reason"] = "Cannot reach Ollama. Start it with 'ollama serve'."
        return info

    async def _openai_compat_status(self, user_key: Optional[str] = None) -> Dict[str, Any]:
        info = {
            "type": ProviderType.OPENAI_COMPATIBLE.value,
            "label": "Local / OpenAI-compatible",
            "base_url": self.openai_compat_url,
            "default_model": self.openai_compat_model,
            "requires_key": False,
            "editable_base_url": True,
            "models": [],
            "available": False,
            "reason": None,
            "has_user_key": bool(user_key),
        }
        key = user_key or self.openai_compat_key
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                headers = {}
                if key:
                    headers["Authorization"] = f"Bearer {key}"
                resp = await client.get(f"{self.openai_compat_url}/models", headers=headers)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    models = [m.get("id") for m in data if m.get("id")]
                    info["models"] = sorted(models)
                    info["available"] = True
                    if models and not info["default_model"]:
                        info["default_model"] = models[0]
                else:
                    info["reason"] = f"Endpoint responded with status {resp.status_code}."
        except Exception:
            info["reason"] = (
                f"No OpenAI-compatible server reachable at {self.openai_compat_url} "
                "(e.g. LM Studio, llama.cpp, vLLM)."
            )
        return info

    def _gemini_status(self, user_key: Optional[str] = None) -> Dict[str, Any]:
        available = bool(user_key or self.gemini_api_key)
        return {
            "type": ProviderType.GEMINI.value,
            "label": "Google Gemini",
            "base_url": None,
            "default_model": self.gemini_default_model,
            "requires_key": True,
            "editable_base_url": False,
            "has_user_key": bool(user_key),
            "models": [
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-2.0-flash",
                "gemini-2.0-flash-lite",
            ],
            "available": available,
            "reason": None if available else "No Gemini API key. Add one in API Keys (or set GEMINI_API_KEY).",
        }

    def _openai_status(self, user_key: Optional[str] = None) -> Dict[str, Any]:
        available = bool(user_key or self.openai_api_key)
        return {
            "type": ProviderType.OPENAI.value,
            "label": "OpenAI (ChatGPT)",
            "base_url": "https://api.openai.com/v1",
            "default_model": self.openai_default_model,
            "requires_key": True,
            "editable_base_url": False,
            "has_user_key": bool(user_key),
            "models": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "o1-mini"],
            "available": available,
            "reason": None if available else "No OpenAI API key. Add one in API Keys (or set OPENAI_API_KEY).",
        }

    # ------------------------------------------------------------------ #
    # High-level tasks
    # ------------------------------------------------------------------ #
    async def ask_question(self,
                          chart_data: Dict[str, Any],
                          question: str,
                          provider: LLMProvider = LLMProvider.QWEN,
                          config: Optional[ModelConfig] = None,
                          history: Optional[List[Dict[str, str]]] = None,
                          usage: Optional[Dict[str, Any]] = None) -> str:
        """Ask a question about the chart. Pass either a ModelConfig or a legacy
        provider. `history` (prior {role, content} turns) enables multi-turn. If a
        mutable `usage` dict is supplied it is filled with the provider's reported
        token counts once the call completes (parity with the streaming path)."""
        cfg = config or self.resolve_config(legacy_provider=provider.value if isinstance(provider, LLMProvider) else provider)
        if history:
            convo_text = "\n\n=== PRIOR CONVERSATION ===\n" + "\n".join(
                f"{'User' if m.get('role') == 'user' else 'Astrologer'}: {m.get('content', '')}"
                for m in history
            ) + "\n=== END PRIOR CONVERSATION ==="
            prompt = (
                self._render_context_block(chart_data) + convo_text
                + f"\n\nUser's Question: {question}\n\n"
                + "Provide a detailed, personalized answer based on this specific birth chart."
            )
        else:
            prompt = self._build_chart_analysis_prompt(chart_data, question)
        return await self._complete(prompt, cfg, usage=usage)

    async def generate_prediction(self,
                                 chart_data: Dict[str, Any],
                                 prediction_type: str = "general",
                                 provider: LLMProvider = LLMProvider.QWEN,
                                 config: Optional[ModelConfig] = None) -> str:
        """Generate predictions based on chart data."""
        prompt = self._build_prediction_prompt(chart_data, prediction_type)
        cfg = config or self.resolve_config(legacy_provider=provider.value if isinstance(provider, LLMProvider) else provider)
        return await self._complete(prompt, cfg)

    async def analyze_compatibility(self,
                                   male_chart: Dict[str, Any],
                                   female_chart: Dict[str, Any],
                                   koota_score: int,
                                   provider: LLMProvider = LLMProvider.QWEN,
                                   config: Optional[ModelConfig] = None) -> str:
        """Generate compatibility analysis."""
        prompt = self._build_compatibility_prompt(male_chart, female_chart, koota_score)
        cfg = config or self.resolve_config(legacy_provider=provider.value if isinstance(provider, LLMProvider) else provider)
        return await self._complete(prompt, cfg)

    async def compare_charts(self,
                             chart_a: Dict[str, Any],
                             chart_b: Dict[str, Any],
                             name_a: str = "Person 1",
                             name_b: str = "Person 2",
                             provider: LLMProvider = LLMProvider.QWEN,
                             config: Optional[ModelConfig] = None) -> str:
        """Generate a neutral, relationship-agnostic comparison of two charts."""
        prompt = self._build_comparison_prompt(chart_a, chart_b, name_a, name_b)
        cfg = config or self.resolve_config(legacy_provider=provider.value if isinstance(provider, LLMProvider) else provider)
        return await self._complete(prompt, cfg)

    async def analyze_sarvatobhadra(self,
                                    sbc_data: Dict[str, Any],
                                    name: str = "this person",
                                    provider: LLMProvider = LLMProvider.QWEN,
                                    config: Optional[ModelConfig] = None) -> str:
        """Layman interpretation of the Sarvatobhadra Chakra transit reading."""
        prompt = self._build_sarvatobhadra_prompt(sbc_data, name)
        cfg = config or self.resolve_config(legacy_provider=provider.value if isinstance(provider, LLMProvider) else provider)
        return await self._complete(prompt, cfg)

    async def analyze_varshaphal(self,
                                 varsha_data: Dict[str, Any],
                                 name: str = "this person",
                                 provider: LLMProvider = LLMProvider.QWEN,
                                 config: Optional[ModelConfig] = None) -> str:
        """Plain-language year-ahead (Varshaphal / annual) forecast."""
        prompt = self._build_varshaphal_prompt(varsha_data, name)
        cfg = config or self.resolve_config(legacy_provider=provider.value if isinstance(provider, LLMProvider) else provider)
        return await self._complete(prompt, cfg)

    async def explain_rectification(self,
                                    rectification_data: Dict[str, Any],
                                    name: str = "this person",
                                    provider: LLMProvider = LLMProvider.QWEN,
                                    config: Optional[ModelConfig] = None) -> str:
        """Plain-language note on why the suggested (rectified) birth time fits better."""
        prompt = self._build_rectification_prompt(rectification_data, name)
        cfg = config or self.resolve_config(legacy_provider=provider.value if isinstance(provider, LLMProvider) else provider)
        return await self._complete(prompt, cfg)

    async def explain_event_rectification(self,
                                          rectification_data: Dict[str, Any],
                                          name: str = "this person",
                                          provider: LLMProvider = LLMProvider.QWEN,
                                          config: Optional[ModelConfig] = None) -> str:
        """Plain-language note on why the event-matched time fits the supplied events."""
        prompt = self._build_event_rectification_prompt(rectification_data, name)
        cfg = config or self.resolve_config(legacy_provider=provider.value if isinstance(provider, LLMProvider) else provider)
        return await self._complete(prompt, cfg)

    # ------------------------------------------------------------------ #
    # Conversational (chat) birth-time rectification — the AI interviews
    # the user for dated life events; the deterministic engine does the
    # actual rectification once events are collected.
    # ------------------------------------------------------------------ #
    RECT_CHAT_SYSTEM = (
        "You are a warm, patient Vedic astrologer conducting a birth-time RECTIFICATION "
        "interview. Your ONLY job is to collect a handful of well-dated, significant life "
        "events from the person, one question at a time, in plain friendly language. You do "
        "NOT compute or guess the birth time yourself — a separate engine does that from the "
        "events you collect. Always reply with STRICTLY VALID JSON and nothing else: no prose "
        "outside the JSON, no markdown, no code fences."
    )

    # Event types the rectification engine understands (must match
    # astrology.EVENT_SIGNIFICATORS keys).
    RECT_EVENT_TYPES = {
        "marriage": "marriage / wedding",
        "childbirth": "birth of a child",
        "career": "first job / career start",
        "promotion": "promotion or major rise at work",
        "education": "starting higher education / a degree",
        "wealth": "a major financial gain",
        "property": "buying property / a home",
        "relocation": "relocation or long foreign travel",
        "illness": "a major illness",
        "accident": "a serious accident or injury",
        "father_death": "father's passing",
        "mother_death": "mother's passing",
    }

    async def rectification_chat(self,
                                 messages: List[Dict[str, str]],
                                 collected_events: List[Dict[str, str]],
                                 name: str = "this person",
                                 provider: LLMProvider = LLMProvider.QWEN,
                                 config: Optional[ModelConfig] = None) -> Dict[str, Any]:
        """One conversational turn. Returns {reply, events, ready}.

        `messages` is the running transcript ([{role, content}]); `collected_events`
        are the {type, date} pairs gathered so far. The model asks the next question
        (or, when it has enough, invites the user to run the rectification) and returns
        the *full* cumulative event list it understands."""
        cfg = config or self.resolve_config(
            legacy_provider=provider.value if isinstance(provider, LLMProvider) else provider)

        types_block = "\n".join(f'  - "{k}": {v}' for k, v in self.RECT_EVENT_TYPES.items())
        transcript = "\n".join(
            f"{'User' if m.get('role') == 'user' else 'You'}: {m.get('content', '')}"
            for m in messages
        ) or "(no messages yet — greet and ask the first question)"
        known = json.dumps(collected_events or [], ensure_ascii=False)

        prompt = f"""You are interviewing {name} to gather dated life events for birth-time rectification.

Allowed event types (map what the user says to one of these keys — never invent a new key):
{types_block}

Conversation so far:
{transcript}

Events already collected (keep these; add to them as the user gives more):
{known}

Instructions:
- Ask about ONE event at a time, in a warm, simple sentence. Start with the most time-defining events (marriage, a child's birth, first job).
- When the user gives an event, record it as {{"type": <one allowed key>, "date": "YYYY-MM-DD"}}. If they give only a month & year, use the 15th; only a year, use July 1 — and gently note it's approximate.
- Return the FULL cumulative events list each turn (previously collected PLUS any new one).
- Set "ready" to true once you have at least 3 dated events, OR the user says they have no more / are done. When ready, your reply should say you have enough and invite them to run the rectification (a button below the chat).
- Never state or guess a birth time yourself; the engine does that.
- Keep replies to 1-3 short sentences.

Reply with STRICT JSON only, exactly this shape:
{{"reply": "<your next message to the user>", "events": [{{"type": "marriage", "date": "2015-11-20"}}], "ready": false}}"""

        # Small local models sometimes exhaust their output budget and return
        # nothing (done_reason=length, empty response), so use a generous budget and
        # retry once on empty/unparseable output before degrading gracefully.
        data = None
        raw = ""
        for _attempt in range(2):
            raw = await self._complete(prompt, cfg, max_tokens=2048, system=self.RECT_CHAT_SYSTEM)
            try:
                parsed = self._extract_json(raw)
                if isinstance(parsed, dict):
                    data = parsed
                    break
            except Exception:
                pass
        if data is None:
            # Degrade gracefully: keep the events we had, surface any raw text as the reply.
            return {"reply": (raw or "Could you tell me one important life event and its date?").strip(),
                    "events": collected_events or [], "ready": False}

        # Validate + normalise the returned events.
        clean = []
        seen = set()
        for ev in (data.get("events") or []):
            etype = (ev or {}).get("type")
            edate = (ev or {}).get("date")
            if etype not in self.RECT_EVENT_TYPES or not edate:
                continue
            try:
                parts = [int(p) for p in str(edate).split("-")[:3] if p != ""]
                if not parts:
                    continue
                y = parts[0]
                m = parts[1] if len(parts) > 1 else 7   # only year → mid-year
                d = parts[2] if len(parts) > 2 else 15   # only year/month → mid-month
                m = min(12, max(1, m)); d = min(28, max(1, d))
                iso = f"{y:04d}-{m:02d}-{d:02d}"
            except Exception:
                continue
            key = (etype, iso)
            if key in seen:
                continue
            seen.add(key)
            clean.append({"type": etype, "date": iso})

        return {
            "reply": str(data.get("reply") or "").strip()
            or "Could you share another life event and its date?",
            "events": clean,
            "ready": bool(data.get("ready")),
        }

    async def analyze_pancha_pakshi(self,
                                    pp_data: Dict[str, Any],
                                    name: str = "this person",
                                    provider: LLMProvider = LLMProvider.QWEN,
                                    config: Optional[ModelConfig] = None) -> str:
        """Plain-language reading of today's Pancha Pakshi bird-cycle timing."""
        prompt = self._build_pancha_pakshi_prompt(pp_data, name)
        cfg = config or self.resolve_config(legacy_provider=provider.value if isinstance(provider, LLMProvider) else provider)
        return await self._complete(prompt, cfg)

    async def analyze_sensitive_points(self,
                                       data: Dict[str, Any],
                                       name: str = "this person",
                                       provider: LLMProvider = LLMProvider.QWEN,
                                       config: Optional[ModelConfig] = None) -> str:
        """Plain-language reading of the natal sensitive points (Sphuta/Saham/Argala)."""
        prompt = self._build_sensitive_points_prompt(data, name)
        cfg = config or self.resolve_config(legacy_provider=provider.value if isinstance(provider, LLMProvider) else provider)
        return await self._complete(prompt, cfg)

    async def analyze_celestial(self,
                                data: Dict[str, Any],
                                name: str = "this person",
                                provider: LLMProvider = LLMProvider.QWEN,
                                config: Optional[ModelConfig] = None) -> str:
        """Plain-language reading of the Vedic clock + retrograde snapshot."""
        prompt = self._build_celestial_prompt(data, name)
        cfg = config or self.resolve_config(legacy_provider=provider.value if isinstance(provider, LLMProvider) else provider)
        return await self._complete(prompt, cfg)

    async def analyze_almanac(self,
                              data: Dict[str, Any],
                              provider: LLMProvider = LLMProvider.QWEN,
                              config: Optional[ModelConfig] = None) -> str:
        """Plain-language day-guide from the almanac (panchanga + planetary hours)."""
        prompt = self._build_almanac_prompt(data)
        cfg = config or self.resolve_config(legacy_provider=provider.value if isinstance(provider, LLMProvider) else provider)
        return await self._complete(prompt, cfg)

    async def analyze_muhurta(self,
                              muhurta_data: Dict[str, Any],
                              config: Optional[ModelConfig] = None) -> str:
        """Plain-language rationale for the recommended auspicious windows."""
        prompt = self._build_muhurta_prompt(muhurta_data)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_prashna(self,
                              prashna_data: Dict[str, Any],
                              config: Optional[ModelConfig] = None) -> str:
        """Prashna (horary) reading of the moment-chart for the asked question."""
        prompt = self._build_prashna_prompt(prashna_data)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_daily_digest(self,
                                   digest_data: Dict[str, Any],
                                   name: str = "this person",
                                   config: Optional[ModelConfig] = None) -> str:
        """Warm, personalized reading of today's digest for the person."""
        prompt = self._build_daily_digest_prompt(digest_data, name)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_bhrigu_markers(self,
                                     data: Dict[str, Any],
                                     name: str = "this person",
                                     config: Optional[ModelConfig] = None) -> str:
        """Reading of the Bhrigu / Nadi yearly markers (annual progression +
        Bhrigu Bindu activations)."""
        prompt = self._build_bhrigu_markers_prompt(data, name)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_remedies(self,
                               data: Dict[str, Any],
                               name: str = "this person",
                               config: Optional[ModelConfig] = None) -> str:
        """Warm explanation of the suggested per-planet remedies."""
        prompt = self._build_remedies_prompt(data, name)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_kp(self,
                         data: Dict[str, Any],
                         name: str = "this person",
                         config: Optional[ModelConfig] = None) -> str:
        """KP (Krishnamurti Paddhati) reading — cuspal sub-lords, significators,
        ruling planets."""
        prompt = self._build_kp_prompt(data, name)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_kp_horary(self,
                                data: Dict[str, Any],
                                question: str = "",
                                config: Optional[ModelConfig] = None) -> str:
        """KP horary (1-249) judgement of the querent's question."""
        prompt = self._build_kp_horary_prompt(data, question)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_jaimini(self,
                              data: Dict[str, Any],
                              name: str = "this person",
                              config: Optional[ModelConfig] = None) -> str:
        """Jaimini reading — Chara Karakas, Karakamsa/Swamsa, argala."""
        prompt = self._build_jaimini_prompt(data, name)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_now_chart(self,
                                data: Dict[str, Any],
                                config: Optional[ModelConfig] = None) -> str:
        """Read the chart of the moment (current sky) — the tenor of the present."""
        prompt = self._build_now_chart_prompt(data)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    # ------------------------------------------------------------------ #
    # "Learn the Chart" — AI quiz generation + grading
    # ------------------------------------------------------------------ #
    QUIZ_SYSTEM_PROMPT = (
        "You are an expert Vedic (Jyotish) astrology teacher writing an interactive "
        "quiz to help a student learn to read a SPECIFIC birth chart. You reason from "
        "classical Parashari principles, but here your job is to TEACH and TEST, not to "
        "give a reading. Every question and every grade must be grounded in the real, "
        "pre-computed chart facts supplied to you — never invent placements. "
        "You ALWAYS reply with strictly valid JSON and nothing else: no prose, no "
        "markdown, no code fences."
    )

    # Human-facing labels for the four topic groups the UI offers.
    QUIZ_TOPICS = {
        "planets": "Planets, signs & houses (placements and their basic meanings)",
        "yogas": "Yogas & doshas (combinations and afflictions present in the chart)",
        "dashas": "Dashas & transits (timing — current periods and ongoing gochara)",
        "vargas": "Divisional charts (D9 Navamsa, D10 Dasamsa, etc. and what they refine)",
    }
    QUIZ_LEVELS = ("beginner", "intermediate", "advanced")

    async def generate_quiz(self,
                            chart_data: Dict[str, Any],
                            topics: List[str],
                            level: str = "beginner",
                            num_mcq: int = 5,
                            num_free: int = 3,
                            focus_note: str = "",
                            config: Optional[ModelConfig] = None) -> List[Dict[str, Any]]:
        """Generate a quiz about THIS chart. Returns a list of question items, each a
        dict with id/topic/difficulty/format/question and (hidden) answer-key fields
        (correct_index + rationale for MCQ, expected_points + rationale for free-text).
        The caller strips the answer key before sending items to the browser."""
        cfg = config or self.resolve_config()
        prompt = self._build_quiz_gen_prompt(chart_data, topics, level,
                                             num_mcq, num_free, focus_note)
        # Generous output budget: small local models can spend a lot before the
        # JSON closes; too small a cap returns an empty/truncated reply.
        last_raw = ""
        for attempt in range(2):
            raw = await self._complete(prompt, cfg, max_tokens=8192,
                                       system=self.QUIZ_SYSTEM_PROMPT)
            last_raw = raw or last_raw
            if not (raw or "").strip():
                continue  # empty reply — retry once
            try:
                data = self._extract_json(raw)
            except ValueError:
                continue  # unparseable — retry once
            items = data.get("questions") if isinstance(data, dict) else data
            if isinstance(items, list) and items:
                try:
                    return self._normalize_items(items, topics, level)
                except ValueError:
                    continue
        snippet = (last_raw or "").strip()[:200]
        raise ValueError(
            "The AI model returned an empty or unreadable quiz"
            + (f" (it said: '{snippet}…')" if snippet else "")
            + ". Try fewer questions, or pick a larger/cloud model in Ask AI Astrologer."
        )

    async def grade_quiz_answers(self,
                                 chart_data: Dict[str, Any],
                                 free_items: List[Dict[str, Any]],
                                 answers: Dict[str, str],
                                 config: Optional[ModelConfig] = None) -> Dict[str, Dict[str, Any]]:
        """LLM-grade the free-text answers against the expected points + chart facts.
        Returns {item_id: {score, verdict, what_was_right, what_was_wrong, reasoning}}.
        MCQ items are graded deterministically by the caller, not here."""
        if not free_items:
            return {}
        cfg = config or self.resolve_config()
        prompt = self._build_quiz_grade_prompt(chart_data, free_items, answers)
        grades = None
        for attempt in range(2):
            raw = await self._complete(prompt, cfg, max_tokens=8192,
                                       system=self.QUIZ_SYSTEM_PROMPT)
            if not (raw or "").strip():
                continue
            try:
                data = self._extract_json(raw)
            except ValueError:
                continue
            grades = data.get("grades") if isinstance(data, dict) else data
            if isinstance(grades, list):
                break
        # If the model never returned usable grades, degrade gracefully: the caller
        # fills in a per-item fallback (the reference rationale) rather than 500ing.
        if not isinstance(grades, list):
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for g in (grades or []):
            gid = str(g.get("id", ""))
            if not gid:
                continue
            try:
                score = max(0.0, min(1.0, float(g.get("score", 0))))
            except (TypeError, ValueError):
                score = 0.0
            verdict = g.get("verdict")
            if verdict not in ("correct", "partial", "incorrect"):
                verdict = "correct" if score >= 0.8 else ("partial" if score >= 0.34 else "incorrect")
            out[gid] = {
                "score": round(score, 2),
                "verdict": verdict,
                "what_was_right": (g.get("what_was_right") or "").strip(),
                "what_was_wrong": (g.get("what_was_wrong") or "").strip(),
                "reasoning": (g.get("reasoning") or "").strip(),
            }
        return out

    @staticmethod
    def _extract_json(raw: Optional[str]) -> Any:
        """Parse a JSON object/array from a model reply, tolerating code fences and
        surrounding prose."""
        if not raw:
            raise ValueError("Empty response from model.")
        s = raw.strip()
        if s.startswith("```"):
            s = s.strip("`")
            if s[:4].lower() == "json":
                s = s[4:]
            s = s.strip()
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        # Fall back to the widest {...} or [...] span in the text.
        for open_c, close_c in (("[", "]"), ("{", "}")):
            i, j = s.find(open_c), s.rfind(close_c)
            if i != -1 and j > i:
                try:
                    return json.loads(s[i:j + 1])
                except json.JSONDecodeError:
                    continue
        raise ValueError(f"Could not parse JSON from model reply: {raw[:300]}")

    def _normalize_items(self, items: List[Dict[str, Any]], topics: List[str],
                         level: str) -> List[Dict[str, Any]]:
        """Validate + clean raw model items into the stored question schema."""
        out: List[Dict[str, Any]] = []
        for n, it in enumerate(items, start=1):
            if not isinstance(it, dict):
                continue
            fmt = "mcq" if it.get("format") == "mcq" else ("free" if it.get("format") == "free" else None)
            q = (it.get("question") or "").strip()
            if not fmt or not q:
                continue
            topic = it.get("topic") if it.get("topic") in self.QUIZ_TOPICS else (topics[0] if topics else "planets")
            difficulty = it.get("difficulty") if it.get("difficulty") in self.QUIZ_LEVELS else level
            item: Dict[str, Any] = {
                "id": f"q{n}",
                "topic": topic,
                "difficulty": difficulty,
                "format": fmt,
                "question": q,
                "rationale": (it.get("rationale") or "").strip(),
            }
            if fmt == "mcq":
                opts = [str(o).strip() for o in (it.get("options") or []) if str(o).strip()]
                if len(opts) < 2:
                    continue
                try:
                    ci = int(it.get("correct_index"))
                except (TypeError, ValueError):
                    continue
                if not (0 <= ci < len(opts)):
                    continue
                item["options"] = opts
                item["correct_index"] = ci
            else:
                pts = [str(p).strip() for p in (it.get("expected_points") or []) if str(p).strip()]
                item["expected_points"] = pts
            out.append(item)
        if not out:
            raise ValueError("No valid quiz questions after normalization.")
        return out

    def _build_quiz_gen_prompt(self, chart_data: Dict[str, Any], topics: List[str],
                               level: str, num_mcq: int, num_free: int,
                               focus_note: str) -> str:
        topic_lines = "\n".join(
            f"- {t}: {self.QUIZ_TOPICS[t]}" for t in topics if t in self.QUIZ_TOPICS
        ) or f"- planets: {self.QUIZ_TOPICS['planets']}"
        level_guide = {
            "beginner": "Beginner: test recall of single placements and their plain meaning "
                        "(which sign/house a planet is in, what a house signifies).",
            "intermediate": "Intermediate: combine two factors (lord placement + aspect, "
                            "dignity of a house lord, what a present yoga implies).",
            "advanced": "Advanced: synthesize multiple factors (dasha + transit timing, "
                        "varga corroboration, strength/ashtakavarga weighed together).",
        }.get(level, "Beginner")
        return (
            self._render_context_block(chart_data)
            + "\n\n=== YOUR TASK: WRITE A QUIZ ABOUT THIS CHART ===\n"
            + f"Create exactly {num_mcq} multiple-choice and {num_free} free-text "
              "(open-ended) questions that teach the student to read THIS chart.\n\n"
            + "Difficulty: " + level_guide + "\n\n"
            + "Cover these topics (spread the questions across them):\n" + topic_lines + "\n"
            + (f"\nFocus emphasis: {focus_note}\n" if focus_note else "")
            + "\nRULES:\n"
            + "1. Every question MUST reference the real placements above (e.g. 'Your Moon "
              "is in Scorpio in the 4th house — what does that suggest about ...'). Never "
              "ask about factors not present in the chart data.\n"
            + "2. Multiple-choice: exactly 4 plausible options, ONE correct; put its index "
              "(0-3) in correct_index. Make distractors believable, not silly.\n"
            + "3. Free-text: list 2-4 'expected_points' — the key ideas a correct answer "
              "should contain — used later for grading.\n"
            + "4. 'rationale' explains the correct answer citing the specific chart factors.\n"
            + "5. Keep questions clear and answerable from the chart; avoid trick wording.\n\n"
            + "Reply with ONLY this JSON (no prose, no code fences):\n"
            + '{"questions": [\n'
            + '  {"topic": "planets", "difficulty": "beginner", "format": "mcq", '
              '"question": "...", "options": ["...","...","...","..."], '
              '"correct_index": 0, "rationale": "..."},\n'
            + '  {"topic": "dashas", "difficulty": "beginner", "format": "free", '
              '"question": "...", "expected_points": ["...","..."], "rationale": "..."}\n'
            + "]}"
        )

    def _build_quiz_grade_prompt(self, chart_data: Dict[str, Any],
                                 free_items: List[Dict[str, Any]],
                                 answers: Dict[str, str]) -> str:
        blocks = []
        for it in free_items:
            pts = "; ".join(it.get("expected_points", [])) or "(none provided)"
            ans = (answers.get(it["id"]) or "").strip() or "(no answer given)"
            blocks.append(
                f"--- Question {it['id']} (topic: {it.get('topic')}) ---\n"
                f"Question: {it.get('question')}\n"
                f"Expected key points: {pts}\n"
                f"Reference rationale: {it.get('rationale') or '(none)'}\n"
                f"STUDENT'S ANSWER: {ans}"
            )
        questions_block = "\n\n".join(blocks)
        return (
            self._render_context_block(chart_data)
            + "\n\n=== YOUR TASK: GRADE THESE FREE-TEXT ANSWERS ===\n"
            + "Grade each student answer against the expected key points AND the real "
              "chart facts above. Award partial credit. Be encouraging but honest.\n\n"
            + questions_block
            + "\n\nFor each question return: a score from 0.0 to 1.0; a verdict of "
              "'correct' (>=0.8), 'partial' (0.34-0.79) or 'incorrect' (<0.34); a short "
              "'what_was_right'; a short 'what_was_wrong' (empty string if fully correct); "
              "and 'reasoning' — a detailed explanation of the right answer citing the "
              "specific chart factors, so the student learns WHY.\n\n"
            + "Reply with ONLY this JSON (no prose, no code fences):\n"
            + '{"grades": [\n'
            + '  {"id": "q3", "score": 0.5, "verdict": "partial", "what_was_right": "...", '
              '"what_was_wrong": "...", "reasoning": "..."}\n'
            + "]}"
        )

    # ------------------------------------------------------------------ #
    # Provider dispatch
    # ------------------------------------------------------------------ #
    async def _complete(self, prompt: str, cfg: ModelConfig, max_tokens: int = 4096,
                        system: Optional[str] = None,
                        usage: Optional[Dict[str, Any]] = None) -> str:
        max_tokens = cfg.max_tokens or max_tokens
        sys_prompt = system or SYSTEM_PROMPT
        if cfg.provider_type == ProviderType.OLLAMA:
            return await self._call_ollama(prompt, cfg, max_tokens, sys_prompt, usage)
        if cfg.provider_type in (ProviderType.OPENAI, ProviderType.OPENAI_COMPATIBLE):
            return await self._call_openai_style(prompt, cfg, max_tokens, sys_prompt, usage)
        if cfg.provider_type == ProviderType.GEMINI:
            return await self._call_gemini(prompt, cfg, max_tokens, sys_prompt, usage)
        return "Unsupported LLM provider"

    @staticmethod
    def _fill_usage(usage: Optional[Dict[str, Any]],
                    prompt_tokens, completion_tokens, total_tokens=None) -> None:
        """Populate a mutable usage dict from a provider's reported counts."""
        if usage is None:
            return
        if prompt_tokens is None and completion_tokens is None and total_tokens is None:
            return
        usage["prompt_tokens"] = prompt_tokens
        usage["completion_tokens"] = completion_tokens
        usage["total_tokens"] = (total_tokens if total_tokens is not None
                                 else (prompt_tokens or 0) + (completion_tokens or 0))

    # ------------------------------------------------------------------ #
    # Streaming (chat) — yields text chunks as they arrive
    # ------------------------------------------------------------------ #
    async def stream_answer(self, chart_data: Dict[str, Any], question: str,
                            history: Optional[List[Dict[str, str]]], cfg: ModelConfig,
                            max_tokens: int = 4096,
                            usage: Optional[Dict[str, Any]] = None) -> AsyncGenerator[str, None]:
        """Stream an answer for a question, including chart context + prior turns.

        If a mutable `usage` dict is supplied it is populated in place with the
        provider's reported token counts (prompt_tokens/completion_tokens/
        total_tokens) once the stream completes, so the caller can persist/show it.

        Transient failures that occur *before any content is emitted* (provider
        unreachable, 5xx/429, timeout) are retried up to MAX_STREAM_RETRIES with a
        short backoff; once real tokens have streamed to the client we can't retry
        without duplicating text, so a mid-stream failure is surfaced as-is."""
        max_tokens = cfg.max_tokens or max_tokens
        messages = self.build_chat_messages(chart_data, question, history)

        def _new_gen():
            if cfg.provider_type == ProviderType.OLLAMA:
                return self._stream_ollama(messages, cfg, max_tokens, usage)
            if cfg.provider_type in (ProviderType.OPENAI, ProviderType.OPENAI_COMPATIBLE):
                return self._stream_openai_style(messages, cfg, max_tokens, usage)
            if cfg.provider_type == ProviderType.GEMINI:
                return self._stream_gemini(messages, cfg, max_tokens, usage)

            async def _unsupported():
                yield "Unsupported LLM provider"
            return _unsupported()

        attempt = 0
        while True:
            gen = _new_gen()
            emitted = False          # any real content yielded yet?
            pending_error = None     # a transient error seen before any content
            async for chunk in gen:
                if not emitted and pending_error is None and _is_transient_stream_error(chunk):
                    # Provider failed at connect time (no content yet) — hold the
                    # error; we may retry instead of surfacing it.
                    pending_error = chunk
                    continue
                emitted = True
                yield chunk
            if pending_error is not None and not emitted:
                if attempt < MAX_STREAM_RETRIES:
                    attempt += 1
                    if usage is not None:
                        usage.clear()  # nothing was produced; reset before retry
                    await asyncio.sleep(STREAM_RETRY_BACKOFF * attempt)
                    continue
                # Out of retries — surface the transient error to the client.
                yield pending_error
            return

    async def _stream_ollama(self, messages, cfg, max_tokens, usage=None) -> AsyncGenerator[str, None]:
        url = (cfg.base_url or self.ollama_url).rstrip("/")
        model = cfg.model or self.ollama_default_model
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": 0.7, "num_predict": max_tokens},
        }
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("POST", f"{url}/api/chat", json=payload) as r:
                    if r.status_code != 200:
                        body = (await r.aread()).decode("utf-8", "ignore")
                        yield f"Error from Ollama ({model}): {r.status_code} - {body}"
                        return
                    async for line in r.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        chunk = obj.get("message", {}).get("content", "")
                        if chunk:
                            yield chunk
                        if obj.get("done"):
                            if usage is not None:
                                pt = obj.get("prompt_eval_count")
                                ct = obj.get("eval_count")
                                if pt is not None or ct is not None:
                                    usage["prompt_tokens"] = pt
                                    usage["completion_tokens"] = ct
                                    usage["total_tokens"] = (pt or 0) + (ct or 0)
                            break
        except httpx.ConnectError:
            yield (f"Error: Cannot connect to Ollama. Ensure it is running and the "
                   f"model is installed ('ollama pull {model}').")
        except Exception as e:
            yield f"Error calling Ollama: {str(e)}"

    async def _stream_openai_style(self, messages, cfg, max_tokens, usage=None) -> AsyncGenerator[str, None]:
        base_url = (cfg.base_url or "").rstrip("/")
        if not base_url:
            yield "Error: no base URL configured for this provider."
            return
        if cfg.provider_type == ProviderType.OPENAI and not cfg.api_key:
            yield "Error: OPENAI_API_KEY is not set. Add it to your .env file."
            return
        if not cfg.model:
            yield "Error: no model specified for this provider."
            return
        headers = {"Content-Type": "application/json"}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"
        payload = {
            "model": cfg.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": max_tokens,
            "stream": True,
            # Ask for a final usage chunk; servers that don't support it ignore this.
            "stream_options": {"include_usage": True},
        }
        timeout = 300.0 if cfg.provider_type == ProviderType.OPENAI_COMPATIBLE else 120.0
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", f"{base_url}/chat/completions",
                                         json=payload, headers=headers) as r:
                    if r.status_code != 200:
                        body = (await r.aread()).decode("utf-8", "ignore")
                        yield f"Error from {cfg.model}: {r.status_code} - {body}"
                        return
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = obj.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {}).get("content")
                            if delta:
                                yield delta
                        u = obj.get("usage")
                        if u and usage is not None:
                            usage["prompt_tokens"] = u.get("prompt_tokens")
                            usage["completion_tokens"] = u.get("completion_tokens")
                            usage["total_tokens"] = u.get("total_tokens")
        except httpx.ConnectError:
            yield f"Error: Cannot connect to {base_url}. Is the server running?"
        except Exception as e:
            yield f"Error calling model: {str(e)}"

    async def _stream_gemini(self, messages, cfg, max_tokens, usage=None) -> AsyncGenerator[str, None]:
        api_key = cfg.api_key or self.gemini_api_key
        model = cfg.model or self.gemini_default_model
        if not api_key:
            yield "Error: GEMINI_API_KEY environment variable not set."
            return
        # Map chat messages -> Gemini contents (+ system_instruction)
        system_text = next((m["content"] for m in messages if m["role"] == "system"), None)
        contents = []
        for m in messages:
            if m["role"] == "system":
                continue
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        payload = {
            "contents": contents,
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens},
        }
        if system_text:
            payload["system_instruction"] = {"parts": [{"text": system_text}]}
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:streamGenerateContent?alt=sse&key={api_key}")
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=payload) as r:
                    if r.status_code != 200:
                        body = (await r.aread()).decode("utf-8", "ignore")
                        yield f"Error from Gemini ({model}): {r.status_code} - {body}"
                        return
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if not data:
                            continue
                        try:
                            obj = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        for cand in obj.get("candidates", []):
                            for part in cand.get("content", {}).get("parts", []):
                                text = part.get("text")
                                if text:
                                    yield text
                        um = obj.get("usageMetadata")
                        if um and usage is not None:
                            usage["prompt_tokens"] = um.get("promptTokenCount")
                            usage["completion_tokens"] = um.get("candidatesTokenCount")
                            usage["total_tokens"] = um.get("totalTokenCount")
        except Exception as e:
            yield f"Error calling Gemini: {str(e)}"

    async def _call_ollama(self, prompt: str, cfg: ModelConfig, max_tokens: int = 4096,
                           system: str = SYSTEM_PROMPT,
                           usage: Optional[Dict[str, Any]] = None) -> str:
        url = (cfg.base_url or self.ollama_url).rstrip("/")
        model = cfg.model or self.ollama_default_model
        try:
            # Local models can be slow to cold-load + generate; allow up to 5 min
            async with httpx.AsyncClient(timeout=300.0) as client:
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": max_tokens},
                }
                response = await client.post(f"{url}/api/generate", json=payload)
                if response.status_code == 200:
                    data = response.json()
                    self._fill_usage(usage, data.get("prompt_eval_count"),
                                     data.get("eval_count"))
                    return data.get("response", "No response from model")
                return f"Error from Ollama ({model}): {response.status_code} - {response.text}"
        except httpx.ConnectError:
            return ("Error: Cannot connect to Ollama. Ensure it is running "
                    "('ollama serve') and the model is installed ('ollama pull " + model + "').")
        except Exception as e:
            return f"Error calling Ollama: {str(e)}"

    async def _call_openai_style(self, prompt: str, cfg: ModelConfig, max_tokens: int = 4096,
                                 system: str = SYSTEM_PROMPT,
                                 usage: Optional[Dict[str, Any]] = None) -> str:
        """OpenAI and any OpenAI-compatible server share the /chat/completions schema."""
        base_url = (cfg.base_url or "").rstrip("/")
        if not base_url:
            return "Error: no base URL configured for this OpenAI-compatible provider."
        if cfg.provider_type == ProviderType.OPENAI and not cfg.api_key:
            return "Error: OPENAI_API_KEY is not set. Add it to your .env file."
        if not cfg.model:
            return "Error: no model specified for this provider."
        # Local OpenAI-compatible servers can be slow; cloud OpenAI is fast
        req_timeout = 300.0 if cfg.provider_type == ProviderType.OPENAI_COMPATIBLE else 120.0
        try:
            async with httpx.AsyncClient(timeout=req_timeout) as client:
                headers = {"Content-Type": "application/json"}
                if cfg.api_key:
                    headers["Authorization"] = f"Bearer {cfg.api_key}"
                payload = {
                    "model": cfg.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": max_tokens,
                }
                response = await client.post(f"{base_url}/chat/completions",
                                             json=payload, headers=headers)
                if response.status_code == 200:
                    result = response.json()
                    u = result.get("usage") or {}
                    self._fill_usage(usage, u.get("prompt_tokens"),
                                     u.get("completion_tokens"), u.get("total_tokens"))
                    choices = result.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "No response")
                    return "No response from model"
                return f"Error from {cfg.model}: {response.status_code} - {response.text}"
        except httpx.ConnectError:
            return f"Error: Cannot connect to {base_url}. Is the server running?"
        except Exception as e:
            return f"Error calling model: {str(e)}"

    async def _call_gemini(self, prompt: str, cfg: ModelConfig, max_tokens: int = 4096,
                           system: str = SYSTEM_PROMPT,
                           usage: Optional[Dict[str, Any]] = None) -> str:
        api_key = cfg.api_key or self.gemini_api_key
        model = cfg.model or self.gemini_default_model
        if not api_key:
            return "Error: GEMINI_API_KEY environment variable not set. Please add it to your .env file."
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                       f"{model}:generateContent?key={api_key}")
                payload = {
                    "system_instruction": {"parts": [{"text": system}]},
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens},
                }
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    um = result.get("usageMetadata") or {}
                    self._fill_usage(usage, um.get("promptTokenCount"),
                                     um.get("candidatesTokenCount"),
                                     um.get("totalTokenCount"))
                    candidates = result.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "No response from Gemini")
                    return "No valid response from Gemini"
                return f"Error from Gemini ({model}): {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error calling Gemini: {str(e)}"

    def _render_context_block(self, chart_data: Dict[str, Any], tool_mode: bool = False) -> str:
        """Render the chart context (no question) — reused by the single-shot prompt
        and as the system message for streaming/multi-turn chat. When `tool_mode` is
        set the closing instructions acknowledge the context may be partial and the
        model should fetch the rest via tools (rather than claiming it's complete)."""

        from datetime import datetime

        # Get current date for Dasha period identification
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Extract key information
        lagna_info = chart_data.get("lagna", {})
        moon_info = chart_data.get("moon_sign", {})
        sun_info = chart_data.get("sun_sign", {})
        planets = chart_data.get("planetary_positions", {})
        birth_details = chart_data.get("birth_details", {})

        # Build comprehensive chart description
        chart_description = f"""TODAY'S DATE: {current_date}

Birth Details:
- Date of Birth: {birth_details.get('dob', 'Unknown')}
- Time of Birth: {birth_details.get('tob', 'Unknown')}
- Place of Birth: {birth_details.get('place', 'Unknown')}

Lagna (Ascendant):
- Sign: {lagna_info.get('sign_name', 'Unknown')} (House #{lagna_info.get('house', 'Unknown')})
- Nakshatra: {lagna_info.get('nakshatra', 'Unknown')} Pada {lagna_info.get('nakshatra_pada', 'Unknown')}
- Degrees: {lagna_info.get('degrees', 'Unknown')}°

Moon Sign (Chandra Rasi):
- Sign: {moon_info.get('sign_name', 'Unknown')} (Rasi #{moon_info.get('rasi', 'Unknown')})
- Nakshatra: {moon_info.get('nakshatra', 'Unknown')} Pada {moon_info.get('nakshatra_pada', 'Unknown')}

Sun Sign (Surya Rasi):
- Sign: {sun_info.get('sign_name', 'Unknown')} (Rasi #{sun_info.get('rasi', 'Unknown')})
- Nakshatra: {sun_info.get('nakshatra', 'Unknown')} Pada {sun_info.get('nakshatra_pada', 'Unknown')}

Planetary Positions (All 9 Grahas):"""

        # Add planetary positions with nakshatras
        for planet, data in planets.items():
            nakshatra_info = ""
            if data.get('nakshatra'):
                nakshatra_info = f", Nakshatra: {data.get('nakshatra', 'Unknown')} Pada {data.get('nakshatra_pada', 'Unknown')}"
            chart_description += f"\n- {planet}: {data.get('sign_name', 'Unknown')} sign (Rasi #{data.get('rasi', 'Unknown')}), {data.get('degrees', 0):.2f}°{nakshatra_info}"

        # Divisional charts (vargas) — compact one line per chart for token economy
        vargas = chart_data.get("vargas", [])
        if vargas:
            chart_description += "\n\nDivisional Charts (Vargas):"
            for v in vargas:
                lagna_sign = v.get("lagna", {}).get("sign_name", "?")
                placements = ", ".join(
                    f"{name} {p.get('sign_name', '?')}"
                    for name, p in v.get("planets", {}).items()
                )
                chart_description += (
                    f"\n- {v.get('code', '?')} {v.get('name', '')} "
                    f"({v.get('significance', '')}): Asc {lagna_sign}; {placements}"
                )

        # Add Dasha information
        current_dasha = chart_data.get("current_dasha", {})
        next_dasha = chart_data.get("next_dasha", {})
        current_bhukthi = chart_data.get("current_bhukthi", {})
        dasha_tree = chart_data.get("dasha_tree", [])

        if dasha_tree:
            # Preferred: the precise running chain Maha -> Bhukti -> Antara -> Sookshma
            chart_description += f"\n\nCurrently Active Vimsottari Dasha Chain (as of {current_date}):"
            for node in dasha_tree:
                chart_description += (
                    f"\n- {node.get('level_name', 'Level')}: {node.get('lord', 'Unknown')} "
                    f"({node.get('start_date', '?')} to {node.get('end_date', '?')})"
                )
        elif current_dasha:
            chart_description += f"\n\nCurrent Dasha (Vimsottari):"
            chart_description += f"\n- Maha Dasha: {current_dasha.get('lord', 'Unknown')} ({current_dasha.get('start_date', 'Unknown')} to {current_dasha.get('end_date', 'Unknown')})"
            chart_description += f"\n- Duration: {current_dasha.get('duration_years', 0)} years"

        if current_bhukthi and current_bhukthi.get('periods'):
            chart_description += f"\n\nAll Sub-periods (Antar Dasha / Bhukti) within {current_dasha.get('lord', 'Unknown')} Maha Dasha:"
            # Show ALL sub-periods so LLM can identify which one is current
            for period in current_bhukthi.get('periods', []):
                chart_description += f"\n- {period.get('lord', 'Unknown')}: {period.get('start_date', 'Unknown')} to {period.get('end_date', 'Unknown')} ({period.get('duration_months', 0)} months)"

        if next_dasha:
            chart_description += f"\n\nNext Maha Dasha:"
            chart_description += f"\n- {next_dasha.get('lord', 'Unknown')} starting {next_dasha.get('start_date', 'Unknown')}"

        # Yogas present in the chart (name + short description; token-budgeted)
        yogas = chart_data.get("yogas", [])
        if yogas:
            chart_description += f"\n\nYogas Present in the Chart ({len(yogas)}):"
            for y in yogas:
                desc = (y.get("description") or "").strip()
                if len(desc) > 140:
                    desc = desc[:137].rstrip() + "..."
                chart_description += f"\n- {y.get('name', 'Unknown')}" + (f": {desc}" if desc else "")

        # Doshas — list present ones with detail, name-only for absent
        doshas = chart_data.get("doshas", [])
        if doshas:
            present = [d for d in doshas if d.get("present")]
            absent = [d for d in doshas if not d.get("present")]
            chart_description += f"\n\nDoshas:"
            if present:
                chart_description += "\n- Present:"
                for d in present:
                    desc = (d.get("description") or "").strip()
                    if len(desc) > 140:
                        desc = desc[:137].rstrip() + "..."
                    chart_description += f"\n  • {d.get('name', 'Unknown')}" + (f": {desc}" if desc else "")
            else:
                chart_description += "\n- Present: none"
            if absent:
                chart_description += "\n- Absent: " + ", ".join(d.get("name", "?") for d in absent)

        # Current transits (Gochara) over the natal chart
        transits = chart_data.get("transits", {})
        t_planets = transits.get("planets", {}) if isinstance(transits, dict) else {}
        if t_planets:
            chart_description += f"\n\nCurrent Transits (Gochara) as of {transits.get('transit_date', current_date)}:"
            chart_description += "\n(house counted from natal Lagna / natal Moon)"
            for name, p in t_planets.items():
                retro = " [Retrograde]" if p.get("retrograde") else ""
                chart_description += (
                    f"\n- {name}: {p.get('sign_name', '?')} {p.get('degrees', 0):.1f}° "
                    f"({p.get('nakshatra', '?')}), house {p.get('house_from_lagna', '?')} "
                    f"from Lagna / {p.get('house_from_moon', '?')} from Moon{retro}"
                )
            for u in transits.get("upcoming", []):
                chart_description += (
                    f"\n- Upcoming: {u.get('planet', '?')} enters {u.get('to_sign', '?')} "
                    f"(from {u.get('from_sign', '?')}) on {u.get('date', '?')}"
                )

        # Ashtakavarga — Sarva (combined) bindus per sign (higher = more supportive)
        ashtakavarga = chart_data.get("ashtakavarga", {})
        sav = ashtakavarga.get("sarva") if isinstance(ashtakavarga, dict) else None
        if sav:
            signs = ashtakavarga.get("signs", [])
            pairs = ", ".join(
                f"{signs[i] if i < len(signs) else i}: {v}" for i, v in enumerate(sav)
            )
            chart_description += (
                f"\n\nSarva Ashtakavarga (bindus per sign, total "
                f"{ashtakavarga.get('sarva_total', sum(sav))}/337):\n- {pairs}"
            )

        # Shadbala — per-planet strength (ratio >= 1.0 means sufficiently strong)
        shadbala = chart_data.get("shadbala", [])
        if shadbala:
            chart_description += "\n\nShadbala (planetary strength, rupas):"
            for p in shadbala:
                flag = "" if p.get("sufficient") else " (below required)"
                chart_description += (
                    f"\n- {p.get('planet', '?')}: {p.get('total_rupa', '?')} rupa, "
                    f"ratio {p.get('strength_ratio', '?')}, rank {p.get('rank', '?')}{flag}"
                )

        # Graha drishti (aspects) — one compact line per aspecting graha, with the
        # Parashari sphuta strength (%) so partial aspects can be weighed.
        aspects = chart_data.get("aspects", {})
        a_planets = aspects.get("planets", []) if isinstance(aspects, dict) else []
        if a_planets:
            chart_description += "\n\nGraha Drishti (aspects; strength 0-100%, 100 = full):"
            for a in a_planets:
                houses = ", ".join(
                    f"{h['house']}({h['strength']}%)" for h in a.get("aspects_houses", [])
                )
                pl = ", ".join(
                    f"{p.get('planet', '?')} {p.get('strength', 0)}%"
                    for p in a.get("aspects_planets", [])
                ) or "none"
                special = " [special aspects]" if a.get("special_aspect") else ""
                chart_description += (
                    f"\n- {a.get('planet', '?')}{special}: houses {houses or 'none'}; "
                    f"planets {pl}"
                )
                rasi_pl = a.get("rasi_drishti_planets", [])
                if rasi_pl:
                    chart_description += f"; rasi-drishti on {', '.join(rasi_pl)}"

        # Arudha padas — AL (perceived image/status), UL (spouse), A2..A11, each the
        # sign the arudha occupies. One compact line.
        arudhas = chart_data.get("arudhas", {})
        ar_padas = arudhas.get("padas", []) if isinstance(arudhas, dict) else []
        if ar_padas:
            items = ", ".join(
                f"{p.get('short', '?')} {p.get('sign_name', '?')}" for p in ar_padas
            )
            chart_description += (
                "\n\nArudha Padas (AL=perceived image/status, UL=spouse; sign each "
                f"arudha occupies): {items}"
            )

        header = ("Below is birth chart data for this person, calculated using precise "
                  f"astronomical calculations from the {SITE_NAME} Vedic astrology software. "
                  "This is REAL, VERIFIED CHART DATA - not hypothetical."
                  if tool_mode else
                  "Below is the COMPLETE BIRTH CHART DATA for this person, calculated "
                  f"using precise astronomical calculations from the {SITE_NAME} Vedic "
                  "astrology software. This is REAL, VERIFIED CHART DATA - not "
                  "hypothetical.")
        title = "=== BIRTH CHART ===" if tool_mode else "=== COMPLETE BIRTH CHART ==="
        closing = (
            "Give practical, actionable guidance. Some sections may be omitted above — "
            "call the available tools to fetch any additional data you need rather than "
            "asking the user."
            if tool_mode else
            "Give practical, actionable guidance. Do NOT ask for more information — you "
            "have the complete chart and today's date.")

        context_block = f"""{header}

{title}

{chart_description}

=== END OF CHART DATA ===

IMPORTANT INSTRUCTIONS:
1. TODAY'S DATE is {current_date} - use it to determine which Dasha/sub-period is CURRENTLY active.
2. The planetary positions, signs, houses, nakshatras, divisional charts (vargas) and Dasha periods above were calculated accurately from the exact birth time and location.
3. Be specific to THIS chart: cite the placements/dashas/yogas behind your reasoning rather than giving generic horoscope text.
4. {closing}"""

        return context_block

    def _build_chart_analysis_prompt(self, chart_data: Dict[str, Any], question: str) -> str:
        """Single-shot prompt: chart context block followed by the user's question."""
        return (
            self._render_context_block(chart_data)
            + f"\n\nUser's Question: {question}\n\n"
            + "Provide a detailed, personalized answer based on this specific birth chart."
        )

    def build_chat_messages(self, chart_data: Dict[str, Any], question: str,
                            history: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
        """Chat-format messages for streaming/multi-turn: a system message carrying
        the chart context, then prior turns, then the new question."""
        messages = [{
            "role": "system",
            "content": SYSTEM_PROMPT + "\n\n" + self._render_context_block(chart_data),
        }]
        for m in (history or []):
            role = m.get("role")
            if role in ("user", "assistant") and m.get("content"):
                messages.append({"role": role, "content": m["content"]})
        messages.append({"role": "user", "content": question})
        return messages

    def _build_prediction_prompt(self, chart_data: Dict[str, Any], prediction_type: str) -> str:
        """Build prompt for predictions, using the full structured chart context
        (D1 + dasha chain + yogas + doshas + transits + vargas) when available."""

        type_specific = {
            "general": "overall life path, personality, and general predictions",
            "health": "health constitution, potential health issues, and wellness recommendations",
            "career": "career inclinations, professional success factors, and recommended fields",
            "relationships": "relationship patterns, marriage timing, and compatibility factors"
        }
        focus = type_specific.get(prediction_type, type_specific["general"])

        return (
            self._render_context_block(chart_data)
            + f"\n\nBased on THIS SPECIFIC BIRTH CHART above, provide detailed "
            + f"{prediction_type} predictions focusing on {focus}.\n\n"
            + "Your prediction should cover:\n"
            + "1. Key strengths and characteristics from their specific placements (cite the houses/lords/karakas).\n"
            + "2. Challenges and areas for growth indicated by their chart.\n"
            + "3. Opportunities in the near future based on the running dasha and current transits.\n"
            + "4. Practical remedies or recommendations specific to their placements.\n"
            + "5. Auspicious timing considerations grounded in the dasha chain.\n\n"
            + "Be specific, insightful, personalized, and encouraging. Do NOT ask for "
            + "more information — you have the complete chart and today's date."
        )

    def _build_compatibility_prompt(self, male_chart: Dict[str, Any],
                                   female_chart: Dict[str, Any], koota_score: int) -> str:
        """Build prompt for compatibility analysis"""

        male_lagna = male_chart.get("lagna", {})
        male_moon = male_chart.get("moon_sign", {})
        male_sun = male_chart.get("sun_sign", {})
        female_lagna = female_chart.get("lagna", {})
        female_moon = female_chart.get("moon_sign", {})
        female_sun = female_chart.get("sun_sign", {})

        prompt = f"""You are an expert Vedic astrologer specializing in marriage compatibility. Below are the COMPLETE, ACCURATELY CALCULATED birth charts for both partners from {SITE_NAME} software.

=== MALE BIRTH CHART ===
Lagna (Ascendant): {male_lagna.get('sign_name', 'Unknown')} in {male_lagna.get('nakshatra', 'Unknown')} nakshatra
Moon Sign: {male_moon.get('sign_name', 'Unknown')} in {male_moon.get('nakshatra', 'Unknown')} nakshatra (Pada {male_moon.get('pada', 'Unknown')})
Sun Sign: {male_sun.get('sign_name', 'Unknown')}

=== FEMALE BIRTH CHART ===
Lagna (Ascendant): {female_lagna.get('sign_name', 'Unknown')} in {female_lagna.get('nakshatra', 'Unknown')} nakshatra
Moon Sign: {female_moon.get('sign_name', 'Unknown')} in {female_moon.get('nakshatra', 'Unknown')} nakshatra (Pada {female_moon.get('pada', 'Unknown')})
Sun Sign: {female_sun.get('sign_name', 'Unknown')}

=== COMPATIBILITY SCORE ===
Ashta Koota Score: {koota_score}/36 (Calculated using traditional Vedic methods)

Interpretation:
- 28-36: Excellent compatibility
- 24-27: Good compatibility
- 18-23: Average compatibility (workable with effort)
- Below 18: Challenging compatibility

Based on these SPECIFIC CHARTS and the {koota_score}/36 Ashta Koota score, provide a comprehensive compatibility analysis:

1. Overall compatibility assessment - interpret the {koota_score}/36 score in context
2. Strengths in the relationship based on their specific placements
3. Potential challenges indicated by their charts and how to overcome them
4. Mental and emotional compatibility (Moon signs and nakshatras)
5. Long-term relationship prospects
6. Practical recommendations for a harmonious marriage

IMPORTANT: Use the actual chart data provided above. Be balanced, specific to their placements, insightful, and constructive. Do not ask for more information."""

        return prompt

    def _build_comparison_prompt(self, chart_a: Dict[str, Any], chart_b: Dict[str, Any],
                                 name_a: str, name_b: str) -> str:
        """Build a neutral, relationship-agnostic two-chart comparison prompt.

        Unlike compatibility (which assumes marriage/Guna Milan), this contrasts the
        two charts as individuals — useful for any pairing (friends, family, the same
        person across a rectification, etc.)."""

        def block(name: str, chart: Dict[str, Any]) -> str:
            lagna = chart.get("lagna", {})
            moon = chart.get("moon_sign", {})
            sun = chart.get("sun_sign", {})
            return (
                f"=== {name} ===\n"
                f"Lagna (Ascendant): {lagna.get('sign_name', 'Unknown')} in "
                f"{lagna.get('nakshatra', 'Unknown')} nakshatra\n"
                f"Moon: {moon.get('sign_name', 'Unknown')} in {moon.get('nakshatra', 'Unknown')} "
                f"nakshatra (Pada {moon.get('nakshatra_pada', 'Unknown')})\n"
                f"Sun: {sun.get('sign_name', 'Unknown')}\n"
                f"Planets:\n{self._format_planets(chart.get('planetary_positions', {}))}"
            )

        prompt = f"""You are an expert Vedic astrologer. Below are two COMPLETE, ACCURATELY CALCULATED birth charts from {SITE_NAME} software. Compare and contrast them as two individuals. This is NOT a marriage/compatibility (Guna Milan) reading — make no assumptions about the nature of any relationship between them.

{block(name_a, chart_a)}

{block(name_b, chart_b)}

Provide a clear side-by-side comparison covering:

1. Personality & temperament — contrast their Lagna and overall disposition
2. Mind & emotions — contrast their Moon signs/nakshatras
3. Vitality, ego & self-expression — contrast their Sun
4. Notable similarities (shared signs, nakshatras, or planetary patterns)
5. Notable differences and how their natures diverge
6. A short, neutral synthesis of how the two charts compare

IMPORTANT: Use the actual chart data above. Be specific to their placements, balanced, and concise. Refer to them as "{name_a}" and "{name_b}". Do not score them and do not ask for more information."""

        return prompt

    def _build_sarvatobhadra_prompt(self, sbc: Dict[str, Any], name: str) -> str:
        """Build a plain-language Sarvatobhadra Chakra (transit) reading prompt.

        The chakra logic is already computed (occupation + facing/saamne vedha on
        the native's sensitive points); the model's job is to translate the
        structured findings into something a non-astrologer can act on."""
        anchors = sbc.get("anchors", {})
        anchor_lines = []
        for a in anchors.values():
            anchor_lines.append(f"- {a.get('label')}: {a.get('name')}")

        findings = sbc.get("findings", [])
        if findings:
            find_lines = []
            for f in findings:
                kind = ("a graha sitting ON it" if f.get("kind") == "occupation"
                        else "vedha (obstruction) facing it across the chakra")
                find_lines.append(
                    f"- {f.get('planet')} ({f.get('planet_nature')}, {f.get('tone')}) — "
                    f"{kind} → {f.get('anchor_label')} ({f.get('anchor_name')})"
                )
            findings_block = "\n".join(find_lines)
        else:
            findings_block = "- No graha is currently occupying or casting vedha on the native's sensitive points (a quiet, neutral window on the chakra)."

        pan = sbc.get("transit_panchanga", {})
        pan_line = (
            f"Today's tithi group: {pan.get('tithi_group')} "
            f"({'matches' if pan.get('same_tithi_group') else 'differs from'} the birth tithi group); "
            f"today's weekday: {pan.get('weekday')} "
            f"({'matches' if pan.get('same_weekday') else 'differs from'} the birth weekday)."
        )

        planets = sbc.get("planets", [])
        planet_line = ", ".join(
            f"{p.get('name')} in {p.get('nakshatra')}/{p.get('sign_name')}"
            f"{' (retrograde)' if p.get('retrograde') else ''}"
            for p in planets
        )

        return f"""You are a warm, plain-spoken Vedic astrologer explaining a Sarvatobhadra Chakra reading to someone with NO astrology background. Avoid jargon; when you must use a term (vedha, nakshatra), explain it in a few words.

The Sarvatobhadra Chakra is a 9×9 grid of all the stars, signs, syllables, tithis and weekdays. We map where the planets are TODAY onto it and check the person's most sensitive cells: their birth star, Moon sign, name star, birth tithi and birth weekday. A planet "occupying" a sensitive cell, or a planet "facing" it from across the grid (called vedha, meaning obstruction), activates that part of life — gently if the planet is a natural benefic (Jupiter, Venus, Mercury, Moon), more testingly if it is a malefic (Saturn, Mars, Rahu, Ketu, Sun).

Reading for: {name}
Transit date: {sbc.get('transit_date')} {sbc.get('transit_time')}

The person's sensitive points on the chakra:
{chr(10).join(anchor_lines)}

Where the planets sit today: {planet_line}

{pan_line}

What the chakra flags right now (already computed — trust these):
{findings_block}

Write a clear, encouraging reading (about 500 words) with these parts:
1. **The headline** — one or two sentences on the overall tone of this period for {name} (supportive, mixed, or a time for care).
2. **What's being touched** — for each flagged planet above, say in everyday language what it tends to stir up and which life area (e.g. Saturn → patience, work, delays; Jupiter → growth, opportunity, optimism), tied to which sensitive point it hits.
3. **What to expect & do** — 2-4 concrete, gentle suggestions for the weeks ahead.
4. End with one short line of reassurance.

Be specific to the findings above — do not invent placements that aren't listed. If nothing is flagged, say plainly that this is a calm, unremarkable window and give light general guidance. Do NOT predict death, disease, disasters, or precise dates. Close with a brief reminder that this is for reflection, not a substitute for professional advice."""

    def _build_varshaphal_prompt(self, v: Dict[str, Any], name: str) -> str:
        """Build a plain-language year-ahead (Varshaphal / Tajaka) forecast prompt.

        The annual chart, Muntha, year-lord, Sahams, Tajaka yogas and annual
        dasha are already computed; the model's job is to weave them into a
        grounded, encouraging forecast for the year."""
        year = v.get("year")
        entry = v.get("year_entry", {})
        muntha = v.get("muntha", {})
        yl = v.get("year_lord") or {}

        lagna = v.get("lagna", {})
        planets = v.get("planets", {})
        placements = ", ".join(
            f"{p}: {d.get('sign_name')}" for p, d in planets.items()
        )

        sahams = v.get("sahams", [])
        saham_lines = "\n".join(
            f"- {s.get('name')} ({s.get('significance')}): {s.get('sign_name')} "
            f"(house {s.get('house')})"
            for s in sahams
        ) or "- (none computed)"

        yogas = v.get("tajaka_yogas", [])
        if yogas:
            yoga_lines = "\n".join(
                f"- {y.get('name')}"
                + (f" [{'/'.join(y.get('pair'))}]" if y.get("pair") else "")
                + f": {y.get('description')}"
                for y in yogas
            )
        else:
            yoga_lines = "- No notable Tajaka yoga this year (a steady, unremarkable year on this measure)."

        periods = v.get("annual_dasha", {}).get("periods", [])
        dasha_lines = "\n".join(
            f"- {p.get('lord_name')}: {p.get('start')} → {p.get('end')}"
            + (" (running now)" if p.get("current") else "")
            for p in periods
        ) or "- (none computed)"

        return f"""You are a warm, plain-spoken Vedic astrologer giving a YEAR-AHEAD reading (Varshaphal, the annual solar-return chart in the Tajaka system) to someone with little astrology background. Avoid jargon; when you must use a term (Muntha, Saham, dasha), explain it in a few words.

The Varshaphal is a fresh chart cast for the moment the Sun returns to its birth position each year. It is read for that one year only, alongside the natal chart. Key annual factors are already computed for you — trust them, do not invent placements.

Reading for: {name}
Year: {year} (solar-year begins {entry.get('date')} {entry.get('time')})
Annual Ascendant (Lagna): {lagna.get('sign_name')}
Planet placements this year: {placements}
Muntha (the progressed point that advances one sign a year; the year's spotlight): {muntha.get('sign_name')} — house {muntha.get('house')} of the annual chart
Year-lord (Varsheshwara, the planet governing the year): {yl.get('planet', 'undetermined')}

Sahams (sensitive points, like signposts for specific matters):
{saham_lines}

Tajaka yogas active this year (already computed — trust these):
{yoga_lines}

Annual dasha (Mudda / Varsha Vimsottari — sub-periods within the year, each ruled by a planet):
{dasha_lines}

Write a clear, encouraging year-ahead reading (about 500 words) with these parts:
1. **The headline** — one or two sentences on the overall tone and theme of {year} for {name}, anchored in the Muntha house and the year-lord.
2. **What the year emphasises** — translate the Muntha house, the year-lord's nature, and 2-3 of the most relevant Sahams into everyday life areas (work, money, relationships, health, learning, home).
3. **Timing within the year** — use the annual dasha sequence to note which stretches look more active or supportive, in plain terms.
4. **What to do** — 2-4 concrete, gentle suggestions for the year.
5. End with one short line of reassurance.

Be specific to the factors above — do not invent anything not listed. Do NOT predict death, disease, disasters, or precise dates. Close with a brief reminder that this is for reflection and planning, not a substitute for professional advice."""

    def _build_pancha_pakshi_prompt(self, p: Dict[str, Any], name: str) -> str:
        """Build a plain-language day-timing reading from the Pancha Pakshi data.

        The birth bird, the day's best/worst windows and the segment timeline are
        already computed; the model turns them into gentle 'good times for X'
        guidance for the day."""
        bird = p.get("birth_bird", {})
        best = p.get("best_times", [])
        avoid = p.get("avoid_times", [])

        best_lines = "\n".join(
            f"- {b.get('start')}–{b.get('end')} ({b.get('phase')}): "
            f"{b.get('main_activity')}/{b.get('sub_activity')} — {b.get('effect')}"
            for b in best
        ) or "- (none)"
        avoid_lines = "\n".join(
            f"- {a.get('start')}–{a.get('end')} ({a.get('phase')}): "
            f"{a.get('main_activity')}/{a.get('sub_activity')} — {a.get('effect')}"
            for a in avoid
        ) or "- (none)"

        return f"""You are a warm, plain-spoken guide explaining PANCHA PAKSHI SASTRA — an old South-Indian (Tamil Siddha) system of timing the day. In it, each person has a "birth bird" (from their birth star), and the day is divided into windows where that bird is Ruling, Eating, Walking, Sleeping or Dying — from strongest to weakest. You favour the strong windows for important actions and rest during the weak ones. Explain simply; avoid jargon.

Reading for: {name}
Date: {p.get('date')} ({p.get('weekday')}, {p.get('paksha')} paksha)
Birth bird: {bird.get('name')} (from birth star {bird.get('star_name')})
Sunrise {p.get('sunrise')}, sunset {p.get('sunset')}.

The strongest windows today (best for important or demanding activities):
{best_lines}

The weakest windows today (better for rest, routine, low-stakes tasks):
{avoid_lines}

Write a short, friendly day-guide (about 250-300 words):
1. **Your bird today** — one or two sentences on what having the {bird.get('name')} as the birth bird means in this system, kept light.
2. **Best times** — translate the strong windows into concrete "good for…" suggestions (starting important work, meetings, travel, exercise, decisions), with the clock times.
3. **Quieter times** — note the weak windows as good for rest, chores, reflection.
4. End with one short, encouraging line.

Use the clock times given. Do NOT invent windows not listed. Do NOT make medical, financial or fated claims. Close with a one-line reminder that this is a traditional timing aid for reflection, not a rule to live by."""

    def _build_sensitive_points_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Turn the computed Sphutas, Sahams and Argala into a gentle, plain
        explanation. All values are already computed — the model interprets."""
        sphuta = (d.get("sphuta") or {}).get("sphutas", [])
        sahams = (d.get("sahams") or {}).get("sahams", [])
        argala = (d.get("argala") or {}).get("houses", [])

        sph_lines = "\n".join(
            f"- {s['name']} ({s['significance']}): {s['sign_name']} {s['degrees']}°, "
            f"house {s['house']}" for s in sphuta[:12]
        ) or "- (none)"
        # Only the sahams likely to matter most, to keep the prompt lean.
        key = {"Punya", "Vidya", "Yasas", "Karma", "Artha", "Vivaha", "Puthra",
               "Roga", "Laabha", "Rajya", "Jeeva"}
        sah_lines = "\n".join(
            f"- {s['name']} ({s['significance']}): {s['sign_name']}, house {s['house']}"
            for s in sahams if s['name'] in key
        ) or "- (none)"
        arg_lines = "\n".join(
            f"- House {h['bhava']} ({h['sign_name']}): net {h['net']}"
            for h in argala if h.get('net') not in (None, 'none', 'balanced')
        )[:800] or "- (mostly balanced)"

        return f"""You are a warm, plain-spoken Vedic astrologer explaining a chart's SENSITIVE POINTS to {name}. These are technical helper points, so translate them into everyday meaning and never overwhelm with jargon.

SPHUTAS (sensitive longitudes derived from the chart):
{sph_lines}

Key SAHAMS (Arabic-part-like points for life themes):
{sah_lines}

ARGALA (which houses receive strong planetary "intervention" support vs obstruction):
{arg_lines}

Write a friendly ~300-word note:
1. **What these are** — one or two sentences: sensitive supporting points that fine-tune a reading, not core predictions.
2. **A few highlights** — pick 3-4 of the most telling points (e.g. a Saham for career/wealth/marriage sitting in a notable house, or a house with strong argala) and say plainly what they gently emphasise.
3. **How to use them** — note they colour and confirm the main chart rather than override it.
Keep it encouraging and non-deterministic. Do NOT dwell on Mrityu/Apamrithyu points or make any health, death, financial or fated claims. Close with a one-line reminder that these are supportive nuances for reflection."""

    def _build_celestial_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Explain the current Vedic clock + retrograde snapshot in plain terms."""
        clock = d.get("clock") or {}
        retro = d.get("retrograde") or {}
        panch = clock.get("panchanga") or {}
        hora = clock.get("current_hora") or {}
        retro_now = retro.get("retrograde_now") or []
        stations = "\n".join(
            f"- {p['planet']} turns {p['next_station']['becomes']} on {p['next_station']['date']}"
            for p in retro.get("planets", []) if p.get("next_station")
        ) or "- (none upcoming in range)"

        return f"""You are a warm, plain-spoken guide explaining the CURRENT SKY in Vedic terms to {name}, tying the traditional day-clock to what the planets are doing right now. Keep it simple and grounded.

Date: {clock.get('date')} at {clock.get('place') or 'the chosen place'}
Sunrise {clock.get('sunrise')}, sunset {clock.get('sunset')} (day length {clock.get('day_length_hours')} h).
Running hora (planetary hour) lord: {hora.get('planet')} ({'benefic' if hora.get('benefic') else 'malefic'}).
Panchanga now: tithi {panch.get('tithi')}, nakshatra {panch.get('nakshatra')}, yoga {panch.get('yoga')}.
Planets retrograde right now: {', '.join(retro_now) if retro_now else 'none'}.
Upcoming direction changes (stations):
{stations}

Write a friendly ~250-word note:
1. **The Vedic day** — explain the ghati/hora idea in a sentence, then what the current hora lord tends to favour (e.g. Jupiter-hora good for learning, Mercury for communication), lightly.
2. **Retrograde now** — for any planet currently retrograde, explain in everyday terms what retrograde traditionally invites (review, revisit, slow down) — NOT doom.
3. **What's coming** — mention the next station date(s) as gentle "watch for a shift" notes.
End with one encouraging line. Do NOT make fated, medical or financial claims; frame retrogrades as invitations to reflect, not warnings."""

    def _build_almanac_prompt(self, d: Dict[str, Any]) -> str:
        """Turn the day's panchanga + planetary hours into a friendly day-guide."""
        p = d.get("panchanga") or {}
        hours = (d.get("hours") or {}).get("horas", [])
        tithi = p.get("tithi") or {}
        nak = p.get("nakshatra") or {}
        yoga = p.get("yoga") or {}
        karana = p.get("karana") or {}
        vaara = p.get("vaara") or {}
        hijri = p.get("hijri") or {}

        def _rng(x):
            return f"{x.get('start')}–{x.get('end')}" if x and x.get("start") else "—"

        # A couple of upcoming benefic day-horas as favourable windows.
        good = [h for h in hours if h.get("period") == "day" and h.get("benefic")]
        good_lines = "\n".join(
            f"- {h['planet']} hora {h['start']}–{h['end']}" for h in good[:4]
        ) or "- (none listed)"
        engine = "Surya-Siddhanta" if p.get("system") == "surya_siddhanta" else "Drik"

        return f"""You are a warm, plain-spoken almanac guide explaining today's PANCHANGA (the Vedic daily almanac) in everyday language. Keep it simple, practical and encouraging — no heavy jargon.

Date: {p.get('date')} ({vaara.get('name')}) at {p.get('place') or 'the chosen place'} — computed with the {engine} engine.
Sunrise {p.get('sunrise')}, sunset {p.get('sunset')}.
The five limbs:
- Tithi (lunar day): {tithi.get('name')} ({tithi.get('paksha')} paksha){', ends ' + tithi.get('ends') if tithi.get('ends') else ''}
- Nakshatra (star): {nak.get('name')}{' pada ' + str(nak.get('pada')) if nak.get('pada') else ''}
- Yoga: {yoga.get('name')}
- Karana: {karana.get('name')}
Auspicious window — Abhijit muhurta: {_rng(p.get('abhijit'))}.
Periods to avoid — Rahu Kalam {_rng(p.get('rahu_kalam'))}, Yamaganda {_rng(p.get('yamaganda'))}, Gulika {_rng(p.get('gulika'))}.
Favourable planetary hours (benefic day-horas):
{good_lines}
Hijri (Islamic) date: {(str(hijri.get('day')) + ' ' + hijri.get('month_name') + ' ' + str(hijri.get('year')) + ' AH') if hijri else 'n/a'}.

Write a friendly ~250-300 word day-guide:
1. **The day's mood** — what this tithi + nakshatra + weekday combination traditionally feels like, in a sentence or two.
2. **Good windows** — point to the Abhijit muhurta and a benefic hora as good times for important tasks (starting things, meetings, decisions), with the clock times.
3. **Go gently** — note the Rahu Kalam / Yamaganda / Gulika windows as times to avoid launching anything important, framed lightly.
4. End with one short, encouraging line.

Use only the times given; do NOT invent windows. Do NOT make medical, financial, legal or fated claims. Close with a one-line reminder that the panchanga is a traditional rhythm-of-the-day aid for reflection, not a rule to live by."""

    def _build_muhurta_prompt(self, m: Dict[str, Any]) -> str:
        """Explain the recommended auspicious windows for the chosen activity."""
        windows = m.get("best_windows", [])[:8]
        win_lines = "\n".join(
            f"- {w['date']} {w['start']}–{w['end']} · {w['label']} ({w['quality']}) — {w['reason']}"
            for w in windows
        ) or "- (no clearly auspicious window found in this range)"

        # A few of the strongest days for context.
        days = sorted(m.get("days", []), key=lambda d: -d.get("score", 0))[:4]
        day_lines = "\n".join(
            f"- {d['date']} ({d['weekday']}): {d['rating']} — {d['nakshatra']['name']} nakshatra, "
            f"{d['tithi']['name']} tithi, {d['yoga']['name']} yoga"
            for d in days
        ) or "- (none)"

        return f"""You are a warm, practical Vedic muhurta (electional astrology) guide helping someone pick an auspicious time for: **{m.get('activity_label', 'their activity')}**, between {m.get('start_date')} and {m.get('end_date')} at {m.get('place') or 'the chosen place'}.

The engine has already scored each day from its Panchanga (nakshatra, tithi, weekday, yoga) and, avoiding Rahu Kalam / Yamaganda / Gulika, extracted concrete time windows.

Top recommended windows (use ONLY these — do not invent times):
{win_lines}

Strongest days in the range:
{day_lines}

Write a friendly ~250-word note:
1. **Best pick** — recommend the single strongest window (date + clock time) and say plainly WHY (which nakshatra / tithi / hora makes it good).
2. **Alternatives** — mention 1–2 backup windows.
3. **What to avoid** — remind them the choppy periods (Rahu Kalam etc.) are already excluded, and to keep the activity within the given window.
Keep it grounded and encouraging. Do NOT make fated, medical, legal or financial guarantees. Close with one line noting muhurta is a traditional aid to timing, and personal readiness matters too."""

    def _build_prashna_prompt(self, p: Dict[str, Any]) -> str:
        """A Prashna (horary) reading of the moment-chart for the question asked."""
        lagna = p.get("lagna") or {}
        moon = p.get("moon") or {}
        sun = p.get("sun") or {}
        panch = p.get("panchanga") or {}
        moment = p.get("moment") or {}
        planets = p.get("planets") or {}

        # Compact one-line placements for the nine grahas.
        plines = "\n".join(
            f"- {name}: {info.get('sign_name')} {round(info.get('degrees', 0), 1)}°"
            f"{' (retrograde)' if info.get('retrograde') else ''}, "
            f"{info.get('nakshatra')} nakshatra"
            for name, info in planets.items()
        )
        tithi = panch.get("tithi") or {}
        nak = panch.get("nakshatra") or {}

        question = p.get("question") or "(no specific question given — read the general tenor)"

        return f"""You are an experienced Vedic PRASHNA (horary) astrologer. A chart has been cast for the exact MOMENT the question was asked — in Prashna, this moment-chart itself answers the question; no birth data is used. Read it in that spirit: the Ascendant is the querent, the Moon is the mind and the matter asked about, and the relevant house/lord shows the outcome.

The question: "{question}"

Moment: {moment.get('date')} {moment.get('time')} at {p.get('place') or 'the chosen place'}
Ascendant (Lagna): {lagna.get('sign_name')} {round(lagna.get('degrees', 0), 1)}°
Moon: {moon.get('sign_name')}, {moon.get('nakshatra')} nakshatra pada {moon.get('nakshatra_pada')}
Sun: {sun.get('sign_name')}
Running hora (planetary hour) lord: {p.get('hora_lord') or 'n/a'}
Panchanga: {tithi.get('name')} tithi ({tithi.get('paksha')} paksha), {nak.get('name')} nakshatra.
Planetary placements at the moment:
{plines}

Write a focused ~300-word horary reading:
1. **The lay of the chart** — one line on the Ascendant + the Moon's condition (its sign, nakshatra, whether it's waxing/strong), since the Moon is central in Prashna.
2. **The answer** — address the question directly: lean toward a "likely yes", "likely no", or "mixed / conditional", grounded in the relevant house, its lord, and the Moon's placement/aspects. Be honest about ambiguity.
3. **Timing** — if the chart suggests a timeframe (from the Moon's nakshatra, the lord's position, or an applying aspect), give a gentle sense of when.
4. **Guidance** — one practical, encouraging suggestion.
Reason from the placements given; cite the factors behind your read. Do NOT make medical, legal or financial guarantees, and frame the answer as astrological guidance, not certainty."""

    def _build_daily_digest_prompt(self, d: Dict[str, Any], name: str) -> str:
        """A warm personalized 'today' reading tying panchanga + dasha + transits."""
        panch = d.get("panchanga") or {}
        dasha = d.get("dasha") or {}
        transits = d.get("transits") or {}
        tithi = panch.get("tithi") or {}
        nak = panch.get("nakshatra") or {}
        vaara = panch.get("vaara") or {}
        highlights = "\n".join(f"- {h}" for h in d.get("highlights", [])) or "- (a quiet day)"
        bhukti = (dasha.get("bhukti") or {})
        upcoming = "\n".join(
            f"- {u['planet']} enters {u['to_sign']} on {u['date']}"
            for u in transits.get("upcoming", [])
        ) or "- (none imminent)"
        retro = transits.get("retrograde", [])

        return f"""You are a warm, encouraging personal Vedic astrologer writing {name}'s DAILY briefing for {d.get('date')}. Tie together the day's almanac, their current dasha period, and the sky's transits into one short, grounded note. Speak TO them ("you"), plainly.

Today's panchanga: {vaara.get('name')}, {tithi.get('paksha')} {tithi.get('name')}, {nak.get('name')} nakshatra.
Current dasha: {dasha.get('maha_lord', 'n/a')} Mahadasha{', ' + bhukti.get('lord') + ' Bhukti' if bhukti.get('lord') else ''} (Mahadasha runs to {dasha.get('maha_end', 'n/a')}).
Sade-Sati active: {'yes' if transits.get('sade_sati') else 'no'}.
Retrograde now: {', '.join(retro) if retro else 'none'}.
Upcoming ingresses:
{upcoming}
Key highlights the engine flagged:
{highlights}

Write a friendly ~200-word daily note:
1. **Today's tone** — what the tithi + nakshatra + weekday invite, in a sentence or two.
2. **Your bigger arc** — a line tying it to the current dasha/bhukti (and Sade-Sati or a nearing dasha change if flagged), framed constructively.
3. **A gentle nudge** — one practical suggestion for making the most of today.
End on an encouraging line. Do NOT make fated, medical, legal or financial claims; keep it a supportive daily reflection."""

    def _build_bhrigu_markers_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Read the Nadi/Bhrigu yearly markers: the Moon-based annual progression
        and the Bhrigu Bindu activations."""
        bb = d.get("bhrigu_bindu") or {}
        prog = d.get("progression") or []
        acts = d.get("activations") or []

        prog_lines = "\n".join(
            f"- Age {p['age']} ({p['year']}): {p['sign_name']} (lord {p['sign_lord']})"
            + (f", natal {', '.join(p['planets'])} here" if p.get("planets") else ", empty sign")
            + (" ← Bhrigu Bindu sign" if p.get("is_bhrigu_bindu") else "")
            + (" ← natal Moon sign" if p.get("is_moon_sign") else "")
            for p in prog
        ) or "- (none)"

        act_lines = "\n".join(
            f"- {a['date']}: {a['planet']} enters {a['sign_name']} ({a['target']} sign)"
            for a in acts
        ) or "- (none in the searched horizon)"

        return f"""You are a thoughtful Vedic astrologer explaining {name}'s **Bhrigu / Nadi-style yearly markers**. Two classical, clearly-labelled devices have been pre-computed — read them, do not recompute or invent placements.

**1. Annual progression (Nadi one-sign-per-year from the Moon).** The natal Moon is in {d.get('moon_sign')}. Each year of life the "marker sign" advances by one rasi; the natal planets sitting in that sign are what the year activates. Current age: {d.get('age_now')}.
{prog_lines}

**2. Bhrigu Bindu (the Rahu–Moon midpoint, a Nadi sensitive point).** It sits in {bb.get('sign_name')} at {bb.get('degrees')}°, house {bb.get('house_from_lagna')} from the Lagna (lord {bb.get('sign_lord')}). The next Jupiter/Saturn transits that activate the Bhrigu Bindu and Moon signs:
{act_lines}

Write a grounded ~280-word note:
1. **The theme of the coming years** — walk through 2–3 of the most notable progressed years above (those with natal planets, or the Bhrigu-Bindu / Moon-sign years) and what area of life the sign + its occupants suggest.
2. **Milestone triggers** — mention the nearest Jupiter or Saturn activation date and why a slow-planet touching the Bhrigu Bindu is treated as a turning-point in Nadi thought.
3. **How to use it** — one calm, practical line.
Reason only from the markers given. Frame everything as a traditional predictive *aid* — evocative, not fated. Do NOT make medical, legal or financial predictions. Close with one line noting these are indicative markers, and free will shapes the outcome."""

    def _build_remedies_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Explain the suggested per-planet remedies, warmly and responsibly."""
        rems = d.get("remedies") or []
        if not rems:
            body = "No planet came out clearly weak or afflicted in this chart — a reassuring sign."
            rem_lines = ""
        else:
            body = (f"{len(rems)} planet(s) came out weak or afflicted "
                    "(debilitated, shadbala-deficient, or in a dusthana).")
            rem_lines = "\n".join(
                f"- **{r['planet']}** ({r['reason']}): gemstone {r['gemstone']}, "
                f"mantra \"{r['mantra']}\" (~{r.get('mantra_count')} times), deity {r['deity']}, "
                f"day {r['day']}, charity: {r['donation']}, colour {r['color']}."
                for r in rems
            )

        return f"""You are a warm, responsible Vedic astrologer explaining traditional **remedial measures (upaya)** for {name}. The chart's weak/afflicted planets and the classical remedies for each have already been computed — explain them, do not invent new ones.

{body}
{rem_lines}

Write a caring ~260-word note:
1. **What's asking for support** — in plain language, which planet(s) are running weak and what life-areas they touch (keep it constructive, never alarming).
2. **The gentlest remedies first** — emphasise that mantra, charity (daana), fasting on the planet's weekday, and devotion are the safe, accessible upayas anyone can begin; walk through 1–2 concretely.
3. **On gemstones** — note clearly that gemstones and yantras are powerful and should be worn ONLY after consulting a qualified astrologer, never self-prescribed.
Frame all of this as **traditional guidance and devotional practice, not medical, psychological, legal or financial advice**, and not a guarantee of results. Close by reminding them that sincere effort and good conduct are themselves the strongest remedy."""

    def _build_kp_prompt(self, d: Dict[str, Any], name: str) -> str:
        """A Krishnamurti Paddhati (KP) reading grounded in cuspal sub-lords,
        the four-fold significators and the ruling planets."""
        planets = d.get("planets") or []
        cusps = d.get("cusps") or []
        sig = d.get("significators") or {}
        rp = (d.get("ruling_planets") or {}).get("planets") or []

        p_lines = "\n".join(
            f"- {p['body']}: {p['sign_name']} {p['degrees']}° (house {p['house']}), "
            f"sign lord {p['sign_lord']}, star lord {p['star_lord']}, sub lord {p['sub_lord']}"
            for p in planets)
        c_lines = "\n".join(
            f"- Cusp {c['house']}: {c['sign_name']}, sub lord {c['sub_lord']}"
            for c in cusps)
        s_lines = "\n".join(
            f"- {planet}: signifies houses {', '.join(str(h) for h in info.get('houses', []))} "
            f"(star lord {info.get('star_lord')})"
            for planet, info in sig.items())

        return f"""You are an expert **KP (Krishnamurti Paddhati)** astrologer reading {name}'s chart. KP judges results by the **sub-lord** of the relevant cusp and by a planet's **star (nakshatra) lord** — a planet gives the results of the houses signified by its star lord first. Everything below is already computed on the KP (Krishnamurti) ayanamsa — read it, do not recompute.

Ascendant & planets (sign / star / sub lords):
{p_lines}

Cuspal sub-lords:
{c_lines}

Four-fold significators (houses each planet signifies):
{s_lines}

Ruling planets right now: {', '.join(rp) if rp else 'n/a'}.

Write a focused ~320-word KP reading:
1. **How to read this chart in KP** — one or two lines on what the Ascendant sub-lord and the chart's overall significator pattern suggest.
2. **Two or three life areas** — pick houses that matter (e.g. 7th for marriage, 10th for career, 2nd/11th for wealth) and judge them from their **cuspal sub-lord** and its significations; name the planets that promise each result.
3. **Timing hint** — note that KP times events by the dasha of a house's significators, and mention the ruling planets as the day's active lords.
Reason strictly from the sub-lords and significators given; cite them. Frame it as astrological guidance, not certainty, and avoid medical/legal/financial guarantees."""

    def _build_kp_horary_prompt(self, d: Dict[str, Any], question: str) -> str:
        """A KP horary (1-249) judgement for the querent's number + question."""
        asc = d.get("ascendant") or {}
        planets = d.get("planets") or []
        rp = (d.get("ruling_planets") or {}).get("planets") or []
        moment = d.get("moment") or {}
        p_lines = "\n".join(
            f"- {p['body']}: {p['sign_name']} {p['degrees']}°, star lord {p['star_lord']}, sub lord {p['sub_lord']}"
            for p in planets)
        q = question or "(no specific question given — read the general tenor)"
        return f"""You are an expert **KP horary (Prasna)** astrologer. The querent chose the number **{asc.get('number')}** (of 1-249), which fixes the horary Ascendant at **{asc.get('sign_name')} {asc.get('degrees')}°** — sign lord {asc.get('sign_lord')}, star lord {asc.get('star_lord')}, **sub lord {asc.get('sub_lord')}**. The planets are cast for the moment the question was asked ({moment.get('date')} {moment.get('time')}).

The question: "{q}"

Planetary sub-lords at the moment:
{p_lines}

Ruling planets: {', '.join(rp) if rp else 'n/a'}.

Write a ~280-word KP horary judgement:
1. **The Ascendant sub-lord** — in KP horary this is decisive; read what {asc.get('sub_lord')} as the Ascendant sub-lord indicates for the matter (its house significations and whether it favours the querent).
2. **The answer** — lean toward a "likely yes", "likely no", or "conditional", grounded in the sub-lord of the house that governs the question and the ruling planets. Be honest about ambiguity.
3. **Timing** — a gentle sense of when, from the significators/ruling planets.
Reason from the sub-lords given; cite them. Frame it as guidance, not certainty; no medical/legal/financial guarantees."""

    def _build_jaimini_prompt(self, d: Dict[str, Any], name: str) -> str:
        """A Jaimini reading built on the Chara Karakas, Karakamsa/Swamsa and argala."""
        ck = d.get("chara_karakas") or []
        kk = d.get("karakamsa") or {}
        sw = d.get("swamsa") or {}
        argala = d.get("argala") or []
        ck_lines = "\n".join(
            f"- {k['karaka']}: {k['planet']} in {k['sign_name']}"
            + (f" (house {k['house']})" if k.get('house') else "")
            for k in ck)
        arg_lines = "\n".join(
            f"- House {a['house']} ({a['sign_name']}): argala from {', '.join(a['argala']) or 'none'}; "
            f"virodhargala (counter) from {', '.join(a['virodhargala']) or 'none'}"
            for a in argala)
        return f"""You are an expert **Jaimini** astrologer reading {name}'s chart. Jaimini reasons from the **Chara Karakas** (the eight variable significators, ranked by longitude), the **Karakamsa** (the Atmakaraka's Navamsa sign — read like a second ascendant for the soul's agenda) and **argala** (planetary intervention on a house). Everything below is pre-computed — interpret it, do not recompute.

Chara Karakas:
{ck_lines}

Atmakaraka (soul planet): **{d.get('atmakaraka')}**.
Karakamsa: the Atmakaraka {kk.get('planet')} is in **{kk.get('sign_name')}** in the Navamsa; occupants there: {', '.join(kk.get('occupants', [])) or 'none'}; planets aspecting it (rasi drishti): {', '.join(kk.get('aspecting_planets', [])) or 'none'}.
Swamsa (Navamsa Lagna): **{sw.get('sign_name')}**; occupants: {', '.join(sw.get('occupants', [])) or 'none'}; aspected by: {', '.join(sw.get('aspecting_planets', [])) or 'none'}.

Argala (intervention) on the Lagna & 7th:
{arg_lines}

Write a ~320-word Jaimini reading:
1. **The soul's agenda (Karakamsa)** — what the Karakamsa sign, its occupants and the planets aspecting it say about calling, temperament and the deeper life theme (this is the heart of Karakamsa analysis).
2. **The Chara Karakas** — read 2-3 of the key karakas (Atma, Amatya, Dara) and what their placement suggests for self, career and partnership.
3. **Argala** — one line on where the Lagna receives supportive intervention vs a counter (virodhargala).
Reason from the factors given; cite them. Frame it as astrological insight, not fate; no medical/legal/financial guarantees."""

    def _build_now_chart_prompt(self, d: Dict[str, Any]) -> str:
        """Read the chart of the moment (the current sky) as a general tenor."""
        lagna = d.get("lagna") or {}
        planets = d.get("planets") or {}
        panch = d.get("panchanga") or {}
        moment = d.get("moment") or {}
        tithi = (panch.get("tithi") or {}) if panch else {}
        nak = (panch.get("nakshatra") or {}) if panch else {}
        vaara = (panch.get("vaara") or {}) if panch else {}
        p_lines = "\n".join(
            f"- {name}: {info.get('sign_name')} (house {info.get('house')})"
            for name, info in planets.items())
        return f"""You are a Vedic astrologer reading the **chart of the moment** — the current sky cast for {moment.get('date')} {moment.get('time')} at {d.get('place') or 'this place'}. This is not a birth chart; it reflects the tenor of the present time itself (like a mundane/prasna snapshot). Read it in that spirit.

Ascendant now: {lagna.get('sign_name')} {round(lagna.get('degrees', 0), 1)}°.
Panchanga: {vaara.get('name', 'n/a')}, {tithi.get('name', 'n/a')}, {nak.get('name', 'n/a')} nakshatra. Running hora lord: {d.get('hora_lord') or 'n/a'}.
Planets now:
{p_lines}

Write a short ~220-word reading of the moment:
1. **The mood of now** — what the rising sign + Moon's placement + the panchanga invite, in a couple of sentences.
2. **What's favoured / what to be mindful of** — 2-3 practical notes on the kinds of activity the current planetary positions support or caution against right now.
3. **A gentle close** — one grounding line.
Reason from the placements given; cite them. This is a reflective snapshot of the present, not a personal fated prediction — avoid medical/legal/financial claims."""

    def _build_rectification_prompt(self, r: Dict[str, Any], name: str) -> str:
        """Explain, in plain terms, why the suggested birth time fits better than
        the entered one. The rectification (method, delta, before/after Moon &
        Lagna) is already computed — the model only interprets it, gently, and
        always frames it as experimental."""
        method = r.get("method_label", r.get("method", "a suddhi check"))
        entered = r.get("entered", {})
        suggested = r.get("suggested") or {}
        before = r.get("before", {}) or {}
        after = r.get("after", {}) or {}
        b_moon = before.get("moon") or {}
        a_moon = after.get("moon") or {}
        b_lagna = before.get("lagna") or {}
        a_lagna = after.get("lagna") or {}
        delta = r.get("delta_minutes")
        rectified = r.get("rectified")

        method_expl = {
            "Nakshatra Suddhi": "checks the Moon's birth star (nakshatra) against the star expected from the exact birth moment (the ishtakaal), nudging the time so they agree",
            "Lagna Suddhi": "checks the rising sign (Lagna) against the Moon and Maandi in the Rasi and Navamsa, nudging the time so the Lagna falls in a supportive relationship to them",
            "Janma Suddhi": "checks the classical birth-time gender indication (from the ishtakaal remainder), nudging the time so it agrees with the stated gender",
        }.get(method, "nudges the birth time so a classical consistency check is satisfied")

        if rectified:
            outcome = (f"The entered time {entered.get('tob')} did NOT satisfy the check; "
                       f"the nearest time that does is {suggested.get('tob')} "
                       f"(a shift of about {delta} minutes).")
        elif r.get("already_consistent"):
            outcome = f"The entered time {entered.get('tob')} already satisfies the check — no shift was needed."
        else:
            outcome = "No time within the search window satisfied the check."

        return f"""You are a warm, plain-spoken Vedic astrologer explaining an EXPERIMENTAL birth-time rectification to someone with little astrology background. Avoid jargon; when you must use a term (nakshatra, lagna, ishtakaal), explain it in a few words.

Birth-time rectification tries to refine an uncertain recorded birth time so the chart is internally consistent by a classical rule. This is a HEURISTIC — a suggestion to verify against real life events, never an authoritative correction.

Person: {name}
Method used: {method} — this {method_expl}.
{outcome}

What moved (fast-changing points, within the small time shift):
- Moon star: was {b_moon.get('nakshatra')} pada {b_moon.get('pada')} ({b_moon.get('sign_name')}) → now {a_moon.get('nakshatra')} pada {a_moon.get('pada')} ({a_moon.get('sign_name')})
- Rising sign (Lagna): was {b_lagna.get('sign_name')} (star {b_lagna.get('nakshatra')}) → now {a_lagna.get('sign_name')} (star {a_lagna.get('nakshatra')})

Write a short, clear explanation (about 200-250 words) with:
1. **What was checked** — one or two sentences on what this method looks at, in everyday language.
2. **Why the suggested time fits better** — explain what boundary the suggested time snapped to (which star/pada or rising-sign the shift aligns), using only the before/after facts above. If nothing changed, say the entered time already looked consistent.
3. **How to verify** — 2-3 gentle, concrete suggestions (compare against known timed life events, confirm the recorded time with family/records, try another method).

Be specific to the facts above — do not invent placements. Do NOT predict death, disease, or precise future dates. End with one short line reminding that rectification is experimental and the recorded time, where reliable, should be trusted first."""

    def _build_event_rectification_prompt(self, r: Dict[str, Any], name: str) -> str:
        """Explain why the event-matched birth time fits the supplied life events.
        The candidate scan, the winning time, and the per-event dasha/transit matches
        are already computed deterministically — the model only narrates them, gently,
        and always frames the result as experimental."""
        entered = r.get("entered", {})
        suggested = r.get("suggested") or {}
        rectified = r.get("rectified")
        delta = r.get("delta_minutes")
        confidence = r.get("confidence")
        window = r.get("window_minutes")
        before = r.get("before", {}) or {}
        after = r.get("after", {}) or {}
        b_lagna = (before.get("lagna") or {})
        a_lagna = (after.get("lagna") or {})

        lines = []
        for ev in r.get("events", []):
            matched = ev.get("matched") or []
            m = ("; ".join(matched)) if matched else "no strong dasha/transit link found"
            lines.append(
                f"- {ev.get('type')} on {ev.get('date')}: running Mahadasha "
                f"{ev.get('maha')} / Bhukti {ev.get('bhukti')} → {m} (score {ev.get('score')})"
            )
        event_block = "\n".join(lines) or "- (no events)"

        if rectified:
            outcome = (f"The entered time {entered.get('tob')} was refined to "
                       f"{suggested.get('tob')} (a shift of about {delta} minutes), which "
                       f"scored best against the events (fit ≈ {confidence}%). The rising sign "
                       f"moved from {b_lagna.get('sign_name')} to {a_lagna.get('sign_name')}.")
        else:
            outcome = (f"The entered time {entered.get('tob')} already scored best against the "
                       f"events (fit ≈ {confidence}%); no shift was suggested.")

        return f"""You are a warm, plain-spoken Vedic astrologer explaining an EXPERIMENTAL, event-based birth-time rectification to someone with little astrology background. Avoid jargon; when you must use a term (dasha, bhukti, lagna, transit), explain it in a few words.

Event-based rectification takes known dated life events and finds the birth time whose planetary *timing* (the Vimsottari dasha period running at each event, plus Jupiter/Saturn transits) best lines up with what classically signifies each event. It is a HEURISTIC that gets stronger with more events — a suggestion to verify, never an authoritative correction. It searched within ±{window} minutes of the entered time.

Person: {name}
{outcome}

Per-event timing matches the calculation found (already computed — trust these, do not re-derive):
{event_block}

Write a short, clear explanation (about 220-280 words) with:
1. **How this works** — one or two sentences on the idea (matching event dates to the planetary periods that rule those matters).
2. **Why this time fits the events** — walk through 2-3 of the strongest event matches above in everyday language (e.g. "your marriage fell in a period ruled by the planet governing marriage in your chart"). Use only the matches listed.
3. **How confident to be** — be honest that the fit is ≈{confidence}% and improves with more events; a low fit means the events don't strongly pin the time.
4. **How to verify** — 2-3 gentle suggestions (add more well-dated events, cross-check the recorded time with family/records, compare with the rule-based methods).

Be specific to the matches above — do not invent placements or events. Do NOT predict death, disease, or precise future dates. End with one short line reminding that this is experimental and the recorded time, where reliable, should be trusted first."""

    def _format_planets(self, planets: Dict[str, Any]) -> str:
        """Format planetary positions for prompt"""
        result = []
        for planet, data in planets.items():
            result.append(f"- {planet}: {data.get('sign_name', 'Unknown')}")
        return "\n".join(result)

    # ------------------------------------------------------------------ #
    # Agentic tool-calling mode
    # ------------------------------------------------------------------ #
    # Messages are kept in a provider-neutral internal format and converted per
    # provider on each call (the OpenAI vs Ollama tool-call schemas differ):
    #   {"role": "system"|"user"|"assistant", "content": str}
    #   {"role": "assistant", "content": str|None,
    #    "tool_calls": [{"id", "name", "args": dict}]}
    #   {"role": "tool", "id", "name", "content": str}

    @staticmethod
    def _to_openai_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for m in messages:
            role = m.get("role")
            if role == "assistant" and m.get("tool_calls"):
                out.append({
                    "role": "assistant",
                    "content": m.get("content") or None,
                    "tool_calls": [{
                        "id": c.get("id"), "type": "function",
                        "function": {"name": c["name"],
                                     "arguments": json.dumps(c.get("args") or {})},
                    } for c in m["tool_calls"]],
                })
            elif role == "tool":
                out.append({"role": "tool", "tool_call_id": m.get("id"),
                            "content": m.get("content", "")})
            else:
                out.append({"role": role, "content": m.get("content", "")})
        return out

    @staticmethod
    def _to_ollama_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for m in messages:
            role = m.get("role")
            if role == "assistant" and m.get("tool_calls"):
                out.append({
                    "role": "assistant", "content": m.get("content") or "",
                    "tool_calls": [{"function": {"name": c["name"],
                                                 "arguments": c.get("args") or {}}}
                                   for c in m["tool_calls"]],
                })
            elif role == "tool":
                out.append({"role": "tool", "content": m.get("content", "")})
            else:
                out.append({"role": role, "content": m.get("content", "")})
        return out

    @staticmethod
    def _to_text_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Flatten tool turns into plain text — used for the JSON-protocol path and
        any provider called without native tools."""
        out = []
        for m in messages:
            role = m.get("role")
            if role == "assistant" and m.get("tool_calls"):
                calls = "; ".join(f"{c['name']}({json.dumps(c.get('args') or {})})"
                                  for c in m["tool_calls"])
                out.append({"role": "assistant",
                            "content": f"[Requested data via tools: {calls}]"})
            elif role == "tool":
                out.append({"role": "user",
                            "content": f"[Result of {m.get('name')}]:\n{m.get('content','')}"})
            else:
                out.append({"role": role, "content": m.get("content", "")})
        return out

    @staticmethod
    def _openai_tool_payload(specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{"type": "function", "function": {
            "name": s["name"], "description": s["description"],
            "parameters": s["parameters"]}} for s in specs]

    @staticmethod
    def _json_tools_instructions(specs: List[Dict[str, Any]]) -> str:
        lines = [
            "When you need astrological data you do not yet have, reply with ONLY a "
            "JSON object on its own line and nothing else:",
            '{"tool": "<tool_name>", "args": { ... }}',
            "After you receive the result you may request more tools the same way, or "
            "— when you have enough — reply with your final answer as normal prose "
            "(no JSON).",
            "", "Available tools:",
        ]
        for s in specs:
            props = s["parameters"].get("properties", {})
            req = set(s["parameters"].get("required", []))
            params = (", ".join(f"{k}{'*' if k in req else ''}" for k in props)
                      if props else "no arguments")
            lines.append(f"- {s['name']}({params}): {s['description']}")
        return "\n".join(lines)

    @staticmethod
    def _parse_json_tool(content: Optional[str]) -> Optional[Dict[str, Any]]:
        """Extract a {"tool", "args"} request from a JSON-protocol reply, tolerating
        code fences and surrounding prose."""
        if not content:
            return None
        s = content.strip()
        if s.startswith("```"):
            s = s.strip("`")
            if s[:4].lower() == "json":
                s = s[4:]
            s = s.strip()
        obj = None
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            i, j = s.find("{"), s.rfind("}")
            if i != -1 and j > i:
                try:
                    obj = json.loads(s[i:j + 1])
                except json.JSONDecodeError:
                    return None
        if isinstance(obj, dict) and obj.get("tool"):
            return {"name": obj["tool"], "args": obj.get("args") or {}}
        return None

    def build_tool_messages(self, seed_block: str, question: str,
                            history: Optional[List[Dict[str, str]]],
                            use_json: bool, specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        system = SYSTEM_PROMPT + "\n\n" + seed_block + "\n\n" + TOOL_MODE_NOTE
        if use_json:
            system += "\n\n" + self._json_tools_instructions(specs)
        messages = [{"role": "system", "content": system}]
        for m in (history or []):
            if m.get("role") in ("user", "assistant") and m.get("content"):
                messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": question})
        return messages

    async def run_tool_loop(self, seed_block: str, question: str,
                            history: Optional[List[Dict[str, str]]], cfg: ModelConfig,
                            birth_details: Dict[str, Any], ayanamsa: str,
                            tool_names: Optional[List[str]] = None,
                            max_rounds: int = MAX_TOOL_ROUNDS,
                            usage: Optional[Dict[str, Any]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Drive the agentic loop, yielding event dicts:
          {"type": "tool_call", "name", "args"}
          {"type": "tool_result", "name", "ok"}
          {"type": "notice", "text"}
          {"type": "token", "text"}   (the final answer)
        Tokens reported by each round are summed into `usage` if provided."""
        specs = tool_registry.tool_specs(tool_names)
        # All providers attempt native function-calling first (OpenAI-style, Ollama,
        # Gemini); if a native round throws, the loop falls back to the universal
        # JSON protocol below.
        use_json = False
        messages = self.build_tool_messages(seed_block, question, history, use_json, specs)

        agg = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        have_usage = False
        # Some models write their answer in a tool-calling round (as a preamble) and
        # then return an empty final message — keep the last non-empty content as a
        # fallback so we never end with a blank answer.
        last_content = ""

        def _add_usage(u):
            nonlocal have_usage
            if not u:
                return
            have_usage = True
            for k in agg:
                agg[k] += u.get(k) or 0

        # Within a single answer, identical tool calls (same name + args) are served
        # from a cache so the same compute isn't redone, and a tool repeated past
        # MAX_DUP_TOOL_CALLS is short-circuited with a nudge — this breaks the loop a
        # weak model can fall into where it keeps requesting the same data.
        tool_cache: Dict[str, Any] = {}
        call_counts: Dict[str, int] = {}

        def _tool_key(name: str, args: Optional[Dict[str, Any]]) -> str:
            try:
                return name + "::" + json.dumps(args or {}, sort_keys=True, default=str)
            except Exception:
                return name + "::" + str(args)

        rounds = 0
        while rounds < max_rounds:
            rounds += 1
            try:
                res = await self._chat_once(messages, specs, cfg, use_json)
            except Exception as e:
                if not use_json:
                    # Native tools unsupported/failed → switch to JSON protocol.
                    use_json = True
                    messages[0]["content"] += "\n\n" + self._json_tools_instructions(specs)
                    yield {"type": "notice", "text": "Switching to compatibility tool mode."}
                    rounds -= 1
                    continue
                yield {"type": "token", "text": f"\n\n[Tool mode error: {e}]"}
                if usage is not None and have_usage:
                    usage.update(agg)
                return

            _add_usage(res.get("usage"))
            if res.get("content"):
                last_content = res["content"]
            tool_calls = res.get("tool_calls") or []
            if use_json and not tool_calls:
                parsed = self._parse_json_tool(res.get("content"))
                if parsed:
                    tool_calls = [{"id": f"call_{rounds}",
                                   "name": parsed["name"], "args": parsed["args"]}]

            if not tool_calls:
                final = res.get("content") or ""
                if not final:
                    # Model stopped calling tools but returned no text. Force a plain
                    # prose answer from the data gathered so far (never blank-box).
                    messages.append({"role": "user", "content":
                        "Now write your final answer for the user in prose, based on "
                        "the data above. Do not call any more tools."})
                    try:
                        forced, u = await self._complete_chat(messages, cfg)
                        _add_usage(u)
                        final = forced or last_content
                    except Exception:
                        final = last_content
                yield {"type": "token", "text": final or
                       "[The model did not return an answer. Please try again, or "
                       "switch to Full context mode.]"}
                if usage is not None and have_usage:
                    usage.update(agg)
                return

            messages.append({"role": "assistant", "content": res.get("content"),
                             "tool_calls": tool_calls})
            for c in tool_calls:
                args = c.get("args") or {}
                key = _tool_key(c["name"], args)
                call_counts[key] = call_counts.get(key, 0) + 1
                yield {"type": "tool_call", "name": c["name"], "args": args}
                if call_counts[key] > MAX_DUP_TOOL_CALLS:
                    # Repeated identical call — refuse and steer the model to finish.
                    result = {"error": (
                        f"'{c['name']}' was already called with these arguments "
                        f"{MAX_DUP_TOOL_CALLS} times. Use the earlier result and give "
                        "your final answer now.")}
                    ok = False
                    yield {"type": "tool_result", "name": c["name"], "ok": ok,
                           "result": result, "cached": False}
                elif key in tool_cache:
                    # Identical to an earlier call this answer — reuse, don't recompute.
                    result = tool_cache[key]
                    ok = not (isinstance(result, dict) and result.get("error"))
                    yield {"type": "tool_result", "name": c["name"], "ok": ok,
                           "result": result, "cached": True}
                else:
                    try:
                        result = tool_registry.dispatch(c["name"], args,
                                                        birth_details, ayanamsa)
                        ok = not (isinstance(result, dict) and result.get("error"))
                    except tool_registry.ToolError as te:
                        result = {"error": str(te)}
                        ok = False
                    if ok:
                        tool_cache[key] = result
                    yield {"type": "tool_result", "name": c["name"], "ok": ok,
                           "result": result, "cached": False}
                messages.append({"role": "tool", "id": c.get("id"), "name": c["name"],
                                 "content": json.dumps(result, default=str)})

        # Round cap reached — force a final answer with no further tool calls.
        yield {"type": "notice", "text": "Reached the tool-call limit; answering now."}
        messages.append({"role": "user",
                         "content": "You have enough information now. Provide your "
                                    "final answer without calling any more tools."})
        try:
            content, u = await self._complete_chat(messages, cfg)
            _add_usage(u)
            yield {"type": "token", "text": content or last_content or "[No answer produced]"}
        except Exception as e:
            yield {"type": "token", "text": last_content or f"\n\n[Tool mode error: {e}]"}
        if usage is not None and have_usage:
            usage.update(agg)

    async def _chat_once(self, messages, specs, cfg, use_json) -> Dict[str, Any]:
        """One non-streaming round. Returns
        {"content": str|None, "tool_calls": [...], "usage": {...}|None}."""
        if use_json:
            content, u = await self._complete_chat(messages, cfg)
            return {"content": content, "tool_calls": [], "usage": u}
        if cfg.provider_type == ProviderType.OLLAMA:
            return await self._chat_once_ollama(messages, specs, cfg)
        if cfg.provider_type in (ProviderType.OPENAI, ProviderType.OPENAI_COMPATIBLE):
            return await self._chat_once_openai(messages, specs, cfg)
        if cfg.provider_type == ProviderType.GEMINI:
            return await self._chat_once_gemini(messages, specs, cfg)
        # Unknown provider — fall back to plain chat.
        content, u = await self._complete_chat(messages, cfg)
        return {"content": content, "tool_calls": [], "usage": u}

    async def _chat_once_openai(self, messages, specs, cfg, max_tokens: int = 4096) -> Dict[str, Any]:
        max_tokens = cfg.max_tokens or max_tokens
        base_url = (cfg.base_url or "").rstrip("/")
        if not base_url:
            raise RuntimeError("no base URL configured for this provider")
        if cfg.provider_type == ProviderType.OPENAI and not cfg.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        headers = {"Content-Type": "application/json"}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"
        payload = {
            "model": cfg.model,
            "messages": self._to_openai_messages(messages),
            "temperature": 0.7,
            "max_tokens": max_tokens,
            "tools": self._openai_tool_payload(specs),
            "tool_choice": "auto",
        }
        timeout = 300.0 if cfg.provider_type == ProviderType.OPENAI_COMPATIBLE else 120.0
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
            if r.status_code != 200:
                raise RuntimeError(f"{cfg.model}: {r.status_code} - {r.text[:300]}")
            data = r.json()
        msg = (data.get("choices") or [{}])[0].get("message", {})
        tool_calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append({"id": tc.get("id"), "name": fn.get("name"), "args": args})
        return {"content": msg.get("content"), "tool_calls": tool_calls,
                "usage": data.get("usage")}

    async def _chat_once_ollama(self, messages, specs, cfg, max_tokens: int = 4096) -> Dict[str, Any]:
        max_tokens = cfg.max_tokens or max_tokens
        url = (cfg.base_url or self.ollama_url).rstrip("/")
        payload = {
            "model": cfg.model or self.ollama_default_model,
            "messages": self._to_ollama_messages(messages),
            "stream": False,
            "tools": self._openai_tool_payload(specs),
            "options": {"temperature": 0.7, "num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.post(f"{url}/api/chat", json=payload)
            if r.status_code != 200:
                raise RuntimeError(f"Ollama {payload['model']}: {r.status_code} - {r.text[:300]}")
            data = r.json()
        msg = data.get("message", {})
        tool_calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            tool_calls.append({"id": None, "name": fn.get("name"), "args": args or {}})
        usage = None
        if data.get("prompt_eval_count") is not None or data.get("eval_count") is not None:
            pt, ct = data.get("prompt_eval_count"), data.get("eval_count")
            usage = {"prompt_tokens": pt, "completion_tokens": ct,
                     "total_tokens": (pt or 0) + (ct or 0)}
        return {"content": msg.get("content"), "tool_calls": tool_calls, "usage": usage}

    # ------------------------------------------------------------------ #
    # Gemini native function-calling
    # ------------------------------------------------------------------ #
    # Schema keys Gemini's OpenAPI-subset accepts; everything else (e.g. "default")
    # is dropped so a declaration isn't rejected.
    _GEMINI_SCHEMA_KEYS = {"type", "description", "enum", "items", "properties",
                           "required", "nullable", "format"}

    @classmethod
    def _gemini_schema(cls, schema):
        if not isinstance(schema, dict):
            return schema
        out = {}
        for k, v in schema.items():
            if k not in cls._GEMINI_SCHEMA_KEYS:
                continue
            if k == "properties" and isinstance(v, dict):
                out[k] = {pk: cls._gemini_schema(pv) for pk, pv in v.items()}
            elif k == "items":
                out[k] = cls._gemini_schema(v)
            else:
                out[k] = v
        return out

    @classmethod
    def _gemini_tool_payload(cls, specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        decls = []
        for s in specs:
            decl = {"name": s["name"], "description": s["description"]}
            params = s.get("parameters") or {}
            # Gemini rejects an empty parameters object — omit it for no-arg tools.
            if params.get("properties"):
                decl["parameters"] = cls._gemini_schema(params)
            decls.append(decl)
        return [{"functionDeclarations": decls}]

    @classmethod
    def _to_gemini_contents(cls, messages):
        """Convert neutral messages to (system_text, Gemini contents). A model's
        functionCall turn is followed by a single user turn carrying the matching
        functionResponse part(s) — consecutive tool results are merged into one user
        turn (Gemini forbids two adjacent user turns around a functionResponse)."""
        system_parts: List[str] = []
        contents: List[Dict[str, Any]] = []
        i = 0
        n = len(messages)
        while i < n:
            m = messages[i]
            role = m.get("role")
            if role == "system":
                if m.get("content"):
                    system_parts.append(m["content"])
                i += 1
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": m.get("content", "")}]})
                i += 1
            elif role == "assistant":
                if m.get("tool_calls"):
                    parts = []
                    if m.get("content"):
                        parts.append({"text": m["content"]})
                    for c in m["tool_calls"]:
                        fc = {"name": c["name"], "args": c.get("args") or {}}
                        if c.get("id"):
                            fc["id"] = c["id"]
                        parts.append({"functionCall": fc})
                    contents.append({"role": "model", "parts": parts})
                else:
                    contents.append({"role": "model", "parts": [{"text": m.get("content", "")}]})
                i += 1
            elif role == "tool":
                # Merge a run of consecutive tool results into one user turn.
                parts = []
                while i < n and messages[i].get("role") == "tool":
                    tm = messages[i]
                    try:
                        resp = json.loads(tm.get("content") or "{}")
                    except json.JSONDecodeError:
                        resp = {"result": tm.get("content", "")}
                    if not isinstance(resp, dict):
                        resp = {"result": resp}
                    fr = {"name": tm.get("name"), "response": resp}
                    if tm.get("id"):
                        fr["id"] = tm["id"]
                    parts.append({"functionResponse": fr})
                    i += 1
                contents.append({"role": "user", "parts": parts})
            else:
                i += 1
        return ("\n\n".join(system_parts) if system_parts else None, contents)

    async def _chat_once_gemini(self, messages, specs, cfg, max_tokens: int = 4096) -> Dict[str, Any]:
        max_tokens = cfg.max_tokens or max_tokens
        api_key = cfg.api_key or self.gemini_api_key
        model = cfg.model or self.gemini_default_model
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        system_text, contents = self._to_gemini_contents(messages)
        payload = {
            "contents": contents,
            "tools": self._gemini_tool_payload(specs),
            "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}},
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens},
        }
        if system_text:
            payload["system_instruction"] = {"parts": [{"text": system_text}]}
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={api_key}")
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, json=payload)
            if r.status_code != 200:
                raise RuntimeError(f"Gemini {model}: {r.status_code} - {r.text[:300]}")
            data = r.json()
        parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
        text_bits, tool_calls = [], []
        for p in parts:
            fc = p.get("functionCall")
            if fc:
                tool_calls.append({"id": fc.get("id"), "name": fc.get("name"),
                                   "args": fc.get("args") or {}})
            elif p.get("text"):
                text_bits.append(p["text"])
        um = data.get("usageMetadata") or {}
        usage = ({"prompt_tokens": um.get("promptTokenCount"),
                  "completion_tokens": um.get("candidatesTokenCount"),
                  "total_tokens": um.get("totalTokenCount")} if um else None)
        return {"content": "".join(text_bits), "tool_calls": tool_calls, "usage": usage}

    async def _complete_chat(self, messages, cfg: ModelConfig, max_tokens: int = 4096):
        """Non-streaming plain chat (no tools) over neutral messages. Returns
        (content, usage). Used by the JSON-protocol path and the forced final answer."""
        max_tokens = cfg.max_tokens or max_tokens
        if cfg.provider_type == ProviderType.OLLAMA:
            url = (cfg.base_url or self.ollama_url).rstrip("/")
            payload = {"model": cfg.model or self.ollama_default_model,
                       "messages": self._to_text_messages(messages), "stream": False,
                       "options": {"temperature": 0.7, "num_predict": max_tokens}}
            async with httpx.AsyncClient(timeout=300.0) as client:
                r = await client.post(f"{url}/api/chat", json=payload)
                if r.status_code != 200:
                    raise RuntimeError(f"Ollama: {r.status_code} - {r.text[:300]}")
                data = r.json()
            pt, ct = data.get("prompt_eval_count"), data.get("eval_count")
            usage = ({"prompt_tokens": pt, "completion_tokens": ct,
                      "total_tokens": (pt or 0) + (ct or 0)}
                     if pt is not None or ct is not None else None)
            return data.get("message", {}).get("content", ""), usage

        if cfg.provider_type in (ProviderType.OPENAI, ProviderType.OPENAI_COMPATIBLE):
            base_url = (cfg.base_url or "").rstrip("/")
            headers = {"Content-Type": "application/json"}
            if cfg.api_key:
                headers["Authorization"] = f"Bearer {cfg.api_key}"
            payload = {"model": cfg.model, "messages": self._to_text_messages(messages),
                       "temperature": 0.7, "max_tokens": max_tokens}
            timeout = 300.0 if cfg.provider_type == ProviderType.OPENAI_COMPATIBLE else 120.0
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
                if r.status_code != 200:
                    raise RuntimeError(f"{cfg.model}: {r.status_code} - {r.text[:300]}")
                data = r.json()
            msg = (data.get("choices") or [{}])[0].get("message", {})
            return msg.get("content", ""), data.get("usage")

        if cfg.provider_type == ProviderType.GEMINI:
            api_key = cfg.api_key or self.gemini_api_key
            model = cfg.model or self.gemini_default_model
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY is not set")
            plain = self._to_text_messages(messages)
            system_text = next((m["content"] for m in plain if m["role"] == "system"), None)
            contents = [{"role": "model" if m["role"] == "assistant" else "user",
                         "parts": [{"text": m["content"]}]}
                        for m in plain if m["role"] != "system"]
            payload = {"contents": contents,
                       "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens}}
            if system_text:
                payload["system_instruction"] = {"parts": [{"text": system_text}]}
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{model}:generateContent?key={api_key}")
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(url, json=payload)
                if r.status_code != 200:
                    raise RuntimeError(f"Gemini {model}: {r.status_code} - {r.text[:300]}")
                data = r.json()
            parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
            content = "".join(p.get("text", "") for p in parts)
            um = data.get("usageMetadata") or {}
            usage = ({"prompt_tokens": um.get("promptTokenCount"),
                      "completion_tokens": um.get("candidatesTokenCount"),
                      "total_tokens": um.get("totalTokenCount")} if um else None)
            return content, usage

        raise RuntimeError("Unsupported provider for tool mode")


# Singleton instance
llm_service = LLMService()
