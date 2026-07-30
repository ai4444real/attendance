from __future__ import annotations

import asyncio
import json
import os
import signal
from pathlib import Path

from .config import Settings
from .db import Database, utcnow


class JobRunner:
    def __init__(self, database: Database, settings: Settings):
        self.db = database
        self.settings = settings
        self._task: asyncio.Task | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()

    async def recover(self) -> None:
        # A child process cannot be re-attached reliably after its parent service
        # has died. systemd's KillMode=control-group terminates it with the service.
        self.db.execute(
            """
            UPDATE jobs
            SET status = 'failed', finished_at = ?, pid = NULL,
                error = COALESCE(error || '\n', '') ||
                    'Il servizio è stato riavviato durante l’esecuzione.'
            WHERE status IN ('queued','running')
            """,
            (utcnow(),),
        )

    async def start(self, job_id: str) -> None:
        async with self._lock:
            if self._task and not self._task.done():
                raise RuntimeError("a job is already running")
            self._task = asyncio.create_task(self._run(job_id))

    async def stop(self) -> bool:
        process = self._process
        active = self.db.fetchone(
            "SELECT id FROM jobs WHERE status IN ('queued','running') LIMIT 1"
        )
        if not active:
            return False
        self.db.execute(
            "UPDATE jobs SET status = 'cancelled', finished_at = ? WHERE id = ?",
            (utcnow(), active["id"]),
        )
        if process and process.returncode is None:
            await self._terminate_group(process)
        elif self._task and not self._task.done():
            self._task.cancel()
        return True

    async def _run(self, job_id: str) -> None:
        job = self.db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if not job or job["status"] != "queued":
            return
        command = self._command(job)
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=self.settings.repo,
                stdin=asyncio.subprocess.PIPE if job["kind"] == "codex" else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
            self._process = process
            self.db.execute(
                """
                UPDATE jobs SET status = 'running', started_at = ?, pid = ?
                WHERE id = ? AND status = 'queued'
                """,
                (utcnow(), process.pid, job_id),
            )
            if job["kind"] == "codex" and process.stdin:
                process.stdin.write(job["request"].encode("utf-8"))
                await process.stdin.drain()
                process.stdin.close()

            final_message = ""
            assert process.stdout
            while line := await process.stdout.readline():
                text = line.decode("utf-8", errors="replace")
                self.db.execute(
                    "UPDATE jobs SET output = output || ? WHERE id = ?",
                    (text, job_id),
                )
                if job["kind"] == "codex":
                    session_id, message = self._parse_event(text)
                    if session_id:
                        self.db.set_setting("session_id", session_id)
                        self.db.execute(
                            "UPDATE jobs SET session_id = ? WHERE id = ?",
                            (session_id, job_id),
                        )
                    if message:
                        final_message = message

            exit_code = await process.wait()
            current = self.db.fetchone("SELECT status FROM jobs WHERE id = ?", (job_id,))
            if not current or current["status"] == "cancelled":
                return
            if exit_code == 0:
                response = (
                    final_message
                    if job["kind"] == "codex"
                    else "Deploy completato correttamente."
                )
                self.db.execute(
                    """
                    UPDATE jobs SET status = 'completed', finished_at = ?,
                        response = ?, exit_code = ?, pid = NULL
                    WHERE id = ?
                    """,
                    (utcnow(), response, exit_code, job_id),
                )
            else:
                self.db.execute(
                    """
                    UPDATE jobs SET status = 'failed', finished_at = ?,
                        error = ?, exit_code = ?, pid = NULL
                    WHERE id = ?
                    """,
                    (
                        utcnow(),
                        f"Il processo è terminato con codice {exit_code}.",
                        exit_code,
                        job_id,
                    ),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.db.execute(
                """
                UPDATE jobs SET status = 'failed', finished_at = ?,
                    error = ?, pid = NULL WHERE id = ?
                """,
                (utcnow(), str(exc), job_id),
            )
        finally:
            self._process = None

    def _command(self, job: dict) -> list[str]:
        if job["kind"] == "deploy":
            return [
                "sudo",
                "-n",
                "systemd-run",
                "--quiet",
                "--wait",
                "--pipe",
                "--collect",
                "--unit",
                f"rebekko-agent-deploy-{job['id']}",
                "--uid",
                "ubuntu",
                "--gid",
                "ubuntu",
                "--property",
                f"WorkingDirectory={self.settings.deploy_script.parent.parent}",
                str(self.settings.deploy_script),
            ]
        base = [
            str(self.settings.codex),
            "exec",
            "--json",
            "--color",
            "never",
            "--sandbox",
            "workspace-write",
            "--ask-for-approval",
            "never",
            "-C",
            str(self.settings.repo),
        ]
        session_id = job.get("session_id")
        if session_id:
            return [*base, "resume", session_id, "-"]
        return [*base, "-"]

    @staticmethod
    def _parse_event(line: str) -> tuple[str | None, str | None]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return None, None
        session_id = None
        message = None
        if event.get("type") in {"thread.started", "session.started"}:
            session_id = event.get("thread_id") or event.get("session_id")
        item = event.get("item") or {}
        if (
            event.get("type") in {"item.completed", "message.completed"}
            and item.get("type") == "agent_message"
        ):
            message = item.get("text")
        return session_id, message

    @staticmethod
    async def _terminate_group(process: asyncio.subprocess.Process) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            await asyncio.wait_for(process.wait(), timeout=8)
        except ProcessLookupError:
            return
        except asyncio.TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()
