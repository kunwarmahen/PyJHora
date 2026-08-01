"""Admin console API (§44).

Every route here is gated by `get_admin_user` (deployer allowlist). Content
drill-down adds `require_content_access`. Moderation + content views are
audit-logged. See `admin.py` for the design rationale.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

import admin as admin_service
import runtime_config
from deps import get_admin_user, require_content_access, get_current_user

router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class SuspendRequest(BaseModel):
    suspended: bool


class RuntimeConfigRequest(BaseModel):
    """Partial update of the runtime knobs. A field left unset is untouched; a
    field set to null clears the override and returns it to the deployed default."""
    digest_scheduler_enabled: Optional[bool] = None
    digest_scheduler_interval_minutes: Optional[int] = None
    digest_ai_max_delay_minutes: Optional[int] = None
    # Which of the above the caller means to clear (JSON null is indistinguishable
    # from "absent" once parsed, so clearing is requested explicitly).
    clear: Optional[list] = None


@router.get("/api/admin/me")
async def admin_me(current_user: str = Depends(get_current_user)):
    """Cheap 'am I an admin?' check used by the frontend to decide whether to show
    the console entry. Never 404s (unlike the gated routes) — it's the discovery
    endpoint every logged-in user is allowed to call about themselves."""
    is_admin = admin_service.is_admin_user(current_user)
    if not is_admin:
        from database import database
        if database is not None:
            doc = await database["users"].find_one(
                {"username": current_user}, {"is_admin": 1, "email": 1})
            is_admin = bool(doc and admin_service.is_admin_user(current_user, doc))
    return {
        "is_admin": is_admin,
        "content_access_enabled": admin_service.content_access_enabled() if is_admin else False,
    }


@router.get("/api/admin/stats")
async def admin_stats(request: Request, admin: str = Depends(get_admin_user)):
    # The console's landing call — recorded so "who opened the admin console, and
    # from where" is answerable, which is the first question after any surprise.
    await admin_service.security_event("admin_console_opened", actor=admin,
                                       ip=_client_ip(request))
    return await admin_service.global_stats()


@router.get("/api/admin/users")
async def admin_users(q: str = "", limit: int = 200, admin: str = Depends(get_admin_user)):
    return {"users": await admin_service.list_users(query=q, limit=min(limit, 500))}


@router.get("/api/admin/users/{username}")
async def admin_user_detail(username: str, admin: str = Depends(get_admin_user)):
    detail = await admin_service.user_detail(username)
    if not detail:
        raise HTTPException(status_code=404, detail="User not found")
    return detail


@router.get("/api/admin/users/{username}/content/{kind}")
async def admin_user_content(username: str, kind: str, request: Request,
                             admin: str = Depends(get_admin_user),
                             _: None = Depends(require_content_access)):
    if kind not in admin_service.COUNT_COLLECTIONS:
        raise HTTPException(status_code=400, detail="Unknown content kind")
    await admin_service.audit(admin, "view_content", target=username,
                              detail=kind, ip=_client_ip(request))
    return {"items": await admin_service.user_content(username, kind)}


@router.post("/api/admin/users/{username}/suspend")
async def admin_suspend(username: str, req: SuspendRequest, request: Request,
                        admin: str = Depends(get_admin_user)):
    if username == admin and req.suspended:
        raise HTTPException(status_code=400, detail="You cannot suspend your own account.")
    target = await admin_service.user_detail(username)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target["is_admin"] and req.suspended:
        raise HTTPException(status_code=400, detail="Cannot suspend another admin.")
    ok = await admin_service.set_suspended(username, req.suspended)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    await admin_service.audit(admin, "suspend" if req.suspended else "unsuspend",
                              target=username, ip=_client_ip(request))
    return {"status": "ok", "suspended": req.suspended}


@router.delete("/api/admin/users/{username}")
async def admin_delete_user(username: str, request: Request,
                            admin: str = Depends(get_admin_user)):
    if username == admin:
        raise HTTPException(status_code=400, detail="You cannot delete your own account here.")
    target = await admin_service.user_detail(username)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target["is_admin"]:
        raise HTTPException(status_code=400, detail="Cannot delete another admin.")
    deleted = await admin_service.delete_user(username)
    await admin_service.audit(admin, "delete_user", target=username,
                              detail=str(deleted), ip=_client_ip(request))
    return {"status": "deleted", "deleted": deleted}


@router.get("/api/admin/audit")
async def admin_audit_log(limit: int = 200, category: str = "", action: str = "",
                          actor: str = "", target: str = "", since_days: int = 0,
                          admin: str = Depends(get_admin_user)):
    """Audit rows with optional filters, plus a summary so the console can explain
    a quiet log (it records events, not activity — see /api/admin/activity)."""
    entries = await admin_service.list_audit(
        limit=min(limit, 1000), category=category or None, action=action or None,
        actor=actor or None, target=target or None, since_days=since_days or None)
    return {
        "entries": entries,
        "summary": await admin_service.audit_summary(),
        "actions": admin_service.SECURITY_ACTIONS,
    }


@router.get("/api/admin/activity")
async def admin_activity(limit: int = 200, kinds: str = "", username: str = "",
                         admin: str = Depends(get_admin_user)):
    """The derived activity stream — what the deployment has been doing, assembled
    on read from the collections that already hold it (so it covers everything
    that ever happened, not only what has been logged since event logging existed).

    Metadata only: titles, kinds and counts, never the body of anything a user
    wrote. This is deliberately readable *without* ADMIN_CONTENT_ACCESS."""
    wanted = [k.strip() for k in kinds.split(",") if k.strip()] or None
    rows = await admin_service.activity_feed(
        limit=min(limit, 1000), kinds=wanted, username=username or None)
    return {"entries": rows, "kinds": admin_service.ACTIVITY_KINDS}


@router.get("/api/admin/config")
async def admin_get_config(admin: str = Depends(get_admin_user)):
    """The effective runtime settings, the deployed defaults behind them, and which
    fields are currently overridden — so the console can show what has been
    changed and offer to put it back."""
    values = await runtime_config.get()
    return {
        "values": values,
        "defaults": runtime_config.defaults(),
        "overridden": list((await runtime_config.overrides()).keys()),
        "max_deferrals": runtime_config.max_deferrals(values),
    }


@router.put("/api/admin/config")
async def admin_set_config(req: RuntimeConfigRequest, request: Request,
                           admin: str = Depends(get_admin_user)):
    updates: Dict[str, Any] = {
        k: v for k, v in req.model_dump(exclude={"clear"}).items() if v is not None}
    for name in (req.clear or []):
        updates[name] = None
    if not updates:
        raise HTTPException(status_code=400, detail="No settings supplied")
    values = await runtime_config.set_values(updates)
    await admin_service.audit(admin, "update_config", detail=str(updates),
                              ip=_client_ip(request))
    return {
        "values": values,
        "defaults": runtime_config.defaults(),
        "overridden": list((await runtime_config.overrides()).keys()),
        # What the configured delay works out to in scheduler ticks — the number
        # the operator would otherwise have to derive to sanity-check the setting.
        "max_deferrals": runtime_config.max_deferrals(values),
    }
