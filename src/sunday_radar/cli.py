from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import typer
from sqlalchemy.orm import Session

from sunday_radar.adapters.morningnews import DailyInput, load_window
from sunday_radar.analysis import build_brief
from sunday_radar.db import Publication, create_db, import_day, remove_orphan_articles
from sunday_radar.rendering import check_html as validate_html
from sunday_radar.rendering import content_hash, render_site
from sunday_radar.settings import Settings
from sunday_radar.telegram import preview_text, send_preview

app = typer.Typer(no_args_is_help=True, help="Build and publish the Sunday Radar briefing.")


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("Use YYYY-MM-DD") from exc


def _target_date(value: str | None) -> date:
    if value:
        return _parse_date(value)
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    return today - timedelta(days=(today.weekday() + 1) % 7)


def _load_and_import(as_of: date, settings: Settings) -> tuple[list[DailyInput], Session]:
    days = load_window(settings.morningnews_root, as_of)
    if len(days) < 3:
        raise typer.BadParameter(f"At least 3 input days are required; found {len(days)}")
    _, session = create_db(settings.database_path)
    changed = sum(import_day(session, day) for day in days)
    remove_orphan_articles(session)
    typer.echo(f"Imported {changed} changed day(s); {len(days)} day(s) available.")
    return days, session


@app.command("import-data")
def import_data(
    as_of: Annotated[
        str | None,
        typer.Option(help="Window end date (YYYY-MM-DD); defaults to the latest KST Sunday"),
    ] = None,
) -> None:
    settings = Settings.load()
    _load_and_import(_target_date(as_of), settings)


@app.command()
def build(
    as_of: Annotated[
        str | None,
        typer.Option(help="Window end date (YYYY-MM-DD); defaults to the latest KST Sunday"),
    ] = None,
) -> None:
    target = _target_date(as_of)
    settings = Settings.load()
    days, session = _load_and_import(target, settings)
    brief = build_brief(days, target)
    issue_path = render_site(brief, settings.output_dir, settings.project_root / "templates")
    digest = content_hash(brief)
    publication = session.get(Publication, target)
    if publication is None:
        publication = Publication(
            week_ending=target,
            content_hash=digest,
            status="generated",
            generated_at=datetime.now(),
        )
        session.add(publication)
    else:
        publication.content_hash = digest
        publication.status = "generated"
        publication.generated_at = datetime.now()
    session.commit()
    errors = validate_html(settings.output_dir)
    if errors:
        publication.status = "failed"
        session.commit()
        typer.echo("\n".join(errors), err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Generated {issue_path}")


@app.command("check-html")
def check_html(path: Annotated[Path, typer.Argument(exists=True, file_okay=False)]) -> None:
    errors = validate_html(path)
    if errors:
        typer.echo("\n".join(errors), err=True)
        raise typer.Exit(code=1)
    typer.echo(f"HTML checks passed: {path}")


@app.command("telegram-preview")
def telegram_preview(
    as_of: Annotated[str, typer.Option(help="Edition date (YYYY-MM-DD)")],
    send: Annotated[bool, typer.Option(help="Actually call Telegram API")] = False,
    force: Annotated[bool, typer.Option(help="Allow a correction re-notification")] = False,
) -> None:
    target = _parse_date(as_of)
    settings = Settings.load()
    days = load_window(settings.morningnews_root, target)
    brief = build_brief(days, target)
    typer.echo(preview_text(brief, settings.public_base_url))
    if send:
        _, session = create_db(settings.database_path)
        send_preview(session, settings, brief, force=force)
        typer.echo("Telegram preview sent.")


if __name__ == "__main__":
    app()
