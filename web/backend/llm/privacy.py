"""Birth details kept back from hosted models (§78).

A reading is written from a chart the engine has already computed — the model
never works a position out from the birth moment — so it has no use for the
birth date, time or place. Those three are also the strongest identifiers we
hold, so by default they stay on this server whenever the answer comes from a
hosted provider (Gemini, OpenAI, OpenRouter, a cloud OpenAI-compatible host).
Each user can opt back in per item from Settings → AI; a self-hosted model on
this machine or the LAN always gets everything, since nothing leaves.

Redaction happens at the four places a request actually leaves (see
`LLMService._outbound_*`), not in the ~40 prompt builders: a builder added next
year cannot forget it, and the Ask tool loop's JSON tool results — which carry
whole birth-details objects — are covered by the same pass. Three passes:

  * the labelled lines of the chart prompt ("Date of Birth: …"), where the date
    becomes the person's age — the one thing the model does use it for;
  * birth-details objects inside JSON (tool results), found by their `dob`/`tob`
    keys so a muhurta's own location, which has neither, is left alone;
  * the request's own date and place wherever they appear as bare text.

A bare birth time is deliberately NOT replaced: "10:45" is just as likely a
muhurta window or a sunrise, and a wrong window is worse than a leaked minute.
"""
import ipaddress
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .base import LOCAL_PROVIDERS, ModelConfig

# Synced preference keys (user_settings.PREFERENCE_KEYS), "true" = send it.
PREF_KEYS = {
    "date": "ai_share_birth_date",
    "time": "ai_share_birth_time",
    "place": "ai_share_birth_place",
}

WITHHELD = {
    "date": "[birth date withheld]",
    "time": "[birth time withheld]",
    "place": "[birth place withheld]",
}

# The labelled lines the chart prompt writes (llm/prompts.py, chart description).
_LABELS = {"date": "Date of Birth", "time": "Time of Birth", "place": "Place of Birth"}

# Fields of a birth-details object, by which setting withholds them.
_FIELDS = {
    "date": ("dob", "date_of_birth", "birth_date"),
    "time": ("tob", "time_of_birth", "birth_time"),
    "place": ("place", "birth_place", "place_of_birth",
              "latitude", "longitude", "lat", "lon", "lng"),
}
_MARKERS = ("dob", "tob", "date_of_birth", "birth_date")

_TODAY = re.compile(r"TODAY'S DATE:\s*(\d{4}-\d{2}-\d{2})")


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _age(dob: str, text: str) -> Optional[int]:
    """Whole years from `dob` to the prompt's own "today" (the reader's date),
    falling back to the server's."""
    try:
        born = date.fromisoformat(dob.strip()[:10])
    except ValueError:
        return None
    m = _TODAY.search(text)
    try:
        today = date.fromisoformat(m.group(1)) if m else date.today()
    except ValueError:
        today = date.today()
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return years if years >= 0 else None


