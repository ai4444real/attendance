from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    repo: Path
    codex: Path
    database: Path
    deploy_script: Path
    deploy_confirm_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            repo=Path(
                os.getenv("REBEKKO_AGENT_REPO", "/home/ubuntu/src/rebekko-webapps")
            ),
            codex=Path(
                os.getenv("REBEKKO_AGENT_CODEX", "/home/ubuntu/.npm-global/bin/codex")
            ),
            database=Path(
                os.getenv("REBEKKO_AGENT_DB", "/var/lib/rebekko-agent/agent.sqlite3")
            ),
            deploy_script=Path(
                os.getenv(
                    "REBEKKO_AGENT_DEPLOY_SCRIPT", "/opt/rebekko/webapps/deploy.sh"
                )
            ),
            deploy_confirm_seconds=int(
                os.getenv("REBEKKO_AGENT_DEPLOY_CONFIRM_SECONDS", "60")
            ),
        )


settings = Settings.from_env()
