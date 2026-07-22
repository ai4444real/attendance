"""
Rebekko Webapps - FastAPI Server

Single backend entry point for the Rebekko webapps workspace.
At the moment it serves the Attendance module and its related APIs.
"""

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import base64
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from backend.attendance_normalization.service import normalize_zoom_csv_file
from backend.attendance_app.models import ImportBatchCreate
from backend.attendance_app.services import (
    AttendanceCourseConfigService,
    AttendanceDraftRecalculationService,
    AttendanceLessonIdentityRebuildService,
    AttendanceIdentityAliasService,
    AttendanceImportService,
    AttendanceLessonSplitService,
    AttendanceLessonStateService,
    AttendanceManualPresenceService,
    AttendanceReviewActionService,
    _apply_identity_alias_maps,
    _load_identity_alias_maps,
)
from backend.db.attendance_draft_import_repository import PostgresAttendanceDraftImportRepository
from backend.db.attendance_identity_repository import PostgresAttendanceIdentityRepository
from backend.db.attendance_identity_alias_repository import PostgresAttendanceIdentityAliasRepository
from backend.db.attendance_instructor_repository import PostgresAttendanceInstructorRepository
from backend.db.attendance_draft_mutation_repository import PostgresAttendanceDraftMutationRepository
from backend.db.attendance_draft_query_repository import PostgresAttendanceDraftQueryRepository
from backend.db.attendance_review_action_repository import PostgresAttendanceReviewActionRepository

# Resolve workspace paths from the backend package location
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(BACKEND_DIR)

# Load environment variables from the workspace .env file (for local development)
load_dotenv(os.path.join(WORKSPACE_DIR, ".env"))


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


AUTH_ENABLED = _env_bool("AUTH_ENABLED", False)
AUTH_GOOGLE_CLIENT_ID = os.getenv("AUTH_GOOGLE_CLIENT_ID", "").strip()
AUTH_ALLOWED_EMAILS = {
    email.strip().lower()
    for email in os.getenv("AUTH_ALLOWED_EMAILS", "").split(",")
    if email.strip()
}
AUTH_SESSION_SECRET = os.getenv("AUTH_SESSION_SECRET", "").strip()
AUTH_SESSION_COOKIE = os.getenv("AUTH_SESSION_COOKIE", "rebekko_session").strip() or "rebekko_session"
AUTH_SESSION_MAX_AGE_SECONDS = int(os.getenv("AUTH_SESSION_MAX_AGE_SECONDS", "28800"))
AUTH_COOKIE_SECURE = _env_bool("AUTH_COOKIE_SECURE", True)

PUBLIC_AUTH_PREFIXES = (
    "/login",
    "/logout",
    "/auth/",
    "/health",
    "/assets/",
    "/attendance/static/",
    "/utilities/static/",
    "/favicon.ico",
)

