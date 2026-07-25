"""OpenAI / OpenAI-compatible provider adapter: status, streaming, completion, chat, tool payloads.

Part of the §4c llm_service split — methods moved verbatim from the
single LLMService class. These are instance methods, so the mixin
composes over `self` with no other changes.
"""
from ..base import *  # noqa: F401,F403


class OpenAIMixin:

    def _openai_style_headers(self, cfg: ModelConfig) -> Dict[str, str]:
        """Request headers shared by every OpenAI-schema provider."""
        headers = {"Content-Type": "application/json"}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"
        if cfg.provider_type == ProviderType.OPENROUTER:
            # Optional attribution headers: OpenRouter uses them to label the
            # traffic in its dashboards/leaderboard. Ignored when absent.
            headers["X-Title"] = SITE_NAME
            if self.openrouter_site_url:
                headers["HTTP-Referer"] = self.openrouter_site_url
        return headers

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

    # Shown only when the live catalogue can't be read (no key yet, or the API is
    # unreachable). Anything newer comes from _openai_models().
    _OPENAI_FALLBACK_MODELS = ("gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "o1-mini")

    # Chat-capable id prefixes. /v1/models also lists embeddings, TTS, whisper,
    # image and moderation models, none of which can answer a chat completion.
    _OPENAI_CHAT_PREFIXES = ("gpt-", "chatgpt-", "o1", "o3", "o4")

    async def _openai_status(self, user_key: Optional[str] = None) -> Dict[str, Any]:
        key = user_key or self.openai_api_key
        available = bool(key)
        models = await self._openai_models(key) if key else []
        return {
            "type": ProviderType.OPENAI.value,
            "label": "OpenAI (ChatGPT)",
            "base_url": "https://api.openai.com/v1",
            "default_model": self._pick_default_model(
                self.openai_default_model, models, self._OPENAI_FALLBACK_MODELS),
            "requires_key": True,
            "editable_base_url": False,
            "has_user_key": bool(user_key),
            "models": models or list(self._OPENAI_FALLBACK_MODELS),
            "available": available,
            "reason": None if available else "No OpenAI API key. Add one in API Keys (or set OPENAI_API_KEY).",
        }

    async def _openai_models(self, api_key: str) -> List[str]:
        """Live /v1/models, filtered to the chat-capable ids."""
        async def _fetch() -> List[str]:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get("https://api.openai.com/v1/models",
                                        headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code != 200:
                    return []
                ids = [m.get("id") for m in resp.json().get("data", []) if m.get("id")]
                return sorted(i for i in ids
                              if i.startswith(self._OPENAI_CHAT_PREFIXES))

        return await self._cached_models("openai", _fetch)

    # Tried in order when the configured OpenRouter default no longer exists.
    # All are cheap, fast and support the tool calling the agentic mode needs.
    _OPENROUTER_FALLBACK_MODELS = (
        "google/gemini-2.5-flash",
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-haiku",
    )

    async def _openrouter_status(self, user_key: Optional[str] = None) -> Dict[str, Any]:
        """OpenRouter: one key, hundreds of hosted models across vendors."""
        key = user_key or self.openrouter_api_key
        available = bool(key)
        models = await self._openrouter_models()
        info = {
            "type": ProviderType.OPENROUTER.value,
            "label": "OpenRouter",
            "base_url": self.openrouter_url,
            "default_model": self._pick_default_model(
                self.openrouter_default_model, models, self._OPENROUTER_FALLBACK_MODELS),
            "requires_key": True,
            "editable_base_url": False,
            "has_user_key": bool(user_key),
            "models": models,
            "available": available,
            "reason": None if available else (
                "No OpenRouter API key. Add one in API Keys (or set OPENROUTER_API_KEY). "
                "Create a key at https://openrouter.ai/keys."
            ),
        }
        return info

    async def _openrouter_models(self) -> List[str]:
        """OpenRouter model ids ("vendor/model"). The catalogue is public, so
        unlike the other cloud providers this needs no key to enumerate."""
        async def _fetch() -> List[str]:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(f"{self.openrouter_url}/models")
                if resp.status_code != 200:
                    return []
                return sorted(m.get("id") for m in resp.json().get("data", [])
                              if m.get("id"))

        return await self._cached_models("openrouter", _fetch)

    async def _stream_openai_style(self, messages, cfg, max_tokens, usage=None) -> AsyncGenerator[str, None]:
        base_url = (cfg.base_url or "").rstrip("/")
        if not base_url:
            yield "Error: no base URL configured for this provider."
            return
        if not cfg.api_key and _missing_key_error(cfg.provider_type):
            yield _missing_key_error(cfg.provider_type)
            return
        if not cfg.model:
            yield "Error: no model specified for this provider."
            return
        headers = self._openai_style_headers(cfg)
        payload = {
            "model": cfg.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": max_tokens,
            "stream": True,
            # Ask for a final usage chunk; servers that don't support it ignore this.
            "stream_options": {"include_usage": True},
        }
        timeout = _request_timeout(cfg.provider_type)
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

    async def _call_openai_style(self, prompt: str, cfg: ModelConfig, max_tokens: int = 4096,
                                 system: str = SYSTEM_PROMPT,
                                 usage: Optional[Dict[str, Any]] = None) -> str:
        """OpenAI and any OpenAI-compatible server share the /chat/completions schema."""
        base_url = (cfg.base_url or "").rstrip("/")
        if not base_url:
            return "Error: no base URL configured for this OpenAI-compatible provider."
        if not cfg.api_key and _missing_key_error(cfg.provider_type):
            return _missing_key_error(cfg.provider_type)
        if not cfg.model:
            return "Error: no model specified for this provider."
        # Local OpenAI-compatible servers can be slow; cloud OpenAI is fast
        req_timeout = _request_timeout(cfg.provider_type)
        try:
            async with httpx.AsyncClient(timeout=req_timeout) as client:
                headers = self._openai_style_headers(cfg)
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
    def _openai_tool_payload(specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{"type": "function", "function": {
            "name": s["name"], "description": s["description"],
            "parameters": s["parameters"]}} for s in specs]

    async def _chat_once_openai(self, messages, specs, cfg, max_tokens: int = 4096) -> Dict[str, Any]:
        max_tokens = cfg.max_tokens or max_tokens
        base_url = (cfg.base_url or "").rstrip("/")
        if not base_url:
            raise RuntimeError("no base URL configured for this provider")
        if not cfg.api_key and _KEY_ENV_VAR.get(cfg.provider_type):
            raise RuntimeError(f"{_KEY_ENV_VAR[cfg.provider_type]} is not set")
        headers = self._openai_style_headers(cfg)
        payload = {
            "model": cfg.model,
            "messages": self._to_openai_messages(messages),
            "temperature": 0.7,
            "max_tokens": max_tokens,
            "tools": self._openai_tool_payload(specs),
            "tool_choice": "auto",
        }
        timeout = _request_timeout(cfg.provider_type)
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