@dataclass
class PrivacyPolicy:
    """What one user lets a hosted model see, plus the values to look out for."""
    share: Dict[str, bool] = field(
        default_factory=lambda: {k: False for k in PREF_KEYS})
    dates: set = field(default_factory=set)
    places: set = field(default_factory=set)

    @classmethod
    def from_prefs(cls, prefs: Optional[Dict[str, Any]]) -> "PrivacyPolicy":
        prefs = prefs or {}
        return cls(share={k: _truthy(prefs.get(p, "")) for k, p in PREF_KEYS.items()})

    @property
    def withholds_anything(self) -> bool:
        return not all(self.share.values())

    def remember(self, obj: Any) -> None:
        """Note every birth-details dict inside `obj` (a request body), so its
        date and place are caught even where they turn up as bare text."""
        if isinstance(obj, dict):
            if obj.get("dob"):
                self.dates.add(str(obj["dob"]).strip())
                place = str(obj.get("place") or "").strip()
                if place:
                    self.places.add(place)
                    # "Shahgarh, Uttar Pradesh, India" is also written as "Shahgarh".
                    city = place.split(",")[0].strip()
                    if len(city) >= 4:
                        self.places.add(city)
            for v in obj.values():
                self.remember(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                self.remember(v)

    # ---------------------------------------------------------------- #
    # Redaction
    # ---------------------------------------------------------------- #
    def _withheld(self, kind: str) -> bool:
        return not self.share.get(kind, False)

    def _redact_obj(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            is_birth = any(k in obj for k in _MARKERS)
            out = {}
            for k, v in obj.items():
                kind = next((c for c, keys in _FIELDS.items() if k in keys), None)
                if is_birth and kind and self._withheld(kind) and v not in (None, ""):
                    out[k] = WITHHELD[kind]
                else:
                    out[k] = self._redact_obj(v)
            return out
        if isinstance(obj, list):
            return [self._redact_obj(v) for v in obj]
        if isinstance(obj, str):
            return self._redact_literals(obj)
        return obj

    def _redact_literals(self, text: str) -> str:
        if self._withheld("date"):
            for d in self.dates:
                if d:
                    text = text.replace(d, WITHHELD["date"])
        if self._withheld("place"):
            # Longest first, so the full "City, State" goes before the bare city.
            for p in sorted(self.places, key=len, reverse=True):
                text = re.sub(rf"(?<!\w){re.escape(p)}(?!\w)", WITHHELD["place"], text)
        return text

    def redact_text(self, text: Optional[str]) -> Optional[str]:
        if not text or not self.withholds_anything:
            return text
        original = text

        def _line(kind):
            def _sub(m):
                if kind == "date":
                    age = _age(m.group(2), original)
                    if age is not None:
                        return f"{m.group(1)}{WITHHELD['date']} (age {age})"
                return m.group(1) + WITHHELD[kind]
            return _sub

        for kind, label in _LABELS.items():
            if self._withheld(kind):
                text = re.sub(rf"({label}:[ \t]*)([^\n]*)", _line(kind), text)

        stripped = text.lstrip()
        if stripped[:1] in ("{", "["):
            try:
                parsed = json.loads(text)
            except ValueError:
                parsed = None
            if parsed is not None:
                return json.dumps(self._redact_obj(parsed), default=str)

        # Birth-detail fields written into prose as a dict/JSON fragment.
        for kind in ("date", "time"):
            if self._withheld(kind):
                keys = "|".join(_FIELDS[kind])
                text = re.sub(rf"""(["']({keys})["']\s*:\s*)(["'])[^"'\n]*\3""",
                              lambda m, k=kind: f"{m.group(1)}{m.group(3)}{WITHHELD[k]}{m.group(3)}",
                              text)
        return self._redact_literals(text)

    def redact_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """A redacted copy — the caller's list is the conversation it keeps."""
        if not self.withholds_anything:
            return messages
        out = []
        for m in messages:
            c = m.get("content")
            if isinstance(c, str):
                m = {**m, "content": self.redact_text(c)}
            elif isinstance(c, list):
                m = {**m, "content": [
                    {**p, "text": self.redact_text(p["text"])}
                    if isinstance(p, dict) and isinstance(p.get("text"), str) else p
                    for p in c]}
            out.append(m)
        return out


# -------------------------------------------------------------------- #
# Where a model runs
# -------------------------------------------------------------------- #
def _extra_hosts() -> set:
    """SELF_HOSTED_LLM_HOSTS: hosts to trust beyond the network test — e.g. a
    Tailscale MagicDNS name for the NAS, which looks public by its spelling."""
    return {h.strip().lower() for h in os.getenv("SELF_HOSTED_LLM_HOSTS", "").split(",")
            if h.strip()}


def is_self_hosted(cfg: Optional[ModelConfig]) -> bool:
    """True when `cfg` is a model on this machine or the private network.

    Judged by where the endpoint IS, not by the provider type: Ollama pointed at
    a cloud host, or an "OpenAI-compatible" endpoint that is really a hosted
    API, is as external as Gemini.
    """
    if cfg is None or cfg.provider_type not in LOCAL_PROVIDERS:
        return False
    host = (urlparse(cfg.base_url or "").hostname or "").lower()
    if not host:
        return True          # no URL → the server's own default endpoint
    if host in _extra_hosts() or host == "localhost" or "." not in host:
        return True          # single-label names only resolve on a LAN / compose net
    if host.endswith((".local", ".lan", ".internal", ".home.arpa")):
        return True
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return False


def outbound_policy(cfg: Optional[ModelConfig]) -> Optional[PrivacyPolicy]:
    """The policy to apply to a request leaving on `cfg`, or None to send as-is.

    A config that arrived without a policy (a code path that never went through
    `deps._resolve_cfg`) gets the default — everything withheld — so forgetting
    to wire one fails closed.
    """
    if is_self_hosted(cfg):
        return None
    policy = getattr(cfg, "privacy", None) or PrivacyPolicy()
    return policy if policy.withholds_anything else None
