#!/bin/bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ "$ROOT" != /data/projects/sunday-radar ]]; then
    echo "The service units require /data/projects/sunday-radar" >&2
    exit 1
fi

# Use a versioned interpreter and copies, not the mutable /usr/bin/python3 symlink.
# Fail rather than silently reusing a virtualenv belonging to another Python version.
if [[ ! -e "$ROOT/.venv/bin/python" ]]; then
    /usr/bin/python3.12 -m venv --copies "$ROOT/.venv"
fi
"$ROOT/.venv/bin/python" - <<'PY'
import sys
from pathlib import Path

if sys.version_info[:2] != (3, 12) or Path(sys.executable).is_symlink():
    raise SystemExit("Recreate .venv with /usr/bin/python3.12 -m venv --copies first")
PY
"$ROOT/.venv/bin/python" -m pip install -e "$ROOT[dev]"
"$ROOT/.venv/bin/python" -m pip check
"$ROOT/.venv/bin/sunday-radar" --help >/dev/null

UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$UNIT_DIR"
install -m 644 "$ROOT/deploy/sunday-radar.service" "$UNIT_DIR/sunday-radar.service"
install -m 644 "$ROOT/deploy/sunday-radar.timer" "$UNIT_DIR/sunday-radar.timer"
systemctl --user daemon-reload
systemctl --user enable sunday-radar.timer
systemctl --user restart sunday-radar.timer
systemctl --user list-timers sunday-radar.timer --no-pager

if [[ "$(loginctl show-user "$(id -un)" -p Linger --value)" != yes ]]; then
    echo "WARNING: enable boot/logout scheduling: loginctl enable-linger $(id -un)" >&2
fi