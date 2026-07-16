"""Per-provider adapter mixins (§4c split)."""
from .ollama import OllamaMixin  # noqa: F401
from .openai import OpenAIMixin  # noqa: F401
from .gemini import GeminiMixin  # noqa: F401
