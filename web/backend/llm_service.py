"""Multi-provider LLM service — the public API the app calls.

Provider adapters (Ollama / OpenAI-compatible / Gemini) live in llm/providers/*.py
and the ~1,700 lines of prompt builders in llm/prompts.py; LLMService composes them
as mixins. Constants/enums/ModelConfig live in llm/base.py and are re-exported here,
so the import surface is unchanged (`from llm_service import llm_service, LLMProvider`)
AND there is exactly one definition of each enum — importing them twice would create
distinct classes and silently break isinstance checks across the mixins.
"""
from llm.base import *  # noqa: F401,F403  (constants, enums, ModelConfig, stdlib deps)
from llm.base import __all__ as _base_all
from llm.prompts import PromptsMixin
from llm.providers import OllamaMixin, OpenAIMixin, GeminiMixin


class LLMService(PromptsMixin, OllamaMixin, OpenAIMixin, GeminiMixin):
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
                                   marriage: Optional[Dict[str, Any]] = None,
                                   provider: LLMProvider = LLMProvider.QWEN,
                                   config: Optional[ModelConfig] = None) -> str:
        """Generate compatibility analysis.

        `marriage` (optional) is the §2.6 7th-house workspace block for both
        partners; when present it sharpens the couple reading with the marriage
        houses/karakas rather than Guna Milan alone."""
        prompt = self._build_compatibility_prompt(male_chart, female_chart, koota_score, marriage)
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

    async def analyze_fortnightly_digest(self,
                                         digest_data: Dict[str, Any],
                                         name: str = "this person",
                                         config: Optional[ModelConfig] = None) -> str:
        """Warm, personalized reading of the fortnight (Paksha Pravesha) digest."""
        prompt = self._build_period_digest_prompt(digest_data, name, "fortnight")
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_monthly_digest(self,
                                     digest_data: Dict[str, Any],
                                     name: str = "this person",
                                     config: Optional[ModelConfig] = None) -> str:
        """Warm, personalized reading of the monthly digest — the Maasa Pravesha
        (solar) or birth-tithi-return (lunar) chart, per the digest's basis."""
        prompt = self._build_period_digest_prompt(digest_data, name, "month")
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_tithi_pravesha(self,
                                     tp_data: Dict[str, Any],
                                     name: str = "this person",
                                     config: Optional[ModelConfig] = None) -> str:
        """Plain-language year-ahead reading of the Tithi Pravesha (annual
        lunar-return) chart — the lunar counterpart of Varshaphal."""
        prompt = self._build_tithi_pravesha_prompt(tp_data, name)
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

    async def analyze_timeline_window(self,
                                      data: Dict[str, Any],
                                      name: str = "this person",
                                      config: Optional[ModelConfig] = None) -> str:
        """Reading of "what's running" at a chosen point on the life timeline —
        the active Maha/Bhukti, Saturn phase and nearby transits."""
        prompt = self._build_timeline_window_prompt(data, name)
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

    async def analyze_planet_conditions(self,
                                        data: Dict[str, Any],
                                        name: str = "this person",
                                        config: Optional[ModelConfig] = None) -> str:
        """Reading of the classical planet-condition flags (combustion,
        vargottama, gandanta, mrityu bhaga, …)."""
        prompt = self._build_planet_conditions_prompt(data, name)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_avasthas(self,
                               data: Dict[str, Any],
                               name: str = "this person",
                               config: Optional[ModelConfig] = None) -> str:
        """Reading of the planetary avasthas (Baladi / Jagradadi / Deeptadi)."""
        prompt = self._build_avasthas_prompt(data, name)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_strength(self,
                               data: Dict[str, Any],
                               name: str = "this person",
                               config: Optional[ModelConfig] = None) -> str:
        """Reading of the strength picture (Shadbala + Bhava Bala + Vimsopaka)."""
        prompt = self._build_strength_prompt(data, name)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_saturn_transits(self,
                                      data: Dict[str, Any],
                                      name: str = "this person",
                                      config: Optional[ModelConfig] = None) -> str:
        """Calm reading of the Sade Sati / Saturn transits."""
        prompt = self._build_saturn_transits_prompt(data, name)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_friendships(self,
                                  data: Dict[str, Any],
                                  name: str = "this person",
                                  config: Optional[ModelConfig] = None) -> str:
        """Reading of the planetary friendships + house-lord placements."""
        prompt = self._build_friendships_prompt(data, name)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_nakshatra_profile(self,
                                        data: Dict[str, Any],
                                        name: str = "this person",
                                        config: Optional[ModelConfig] = None) -> str:
        """Warm reading of the janma-nakshatra profile + tarabala calendar."""
        prompt = self._build_nakshatra_profile_prompt(data, name)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

    async def analyze_gochara_phala(self,
                                    data: Dict[str, Any],
                                    name: str = "this person",
                                    config: Optional[ModelConfig] = None) -> str:
        """Warm reading of the Moon-referenced gochara-phala (with vedha)."""
        prompt = self._build_gochara_phala_prompt(data, name)
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

    async def generate_life_report_chapter(self, chart_data: Dict[str, Any],
                                           title: str, focus: str, name: str,
                                           config: Optional[ModelConfig] = None) -> str:
        prompt = self._build_life_report_chapter_prompt(chart_data, title, focus, name)
        cfg = config or self.resolve_config()
        return await self._complete(prompt, cfg)

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

__all__ = list(_base_all) + ['LLMService', 'llm_service']
