#!/bin/bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
mkdir -p "$ROOT/var"

# Hold one lock across collection, build, Git push and notification.
exec 9>"$ROOT/var/weekly-publish.lock"
flock -n -E 75 9

# Resolve the edition once so a retry/catch-up never mixes dates between steps.
TARGET=$("$ROOT/.venv/bin/python" - "${1:-}" <<'PY'
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

if sys.argv[1]:
    target = date.fromisoformat(sys.argv[1])
else:
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    target = today - timedelta(days=(today.weekday() + 1) % 7)
if target.weekday() != 6:
    raise SystemExit("Edition date must be a Sunday")
print(target.isoformat())
PY
)

CLI="$ROOT/.venv/bin/sunday-radar"
echo "Sunday Radar: publishing edition $TARGET"
"$CLI" collect-sources --as-of "$TARGET"
"$CLI" build --as-of "$TARGET"
"$CLI" check-html "$ROOT/docs"
"$CLI" publish --as-of "$TARGET"
echo "Sunday Radar: publication completed for $TARGET"