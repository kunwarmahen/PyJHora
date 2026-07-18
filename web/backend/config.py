from pydantic_settings import BaseSettings
from typing import List

# Populate os.environ from .env so modules that read os.getenv() directly
# (e.g. llm_service) see the same values pydantic-settings loads here.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

class Settings(BaseSettings):
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "jyotirai_db"
    SECRET_KEY: str = "your-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # Refresh-token lifetimes. A long-lived, revocable refresh token lets the
    # frontend silently mint fresh access tokens, so users aren't logged out
    # every ACCESS_TOKEN_EXPIRE_MINUTES. "Remember me" picks the long TTL; a
    # plain login gets the short one.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_TOKEN_SHORT_DAYS: int = 1

    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Interactive map location picker (Leaflet + OpenStreetMap). When False the
    # backend reverse-geocode endpoint returns 403 so the feature can be fully
    # disabled for production deployments. The frontend has its own
    # REACT_APP_ENABLE_MAP_PICKER flag to hide the UI; keep the two in sync.
    MAP_PICKER_ENABLED: bool = True

    # Public base URL of the frontend, used to build absolute links in outbound
    # email (e.g. the password-reset link). No trailing slash.
    APP_BASE_URL: str = "http://localhost:3000"

    # Product / brand name used in outbound email and the API docs title. Keep in
    # sync with the frontend's REACT_APP_SITE_TITLE. (This is the app brand, not
    # the underlying "jhora" calculation library.)
    SITE_NAME: str = "Jyotir AI"

    # Transactional email (SMTP). Provider-agnostic — works with Gmail (app
    # password), SendGrid, Mailgun, Amazon SES SMTP, etc. When SMTP_HOST is unset
    # the email layer becomes a graceful no-op that only logs the message, so
    # development works without a mail server. STARTTLS is used on port 587;
    # implicit TLS ("SSL") on port 465.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""            # e.g. "Jyotir Ai <no-reply@example.com>"; falls back to SMTP_USER
    SMTP_USE_TLS: bool = True      # STARTTLS (587). Set False + port 465 for implicit SSL.

    # Password-reset token lifetime (minutes).
    PASSWORD_RESET_TTL_MINUTES: int = 30

    # "Sign in with Google" (Google Identity Services). Create an OAuth 2.0 Client
    # ID of type "Web application" in Google Cloud Console, add your frontend
    # origins (e.g. http://localhost:3000 and your public domain) as Authorized
    # JavaScript origins, and paste the Client ID here. The frontend needs the SAME
    # value baked in as REACT_APP_GOOGLE_CLIENT_ID. When unset, the Google endpoint
    # returns 503 and the frontend hides the button — password auth is unaffected.
    GOOGLE_CLIENT_ID: str = ""

    # Web Push (PWA notifications) via VAPID. Generate a keypair once with
    # `python -m notifications genkeys` (or vapid CLI) and set these. When unset,
    # push is disabled (subscribe endpoints return 503) but the rest works.
    VAPID_PUBLIC_KEY: str = ""    # base64url-encoded P-256 public key
    VAPID_PRIVATE_KEY: str = ""   # base64url-encoded P-256 private key (PEM also accepted)
    VAPID_SUBJECT: str = "mailto:admin@example.com"

    # In-process daily-digest scheduler. When enabled, a background task delivers
    # each opted-in user's digest once a day at their preferred local hour. Off by
    # default — a deployer can instead cron `POST /api/notifications/digest/send`.
    # The wake interval must be < 60 min so it catches every target hour.
    DIGEST_SCHEDULER_ENABLED: bool = False
    DIGEST_SCHEDULER_INTERVAL_MINUTES: int = 15

    # ── Admin console (§44) ────────────────────────────────────────────────
    # Deployer-controlled superuser access. This env var is the SOURCE OF TRUTH
    # for who is an admin — the app reconciles the `is_admin` flag on `users`
    # from it at startup, so an admin is granted purely by editing the deploy
    # secret, never by touching Mongo (which is only reachable inside the pod).
    # Comma-separated; each entry matches a user by username OR email (case-
    # insensitive). Empty ⇒ no admins, and the whole console is effectively off.
    ADMIN_USERNAMES: str = ""
    # "Break glass" switch for drilling into a user's actual PRIVATE content
    # (readings, chats, journal, birth details) — not just metadata/counts.
    # OFF by default: the console shows aggregates only. Flip to true and
    # redeploy when something is genuinely wrong and you must inspect content;
    # every such access is audit-logged regardless.
    ADMIN_CONTENT_ACCESS: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
