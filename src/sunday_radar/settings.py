from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    morningnews_root: Path
    bank_of_korea_cache_dir: Path
    database_path: Path
    output_dir: Path
    public_base_url: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    editor_mode: str = "llm-with-fallback"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-terra"
    openai_base_url: str = "https://api.openai.com/v1"
    editorial_cache_dir: Path | None = None

    @classmethod
    def load(cls) -> Settings:
        project_root = Path(__file__).resolve().parents[2]
        return cls(
            project_root=project_root,
            morningnews_root=Path(
                os.getenv("SUNDAY_RADAR_MORNINGNEWS_ROOT", "/data/projects/morningnews")
            ),
            bank_of_korea_cache_dir=Path(
                os.getenv(
                    "SUNDAY_RADAR_BANK_OF_KOREA_CACHE_DIR",
                    project_root / "var" / "sources" / "bank_of_korea",
                )
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
            editor_mode=os.getenv("SUNDAY_RADAR_EDITOR_MODE", "llm-with-fallback"),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_model=os.getenv("SUNDAY_RADAR_OPENAI_MODEL", "gpt-5.6-terra"),
            openai_base_url=os.getenv(
                "SUNDAY_RADAR_OPENAI_BASE_URL", "https://api.openai.com/v1"
            ).rstrip("/"),
            editorial_cache_dir=Path(
                os.getenv(
                    "SUNDAY_RADAR_EDITORIAL_CACHE_DIR",
                    project_root / "var" / "editorial-cache",
                )
            ),
        )
