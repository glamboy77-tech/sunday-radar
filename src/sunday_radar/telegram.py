from __future__ import annotations

from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from sunday_radar.db import Publication
from sunday_radar.domain import WeeklyBrief
from sunday_radar.settings import Settings


def preview_text(brief: WeeklyBrief, public_base_url: str) -> str:
    bullets = "\n".join(f"• {issue.title}" for issue in brief.issues[:3])
    return (
        f"📡 Sunday Radar | {brief.week_ending.isoformat()}\n"
        f"{brief.headline}\n\n{bullets}\n\n"
        f"{public_base_url}/issues/{brief.week_ending.isoformat()}/"
    )


def send_preview(
    session: Session, settings: Settings, brief: WeeklyBrief, *, force: bool = False
) -> None:
    publication = session.get(Publication, brief.week_ending)
    if publication is None:
        raise RuntimeError("Build the publication before sending Telegram")
    if publication.telegram_sent_at and not force:
        raise RuntimeError("Telegram preview was already sent for this edition")
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
    response = httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
        json={
            "chat_id": settings.telegram_chat_id,
            "text": preview_text(brief, settings.public_base_url),
            "disable_web_page_preview": False,
        },
        timeout=20,
    )
    response.raise_for_status()
    publication.telegram_sent_at = datetime.now()
    session.commit()