# Initialize FastAPI app
app = FastAPI(
    title="Rebekko Webapps",
    description="Workspace backend per le webapp del progetto Rebekko",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _auth_is_configured() -> bool:
    return bool(AUTH_GOOGLE_CLIENT_ID and AUTH_ALLOWED_EMAILS and AUTH_SESSION_SECRET)


def _auth_missing_config() -> list[str]:
    missing = []
    if not AUTH_GOOGLE_CLIENT_ID:
        missing.append("AUTH_GOOGLE_CLIENT_ID")
    if not AUTH_ALLOWED_EMAILS:
        missing.append("AUTH_ALLOWED_EMAILS")
    if not AUTH_SESSION_SECRET:
        missing.append("AUTH_SESSION_SECRET")
    return missing


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign_session_payload(payload: dict) -> str:
    body = _base64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(AUTH_SESSION_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_base64url_encode(signature)}"


def _read_session_cookie(request: Request) -> dict | None:
    token = request.cookies.get(AUTH_SESSION_COOKIE)
    if not token or "." not in token or not AUTH_SESSION_SECRET:
        return None
    body, signature = token.rsplit(".", 1)
    expected_signature = _base64url_encode(
        hmac.new(AUTH_SESSION_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(signature, expected_signature):
        return None
    try:
        payload = json.loads(_base64url_decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    expires_at = int(payload.get("exp") or 0)
    email = str(payload.get("email") or "").strip().lower()
    if expires_at <= int(time.time()) or not email:
        return None
    if email not in AUTH_ALLOWED_EMAILS:
        return None
    return payload


def _request_wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return request.url.path.startswith("/api/") or "application/json" in accept


def _is_public_path(path: str) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in PUBLIC_AUTH_PREFIXES)


@app.middleware("http")
async def require_authentication(request: Request, call_next):
    if not AUTH_ENABLED or _is_public_path(request.url.path):
        return await call_next(request)

    if not _auth_is_configured():
        return JSONResponse(
            {"detail": f"Auth enabled but missing config: {', '.join(_auth_missing_config())}"},
            status_code=503,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )

    session = _read_session_cookie(request)
    if session is None:
        if _request_wants_json(request):
            return JSONResponse(
                {"detail": "Authentication required."},
                status_code=401,
                headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
            )
        return RedirectResponse(url=f"/login?next={request.url.path}", status_code=303)

    request.state.user = session
    return await call_next(request)

# Attendance module paths
ATTENDANCE_STATIC_DIR = os.path.join(WORKSPACE_DIR, "attendance", "static")
ATTENDANCE_INDEX_FILE = os.path.join(ATTENDANCE_STATIC_DIR, "index.html")
ATTENDANCE_REVIEW_FILE = os.path.join(ATTENDANCE_STATIC_DIR, "review-normalized.html")
ATTENDANCE_IMPORT_FILE = os.path.join(ATTENDANCE_STATIC_DIR, "import-zoom.html")
ATTENDANCE_DRAFTS_FILE = os.path.join(ATTENDANCE_STATIC_DIR, "draft-imports.html")
ATTENDANCE_ALIASES_FILE = os.path.join(ATTENDANCE_STATIC_DIR, "attendance-aliases.html")
ATTENDANCE_IDENTITIES_FILE = os.path.join(ATTENDANCE_STATIC_DIR, "attendance-identities.html")
ATTENDANCE_SCHOOL_FILE = os.path.join(ATTENDANCE_STATIC_DIR, "attendance-school.html")
ATTENDANCE_COURSES_FILE = os.path.join(ATTENDANCE_STATIC_DIR, "attendance-courses.html")
ATTENDANCE_FOLLOWUPS_FILE = os.path.join(ATTENDANCE_STATIC_DIR, "attendance-followups.html")
ATTENDANCE_MANUAL_PRESENCE_FILE = os.path.join(ATTENDANCE_STATIC_DIR, "manual-presence.html")
ATTENDANCE_INSTRUCTORS_FILE = os.path.join(ATTENDANCE_STATIC_DIR, "attendance-instructors.html")
ATTENDANCE_ADAPTER_DIR = os.path.join(WORKSPACE_DIR, "attendance", "adapter")
UTILITIES_STATIC_DIR = os.path.join(WORKSPACE_DIR, "utilities")
UTILITIES_CLASSROOM_MANAGER_FILE = os.path.join(UTILITIES_STATIC_DIR, "classroom-manager.html")
UTILITIES_SMALLINVOICE_FILE = os.path.join(UTILITIES_STATIC_DIR, "smallinvoice.html")
GLOBAL_ASSETS_DIR = os.path.join(WORKSPACE_DIR, "assets")

SMALLINVOICE_API_BASE_URL = os.getenv("SMALLINVOICE_API_BASE_URL", "https://api.smallinvoice.com/v2").rstrip("/")
SMALLINVOICE_CLIENT_ID = os.getenv("SMALLINVOICE_CLIENT_ID", "").strip()
SMALLINVOICE_CLIENT_SECRET = os.getenv("SMALLINVOICE_CLIENT_SECRET", "").strip()

# Mount current module static files
app.mount("/attendance/static", StaticFiles(directory=ATTENDANCE_STATIC_DIR), name="attendance-static")
app.mount("/attendance/manage", StaticFiles(directory=ATTENDANCE_ADAPTER_DIR, html=True), name="attendance-manage")
app.mount("/utilities/static", StaticFiles(directory=UTILITIES_STATIC_DIR), name="utilities-static")
app.mount("/assets", StaticFiles(directory=GLOBAL_ASSETS_DIR), name="global-assets")

_identity_alias_bootstrap_done = False


def _bootstrap_identity_aliases_if_needed() -> None:
    global _identity_alias_bootstrap_done
    if _identity_alias_bootstrap_done:
        return
    service = AttendanceIdentityAliasService(PostgresAttendanceIdentityAliasRepository())
    service.bootstrap_from_legacy_rules()
    _identity_alias_bootstrap_done = True


def render_module_shell(title: str, subtitle: str, body_html: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="/assets/styles/brand.css">
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            background: var(--brand-surface);
            color: #1f2933;
        }}
        .topbar {{
            position: sticky;
            top: 0;
            z-index: 10;
            background: rgba(255,255,255,0.92);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--brand-border);
        }}
        .topbar-inner {{
            max-width: 1120px;
            margin: 0 auto;
            padding: 14px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            flex-wrap: wrap;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 14px;
            text-decoration: none;
            color: inherit;
        }}
        .brand img {{
            height: 42px;
            width: auto;
            display: block;
        }}
        .brand-text {{
            display: flex;
            flex-direction: column;
            gap: 2px;
        }}
        .brand-title {{
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: var(--brand-ink);
        }}
        .brand-subtitle {{
            font-size: 12px;
            color: var(--brand-muted);
        }}
        .nav {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .nav a {{
            text-decoration: none;
            color: #155e75;
            font-weight: 600;
        }}
        .nav a:hover {{
            text-decoration: underline;
        }}
        .page {{
            max-width: 1120px;
            margin: 0 auto;
            padding: 40px 24px 72px;
        }}
        .hero {{
            background: linear-gradient(135deg, var(--brand-pnl-blue) 0%, var(--brand-pnl-green) 100%);
            color: white;
            border-radius: 18px;
            padding: 36px;
            margin-bottom: 26px;
            box-shadow: 0 14px 30px rgba(22, 50, 79, 0.18);
        }}
        .hero h1 {{
            margin: 0 0 10px;
            font-size: 36px;
        }}
        .hero p {{
            margin: 0;
            font-size: 17px;
            line-height: 1.55;
            max-width: 760px;
            opacity: 0.96;
        }}
        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            border: 1px solid var(--brand-border);
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
        }}
        a.card {{
            text-decoration: none;
            color: inherit;
            transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
        }}
        a.card:hover {{
            transform: translateY(-3px);
            border-color: var(--brand-pnl-blue);
            box-shadow: 0 14px 28px rgba(0, 80, 144, 0.14);
        }}
        .card-label {{
            display: inline-block;
            margin-bottom: 10px;
            padding: 6px 10px;
            border-radius: 999px;
            background: var(--brand-pnl-blue-soft);
            color: var(--brand-pnl-blue);
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }}
        .card h2 {{
            margin: 0 0 10px;
            font-size: 28px;
        }}
        .card p {{
            margin: 0;
            line-height: 1.6;
            color: var(--brand-muted);
        }}
        .placeholder-note {{
            margin-top: 14px;
            padding: 12px 14px;
            background: var(--brand-pnl-green-soft);
            color: var(--brand-green-dark, #0f5132);
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <header class="topbar">
        <div class="topbar-inner">
            <a class="brand" href="/">
                <img src="/assets/brand/logo_pnl_evolution.png" alt="PNL Evolution">
                <div class="brand-text">
                    <span class="brand-title">Rebekko Webapps</span>
                    <span class="brand-subtitle">PNL Evolution</span>
                </div>
            </a>
            <nav class="nav" aria-label="Workspace navigation">
                <a href="/">Home</a>
                <a href="/attendance">Attendance</a>
            </nav>
        </div>
    </header>
    <main class="page">
        <section class="hero">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </section>
        {body_html}
    </main>
</body>
</html>
    """


def render_login_page(error: str = "", next_url: str = "/") -> str:
    config_missing = _auth_missing_config()
    config_note = ""
    google_button = ""
    if config_missing:
        config_note = f"""
            <div class="login-error">
                Configurazione auth incompleta: {", ".join(config_missing)}.
                Con AUTH_ENABLED=false questa pagina puo' esistere, ma il login non e' operativo.
            </div>
        """
    else:
        google_button = f"""
            <div id="g_id_onload"
                data-client_id="{AUTH_GOOGLE_CLIENT_ID}"
                data-callback="handleGoogleCredential"
                data-auto_prompt="false"></div>
            <div class="g_id_signin"
                data-type="standard"
                data-size="large"
                data-theme="outline"
                data-text="signin_with"
                data-shape="pill"
                data-logo_alignment="left"></div>
        """
    error_html = f'<div class="login-error">{error}</div>' if error else ""
    return f"""
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Rebekko Webapps</title>
    <link rel="stylesheet" href="/assets/styles/brand.css">
    <script src="https://accounts.google.com/gsi/client" async defer></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            padding: 24px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            background: var(--brand-surface);
            color: var(--brand-ink);
        }}
        .login-card {{
            width: min(520px, 100%);
            background: #fff;
            border: 1px solid var(--brand-border);
            border-radius: 22px;
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.12);
            overflow: hidden;
        }}
        .login-hero {{
            padding: 28px;
            background: linear-gradient(135deg, var(--brand-pnl-blue) 0%, var(--brand-pnl-green) 100%);
            color: #fff;
        }}
        .login-brand {{ display: flex; align-items: center; gap: 14px; margin-bottom: 22px; }}
        .login-brand img {{ height: 46px; width: auto; background: rgba(255,255,255,0.95); border-radius: 10px; padding: 4px; }}
        .login-brand-title {{ font-size: 14px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; }}
        h1 {{ margin: 0 0 8px; font-size: 34px; }}
        p {{ margin: 0; line-height: 1.55; opacity: 0.95; }}
        .login-body {{ padding: 26px 28px 30px; display: flex; flex-direction: column; gap: 18px; }}
        .login-error {{
            padding: 12px 14px;
            border-radius: 12px;
            background: #fde7ec;
            color: #b42318;
            font-weight: 700;
            font-size: 14px;
            line-height: 1.45;
        }}
        .login-note {{ color: var(--brand-muted); font-size: 14px; line-height: 1.5; }}
    </style>
