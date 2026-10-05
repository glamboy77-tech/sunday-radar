from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import typer
from sqlalchemy.orm import Session

from sunday_radar.adapters.bank_of_korea import collect_window as collect_bank_of_korea
from sunday_radar.analysis import build_brief
from sunday_radar.db import Publication, create_db, import_days
from sunday_radar.domain import SourceDay
from sunday_radar.editorial import EditorialError, edit_brief
from sunday_radar.publishing import publish_pages, wait_for_pages
from sunday_radar.rendering import RenderValidationError, content_hash, render_site
from sunday_radar.rendering import check_html as validate_html
from sunday_radar.settings import Settings
from sunday_radar.sources import load_sources
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


def _editorial_dates(days: list[SourceDay]) -> set[date]:
    return {day.report_date for day in days if day.source_kind == "morningnews"}


def _publication_is_current(
    publication: Publication | None, digest: str, output_dir: Path, target: date
) -> bool:
    issue_path = output_dir / "issues" / target.isoformat() / "index.html"
    return bool(
        publication is not None
        and publication.status == "generated"
        and publication.content_hash == digest
        and issue_path.exists()
        and (output_dir / "index.html").exists()
        and not validate_html(output_dir)
    )


def _load_and_import(as_of: date, settings: Settings) -> tuple[list[SourceDay], Session]:
    days = load_sources(settings, as_of)
    editorial_dates = _editorial_dates(days)
    if len(editorial_dates) < 3:
        raise typer.BadParameter(
            f"At least 3 Morning News input dates are required; found {len(editorial_dates)}"
        )
    _, session = create_db(settings.database_path)
    changed = import_days(session, days)
    kinds = ", ".join(sorted({day.source_kind for day in days}))
    typer.echo(
        f"Imported {changed} changed snapshot(s); {len(editorial_dates)} Morning News date(s) "
        f"available from {kinds}."
    )
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


@app.command("collect-sources")
def collect_sources(
    as_of: Annotated[
        str | None,
        typer.Option(help="Window end date (YYYY-MM-DD); defaults to the latest KST Sunday"),
    ] = None,
) -> None:
    target = _target_date(as_of)
    settings = Settings.load()
    paths = collect_bank_of_korea(settings.bank_of_korea_cache_dir, target)
    typer.echo(f"Collected {len(paths)} Bank of Korea daily cache file(s).")


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
    try:
        editorial = edit_brief(brief, settings)
    except EditorialError as exc:
        typer.echo(f"Editorial generation failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if settings.editor_mode != "rules" and editorial is None:
        typer.echo("Editorial LLM unavailable or invalid; using rule-based fallback.", err=True)
    elif editorial is not None:
        typer.echo(f"Editorial draft ready with {settings.openai_model}.")
    digest = content_hash(brief, editorial)
    publication = session.get(Publication, target)
    if _publication_is_current(publication, digest, settings.output_dir, target):
        typer.echo(
            f"Unchanged {settings.output_dir / 'issues' / target.isoformat() / 'index.html'}"
        )
        return
    try:
        issue_path = render_site(
            brief,
            settings.output_dir,
            settings.project_root / "templates",
            editorial,
        )
    except RenderValidationError as exc:
        now = datetime.now()
        if publication is None:
            publication = Publication(
                week_ending=target,
                content_hash=digest,
                status="failed",
                generated_at=now,
            )
            session.add(publication)
        else:
            publication.content_hash = digest
            publication.status = "failed"
            publication.generated_at = now
        session.commit()
        typer.echo("\n".join(exc.errors), err=True)
        raise typer.Exit(code=1) from exc
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
    days = load_sources(settings, target)
    brief = build_brief(days, target)
    typer.echo(preview_text(brief, settings.public_base_url))
    if send:
        _, session = create_db(settings.database_path)
        send_preview(session, settings, brief, force=force)
        typer.echo("Telegram preview sent.")


@app.command("publish")
def publish(
    as_of: Annotated[
        str | None, typer.Option(help="Edition date; defaults to the latest KST Sunday")
    ] = None,
) -> None:
    """Publish a built edition to Pages, verify it is live, then notify Telegram."""
    target = _target_date(as_of)
    settings = Settings.load()
    _, session = create_db(settings.database_path)
    publication = session.get(Publication, target)
    issue = settings.output_dir / "issues" / target.isoformat() / "index.html"
    if publication is None or publication.status != "generated" or not issue.is_file():
        raise typer.BadParameter("Build the edition before publishing")
    if validate_html(settings.output_dir):
        raise typer.BadParameter("Site HTML validation failed")
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise typer.BadParameter("Telegram credentials are required to publish")
    url = f"{settings.public_base_url}/issues/{target.isoformat()}/"
    publish_pages(settings.project_root, settings.output_dir, target)
    typer.echo(f"Pushed {target.isoformat()} to origin/main; waiting for {url}")
    wait_for_pages(url, target)
    if publication.telegram_sent_at:
        typer.echo("Telegram already sent for this edition.")
        return
    brief = build_brief(load_sources(settings, target), target)
    send_preview(session, settings, brief)
    typer.echo("Telegram preview sent.")


if __name__ == "__main__":
    app()
