"""Google Gemini provider adapter: status, streaming, completion, chat, schema/tool payloads.

Part of the §4c llm_service split — methods moved verbatim from the
single LLMService class. These are instance methods, so the mixin
composes over `self` with no other changes.
"""
from ..base import *  # noqa: F401,F403


class GeminiMixin:

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
