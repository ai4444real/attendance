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


@app.get("/")
async def workspace_home():
    return HTMLResponse(
        """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rebekko Webapps</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            background: #f4f7f8;
            color: #1f2933;
        }
        .topbar {
            position: sticky;
            top: 0;
            z-index: 10;
            background: rgba(255,255,255,0.92);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid #d9e2ec;
        }
        .topbar-inner {
            max-width: 1040px;
            margin: 0 auto;
            padding: 14px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 14px;
            text-decoration: none;
            color: inherit;
        }
        .brand img {
            height: 42px;
            width: auto;
            display: block;
        }
        .brand-text {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .brand-title {
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: #102a43;
        }
        .brand-subtitle {
            font-size: 12px;
            color: #52606d;
        }
        .nav-link {
            text-decoration: none;
            color: #155e75;
            font-weight: 600;
        }
        .nav-link:hover {
            text-decoration: underline;
        }
        .page {
            max-width: 1040px;
            margin: 0 auto;
            padding: 48px 24px 80px;
        }
        .hero {
            background: linear-gradient(135deg, #16324f 0%, #1f7a8c 100%);
            color: white;
            border-radius: 18px;
            padding: 40px;
            margin-bottom: 28px;
            box-shadow: 0 14px 30px rgba(22, 50, 79, 0.18);
        }
        .hero h1 {
            margin: 0 0 12px;
            font-size: 40px;
        }
        .hero p {
            margin: 0;
            font-size: 18px;
            line-height: 1.5;
            max-width: 720px;
            opacity: 0.95;
        }
        .section-title {
            margin: 0 0 14px;
            font-size: 20px;
        }
        .apps-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }
        .app-card {
            background: white;
            border-radius: 16px;
            padding: 24px;
            text-decoration: none;
            color: inherit;
            border: 1px solid #d9e2ec;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
            transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
        }
        .app-card:hover {
            transform: translateY(-3px);
            border-color: #1f7a8c;
            box-shadow: 0 14px 28px rgba(31, 122, 140, 0.14);
        }
        .app-label {
            display: inline-block;
            margin-bottom: 10px;
            padding: 6px 10px;
            border-radius: 999px;
            background: #dff3f6;
            color: #155e75;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .app-card h2 {
            margin: 0 0 10px;
            font-size: 28px;
        }
        .app-card p {
            margin: 0;
            line-height: 1.6;
            color: #52606d;
        }
    </style>
</head>
<body>
    <header class="topbar">
        <div class="topbar-inner">
            <a class="brand" href="/">
                <img src="/assets/brand/logo_pnl_evolution.png" alt="PNL Evolution">
                <div class="brand-text">
                    <span class="brand-title">Rebekko Webapps</span>
                    <span class="brand-subtitle">Workspace applicativo</span>
                </div>
            </a>
            <a class="nav-link" href="/attendance">Apri Attendance</a>
        </div>
    </header>
    <main class="page">
        <section class="hero">
            <h1>Rebekko Webapps</h1>
            <p>Workspace applicativo per i servizi interni Rebekko. Da qui si accede ai moduli attivi, a partire da Attendance.</p>
        </section>
        <section>
            <h2 class="section-title">Applicazioni disponibili</h2>
            <div class="apps-grid">
                <a class="app-card" href="/attendance">
                    <span class="app-label">Disponibile</span>
                    <h2>Attendance</h2>
                    <p>Caricamento e analisi presenze su dati trackcc-like, con filtri, statistiche ed export.</p>
                </a>
            </div>
        </section>
    </main>
</body>
</html>
        """,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


@app.get("/attendance")
@app.get("/attendance/")
async def attendance_home():
    return FileResponse(
        ATTENDANCE_INDEX_FILE,
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
