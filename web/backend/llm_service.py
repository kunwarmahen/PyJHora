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
                            max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        """Stream an answer for a question, including chart context + prior turns."""
        messages = self.build_chat_messages(chart_data, question, history)
        if cfg.provider_type == ProviderType.OLLAMA:
            gen = self._stream_ollama(messages, cfg, max_tokens)
        elif cfg.provider_type in (ProviderType.OPENAI, ProviderType.OPENAI_COMPATIBLE):
            gen = self._stream_openai_style(messages, cfg, max_tokens)
        elif cfg.provider_type == ProviderType.GEMINI:
            gen = self._stream_gemini(messages, cfg, max_tokens)
        else:
            async def _unsupported():
                yield "Unsupported LLM provider"
            gen = _unsupported()
        async for chunk in gen:
            yield chunk

    async def _stream_ollama(self, messages, cfg, max_tokens) -> AsyncGenerator[str, None]:
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
                            break
        except httpx.ConnectError:
            yield (f"Error: Cannot connect to Ollama. Ensure it is running and the "
                   f"model is installed ('ollama pull {model}').")
        except Exception as e:
            yield f"Error calling Ollama: {str(e)}"

    async def _stream_openai_style(self, messages, cfg, max_tokens) -> AsyncGenerator[str, None]:
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
        except httpx.ConnectError:
            yield f"Error: Cannot connect to {base_url}. Is the server running?"
        except Exception as e:
            yield f"Error calling model: {str(e)}"

    async def _stream_gemini(self, messages, cfg, max_tokens) -> AsyncGenerator[str, None]:
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

    def _render_context_block(self, chart_data: Dict[str, Any]) -> str:
        """Render the full chart context (no question) — reused by the single-shot
        prompt and as the system message for streaming/multi-turn chat."""

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

        context_block = f"""Below is the COMPLETE BIRTH CHART DATA for this person, calculated using precise astronomical calculations from the PyJHora Vedic astrology software. This is REAL, VERIFIED CHART DATA - not hypothetical.

=== COMPLETE BIRTH CHART ===

{chart_description}

=== END OF CHART DATA ===

IMPORTANT INSTRUCTIONS:
1. TODAY'S DATE is {current_date} - use it to determine which Dasha/sub-period is CURRENTLY active.
2. The planetary positions, signs, houses, nakshatras, divisional charts (vargas) and Dasha periods above were calculated accurately from the exact birth time and location.
3. Be specific to THIS chart: cite the placements/dashas/yogas behind your reasoning rather than giving generic horoscope text.
4. Give practical, actionable guidance. Do NOT ask for more information — you have the complete chart and today's date."""

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

    def _format_planets(self, planets: Dict[str, Any]) -> str:
        """Format planetary positions for prompt"""
        result = []
        for planet, data in planets.items():
            result.append(f"- {planet}: {data.get('sign_name', 'Unknown')}")
        return "\n".join(result)

# Singleton instance
llm_service = LLMService()
