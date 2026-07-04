"""Transactional email — provider-agnostic SMTP.

A thin wrapper over the stdlib `smtplib`, configured entirely from env
(`SMTP_HOST/PORT/USER/PASSWORD/FROM/USE_TLS`, see config.py). It works with any
SMTP provider: Gmail (app password), SendGrid, Mailgun, Amazon SES SMTP, etc.

**Graceful no-op:** when `SMTP_HOST` is unset the sender does not fail — it logs
the message (including any link) to the server console and returns `False`
("not actually sent"). That keeps local development working without a mail
server, and callers that must not leak whether an address exists (password
reset) don't depend on the return value.

The blocking `smtplib` call is run in a thread via `asyncio.to_thread` so it
never blocks the event loop.
"""
import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional

from config import settings


def is_configured() -> bool:
    """True when an SMTP host is configured (i.e. mail can actually be sent)."""
    return bool((settings.SMTP_HOST or "").strip())


def _from_address() -> str:
    """The From header — SMTP_FROM if set, else SMTP_USER, else a safe default."""
    return (settings.SMTP_FROM or settings.SMTP_USER or "no-reply@pyjhora.local").strip()


def _send_blocking(to: str, subject: str, text: str, html: Optional[str]) -> None:
    msg = EmailMessage()
    msg["From"] = _from_address()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    port = int(settings.SMTP_PORT or 587)
    host = settings.SMTP_HOST
    if port == 465:
        # Implicit TLS.
        with smtplib.SMTP_SSL(host, port, timeout=20) as server:
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)


async def send_email(to: str, subject: str, text: str,
                     html: Optional[str] = None) -> bool:
    """Send an email. Returns True if actually dispatched via SMTP, False if the
    mailer is not configured (no-op) or the send failed. Never raises — a mail
    failure must not break the request flow (e.g. a forgot-password call)."""
    to = (to or "").strip()
    if not to:
        return False
    if not is_configured():
        print(f"[email:noop] To: {to} | Subject: {subject}\n{text}")
        return False
    try:
        await asyncio.to_thread(_send_blocking, to, subject, text, html)
        return True
    except Exception as e:  # pragma: no cover - network dependent
        print(f"[email:error] failed to send to {to}: {e}")
        return False


# --------------------------------------------------------------------------- #
# Templated helpers
# --------------------------------------------------------------------------- #
def _button_html(url: str, label: str) -> str:
    return (
        f'<p style="text-align:center;margin:28px 0;">'
        f'<a href="{url}" style="background:#FF9933;color:#fff;text-decoration:none;'
        f'padding:12px 26px;border-radius:8px;font-weight:600;display:inline-block;">'
        f'{label}</a></p>'
    )


def _shell_html(title: str, body: str) -> str:
    return (
        f'<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;'
        f'max-width:520px;margin:0 auto;color:#2b2b2b;">'
        f'<h2 style="color:#B8541A;">🕉 {settings.SITE_NAME}</h2>'
        f'<h3>{title}</h3>{body}'
        f'<hr style="border:none;border-top:1px solid #eee;margin:24px 0;">'
        f'<p style="font-size:12px;color:#999;">You received this email because an '
        f'action was requested for your {settings.SITE_NAME} account. If it wasn\'t you, you can '
        f'safely ignore this message.</p></div>'
    )


async def send_password_reset(to: str, reset_url: str, ttl_minutes: int) -> bool:
    """Send a password-reset link."""
    subject = f"Reset your {settings.SITE_NAME} password"
    text = (
        f"We received a request to reset your {settings.SITE_NAME} password.\n\n"
        f"Open this link to choose a new password (valid for {ttl_minutes} minutes):\n"
        f"{reset_url}\n\n"
        "If you didn't request this, you can ignore this email — your password "
        "won't change."
    )
    html = _shell_html(
        "Reset your password",
        f"<p>We received a request to reset your {settings.SITE_NAME} password. This link is "
        f"valid for {ttl_minutes} minutes.</p>"
        + _button_html(reset_url, "Choose a new password")
        + f'<p style="font-size:13px;color:#666;">Or paste this URL into your '
          f'browser:<br><a href="{reset_url}">{reset_url}</a></p>',
    )
    return await send_email(to, subject, text, html)


async def send_daily_digest(to: str, subject: str, text: str, html: str) -> bool:
    """Send the personalized daily-digest email (body pre-rendered by the caller)."""
    return await send_email(to, subject, text, _shell_html(subject, html))
