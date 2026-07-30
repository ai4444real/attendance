from __future__ import annotations

import asyncio
import subprocess
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import settings
from .db import ActiveJobError, Database, utcnow
from .runner import JobRunner

database = Database(settings.database)
runner = JobRunner(database, settings)
static_dir = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.initialize()
    await runner.recover()
    yield
    await runner.stop()


app = FastAPI(
    title="Rebekko Codex Agent", docs_url=None, redoc_url=None, lifespan=lifespan
)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class JobRequest(BaseModel):
    message: str = Field(min_length=1, max_length=100_000)


def public_job(job: dict) -> dict:
    return job


def create_completed(request: str, response: str, kind: str = "command") -> dict:
    now = utcnow()
    job_id = str(uuid.uuid4())
    database.create_job(
        {
            "id": job_id,
            "request": request,
            "kind": kind,
            "created_at": now,
            "session_id": database.setting("session_id"),
        }
    )
    database.execute(
        """
        UPDATE jobs SET status = 'completed', started_at = ?,
            finished_at = ?, response = ? WHERE id = ?
        """,
        (now, now, response, job_id),
    )
    return database.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))


@app.get("/")
async def index():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "rebekko-codex-agent"}


@app.get("/api/jobs")
async def list_jobs(limit: int = 100):
    limit = min(max(limit, 1), 500)
    return database.fetchall(
        "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
    )[::-1]


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = database.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
    if not job:
        raise HTTPException(404, "Job non trovato.")
    return public_job(job)


@app.post("/api/jobs", status_code=202)
async def submit_job(request: JobRequest):
    message = request.message.strip()
    if not message:
        raise HTTPException(422, "Il messaggio è vuoto.")
    command = message.lower()
    active = database.fetchone(
        "SELECT id FROM jobs WHERE status IN ('queued','running') LIMIT 1"
    )
    if command in {"/stop"}:
        stopped = await runner.stop()
        return create_completed(
            message,
            "Job interrotto." if stopped else "Non c’è alcun job attivo.",
        )
    if active:
        raise HTTPException(
            409,
            {
                "message": (
                    "Codex sta già lavorando. Attendi la conclusione "
                    "o interrompi il job corrente."
                ),
                "job_id": active["id"],
            },
        )
    if command == "/new":
        database.set_setting("session_id", None)
        return create_completed(
            message,
            "Nuova sessione pronta. Verrà creata con il prossimo messaggio.",
        )
    if command == "/status":
        return create_completed(message, await asyncio.to_thread(status_text))
    if command == "/deploy":
        expires = datetime.now(timezone.utc) + timedelta(
            seconds=settings.deploy_confirm_seconds
        )
        database.set_setting("deploy_confirmation", expires.isoformat())
        return create_completed(
            message,
            (
                "Deploy non ancora avviato. Per confermare entro "
                f"{settings.deploy_confirm_seconds} secondi invia: /deploy confirm"
            ),
        )
    if command == "/deploy confirm":
        expiry = database.setting("deploy_confirmation")
        database.set_setting("deploy_confirmation", None)
        if not expiry or datetime.fromisoformat(expiry) < datetime.now(timezone.utc):
            return create_completed(
                message, "Conferma assente o scaduta. Invia prima /deploy."
            )
        return await enqueue(message, "deploy")
    if command.startswith("/"):
        raise HTTPException(400, "Comando non riconosciuto.")
    return await enqueue(message, "codex")


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    active = database.fetchone(
        "SELECT id FROM jobs WHERE id = ? AND status IN ('queued','running')",
        (job_id,),
    )
    if not active:
        raise HTTPException(409, "Il job non è attivo.")
    await runner.stop()
    return database.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))


async def enqueue(message: str, kind: str) -> dict:
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "request": message,
        "kind": kind,
        "created_at": utcnow(),
        "session_id": database.setting("session_id"),
    }
    try:
        database.create_job(job)
    except ActiveJobError as exc:
        raise HTTPException(
            409,
            {
                "message": (
                    "Codex sta già lavorando. Attendi la conclusione "
                    "o interrompi il job corrente."
                ),
                "job_id": exc.job_id,
            },
        ) from exc
    await runner.start(job_id)
    return database.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))


def status_text() -> str:
    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(settings.repo), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return (result.stdout or result.stderr).strip()

    branch = git("branch", "--show-current") or "(detached)"
    porcelain = git("status", "--short")
    active = database.fetchone(
        "SELECT id, status FROM jobs WHERE status IN ('queued','running') LIMIT 1"
    )
    session_id = database.setting("session_id") or "(nessuna: sarà creata al prossimo messaggio)"
    changes = porcelain if porcelain else "Working tree pulito."
    active_text = f"{active['id']} ({active['status']})" if active else "nessuno"
    return (
        f"Branch: {branch}\n\n"
        f"Git status:\n{changes}\n\n"
        f"Job attivo: {active_text}\n"
        f"Sessione Codex: {session_id}"
    )
