from __future__ import annotations

import subprocess
import time
from datetime import date
from pathlib import Path

import httpx


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def publish_pages(root: Path, output_dir: Path, target: date) -> None:
    """Commit only this edition's generated files, then push the current main branch."""
    if _git(root, "branch", "--show-current") != "main":
        raise RuntimeError("Pages publishing requires the main branch")
    if _git(root, "diff", "--cached", "--name-only"):
        raise RuntimeError("Staged changes exist; refusing to include them in a Pages commit")
    relative = output_dir.resolve().relative_to(root.resolve())
    paths = [
        str(relative / "index.html"),
        str(relative / "archive.html"),
        str(relative / "issues" / target.isoformat() / "index.html"),
    ]
    if not all((root / path).is_file() for path in paths):
        raise RuntimeError("Generated edition or site index is missing")
    _git(root, "add", "--", *paths)
    if _git(root, "diff", "--cached", "--name-only"):
        _git(root, "commit", "-m", f"Publish Sunday Radar {target.isoformat()}", "--", *paths)
    # Also retries a previous successful commit whose push failed.
    _git(root, "push", "origin", "main")


def wait_for_pages(url: str, target: date, *, attempts: int = 20, interval: int = 15) -> None:
    """Do not notify readers until the specific edition is publicly accessible."""
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        for attempt in range(attempts):
            try:
                response = client.get(url)
                if response.status_code == 200 and target.isoformat() in response.text:
                    return
            except httpx.HTTPError:
                pass
            if attempt < attempts - 1:
                time.sleep(interval)
    raise RuntimeError(f"Edition not visible on Pages after {attempts} checks: {url}")