</head>
<body>
    <main class="login-card">
        <section class="login-hero">
            <div class="login-brand">
                <img src="/assets/brand/logo_pnl_evolution.png" alt="PNL Evolution">
                <div class="login-brand-title">Rebekko Webapps</div>
            </div>
            <h1>Accesso</h1>
            <p>Accedi con Google usando un account autorizzato dalla scuola.</p>
        </section>
        <section class="login-body">
            {error_html}
            {config_note}
            {google_button}
            <div id="loginResult" class="login-note">L'accesso e' limitato agli account esplicitamente autorizzati.</div>
        </section>
    </main>
    <script>
        const NEXT_URL = {json.dumps(next_url if next_url.startswith("/") else "/")};
        async function handleGoogleCredential(response) {{
            const result = document.getElementById('loginResult');
            result.textContent = 'Verifica accesso in corso...';
            try {{
                const apiResponse = await fetch('/auth/google', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ credential: response.credential }})
                }});
                const payload = await apiResponse.json();
                if (!apiResponse.ok) {{
                    throw new Error(payload.detail || 'Accesso non riuscito.');
                }}
                window.location.href = NEXT_URL || '/';
            }} catch (error) {{
                result.innerHTML = '<span style="color:#b42318;font-weight:800;">' + error.message + '</span>';
            }}
        }}
    </script>
