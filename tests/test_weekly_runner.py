import os
import subprocess
import sys
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[1] / "deploy" / "run-weekly.sh"


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    deploy = tmp_path / "deploy"
    deploy.mkdir()
    runner = deploy / "run-weekly.sh"
    runner.write_text(RUNNER.read_text())
    bin_dir = tmp_path / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").symlink_to(sys.executable)
    cli = bin_dir / "sunday-radar"
    cli.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$*" >> "$TRACE"\n'
        'if [[ "$1" == "${FAIL_COMMAND:-}" ]]; then exit 1; fi\n'
    )
    cli.chmod(0o755)
    return runner, tmp_path / "trace"


def test_weekly_runner_uses_one_date_and_checks_before_publishing(tmp_path: Path) -> None:
    runner, trace = _setup(tmp_path)
    result = subprocess.run(
        ["bash", str(runner), "2026-10-25"],
        env={**os.environ, "TRACE": str(trace)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert trace.read_text().splitlines() == [
        "collect-sources --as-of 2026-10-25",
        "build --as-of 2026-10-25",
        f"check-html {tmp_path}/docs",
        "publish --as-of 2026-10-25",
    ]


@pytest.mark.parametrize("command", ["collect-sources", "build", "check-html"])
def test_weekly_runner_does_not_publish_after_failure(tmp_path: Path, command: str) -> None:
    runner, trace = _setup(tmp_path)
    result = subprocess.run(
        ["bash", str(runner), "2026-10-25"],
        env={**os.environ, "TRACE": str(trace), "FAIL_COMMAND": command},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "publish --as-of" not in trace.read_text()


def test_weekly_runner_rejects_non_sunday(tmp_path: Path) -> None:
    runner, trace = _setup(tmp_path)
    result = subprocess.run(
        ["bash", str(runner), "2026-10-24"],
        env={**os.environ, "TRACE": str(trace)},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not trace.exists()


def test_weekly_runner_refuses_concurrent_publication(tmp_path: Path) -> None:
    import fcntl

    runner, trace = _setup(tmp_path)
    (tmp_path / "var").mkdir()
    with (tmp_path / "var" / "weekly-publish.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run(
            ["bash", str(runner), "2026-10-25"],
            env={**os.environ, "TRACE": str(trace)},
            capture_output=True,
            text=True,
        )
    assert result.returncode == 75
    assert not trace.exists()
