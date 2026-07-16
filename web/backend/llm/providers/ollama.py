"""Ollama (local) provider adapter: status, streaming, completion, chat.

Part of the §4c llm_service split — methods moved verbatim from the
single LLMService class. These are instance methods, so the mixin
composes over `self` with no other changes.
"""
from ..base import *  # noqa: F401,F403


class OllamaMixin:

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