</body>
</html>
    """


@app.get("/login")
async def login_page(request: Request):
    session = _read_session_cookie(request) if _auth_is_configured() else None
    next_url = request.query_params.get("next") or "/"
    if session and AUTH_ENABLED:
        return RedirectResponse(url=next_url if next_url.startswith("/") else "/", status_code=303)
    return HTMLResponse(
        render_login_page(next_url=next_url),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.post("/auth/google")
async def auth_google(payload: dict):
    if not _auth_is_configured():
        raise HTTPException(status_code=503, detail=f"Auth non configurata: {', '.join(_auth_missing_config())}")
    credential = str(payload.get("credential") or "").strip()
    if not credential:
        raise HTTPException(status_code=400, detail="Credential Google mancante.")

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": credential},
        )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Token Google non valido.")

    token_info = response.json()
    audience = str(token_info.get("aud") or "")
    email = str(token_info.get("email") or "").strip().lower()
    email_verified = str(token_info.get("email_verified") or "").lower() == "true"
    if audience != AUTH_GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Token Google emesso per un client diverso.")
    if not email or not email_verified:
        raise HTTPException(status_code=401, detail="Email Google non verificata.")
    if email not in AUTH_ALLOWED_EMAILS:
        raise HTTPException(status_code=403, detail="Email non autorizzata per Rebekko.")

    now = int(time.time())
    session_payload = {
        "email": email,
        "name": token_info.get("name") or email,
        "iat": now,
        "exp": now + AUTH_SESSION_MAX_AGE_SECONDS,
        "nonce": secrets.token_urlsafe(12),
    }
    token = _sign_session_payload(session_payload)
    response_payload = JSONResponse(
        {"ok": True, "email": email, "name": session_payload["name"]},
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )
    response_payload.set_cookie(
        AUTH_SESSION_COOKIE,
        token,
        max_age=AUTH_SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return response_payload


@app.get("/auth/whoami")
async def auth_whoami(request: Request):
    session = _read_session_cookie(request) if _auth_is_configured() else None
    return JSONResponse(
        {
            "auth_enabled": AUTH_ENABLED,
            "configured": _auth_is_configured(),
            "email": session.get("email") if session else None,
            "name": session.get("name") if session else None,
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(AUTH_SESSION_COOKIE, path="/")
    return response


@app.get("/")
async def workspace_home():
    body_html = """
        <section>
            <div class="cards">
                <a class="card" href="/attendance">
                    <span class="card-label">Disponibile</span>
                    <h2>Attendance</h2>
                    <p>Caricamento e analisi presenze su dati trackcc-like, con filtri, statistiche ed export.</p>
                </a>
                <a class="card" href="/utilities">
                    <span class="card-label">Disponibile</span>
                    <h2>Utilities</h2>
                    <p>Strumenti operativi di supporto, a partire dalla gestione Google Classroom e calendari.</p>
                </a>
            </div>
        </section>
    """
    return HTMLResponse(
        render_module_shell(
            "Rebekko Webapps",
            "Workspace applicativo per i servizi interni Rebekko. Da qui si accede ai moduli attivi, a partire da Attendance.",
            body_html
        ),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/utilities")
@app.get("/utilities/")
async def utilities_home():
    body_html = """
        <section>
            <div class="cards">
                <a class="card" href="/utilities/classroom-manager">
                    <span class="card-label">Google</span>
                    <h2>Classroom Manager</h2>
                    <p>Gestione corsi Google Classroom, calendari, eventi condivisi ed export operativi.</p>
                </a>
                <a class="card" href="/utilities/smallinvoice">
                    <span class="card-label">Finance</span>
                    <h2>Smallinvoice</h2>
                    <p>Ricerca rapida clienti Smallinvoice per nome, senza esporre credenziali API nel browser.</p>
                </a>
            </div>
        </section>
    """
    return HTMLResponse(
        render_module_shell(
            "Utilities",
            "Strumenti operativi separati dai moduli principali, integrati nel workspace Rebekko.",
            body_html
        ),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/utilities/classroom-manager")
@app.get("/utilities/classroom-manager/")
async def utilities_classroom_manager():
    return FileResponse(
        UTILITIES_CLASSROOM_MANAGER_FILE,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/utilities/smallinvoice")
@app.get("/utilities/smallinvoice/")
async def utilities_smallinvoice():
    return FileResponse(
        UTILITIES_SMALLINVOICE_FILE,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


def _smallinvoice_is_configured() -> bool:
    return bool(SMALLINVOICE_CLIENT_ID and SMALLINVOICE_CLIENT_SECRET)


def _smallinvoice_extract_items(payload) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "data", "contacts", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("items", "contacts", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _smallinvoice_contact_text(contact: dict) -> str:
    values = []
    for key in (
        "id",
        "name",
        "display_name",
        "company",
        "company_name",
        "first_name",
        "last_name",
        "email",
        "email_address",
        "city",
        "zip",
    ):
        value = contact.get(key)
        if value:
            values.append(str(value))
    return " ".join(values).casefold()


def _smallinvoice_invoice_sort_key(invoice: dict) -> str:
    for key in ("date", "paid_date", "due", "created_at", "updated_at"):
        value = invoice.get(key)
        if value:
            return str(value)
    return ""


async def _smallinvoice_access_token(client: httpx.AsyncClient) -> str:
    if not _smallinvoice_is_configured():
        raise HTTPException(
            status_code=503,
            detail="Smallinvoice non configurato: imposta SMALLINVOICE_CLIENT_ID e SMALLINVOICE_CLIENT_SECRET.",
        )
    response = await client.post(
        f"{SMALLINVOICE_API_BASE_URL}/auth/access-tokens",
        json={
            "grant_type": "client_credentials",
            "client_id": SMALLINVOICE_CLIENT_ID,
            "client_secret": SMALLINVOICE_CLIENT_SECRET,
            "scope": "invoice contact",
        },
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Autenticazione Smallinvoice fallita.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Risposta auth Smallinvoice non valida.") from exc
    token = payload.get("access_token")
    if not token:
        raise HTTPException(status_code=502, detail="Token Smallinvoice mancante nella risposta auth.")
    return token


@app.get("/api/utilities/smallinvoice/contacts")
async def smallinvoice_search_contacts(request: Request):
    query = (request.query_params.get("query") or "").strip()
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="Inserisci almeno 2 caratteri.")

    query_key = query.casefold()
    matched_contacts: list[dict] = []
    limit = 200
    max_pages = 20

    async with httpx.AsyncClient(timeout=20.0) as client:
        token = await _smallinvoice_access_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        for page in range(max_pages):
            response = await client.get(
                f"{SMALLINVOICE_API_BASE_URL}/contacts",
                headers=headers,
                params={"limit": limit, "offset": page * limit},
            )
            if response.status_code >= 400:
                raise HTTPException(status_code=502, detail="Ricerca contatti Smallinvoice fallita.")
            try:
                payload = response.json()
            except ValueError as exc:
                raise HTTPException(status_code=502, detail="Risposta contatti Smallinvoice non valida.") from exc
            contacts = _smallinvoice_extract_items(payload)
            for contact in contacts:
                if query_key in _smallinvoice_contact_text(contact):
                    matched_contacts.append(contact)
            if len(contacts) < limit:
                break

    return {"query": query, "count": len(matched_contacts), "contacts": matched_contacts[:200]}


@app.get("/api/utilities/smallinvoice/contacts/{contact_id}/invoices")
async def smallinvoice_contact_invoices(contact_id: str):
    contact_id = contact_id.strip()
    if not contact_id:
        raise HTTPException(status_code=400, detail="Contact ID mancante.")

    contact_filter_id: int | str
    contact_filter_id = int(contact_id) if contact_id.isdigit() else contact_id
    invoices: list[dict] = []
    limit = 200
    max_pages = 50

    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await _smallinvoice_access_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        for page in range(max_pages):
            response = await client.get(
                f"{SMALLINVOICE_API_BASE_URL}/receivables/invoices",
                headers=headers,
                params={
                    "filter": json.dumps({"contact_id": contact_filter_id}, separators=(",", ":")),
                    "with": "positions",
                    "sort": "-date",
                    "limit": limit,
                    "offset": page * limit,
                },
            )
            if response.status_code >= 400:
                raise HTTPException(status_code=502, detail="Recupero fatture Smallinvoice fallito.")
            try:
                payload = response.json()
            except ValueError as exc:
                raise HTTPException(status_code=502, detail="Risposta fatture Smallinvoice non valida.") from exc
            page_invoices = _smallinvoice_extract_items(payload)
            invoices.extend(page_invoices)
            pagination = payload.get("pagination") if isinstance(payload, dict) else None
            has_next = bool(pagination and pagination.get("next"))
            if len(page_invoices) < limit or not has_next:
                break

    invoices.sort(key=_smallinvoice_invoice_sort_key, reverse=True)
    return {"contact_id": contact_id, "count": len(invoices), "invoices": invoices}


@app.get("/attendance")
@app.get("/attendance/")
async def attendance_home():
    body_html = """
        <section>
            <div class="cards">
                <a class="card" href="/attendance/import">
                    <span class="card-label">Nuovo</span>
                    <h2>Importa Zoom</h2>
                    <p>Carica il CSV Zoom grezzo, lascia che il backend lo normalizzi e passa subito alla revisione del risultato.</p>
                </a>
                <a class="card" href="/attendance/drafts">
                    <span class="card-label">Nuovo</span>
                    <h2>Draft importati</h2>
                    <p>Apri i batch già salvati nel database e scorri lezioni e partecipanti direttamente dal modello dati persistito.</p>
                </a>
                <a class="card" href="/attendance/school">
                    <span class="card-label">MVP</span>
                    <h2>Analisi scuola</h2>
                    <p>Consulta i dati ufficiali già consolidati: tabella presenze, filtri per corso e studente, riepilogo dei totali.</p>
                </a>
                <a class="card" href="/attendance/followups">
                    <span class="card-label">Nuovo</span>
                    <h2>Studenti da richiamare</h2>
                    <p>Segnala gli studenti che risultano assenti implicitamente nelle ultime lezioni official di un corso.</p>
                </a>
                <a class="card" href="/attendance/manual">
                    <span class="card-label">Nuovo</span>
                    <h2>Presenze manuali</h2>
                    <p>Inserisci presenze gia' aggregate per lezioni in presenza, QR form o import manuali.</p>
                </a>
                <a class="card" href="/attendance/courses">
                    <span class="card-label">Nuovo</span>
                    <h2>Corsi importati</h2>
                    <p>Colpo d'occhio sui corsi official e sulle relative lezioni già importate, in sequenza cronologica.</p>
                </a>
                <a class="card" href="/attendance/aliases">
                    <span class="card-label">Supporto</span>
                    <h2>Alias identità</h2>
                    <p>Controlla gli alias nome registrati nel database e verifica rapidamente se un'unione è stata salvata.</p>
                </a>
                <a class="card" href="/attendance/identities">
                    <span class="card-label">Supporto</span>
                    <h2>Identità osservate</h2>
                    <p>Registro tecnico degli studenti già incontrati nei dati attendance, utile per alias e futuri insiemi didattici.</p>
                </a>
                <a class="card" href="/attendance/instructors">
                    <span class="card-label">Supporto</span>
                    <h2>Docenti</h2>
                    <p>Gestisci nomi e alias dei docenti usati dalle prossime funzionalità scuola.</p>
                </a>
            </div>
        </section>
    """
    return HTMLResponse(
        render_module_shell(
            "Attendance",
            "Scegli l'area di lavoro del modulo attendance.",
            body_html
        ),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/attendance/view")
@app.get("/attendance/view/")
async def attendance_view():
    return FileResponse(
        ATTENDANCE_INDEX_FILE,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/attendance/review")
@app.get("/attendance/review/")
async def attendance_review():
    return FileResponse(
        ATTENDANCE_REVIEW_FILE,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/attendance/import")
@app.get("/attendance/import/")
async def attendance_import():
    return FileResponse(
        ATTENDANCE_IMPORT_FILE,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/attendance/drafts")
@app.get("/attendance/drafts/")
async def attendance_drafts():
    return FileResponse(
        ATTENDANCE_DRAFTS_FILE,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/attendance/aliases")
@app.get("/attendance/aliases/")
async def attendance_aliases():
    return FileResponse(
        ATTENDANCE_ALIASES_FILE,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/attendance/identities")
@app.get("/attendance/identities/")
async def attendance_identities():
    return FileResponse(
        ATTENDANCE_IDENTITIES_FILE,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/attendance/school")
@app.get("/attendance/school/")
async def attendance_school():
    return FileResponse(
        ATTENDANCE_SCHOOL_FILE,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/attendance/courses")
@app.get("/attendance/courses/")
async def attendance_courses():
    return FileResponse(
        ATTENDANCE_COURSES_FILE,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/attendance/followups")
@app.get("/attendance/followups/")
async def attendance_followups():
    return FileResponse(
        ATTENDANCE_FOLLOWUPS_FILE,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/attendance/manual")
@app.get("/attendance/manual/")
async def attendance_manual_presence():
    return FileResponse(
        ATTENDANCE_MANUAL_PRESENCE_FILE,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/attendance/instructors")
@app.get("/attendance/instructors/")
async def attendance_instructors():
    return FileResponse(
        ATTENDANCE_INSTRUCTORS_FILE,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/attendance/manage")
async def attendance_manage():
    return RedirectResponse(url="/attendance/manage/", status_code=307)


@app.on_event("startup")
async def bootstrap_attendance_identity_aliases() -> None:
    try:
        _bootstrap_identity_aliases_if_needed()
    except Exception as exc:
        print(f"[startup] identity alias bootstrap skipped: {exc}")


@app.post("/api/attendance/import-draft")
async def attendance_import_draft(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Serve un file CSV Zoom.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Il file caricato è vuoto.")

    temp_path: str | None = None
    try:
        _bootstrap_identity_aliases_if_needed()
        suffix = Path(filename).suffix or ".csv"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        result = normalize_zoom_csv_file(temp_path)
        service = AttendanceImportService(
            PostgresAttendanceDraftImportRepository(),
            PostgresAttendanceIdentityAliasRepository(),
        )
        persisted = service.persist_normalization_result(
            ImportBatchCreate(
                source_system="zoom",
                source_file_name=filename,
                source_file_path=filename,
                imported_by="manual-upload",
            ),
            result,
        )
        return {
            "batch_created": persisted.batch is not None,
            "batch_id": persisted.batch.id if persisted.batch is not None else None,
            "status": persisted.batch.status if persisted.batch is not None else "skipped",
            "source_file_name": persisted.batch.source_file_name if persisted.batch is not None else filename,
            "lessons_created": persisted.lessons_created,
            "participants_created": persisted.participants_created,
            "imported_lessons": [
                {
                    "course_name": item.course_name,
                    "source_meeting_id": item.source_meeting_id,
                    "lesson_date": item.lesson_date,
                }
                for item in (persisted.imported_lessons or [])
            ],
            "duplicate_lessons_skipped": persisted.duplicate_lessons_skipped,
            "skipped_duplicates": [
                {
                    "course_name": item.course_name,
                    "source_meeting_id": item.source_meeting_id,
                    "lesson_date": item.lesson_date,
                    "existing_lesson_id": item.existing_lesson_id,
                    "existing_batch_id": item.existing_batch_id,
                }
                for item in (persisted.skipped_duplicates or [])
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Import draft fallito: {exc}") from exc
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


@app.get("/api/attendance/import-batches")
async def attendance_import_batches(scope: str = "open"):
    repository = PostgresAttendanceDraftQueryRepository()
    try:
        batches = repository.list_batches(limit=60, scope=scope)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse({
        "batches": [
            {
                "id": batch.id,
                "source_system": batch.source_system,
                "source_file_name": batch.source_file_name,
                "status": batch.status,
                "created_at": batch.created_at.isoformat(),
                "lessons_count": batch.lessons_count,
                "participants_count": batch.participants_count,
            }
            for batch in batches
        ]
    }, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


@app.get("/api/attendance/import-batches/{batch_id}")
async def attendance_import_batch_detail(batch_id: int):
    repository = PostgresAttendanceDraftQueryRepository()
    try:
        detail = repository.get_batch_detail(batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return JSONResponse({
        "batch": {
            "id": detail.batch.id,
            "source_system": detail.batch.source_system,
            "source_file_name": detail.batch.source_file_name,
            "status": detail.batch.status,
            "created_at": detail.batch.created_at.isoformat(),
            "lessons_count": detail.batch.lessons_count,
            "participants_count": detail.batch.participants_count,
        },
        "lessons": [
            {
                "id": lesson.id,
                "course_name": lesson.course_name,
                "lesson_date": lesson.lesson_date,
                "source_meeting_id": lesson.source_meeting_id,
                "status": lesson.status,
                "is_ignored": lesson.is_ignored,
                "threshold_ratio": lesson.threshold_ratio,
                "summary": lesson.summary,
            }
            for lesson in detail.lessons
        ],
    }, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


@app.get("/api/attendance/lessons/{lesson_id}")
async def attendance_lesson_detail(lesson_id: int):
    repository = PostgresAttendanceDraftQueryRepository()
    try:
        lesson = repository.get_lesson_detail(lesson_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    source_segment_groups = _build_lesson_source_groups(repository, lesson_id)
    return JSONResponse({
        "lesson": {
            "id": lesson.id,
            "import_batch_id": lesson.import_batch_id,
            "course_name": lesson.course_name,
            "lesson_date": lesson.lesson_date,
            "source_meeting_id": lesson.source_meeting_id,
            "status": lesson.status,
            "is_ignored": lesson.is_ignored,
            "threshold_ratio": lesson.threshold_ratio,
            "meeting_start_at": lesson.meeting_start_at,
            "meeting_end_at": lesson.meeting_end_at,
            "effective_start_at": lesson.effective_start_at,
            "break_point_at": lesson.break_point_at,
            "effective_end_at": lesson.effective_end_at,
            "break_source": lesson.break_source,
            "effective_start_source": lesson.effective_start_source,
            "effective_end_source": lesson.effective_end_source,
            "warnings": lesson.warnings,
            "diagnostics": lesson.diagnostics,
            "summary": lesson.summary,
            "participants": [
                {
                    "id": participant.id,
                    "participant_key": participant.participant_key,
                    "canonical_full_name": participant.canonical_full_name,
                    "raw_full_name": participant.raw_full_name,
                    "email": participant.email,
                    "segment_count": participant.segment_count,
                    "minutes_first_half": participant.minutes_first_half,
                    "minutes_second_half": participant.minutes_second_half,
                    "duration_first_half": participant.duration_first_half,
                    "duration_second_half": participant.duration_second_half,
                    "total_minutes": participant.total_minutes,
                    "calculated_presence_status": participant.calculated_presence_status,
                    "manual_override_presence_status": participant.manual_override_presence_status,
                    "final_presence_status": participant.final_presence_status,
                    "presence_source": participant.presence_source,
                    "flags": participant.flags,
                    "metadata": participant.metadata,
                    "source_details": source_segment_groups.get(participant.participant_key, []),
                }
                for participant in lesson.participants
            ],
            "review_actions": [
                {
                    "id": action.id,
                    "lesson_id": action.lesson_id,
                    "participant_id": action.participant_id,
                    "action_type": action.action_type,
                    "payload": action.payload,
                    "created_by": action.created_by,
                    "created_at": action.created_at,
                    "applied_at": action.applied_at,
                    "is_applied": action.is_applied,
                    "notes": action.notes,
                }
                for action in lesson.review_actions
            ],
        }
    }, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


def _build_lesson_source_groups(repository: PostgresAttendanceDraftQueryRepository, lesson_id: int) -> dict[str, list[dict]]:
    source_segments = repository.get_lesson_source_segments(lesson_id)
    if not source_segments:
        return {}

    name_alias_map, email_alias_map = _load_identity_alias_maps(PostgresAttendanceIdentityAliasRepository())
    by_participant_key: dict[str, dict[tuple[str, str], dict]] = {}

    for segment in source_segments:
        canonical_full_name, canonical_email = _apply_identity_alias_maps(
            segment.observed_full_name,
            segment.observed_email,
            name_alias_map,
            email_alias_map,
        )
        participant_key = (canonical_email or "").strip().lower() or canonical_full_name.lower()
        raw_name = (segment.observed_full_name or canonical_full_name).strip()
        raw_email = (segment.observed_email or "").strip()
        source_key = (raw_name.casefold(), raw_email.casefold())
        grouped_sources = by_participant_key.setdefault(participant_key, {})
        source_entry = grouped_sources.setdefault(
            source_key,
            {
                "raw_full_name": raw_name,
                "email": raw_email or None,
                "segments": [],
            },
        )
        source_entry["segments"].append((segment.join_time, segment.leave_time))

    return {
        participant_key: list(grouped_sources.values())
        for participant_key, grouped_sources in by_participant_key.items()
    }


@app.post("/api/attendance/lessons/{lesson_id}/review-actions")
async def attendance_create_review_action(lesson_id: int, payload: dict):
    action_type = str(payload.get("action_type") or "").strip()
    action_payload = payload.get("payload") or {}
    created_by = str(payload.get("created_by") or "drafts-ui").strip() or "drafts-ui"
    notes = payload.get("notes")
    participant_id = payload.get("participant_id")
    query_repository = PostgresAttendanceDraftQueryRepository()

    if action_type in {"set_effective_start", "set_break_point", "set_effective_end"}:
        lesson = query_repository.get_lesson_detail(lesson_id)
        has_segments = all(
            isinstance(participant.metadata.get("segments"), list) and participant.metadata.get("segments")
            for participant in lesson.participants
        )
        if not has_segments:
            raise HTTPException(
                status_code=400,
                detail="Questa lezione arriva da un import vecchio senza segmenti grezzi: reimporta il batch per correggere inizio, pausa o fine.",
            )

    service = AttendanceReviewActionService(PostgresAttendanceReviewActionRepository())
    try:
        action = service.create_lesson_review_action(
            lesson_id,
            action_type,
            action_payload,
            created_by=created_by,
            notes=notes,
            participant_id=int(participant_id) if participant_id is not None else None,
        )
        recalculated_lesson = AttendanceDraftRecalculationService(
            query_repository,
            PostgresAttendanceDraftMutationRepository(),
            PostgresAttendanceIdentityAliasRepository(),
        ).recalculate_lesson(
            lesson_id,
            prefer_original_baseline=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Creazione correzione fallita: {exc}") from exc

    return {
        "action": {
            "id": action.id,
            "lesson_id": action.lesson_id,
            "participant_id": action.participant_id,
            "action_type": action.action_type,
            "payload": action.payload,
            "created_by": action.created_by,
            "created_at": action.created_at,
            "applied_at": action.applied_at,
            "is_applied": action.is_applied,
            "notes": action.notes,
        },
        "lesson_id": recalculated_lesson.id,
    }


@app.post("/api/attendance/lessons/{lesson_id}/recalculate")
async def attendance_recalculate_lesson(lesson_id: int):
    try:
        lesson = AttendanceDraftRecalculationService(
            PostgresAttendanceDraftQueryRepository(),
            PostgresAttendanceDraftMutationRepository(),
            PostgresAttendanceIdentityAliasRepository(),
        ).recalculate_lesson(lesson_id, prefer_original_baseline=True)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Ricalcolo lezione fallito: {exc}") from exc
    return {
        "lesson_id": lesson.id,
        "recalculated": True,
        "summary": lesson.summary,
    }


@app.post("/api/attendance/review-actions/{action_id}/delete")
async def attendance_delete_review_action(action_id: int):
    service = AttendanceReviewActionService(PostgresAttendanceReviewActionRepository())
    try:
        lesson_id = service.delete_lesson_review_action(action_id)
        recalculated_lesson = AttendanceDraftRecalculationService(
            PostgresAttendanceDraftQueryRepository(),
            PostgresAttendanceDraftMutationRepository(),
            PostgresAttendanceIdentityAliasRepository(),
        ).recalculate_lesson(lesson_id, prefer_original_baseline=True)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cancellazione correzione fallita: {exc}") from exc
    return {
        "action_id": action_id,
        "lesson_id": recalculated_lesson.id,
        "deleted": True,
    }


@app.post("/api/attendance/lessons/{lesson_id}/ignore")
async def attendance_set_lesson_ignored(lesson_id: int, payload: dict):
    is_ignored = bool(payload.get("is_ignored"))
    service = AttendanceLessonStateService(PostgresAttendanceDraftMutationRepository())
    try:
        service.set_lesson_ignored(lesson_id, is_ignored=is_ignored)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"lesson_id": lesson_id, "is_ignored": is_ignored}


@app.post("/api/attendance/lessons/{lesson_id}/status")
async def attendance_set_lesson_status(lesson_id: int, payload: dict):
    status = str(payload.get("status") or "").strip()
    service = AttendanceLessonStateService(PostgresAttendanceDraftMutationRepository())
    try:
        service.set_lesson_status(lesson_id, status=status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"lesson_id": lesson_id, "status": status}


@app.post("/api/attendance/lessons/{lesson_id}/delete")
async def attendance_delete_lesson(lesson_id: int):
    service = AttendanceLessonStateService(PostgresAttendanceDraftMutationRepository())
    try:
        service.delete_lesson(lesson_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"lesson_id": lesson_id, "deleted": True}


@app.post("/api/attendance/lessons/{lesson_id}/split")
async def attendance_split_lesson(lesson_id: int, payload: dict):
    first_end_at = str(payload.get("first_end_at") or "").strip()
    second_start_at = str(payload.get("second_start_at") or "").strip()
    service = AttendanceLessonSplitService(
        PostgresAttendanceDraftQueryRepository(),
        PostgresAttendanceDraftMutationRepository(),
        PostgresAttendanceIdentityAliasRepository(),
    )
    try:
        result = service.split_lesson(
            lesson_id,
            first_end_at=first_end_at,
            second_start_at=second_start_at,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Split lezione fallito: {exc}") from exc
    return {
        "original_lesson_id": result.original_lesson_id,
        "first_lesson_id": result.first_lesson_id,
        "second_lesson_id": result.second_lesson_id,
        "first_participants_count": result.first_participants_count,
        "second_participants_count": result.second_participants_count,
    }


@app.post("/api/attendance/import-batches/{batch_id}/delete")
async def attendance_delete_import_batch(batch_id: int):
    service = AttendanceLessonStateService(PostgresAttendanceDraftMutationRepository())
    try:
        service.delete_batch(batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"batch_id": batch_id, "deleted": True}


@app.post("/api/attendance/identity-aliases")
async def attendance_create_identity_alias(payload: dict):
    _bootstrap_identity_aliases_if_needed()
    lesson_id = payload.get("lesson_id")
    canonical_participant_id = payload.get("canonical_participant_id")
    alias_participant_id = payload.get("alias_participant_id")
    canonical_full_name = str(payload.get("canonical_full_name") or "").strip()
    canonical_email = str(payload.get("canonical_email") or "").strip() or None
    alias_full_name = str(payload.get("alias_full_name") or "").strip()
    alias_email = str(payload.get("alias_email") or "").strip() or None
    created_by = str(payload.get("created_by") or "drafts-ui").strip() or "drafts-ui"
    notes = payload.get("notes")
    service = AttendanceIdentityAliasService(PostgresAttendanceIdentityAliasRepository())
    rebuilt_lesson = None
    identity_sync = None
    identity_sync_error = None
    try:
        alias = service.merge_participants(
            canonical_full_name=canonical_full_name,
            canonical_email=canonical_email,
            alias_full_name=alias_full_name,
            alias_email=alias_email,
            created_by=created_by,
            notes=notes,
        )
        if lesson_id is not None:
            rebuilt_lesson = AttendanceLessonIdentityRebuildService(
                PostgresAttendanceDraftQueryRepository(),
                PostgresAttendanceDraftMutationRepository(),
                PostgresAttendanceIdentityAliasRepository(),
            ).rebuild_lesson_with_current_aliases_and_hint(
                int(lesson_id),
                canonical_participant_id=int(canonical_participant_id) if canonical_participant_id is not None else None,
                alias_participant_id=int(alias_participant_id) if alias_participant_id is not None else None,
                forced_canonical_full_name=canonical_full_name,
                forced_canonical_email=canonical_email,
            )
        try:
            sync_result = PostgresAttendanceIdentityRepository().sync_alias_identity(alias.id)
            identity_sync = {
                "alias_id": sync_result.alias_id,
                "identity_id": sync_result.identity_id,
                "identity_key": sync_result.identity_key,
                "identity_created": sync_result.identity_created,
                "alias_identity_id": sync_result.alias_identity_id,
                "alias_identity_deactivated": sync_result.alias_identity_deactivated,
            }
        except Exception as exc:
            identity_sync_error = str(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Creazione alias fallita: {exc}") from exc

    return JSONResponse({
        "alias": {
            "id": alias.id,
            "canonical_full_name": alias.canonical_full_name,
            "canonical_email": alias.canonical_email,
            "alias_value": alias.alias_value,
            "alias_type": alias.alias_type,
            "identity_id": identity_sync["identity_id"] if identity_sync else alias.identity_id,
            "created_by": alias.created_by,
            "created_at": alias.created_at.isoformat(),
            "is_active": alias.is_active,
            "notes": alias.notes,
        }
        ,
        "lesson_id": int(lesson_id) if lesson_id is not None else None,
        "lesson_summary": rebuilt_lesson.summary if rebuilt_lesson is not None else None,
        "participants_count": len(rebuilt_lesson.participants) if rebuilt_lesson is not None else None,
        "identity_sync": identity_sync,
        "identity_sync_error": identity_sync_error,
    }, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


@app.get("/api/attendance/identity-aliases")
async def attendance_list_identity_aliases():
    _bootstrap_identity_aliases_if_needed()
    repository = PostgresAttendanceIdentityAliasRepository()
    aliases = repository.list_active_aliases()
    return JSONResponse({
        "aliases": [
            {
                "id": alias.id,
                "canonical_full_name": alias.canonical_full_name,
                "canonical_email": alias.canonical_email,
                "alias_value": alias.alias_value,
                "alias_type": alias.alias_type,
                "identity_id": alias.identity_id,
                "created_by": alias.created_by,
                "created_at": alias.created_at.isoformat(),
                "is_active": alias.is_active,
                "notes": alias.notes,
            }
            for alias in aliases
        ]
    }, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


@app.get("/api/attendance/identity-candidates")
async def attendance_search_identity_candidates(q: str = "", limit: int = 30):
    repository = PostgresAttendanceDraftQueryRepository()
    candidates = repository.search_identity_candidates(q, limit=limit)
    return JSONResponse({
        "candidates": [
            {
                "canonical_full_name": candidate.canonical_full_name,
                "email": candidate.email,
                "appearances_count": candidate.appearances_count,
                "lessons_count": candidate.lessons_count,
                "last_seen_at": candidate.last_seen_at,
            }
            for candidate in candidates
        ]
    }, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


@app.get("/api/attendance/identities")
async def attendance_list_identities(limit: int = 500):
    repository = PostgresAttendanceIdentityRepository()
    identities = repository.list_identities(limit=limit)
    return JSONResponse({
        "total_visible": len(identities),
        "identities": [
            {
                "id": identity.id,
                "identity_key": identity.identity_key,
                "display_name": identity.display_name,
                "email": identity.email,
                "is_active": identity.is_active,
            }
            for identity in identities
        ],
    }, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


@app.post("/api/attendance/identities/rebuild")
async def attendance_rebuild_identities():
    repository = PostgresAttendanceIdentityRepository()
    try:
        result = repository.rebuild_from_participants()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Ricostruzione identità fallita: {exc}") from exc
    return JSONResponse({
        "source_identities": result.source_identities,
        "rows_upserted": result.rows_upserted,
        "identities_count": result.identities_count,
    }, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


@app.post("/api/attendance/identities/{identity_id}/deactivate")
async def attendance_deactivate_identity(identity_id: int):
    repository = PostgresAttendanceIdentityRepository()
    try:
        repository.deactivate_identity(identity_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Disattivazione identità fallita: {exc}") from exc
    return JSONResponse(
        {"identity_id": identity_id, "is_active": False},
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.post("/api/attendance/identities/{identity_id}/display-name")
async def attendance_update_identity_display_name(identity_id: int, payload: dict):
    display_name = str(payload.get("display_name") or "").strip()
    repository = PostgresAttendanceIdentityRepository()
    try:
        identity = repository.update_display_name(identity_id, display_name)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Aggiornamento nome identità fallito: {exc}") from exc
    return JSONResponse(
        {
            "id": identity.id,
            "identity_key": identity.identity_key,
            "display_name": identity.display_name,
            "email": identity.email,
            "is_active": identity.is_active,
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.post("/api/attendance/identity-aliases/{alias_id}/sync-identity")
async def attendance_sync_identity_alias(alias_id: int):
    repository = PostgresAttendanceIdentityRepository()
    try:
        result = repository.sync_alias_identity(alias_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Sync alias-identità fallito: {exc}") from exc
    return JSONResponse(
        {
            "alias_id": result.alias_id,
            "identity_id": result.identity_id,
            "identity_key": result.identity_key,
            "identity_created": result.identity_created,
            "alias_identity_id": result.alias_identity_id,
            "alias_identity_deactivated": result.alias_identity_deactivated,
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.post("/api/attendance/identity-aliases/rebuild-all")
async def attendance_rebuild_all_identity_aliases():
    _bootstrap_identity_aliases_if_needed()
    try:
        result = AttendanceLessonIdentityRebuildService(
            PostgresAttendanceDraftQueryRepository(),
            PostgresAttendanceDraftMutationRepository(),
            PostgresAttendanceIdentityAliasRepository(),
        ).rebuild_all_lessons_with_current_aliases()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Rebuild identità fallito: {exc}") from exc
    return JSONResponse(result, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


@app.get("/api/attendance/instructors")
async def attendance_list_instructors():
    repository = PostgresAttendanceInstructorRepository()
    instructors = repository.list_instructors()
    return JSONResponse(
        {
            "instructors": [
                {
                    "id": instructor.id,
                    "instructor_name": instructor.instructor_name,
                    "alias_of_id": instructor.alias_of_id,
                    "canonical_name": instructor.canonical_name,
                    "notes": instructor.notes,
                    "created_at": instructor.created_at.isoformat(),
                    "updated_at": instructor.updated_at.isoformat(),
                }
                for instructor in instructors
            ],
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.post("/api/attendance/instructors")
async def attendance_create_instructor(payload: dict):
    instructor_name = " ".join(str(payload.get("instructor_name") or "").strip().split())
    raw_alias_of_id = payload.get("alias_of_id")
    alias_of_id = None
    if raw_alias_of_id not in (None, ""):
        try:
            alias_of_id = int(raw_alias_of_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="alias_of_id must be empty or an integer.") from exc
    notes = str(payload.get("notes") or "").strip() or None
    if not instructor_name:
        raise HTTPException(status_code=400, detail="instructor_name is required.")

    repository = PostgresAttendanceInstructorRepository()
    try:
        instructor = repository.create_instructor(
            instructor_name=instructor_name,
            alias_of_id=alias_of_id,
            notes=notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Salvataggio docente fallito: {exc}") from exc

    return JSONResponse(
        {
            "instructor": {
                "id": instructor.id,
                "instructor_name": instructor.instructor_name,
                "alias_of_id": instructor.alias_of_id,
                "canonical_name": instructor.canonical_name,
                "notes": instructor.notes,
                "created_at": instructor.created_at.isoformat(),
                "updated_at": instructor.updated_at.isoformat(),
            },
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/api/attendance/school-records")
async def attendance_school_records():
    repository = PostgresAttendanceDraftQueryRepository()
    records = repository.list_school_attendance_records()
    return JSONResponse(
        {
            "records": [
                {
                    "lesson_id": record.lesson_id,
                    "course_name": record.course_name,
                    "lesson_date": record.lesson_date,
                    "canonical_full_name": record.canonical_full_name,
                    "email": record.email,
                    "final_presence_status": record.final_presence_status,
                    "total_minutes": record.total_minutes,
                    "expected_lessons_count": record.expected_lessons_count,
                    "expected_lessons_source": record.expected_lessons_source,
                }
                for record in records
            ]
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/api/attendance/school-record-source")
async def attendance_school_record_source(lesson_id: int, canonical_full_name: str, email: str = ""):
    repository = PostgresAttendanceDraftQueryRepository()
    lesson = repository.get_lesson_detail(lesson_id)
    if lesson.status != "official" or lesson.is_ignored:
        raise HTTPException(status_code=404, detail="Lesson official non trovata.")

    name_alias_map, email_alias_map = _load_identity_alias_maps(PostgresAttendanceIdentityAliasRepository())
    resolved_name, resolved_email = _apply_identity_alias_maps(canonical_full_name, email, name_alias_map, email_alias_map)
    participant_key = (resolved_email or "").strip().lower() or resolved_name.lower()

    groups = _build_lesson_source_groups(repository, lesson_id)
    sources = groups.get(participant_key, [])
    if not sources:
        # Fallback conservativo per dati storici: se l'email non basta, prova col nome canonico.
        requested_name_key = resolved_name.strip().casefold()
        sources = [
            source
            for grouped_sources in groups.values()
            for source in grouped_sources
            if str(source.get("raw_full_name") or "").strip().casefold() == requested_name_key
        ]

    return JSONResponse(
        {
            "lesson": {
                "id": lesson.id,
                "import_batch_id": lesson.import_batch_id,
                "course_name": lesson.course_name,
                "lesson_date": lesson.lesson_date,
                "meeting_start_at": lesson.meeting_start_at,
            },
            "participant": {
                "canonical_full_name": resolved_name,
                "email": resolved_email or None,
            },
            "sources": [
                {
                    "raw_full_name": source["raw_full_name"],
                    "email": source["email"],
                    "segments": source["segments"],
                }
                for source in sources
            ],
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/api/attendance/school-courses")
async def attendance_school_courses():
    repository = PostgresAttendanceDraftQueryRepository()
    courses = repository.list_school_course_overview()
    total_lessons = sum(len(course.lessons) for course in courses)
    total_records = sum(lesson.total_records for course in courses for lesson in course.lessons)
    total_expected_lessons = sum(course.expected_lessons_count for course in courses)
    return JSONResponse(
        {
            "summary": {
                "courses": len(courses),
                "lessons": total_lessons,
                "expected_lessons": total_expected_lessons,
                "records": total_records,
            },
            "courses": [
                {
                    "course_name": course.course_name,
                    "expected_lessons_count": course.expected_lessons_count,
                    "expected_lessons_source": course.expected_lessons_source,
                    "lessons": [
                        {
                            "lesson_id": lesson.lesson_id,
                            "course_name": lesson.course_name,
                            "lesson_date": lesson.lesson_date,
                            "source_meeting_id": lesson.source_meeting_id,
                            "total_records": lesson.total_records,
                            "presente_count": lesson.presente_count,
                            "prima_meta_count": lesson.prima_meta_count,
                            "seconda_meta_count": lesson.seconda_meta_count,
                            "assente_count": lesson.assente_count,
                        }
                        for lesson in course.lessons
                    ],
                }
                for course in courses
            ],
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/api/attendance/manual-presence-targets")
async def attendance_manual_presence_targets():
    repository = PostgresAttendanceDraftQueryRepository()
    courses = repository.list_school_course_overview()
    return JSONResponse(
        {
            "courses": [
                {
                    "course_name": course.course_name,
                    "lessons": [
                        {
                            "lesson_id": lesson.lesson_id,
                            "lesson_date": lesson.lesson_date,
                            "source_meeting_id": lesson.source_meeting_id,
                            "total_records": lesson.total_records,
                        }
                        for lesson in course.lessons
                    ],
                }
                for course in courses
            ],
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.post("/api/attendance/courses/expected-lessons")
async def attendance_set_course_expected_lessons(payload: dict):
    course_name = str(payload.get("course_name") or "")
    raw_value = payload.get("expected_lessons_count")
    expected_lessons_count = None
    if raw_value is not None and raw_value != "":
        try:
            expected_lessons_count = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="expected_lessons_count must be a positive integer or empty.") from exc

    service = AttendanceCourseConfigService(PostgresAttendanceDraftMutationRepository())
    try:
        service.set_expected_lessons_count(course_name, expected_lessons_count)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Aggiornamento corso fallito: {exc}") from exc

    return JSONResponse(
        {
            "course_name": course_name,
            "expected_lessons_count": expected_lessons_count,
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/api/attendance/school-followups")
async def attendance_school_followups():
    repository = PostgresAttendanceDraftQueryRepository()
    recent_lessons_limit = 4
    missed_lessons_threshold = 3
    followups = repository.list_school_student_followups(
        recent_lessons_limit=recent_lessons_limit,
        missed_lessons_threshold=missed_lessons_threshold,
    )
    return JSONResponse(
        {
            "criteria": {
                "recent_lessons_limit": recent_lessons_limit,
                "missed_lessons_threshold": missed_lessons_threshold,
            },
            "followups": [
                {
                    "course_name": item.course_name,
                    "canonical_full_name": item.canonical_full_name,
                    "email": item.email,
                    "checked_lessons_count": item.checked_lessons_count,
                    "missed_lessons_count": item.missed_lessons_count,
                    "attended_lessons_count": item.attended_lessons_count,
                    "recent_lessons": item.recent_lessons,
                }
                for item in followups
            ],
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.post("/api/attendance/manual-presence")
async def attendance_manual_presence_import(payload: dict):
    service = AttendanceManualPresenceService(
        PostgresAttendanceDraftMutationRepository(),
        PostgresAttendanceIdentityAliasRepository(),
    )
    try:
        result = service.import_manual_presence(
            lesson_id=int(payload["lesson_id"]) if payload.get("lesson_id") else None,
            course_name=str(payload.get("course_name") or ""),
            lesson_date=str(payload.get("lesson_date") or ""),
            presence_source=str(payload.get("presence_source") or "manual"),
            created_by=str(payload.get("created_by") or "manual-ui"),
            records=list(payload.get("records") or []),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Import manuale fallito: {exc}") from exc

    return JSONResponse(
        {
            "lesson_id": result.lesson_id,
            "course_name": result.course_name,
            "lesson_date": result.lesson_date,
            "records_processed": result.records_processed,
            "participants_upserted": result.participants_upserted,
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.post("/api/attendance/identity-aliases/{alias_id}/deactivate")
async def attendance_deactivate_identity_alias(alias_id: int):
    service = AttendanceIdentityAliasService(PostgresAttendanceIdentityAliasRepository())
    try:
        service.deactivate_alias(alias_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Disattivazione alias fallita: {exc}") from exc
    return JSONResponse(
        {"alias_id": alias_id, "is_active": False},
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "rebekko-webapps"}


if __name__ == "__main__":
    import uvicorn

    # Get port from environment variable (Render sets this)
    port = int(os.environ.get("PORT", 8080))

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=True  # Auto-reload on code changes (development only)
    )
