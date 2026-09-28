# Sunday Radar

정치·외교·정책과 시장·부동산·생활의 연결 경로를 설명하는 독립 주간 브리핑입니다.

## 빠른 시작

```bash
cd /data/projects/sunday-radar
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
.venv/bin/sunday-radar build --as-of 2026-09-27
```

기본 입력은 `/data/projects/morningnews`, DB는 `var/sunday-radar.db`, 정적 출력은 `docs/`입니다. 입력 저장소는 읽기 전용으로 취급합니다.

## 명령

```bash
sunday-radar import-data --as-of YYYY-MM-DD
sunday-radar build --as-of YYYY-MM-DD
sunday-radar check-html docs
sunday-radar telegram-preview --as-of YYYY-MM-DD
```

`build`는 import, 분석, HTML 생성을 함께 수행합니다. 실제 Telegram 전송은 `telegram-preview --send`를 명시하고 환경 변수까지 설정한 경우에만 가능합니다.

## 개발 검증

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src
.venv/bin/pytest
.venv/bin/sunday-radar build --as-of 2026-09-27
.venv/bin/sunday-radar check-html docs
```

자세한 결정과 단계는 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), 구성 요소 경계는 [ARCHITECTURE.md](ARCHITECTURE.md)를 참고하세요.
