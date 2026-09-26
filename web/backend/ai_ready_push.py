""""Your answer is ready" — a push when an AI job finishes after you left.

The case this is for: ask on the phone, lock it (or iOS kills the tab), and
the answer — minutes of local-model work — lands with nobody looking. The
header pill (ai_activity) tells you the next time you open the app; this tells
you now.

Sent only when all of these hold:
* nobody was watching it arrive (ai_activity reports `watched`), and it still
  hasn't been seen after a short grace — a reader who comes straight back
  isn't buzzed for an answer already on their screen;
* the user turned browser push on (the `push` channel the digest uses) and
  hasn't turned `ai_ready` off (Settings → Notifications);
* it finished or failed — a job the user stopped needs no news.

The link opens the saved answer on its own page under the right profile
(`?reading=` + `?profile=`, both existing deep links).
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

import ai_activity
import notifications

# Long enough for a reader who switched tabs and came back to be seen.
GRACE_S = 20.0


def build_payload(a: "ai_activity.Activity") -> Dict[str, Any]:
    route = a.route or "/history"
    if a.status == "done":
        title = "Your answer is ready" if a.kind == "ask" else "Your reading is ready"
        params = []
        if a.result_id:
            params.append(f"reading={a.result_id}")
        if a.profile_id:
            params.append(f"profile={a.profile_id}")
        url = route + ("?" + "&".join(params) if params else "")
    else:
        title = "An answer didn't finish"
        url = route + (f"?profile={a.profile_id}" if a.profile_id else "")
    body = (a.title or "").strip()
    if len(body) > 120:
        body = body[:117].rstrip() + "…"
    return {"title": title, "body": body, "url": url}


@ai_activity.on_finish
async def notify_when_ready(a: "ai_activity.Activity", watched: bool) -> None:
    if watched or a.status not in ("done", "failed"):
        return
    await asyncio.sleep(GRACE_S)
    if a.seen:
        return
    prefs = await notifications.get_prefs(a.owner)
    if not (prefs.get("push") and prefs.get("ai_ready", True)):
        return
    await notifications.send_push(a.owner, build_payload(a))
