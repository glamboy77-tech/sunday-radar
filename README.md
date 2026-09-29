# Sunday Radar

거대 이슈가 지갑과 생활비로 번지는 경로, 정치·정책이 현장 사업에 거는 브레이크,
기술·과학·의료의 판을 바꾸는 뉴스를 선별하는 독립 주간 브리핑입니다.

## 빠른 시작

```bash
cd /data/projects/sunday-radar
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
.venv/bin/sunday-radar build --as-of 2026-09-27
```

기본 입력은 `/data/projects/morningnews`이며, 선택적으로 한국은행 공식 보도자료 RSS를 로컬 캐시에 수집해 함께 사용합니다. DB는 `var/sunday-radar.db`, 정적 출력은 `docs/`입니다. Morning News 입력 저장소는 읽기 전용으로 취급합니다.

## 명령

```bash
sunday-radar import-data --as-of YYYY-MM-DD
sunday-radar collect-sources --as-of YYYY-MM-DD
sunday-radar build --as-of YYYY-MM-DD
sunday-radar check-html docs
sunday-radar telegram-preview --as-of YYYY-MM-DD
```

`collect-sources`는 한국은행 공식 RSS를 `var/sources/bank_of_korea/`에 날짜별 JSON으로 저장합니다. `build`는 Morning News와 이미 수집된 공식 자료 캐시를 import·분석하며, LLM 편집이 활성화되고 유효한 캐시가 없을 때만 OpenAI API를 호출합니다. `rules` 모드의 build는 네트워크를 호출하지 않습니다. 실제 Telegram 전송은 `telegram-preview --send`를 명시하고 환경 변수까지 설정한 경우에만 가능합니다.

기본 편집 모드는 `llm-with-fallback`입니다. `OPENAI_API_KEY`가 있으면 규칙 기반으로 선택한 이슈와 출처 범위 안에서 OpenAI가 제목·도입·본문·전환·맺음말을 편집합니다. 응답은 구조, 이슈 순서, source ID와 숫자 검사를 통과해야 하며 실패하거나 키가 없으면 기존 규칙 원고를 사용합니다. `SUNDAY_RADAR_EDITOR_MODE=rules`는 LLM을 완전히 끄고, `llm-required`는 검증된 원고가 없을 때 빌드를 실패시킵니다. 동일 입력·prompt·model의 원고는 `var/editorial-cache/`에서 재사용합니다.

핵심 이슈는 단순 반복 횟수가 아니라 `현실 연쇄 반응`, `실무 리스크`, `Game-changer`의
세 편집 축으로 분류합니다. 전쟁·유가·금리 뉴스는 생활비까지 이어지는 전달 경로가 있을 때,
재판·규제·인허가 뉴스는 일정·자금·착공에 걸리는 병목이 있을 때 우선합니다. 기술·과학·의료는
최초 승인, 임상 성공, 상용화처럼 기존 선택지를 바꾸는 돌파 신호와 분야 표지가 함께 있을 때만
Game-changer로 올리고, 협약·행사·수상·단순 전망은 감점합니다.

`deploy/sunday-radar.service` 예시는 예약 발행 전에 `collect-sources`를 먼저 실행하고, 수집이 성공한 경우에만 `build`를 실행합니다. 발행 가능 여부와 누락일은 본편 입력인 Morning News 날짜를 기준으로 판단하며, 공식 자료만 있는 날짜는 coverage를 채우지 않습니다.

`build`는 기존 공개 디렉터리를 임시 staging 디렉터리에 복제한 뒤 새 판을 렌더링하고, 제목·내부 링크·fragment·로컬 자산을 포함한 HTML 검사를 통과한 경우에만 `docs/`를 교체합니다. 검증 실패 시 기존 공개판은 유지됩니다. 같은 주차와 content hash의 유효한 산출물이 이미 있으면 `Unchanged`로 종료합니다.

7일치 source snapshot import와 orphan 정리는 하나의 DB transaction으로 처리합니다. 중간 날짜나 출처에서 검증·저장 오류가 발생하면 해당 실행의 변경 전체를 rollback합니다. GitHub Actions CI도 외부 네트워크 수집 없이 Ruff, mypy, pytest를 실행합니다.

공식 자료는 `기준금리`, `국제수지`, `소비자심리`처럼 좁게 정의한 주제가 정확히 하나의 핵심 뉴스 흐름과 일치할 때만 `공식 입장` 근거로 연결합니다. 독립된 한국은행 자료는 생활경제 의미를 명확히 풀 수 있는 지표만 `ECONOMY IN PLAIN WORDS`에 표시하며, 기술적인 발표 제목만 나열하지 않습니다. 공식 자료가 연결돼도 본편 제목·점수·포착 기간은 Morning News 신호를 기준으로 유지합니다.

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
