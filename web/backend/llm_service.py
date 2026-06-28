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
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum

SYSTEM_PROMPT = (
    "You are an expert Vedic astrologer with deep knowledge of planetary "
    "positions, yogas, doshas, dashas, and their effects on human life. "
    "Provide insightful, personalized, and accurate astrological guidance."
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
    async def list_providers(self) -> List[Dict[str, Any]]:
        """Return configured providers, their availability, and model lists."""
        return [
            await self._ollama_status(),
            await self._openai_compat_status(),
            self._gemini_status(),
            self._openai_status(),
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

    async def _openai_compat_status(self) -> Dict[str, Any]:
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
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                headers = {}
                if self.openai_compat_key:
                    headers["Authorization"] = f"Bearer {self.openai_compat_key}"
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

    def _gemini_status(self) -> Dict[str, Any]:
        available = bool(self.gemini_api_key)
        return {
            "type": ProviderType.GEMINI.value,
            "label": "Google Gemini",
            "base_url": None,
            "default_model": self.gemini_default_model,
            "requires_key": True,
            "editable_base_url": False,
            "models": [
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-2.0-flash",
                "gemini-2.0-flash-lite",
            ],
            "available": available,
            "reason": None if available else "GEMINI_API_KEY is not set.",
        }

    def _openai_status(self) -> Dict[str, Any]:
        available = bool(self.openai_api_key)
        return {
            "type": ProviderType.OPENAI.value,
            "label": "OpenAI (ChatGPT)",
            "base_url": "https://api.openai.com/v1",
            "default_model": self.openai_default_model,
            "requires_key": True,
            "editable_base_url": False,
            "models": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "o1-mini"],
            "available": available,
            "reason": None if available else "OPENAI_API_KEY is not set.",
        }

    # ------------------------------------------------------------------ #
    # High-level tasks
    # ------------------------------------------------------------------ #
    async def ask_question(self,
                          chart_data: Dict[str, Any],
                          question: str,
                          provider: LLMProvider = LLMProvider.QWEN,
                          config: Optional[ModelConfig] = None) -> str:
        """Ask a question about the chart. Pass either a ModelConfig or a legacy provider."""
        prompt = self._build_chart_analysis_prompt(chart_data, question)
        cfg = config or self.resolve_config(legacy_provider=provider.value if isinstance(provider, LLMProvider) else provider)
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

    def _build_chart_analysis_prompt(self, chart_data: Dict[str, Any], question: str) -> str:
        """Build prompt for answering questions about a chart"""

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

        # Add Dasha information
        current_dasha = chart_data.get("current_dasha", {})
        next_dasha = chart_data.get("next_dasha", {})
        current_bhukthi = chart_data.get("current_bhukthi", {})

        if current_dasha:
            chart_description += f"\n\nCurrent Dasha (Vimsottari):"
            chart_description += f"\n- Maha Dasha: {current_dasha.get('lord', 'Unknown')} ({current_dasha.get('start_date', 'Unknown')} to {current_dasha.get('end_date', 'Unknown')})"
            chart_description += f"\n- Duration: {current_dasha.get('duration_years', 0)} years"

        if current_bhukthi and current_bhukthi.get('periods'):
            chart_description += f"\n\nAll Sub-periods (Antar Dasha / Bhukti) within {current_dasha.get('lord', 'Unknown')} Maha Dasha:"
            # Show ALL sub-periods so LLM can identify which one is current
            for period in current_bhukthi.get('periods', []):
                chart_description += f"\n- {period.get('lord', 'Unknown')}: {period.get('start_date', 'Unknown')} to {period.get('end_date', 'Unknown')} ({period.get('duration_months', 0)} months)"

        if next_dasha:
            chart_description += f"\n\nNext Dasha:"
            chart_description += f"\n- {next_dasha.get('lord', 'Unknown')} starting {next_dasha.get('start_date', 'Unknown')}"

        prompt = f"""You are an expert Vedic astrologer. Below is the COMPLETE BIRTH CHART DATA for this person, calculated using precise astronomical calculations from the PyJHora Vedic astrology software. This is REAL, VERIFIED CHART DATA - not hypothetical.

=== COMPLETE BIRTH CHART ===

{chart_description}

=== END OF CHART DATA ===

IMPORTANT INSTRUCTIONS:
1. TODAY'S DATE is {current_date} - Use this to determine which Dasha and sub-period is CURRENTLY active
2. The above planetary positions, signs, houses, nakshatras, and Dasha periods have been calculated accurately based on the person's exact birth time and location
3. When asked about "current dasha" or "current period", check which Dasha/sub-period TODAY'S DATE ({current_date}) falls within
4. Use the complete chart data directly to answer their question

User's Question: {question}

Please provide a detailed, personalized answer based on THIS SPECIFIC BIRTH CHART. You have all the necessary information above. Analyze:
1. TODAY'S DATE ({current_date}) to identify the current Dasha and sub-period
2. The specific planetary positions in their chart
3. Their lagna (ascendant) in {lagna_info.get('sign_name', 'Unknown')}
4. Their moon sign in {moon_info.get('sign_name', 'Unknown')} and nakshatra {moon_info.get('nakshatra', 'Unknown')}
5. How the planets in their chart relate to the question asked
6. Practical, actionable guidance based on their specific placements

Do NOT ask for more information - you have the complete chart and today's date. Give a confident, detailed answer based on the data provided above."""

        return prompt

    def _build_prediction_prompt(self, chart_data: Dict[str, Any], prediction_type: str) -> str:
        """Build prompt for general predictions"""

        lagna_info = chart_data.get("lagna", {})
        moon_info = chart_data.get("moon_sign", {})
        planets = chart_data.get("planetary_positions", {})

        type_specific = {
            "general": "overall life path, personality, and general predictions",
            "health": "health constitution, potential health issues, and wellness recommendations",
            "career": "career inclinations, professional success factors, and recommended fields",
            "relationships": "relationship patterns, marriage timing, and compatibility factors"
        }

        focus = type_specific.get(prediction_type, type_specific["general"])

        prompt = f"""You are an expert Vedic astrologer. Below is the COMPLETE, ACCURATELY CALCULATED birth chart data from PyJHora software. Use this exact data for your predictions.

=== BIRTH CHART DATA ===

Lagna (Ascendant): {lagna_info.get('sign_name', 'Unknown')} in {lagna_info.get('nakshatra', 'Unknown')} nakshatra
Moon Sign: {moon_info.get('sign_name', 'Unknown')} in {moon_info.get('nakshatra', 'Unknown')} nakshatra
Sun Sign: {sun_info.get('sign_name', 'Unknown')}

Planetary Positions:
{self._format_planets(planets)}

=== END OF CHART DATA ===

Based on THIS SPECIFIC BIRTH CHART above, provide detailed {prediction_type} predictions focusing on {focus}.

Your prediction should cover:
1. Key strengths and characteristics based on their specific planetary placements
2. Challenges and areas for growth indicated by their chart
3. Opportunities in the near future based on current transits
4. Practical remedies or recommendations specific to their placements
5. Auspicious timing considerations for this person

IMPORTANT: Use the actual planetary positions shown above. Do NOT ask for more information - you have the complete chart data. Be specific, insightful, personalized, and encouraging."""

        return prompt

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
