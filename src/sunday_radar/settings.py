from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    morningnews_root: Path
    database_path: Path
    output_dir: Path
    public_base_url: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None

    @classmethod
    def load(cls) -> Settings:
        project_root = Path(__file__).resolve().parents[2]
        return cls(
            project_root=project_root,
            morningnews_root=Path(
                os.getenv("SUNDAY_RADAR_MORNINGNEWS_ROOT", "/data/projects/morningnews")
            ),
            database_path=Path(
                os.getenv("SUNDAY_RADAR_DATABASE_PATH", project_root / "var" / "sunday-radar.db")
            ),
            output_dir=Path(os.getenv("SUNDAY_RADAR_OUTPUT_DIR", project_root / "docs")),
            public_base_url=os.getenv(
                "SUNDAY_RADAR_PUBLIC_BASE_URL",
                "https://glamboy77-tech.github.io/sunday-radar",
            ).rstrip("/"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        )
