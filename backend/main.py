"""
Rebekko Webapps - FastAPI Server

Single backend entry point for the Rebekko webapps workspace.
At the moment it serves the Attendance module and its related APIs.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Resolve workspace paths from the backend package location
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(BACKEND_DIR)

# Load environment variables from the workspace .env file (for local development)
load_dotenv(os.path.join(WORKSPACE_DIR, ".env"))

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

# Attendance module paths
ATTENDANCE_STATIC_DIR = os.path.join(WORKSPACE_DIR, "attendance", "static")
ATTENDANCE_INDEX_FILE = os.path.join(ATTENDANCE_STATIC_DIR, "index.html")
GLOBAL_ASSETS_DIR = os.path.join(WORKSPACE_DIR, "assets")

# Mount current module static files
app.mount("/attendance/static", StaticFiles(directory=ATTENDANCE_STATIC_DIR), name="attendance-static")
app.mount("/assets", StaticFiles(directory=GLOBAL_ASSETS_DIR), name="global-assets")


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


@app.get("/attendance")
@app.get("/attendance/")
async def attendance_home():
    body_html = """
        <section>
            <div class="cards">
                <a class="card" href="/attendance/view">
                    <span class="card-label">Attivo</span>
                    <h2>Visualizzazione presenze</h2>
                    <p>Apri la schermata attuale per caricare i file CSV trackcc-like, analizzare i dati e usare filtri ed export.</p>
                </a>
                <a class="card" href="/attendance/manage">
                    <span class="card-label">Prossimo step</span>
                    <h2>Gestione presenze</h2>
                    <p>Area dedicata al flusso operativo di gestione. Per ora e' un placeholder pronto per lo sviluppo successivo.</p>
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


@app.get("/attendance/manage")
@app.get("/attendance/manage/")
async def attendance_manage():
    body_html = """
        <section>
            <div class="card">
                <span class="card-label">Placeholder</span>
                <h2>Gestione presenze</h2>
                <p>Questa sezione verra' sviluppata a breve. Lo spazio e' gia' predisposto per ospitare il flusso operativo di gestione presenze.</p>
                <div class="placeholder-note">Per ora puoi continuare a usare "Visualizzazione presenze" dalla sezione Attendance.</div>
            </div>
        </section>
    """
    return HTMLResponse(
        render_module_shell(
            "Gestione presenze",
            "Area in preparazione per il flusso di gestione operativo del modulo attendance.",
            body_html
        ),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
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
