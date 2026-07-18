"""Admin console API (§44).

Every route here is gated by `get_admin_user` (deployer allowlist). Content
drill-down adds `require_content_access`. Moderation + content views are
audit-logged. See `admin.py` for the design rationale.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

import admin as admin_service
from deps import get_admin_user, require_content_access, get_current_user

router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class SuspendRequest(BaseModel):
    suspended: bool


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
async def admin_stats(admin: str = Depends(get_admin_user)):
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
async def admin_audit_log(limit: int = 200, admin: str = Depends(get_admin_user)):
    return {"entries": await admin_service.list_audit(limit=min(limit, 1000))}
