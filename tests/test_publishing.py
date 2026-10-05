from datetime import date
from pathlib import Path

import httpx
import pytest

from sunday_radar import publishing


def test_publish_pages_commits_only_edition_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = date(2026, 10, 4)
    root = tmp_path
    for name in ("index.html", "archive.html", "issues/2026-10-04/index.html"):
        path = root / "docs" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("2026-10-04", encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    def git(_root: Path, *args: str) -> str:
        calls.append(args)
        if args == ("branch", "--show-current"):
            return "main"
        if args == ("diff", "--cached", "--name-only"):
            return "" if calls.count(args) == 1 else "docs/index.html"
        return ""

    monkeypatch.setattr(publishing, "_git", git)
    publishing.publish_pages(root, root / "docs", target)
    assert (
        "add",
        "--",
        "docs/index.html",
        "docs/archive.html",
        "docs/issues/2026-10-04/index.html",
    ) in calls
    assert calls[-1] == ("push", "origin", "main")
    assert any(call[:2] == ("commit", "-m") for call in calls)


def test_publish_pages_refuses_staged_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def git(_root: Path, *args: str) -> str:
        return "main" if args[0] == "branch" else "other.py"

    monkeypatch.setattr(publishing, "_git", git)
    with pytest.raises(RuntimeError, match="Staged changes"):
        publishing.publish_pages(tmp_path, tmp_path / "docs", date(2026, 10, 4))


def test_wait_for_pages_requires_live_edition(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(404)
        return httpx.Response(200, text="<h1>Sunday Radar 2026-10-04</h1>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(publishing.httpx, "Client", lambda **kwargs: client)
    publishing.wait_for_pages(
        "https://example.test/issues/2026-10-04/", date(2026, 10, 4), interval=0
    )
    assert calls == 2


def test_wait_for_pages_fails_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    monkeypatch.setattr(publishing.httpx, "Client", lambda **kwargs: client)
    with pytest.raises(RuntimeError, match="not visible"):
        publishing.wait_for_pages(
            "https://example.test/issues/2026-10-04/", date(2026, 10, 4), attempts=1
        )
