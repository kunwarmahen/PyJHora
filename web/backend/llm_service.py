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
import httpx
import json
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, AsyncGenerator
from enum import Enum

import tools as tool_registry

# Agentic ("tool-call") mode tuning.
MAX_TOOL_ROUNDS = 6
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
    "marriage/dharma, D10 for career, D7 for children, etc.\n\n"
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


class LLMService:
    """Unified interface for multiple LLM providers and models"""

    def __init__(self):
        # API keys
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_compat_key = os.getenv("OPENAI_COMPATIBLE_API_KEY", "")

        # Endpoints (QWEN_API_URL kept as a fallback for older configs)
        self.ollama_url = (
            os.getenv("OLLAMA_URL")
            or os.getenv("QWEN_API_URL")
            or "http://localhost:11434"
        )
        self.openai_compat_url = os.getenv(
            "OPENAI_COMPATIBLE_URL", "http://localhost:1234/v1"
        )

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
                          history: Optional[List[Dict[str, str]]] = None) -> str:
        """Ask a question about the chart. Pass either a ModelConfig or a legacy
        provider. `history` (prior {role, content} turns) enables multi-turn."""
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
        return await self._complete(prompt, cfg)

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

    # ------------------------------------------------------------------ #
    # Provider dispatch
    # ------------------------------------------------------------------ #
    async def _complete(self, prompt: str, cfg: ModelConfig, max_tokens: int = 4096) -> str:
        if cfg.provider_type == ProviderType.OLLAMA:
            return await self._call_ollama(prompt, cfg, max_tokens)
        if cfg.provider_type in (ProviderType.OPENAI, ProviderType.OPENAI_COMPATIBLE):
            return await self._call_openai_style(prompt, cfg, max_tokens)
        if cfg.provider_type == ProviderType.GEMINI:
            return await self._call_gemini(prompt, cfg, max_tokens)
        return "Unsupported LLM provider"

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
        total_tokens) once the stream completes, so the caller can persist/show it."""
        messages = self.build_chat_messages(chart_data, question, history)
        if cfg.provider_type == ProviderType.OLLAMA:
            gen = self._stream_ollama(messages, cfg, max_tokens, usage)
        elif cfg.provider_type in (ProviderType.OPENAI, ProviderType.OPENAI_COMPATIBLE):
            gen = self._stream_openai_style(messages, cfg, max_tokens, usage)
        elif cfg.provider_type == ProviderType.GEMINI:
            gen = self._stream_gemini(messages, cfg, max_tokens, usage)
        else:
            async def _unsupported():
                yield "Unsupported LLM provider"
            gen = _unsupported()
        async for chunk in gen:
            yield chunk

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

    async def _call_ollama(self, prompt: str, cfg: ModelConfig, max_tokens: int = 4096) -> str:
        url = cfg.base_url or self.ollama_url
        model = cfg.model or self.ollama_default_model
        try:
            # Local models can be slow to cold-load + generate; allow up to 5 min
            async with httpx.AsyncClient(timeout=300.0) as client:
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "system": SYSTEM_PROMPT,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": max_tokens},
                }
                response = await client.post(f"{url}/api/generate", json=payload)
                if response.status_code == 200:
                    return response.json().get("response", "No response from model")
                return f"Error from Ollama ({model}): {response.status_code} - {response.text}"
        except httpx.ConnectError:
            return ("Error: Cannot connect to Ollama. Ensure it is running "
                    "('ollama serve') and the model is installed ('ollama pull " + model + "').")
        except Exception as e:
            return f"Error calling Ollama: {str(e)}"

    async def _call_openai_style(self, prompt: str, cfg: ModelConfig, max_tokens: int = 4096) -> str:
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
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": max_tokens,
                }
                response = await client.post(f"{base_url}/chat/completions",
                                             json=payload, headers=headers)
                if response.status_code == 200:
                    result = response.json()
                    choices = result.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "No response")
                    return "No response from model"
                return f"Error from {cfg.model}: {response.status_code} - {response.text}"
        except httpx.ConnectError:
            return f"Error: Cannot connect to {base_url}. Is the server running?"
        except Exception as e:
            return f"Error calling model: {str(e)}"

    async def _call_gemini(self, prompt: str, cfg: ModelConfig, max_tokens: int = 4096) -> str:
        api_key = cfg.api_key or self.gemini_api_key
        model = cfg.model or self.gemini_default_model
        if not api_key:
            return "Error: GEMINI_API_KEY environment variable not set. Please add it to your .env file."
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                       f"{model}:generateContent?key={api_key}")
                payload = {
                    "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens},
                }
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    result = response.json()
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

        header = ("Below is birth chart data for this person, calculated using precise "
                  "astronomical calculations from the PyJHora Vedic astrology software. "
                  "This is REAL, VERIFIED CHART DATA - not hypothetical."
                  if tool_mode else
                  "Below is the COMPLETE BIRTH CHART DATA for this person, calculated "
                  "using precise astronomical calculations from the PyJHora Vedic "
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

        prompt = f"""You are an expert Vedic astrologer specializing in marriage compatibility. Below are the COMPLETE, ACCURATELY CALCULATED birth charts for both partners from PyJHora software.

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

        prompt = f"""You are an expert Vedic astrologer. Below are two COMPLETE, ACCURATELY CALCULATED birth charts from PyJHora software. Compare and contrast them as two individuals. This is NOT a marriage/compatibility (Guna Milan) reading — make no assumptions about the nature of any relationship between them.

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

Write a clear, encouraging reading (about 250-350 words) with these parts:
1. **The headline** — one or two sentences on the overall tone of this period for {name} (supportive, mixed, or a time for care).
2. **What's being touched** — for each flagged planet above, say in everyday language what it tends to stir up and which life area (e.g. Saturn → patience, work, delays; Jupiter → growth, opportunity, optimism), tied to which sensitive point it hits.
3. **What to expect & do** — 2-4 concrete, gentle suggestions for the weeks ahead.
4. End with one short line of reassurance.

Be specific to the findings above — do not invent placements that aren't listed. If nothing is flagged, say plainly that this is a calm, unremarkable window and give light general guidance. Do NOT predict death, disease, disasters, or precise dates. Close with a brief reminder that this is for reflection, not a substitute for professional advice."""

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
                yield {"type": "tool_call", "name": c["name"], "args": c.get("args") or {}}
                try:
                    result = tool_registry.dispatch(c["name"], c.get("args"),
                                                    birth_details, ayanamsa)
                    ok = not (isinstance(result, dict) and result.get("error"))
                except tool_registry.ToolError as te:
                    result = {"error": str(te)}
                    ok = False
                yield {"type": "tool_result", "name": c["name"], "ok": ok,
                       "result": result}
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
