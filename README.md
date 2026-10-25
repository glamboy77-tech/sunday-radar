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
sunday-radar publish --as-of YYYY-MM-DD
```

`collect-sources`는 한국은행 공식 RSS를 `var/sources/bank_of_korea/`에 날짜별 JSON으로 저장합니다. `build`는 Morning News와 이미 수집된 공식 자료 캐시를 import·분석하며, LLM 편집이 활성화되고 유효한 캐시가 없을 때만 OpenAI API를 호출합니다. `rules` 모드의 build는 네트워크를 호출하지 않습니다. 실제 Telegram 전송은 `telegram-preview --send`를 명시하고 환경 변수까지 설정한 경우에만 가능합니다.

기본 편집 모드는 `llm-with-fallback`입니다. `OPENAI_API_KEY`가 있으면 규칙 기반으로 선택한 이슈와 출처 범위 안에서 OpenAI가 제목·도입·본문·전환·맺음말을 편집합니다. 응답은 구조, 이슈 순서, source ID와 숫자 검사를 통과해야 하며 실패하거나 키가 없으면 기존 규칙 원고를 사용합니다. `SUNDAY_RADAR_EDITOR_MODE=rules`는 LLM을 완전히 끄고, `llm-required`는 검증된 원고가 없을 때 빌드를 실패시킵니다. 동일 입력·prompt·model의 원고는 `var/editorial-cache/`에서 재사용합니다.

핵심 이슈는 단순 반복 횟수가 아니라 `권력자의 상태 변경`, `현실 연쇄 반응`, `실무 리스크`,
`Game-changer`의 편집 축으로 분류합니다. 특정 인물 이름을 우대하지 않고 대통령·총리·장관·
중앙은행 총재·규제기관장·기업 최고책임자 등의 역할과 실제 행동을 함께 봅니다. 단순 축사나
정치 공방이 아니라 명령·서명·철회·공격·파병·제재·관세·합의처럼 국가·시장·현장 조건을
바꾼 경우에만 `POWER MOVE`로 가점을 줍니다. 전쟁·유가·금리 뉴스는 생활비까지 이어지는 전달 경로가 있을 때,
재판·규제·인허가 뉴스는 일정·자금·착공에 걸리는 병목이 있을 때 우선합니다. 기술·과학·의료는
최초 승인, 임상 성공, 상용화처럼 기존 선택지를 바꾸는 돌파 신호와 분야 표지가 함께 있을 때만
Game-changer로 올리고, 협약·행사·수상·단순 전망은 감점합니다.

`deploy/sunday-radar.service`는 예약 발행 전에 `collect-sources`를 먼저 실행하고 `build` 성공 후 `publish`를 실행합니다. `publish`는 `docs/index.html`, `docs/archive.html`, 해당 주차의 `docs/issues/YYYY-MM-DD/index.html`만 커밋해 `origin/main`으로 푸시하고 공개 URL에서 해당 판을 확인한 뒤 Telegram 알림을 보냅니다. 푸시·공개 확인에 실패하면 전송하지 않으며, 재실행 시 이미 보낸 판의 중복 전송을 막습니다. GitHub Pages의 배포 브랜치가 `main`의 `/docs`이고 서비스 계정에 Git push 권한이 있어야 합니다. 운영 중인 사용자 systemd 유닛을 변경했다면 배포 파일을 다시 복사하고 `systemctl --user daemon-reload`로 갱신해야 합니다. 발행 가능 여부와 누락일은 본편 입력인 Morning News 날짜를 기준으로 판단하며, 공식 자료만 있는 날짜는 coverage를 채우지 않습니다.

`build`는 기존 공개 디렉터리를 임시 staging 디렉터리에 복제한 뒤 새 판을 렌더링하고, 제목·내부 링크·fragment·로컬 자산을 포함한 HTML 검사를 통과한 경우에만 `docs/`를 교체합니다. 검증 실패 시 기존 공개판은 유지됩니다. 같은 주차와 content hash의 유효한 산출물이 이미 있으면 `Unchanged`로 종료합니다.

7일치 source snapshot import와 orphan 정리는 하나의 DB transaction으로 처리합니다. 중간 날짜나 출처에서 검증·저장 오류가 발생하면 해당 실행의 변경 전체를 rollback합니다. GitHub Actions CI도 외부 네트워크 수집 없이 Ruff, mypy, pytest를 실행합니다.

공식 자료는 `기준금리`, `국제수지`, `소비자심리`처럼 좁게 정의한 주제가 정확히 하나의 핵심 뉴스 흐름과 일치할 때만 `공식 입장` 근거로 연결합니다. 독립된 한국은행 자료는 생활경제 의미를 명확히 풀 수 있는 지표만 `ECONOMY IN PLAIN WORDS`에 표시하며, 기술적인 발표 제목만 나열하지 않습니다. 공식 자료가 연결돼도 본편 제목·점수·포착 기간은 Morning News 신호를 기준으로 유지합니다.

## 자동 발행 운영

이 PC의 사용자 systemd 타이머가 **매주 일요일 20:30 (Asia/Seoul)**에 실행합니다.
GitHub Actions는 품질 검사만 담당하며 발행 스케줄러가 아닙니다.

```bash
bash /data/projects/sunday-radar/deploy/install.sh
systemctl --user status sunday-radar.timer --no-pager
journalctl --user -u sunday-radar.service -n 80 --no-pager
```

설치 스크립트는 Python 3.12 복사본 가상환경을 확인하고 의존성 설치, 서비스·타이머
등록, 예약 활성화까지 수행합니다. `/usr/bin/python3`의 버전이 바뀌어도 영향을 받지
않도록 가상환경의 실행 파일은 심볼릭 링크를 쓰지 않습니다. 기존 가상환경이 깨졌다면
이를 `var/` 아래에 백업한 뒤 아래 명령으로 새로 만들고 설치 스크립트를 실행합니다.

```bash
/usr/bin/python3.12 -m venv --copies /data/projects/sunday-radar/.venv
```

`deploy/run-weekly.sh`가 하나의 잠금과 동일한 기준일로 수집 → 빌드 → HTML 검사 →
발행을 순서대로 수행합니다. 발행물 3개만 자동 커밋·푸시하며, 다른 코드 수정은
임의로 커밋하지 않습니다. 실패하면 서비스가 15분마다 재시도합니다. 이미 푸시된
커밋은 다시 푸시할 수 있고, 이미 전송한 판의 Telegram 알림은 생략합니다.
서비스에는 `.env`가 로드되며 Git SSH 인증은 대화형 입력 없이 가능해야 합니다.

`Persistent=true`로 PC가 꺼져 놓친 예약은 다음 기동 때 최신 일요일 기준으로
보충 실행합니다(장기간 중단 시 과거 모든 주차를 자동 복원하는 것은 아닙니다).
로그아웃 상태에서도 예약을 유지하려면 `loginctl enable-linger glamboy`가 필요합니다.
PC가 꺼진 동안 정시 발행은 불가능하므로 24시간 정시 발행에는 상시 가동 호스트가 필요합니다.

수동 즉시 실행(실제 커밋·푸시·Telegram 전송 포함):

```bash
systemctl --user start sunday-radar.service
```

과거 판 보충은 `.env`를 로드한 환경에서
`bash /data/projects/sunday-radar/deploy/run-weekly.sh YYYY-MM-DD`로 실행합니다.
과거 판 빌드도 홈 페이지를 바꾸므로 최신 판보다 먼저 처리해야 합니다.

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
