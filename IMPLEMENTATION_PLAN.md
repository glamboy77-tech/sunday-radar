# Sunday Radar Implementation Plan

## 1. 목적

Sunday Radar는 최근 7일의 정치, 전쟁, 외교, 정책, 거시경제 이슈를 단순 요약하지 않고 주식, 환율, 금리, 코인, 부동산, 물가와 일상생활로 이어지는 전달 경로를 설명하는 독립 주간 브리핑이다. 두 번째 축인 `요즘 흐름`은 일부 관심층에는 알려졌지만 바쁜 독자가 놓치기 쉬운 지역, 주거, 소비, 서비스, 기술, 문화, 음악의 변화를 선별한다.

정기 발행 시각은 매주 일요일 20:30 KST이며, GitHub Pages의 고정 주차 URL을 본문으로 삼고 Telegram에는 미리보기와 링크만 보낸다.

## 2. 편집 원칙

모든 핵심 내용은 다음 네 층을 섞지 않는다.

1. **확인된 사실**: 출처가 있는 발생 사건, 발표, 수치.
2. **공식 주장**: 정부, 정당, 기업, 기관 등 발언 주체가 밝힌 입장.
3. **시장·전문가 해석**: 사실에서 시장이나 생활로 이어지는 설명. 인과를 확정하지 않는다.
4. **가능 시나리오**: 조건부 미래 경로. 조건과 다음 확인 변수를 함께 쓴다.

투자 권유, 목표 가격, 확인되지 않은 음모론, 일회성 연예인 가십, 억지로 만든 미래 혁명 서사는 제외한다. Phase 1의 규칙 기반 결과는 기사 원문을 독립적으로 사실 검증한 결과가 아니라 Morning News 산출물을 재구성한 것임을 명시한다.

## 3. 경계와 의존성

- 프로젝트 루트: `/data/projects/sunday-radar`
- 읽기 전용 입력: `/data/projects/morningnews`
- 참고만 허용: `/data/projects/start-page`
- 기존 저장소의 코드, 설정, 데이터, Git 상태를 수정하지 않는다.
- 기존 저장소 Python 코드를 import하지 않고 JSON 파일 계약으로만 연결한다.
- 런타임 DB, 로그, API 키, 원본 캐시는 공개 `docs/`에 포함하지 않는다.

기술 기준은 Python 3.12, Pydantic 2, SQLAlchemy 2, Alembic, SQLite, Typer, Jinja2, pytest, Ruff, mypy다. `pyproject.toml`이 패키지와 도구 설정의 단일 계약이다. `uv` 사용을 권장하지만 표준 `venv`와 `pip`로도 동작한다.

## 4. Phase 1 데이터 흐름

```text
Morning News 최근 7일 JSON
  -> 파일명/내용 hash 및 Pydantic 검증
  -> 기사 URL/제목 정규화와 중복 제거
  -> SQLite idempotent upsert
  -> 트렌드 키워드 중심 결정론적 이슈 클러스터
  -> 인물·장소·정책·기업·시장 영역 추출
  -> 영향 경로, 확실성, 다음 확인 변수 생성
  -> 3~5분 QUICK READ 모델
  -> Jinja2 HTML
  -> docs/issues/YYYY-MM-DD/index.html + docs/index.html
  -> Telegram preview/link (기본 dry-run)
```

### 입력 파일

- `data_cache/ai_analysis_YYYYMMDD.json`: 섹션별 기사와 출처 메타데이터
- `data_cache/trending_keywords_YYYYMMDD.json`: 일별 키워드, 이유, 대표·관련 기사
- `data_cache/key_persons_YYYYMMDD.json`: 알려진 인물과 역할
- `sentiment_cache/sentiment_YYYYMMDD.json`: 섹션 요약과 보조 신호

필드 추가는 허용하고 필수 핵심 필드의 타입 오류는 해당 파일을 실패시킨다. 개별 선택 파일의 부재는 경고로 처리한다.

## 5. 저장 모델과 멱등성

- `source_snapshots`: 입력 종류, 보고일, 경로, SHA-256. `(source_kind, report_date)` unique.
- `articles`: 정규 URL 우선, 없으면 제목·출처·시각 hash를 안정 ID로 사용.
- `article_occurrences`: 어느 날짜/섹션에서 관측됐는지 저장.
- `trend_signals`: `(report_date, normalized_keyword)` unique.
- `publications`: 주차 종료일, content hash, 상태, Telegram 알림 시각.

동일 hash 재수입은 no-op이다. 같은 날짜 파일의 내용이 바뀌면 해당 snapshot 파생 행을 한 transaction에서 교체한다. 발행 URL은 주차 종료 일요일 날짜로 고정한다.

## 6. 결정론적 분석

Phase 1은 외부 LLM 없이 완전한 보고서를 만들어야 한다.

- Unicode NFKC, 소문자화, 구두점 제거로 비교 문자열을 만든다.
- 트렌드 키워드를 seed로 사용하고 token overlap과 alias 사전으로 병합한다.
- 정치 이슈는 과병합 방지를 위해 더 높은 유사도 기준을 적용한다.
- 빈도는 동일 날짜 내 반복을 한 번으로 계산한 `active_days`를 사용한다.
- 점수는 지속성, 최신성, 출처 다양성, 섹션 가중치, 시장·생활 연결 가능성으로 구성한다.
- 동일 점수는 최신일, 정규화 제목, 안정 ID 순으로 정렬한다.
- 입력 순서, 현재 시각, DB의 무정렬 조회가 결과에 영향을 주지 않게 한다.

주요 시장 영역은 `stocks`, `fx`, `rates`, `crypto`, `real_estate`, `prices`, `jobs`, `daily_life`다. 기사 제목과 키워드의 명시적 표지어만 사용하며, 근거가 없으면 연결하지 않는다.

## 7. QUICK READ 구조

1. 발행 주차, 입력 범위, 읽기 시간, 누락일 표시
2. **이번 주 판세** 3~5개
   - 무엇이 있었나: 확인된 기사 근거
   - 공식 입장: 입력에 명시된 경우에만
   - 왜 연결되나: 규칙 기반 전달 경로
   - 가능한 다음 경로: 조건부 표현
   - 다음 확인 변수
   - 출처 링크
3. **요즘 흐름**: 반복 등장한 생활·부동산·기업·기술 변화
4. 방법론 및 비투자권유 고지

총 한국어 텍스트는 3~5분 읽기 분량을 목표로 한다. 데이터가 부족하면 억지로 항목 수를 채우지 않고 coverage 경고를 노출한다.

## 8. 발행과 중복 방지

- 생성: 임시 디렉터리에 렌더링 후 검증 성공 시 원자적으로 교체한다.
- 고정 URL: `/issues/YYYY-MM-DD/`
- 최신 URL: `/`
- 아카이브: `/archive.html`
- 같은 `week_ending + content_hash`가 이미 생성됐으면 동일 판으로 취급한다.
- Telegram은 `--send`를 명시한 경우만 호출하고, 토큰·chat ID·public base URL이 모두 있어야 한다.
- 같은 publication의 `telegram_sent_at`이 있으면 재전송하지 않는다. `--force`는 수동 정정 알림에만 사용한다.
- 실제 Git push, Pages 설정, Telegram smoke test, systemd 활성화는 별도 운영 승인 전까지 금지한다.

## 9. 품질 게이트

- 입력 범위가 정확히 기준일 포함 7일인지 검사한다.
- 최소 3개 날짜가 없으면 기본적으로 발행 실패한다.
- 모든 이슈에 실제 근거 기사 URL 또는 명시적 보조 신호가 있어야 한다.
- 사실, 주장, 해석, 시나리오의 CSS label과 모델 필드를 구분한다.
- 해석에는 영향 영역과 연결 경로가 있어야 한다.
- 시나리오에는 `~라면`, `~경우` 같은 조건과 다음 확인 변수가 있어야 한다.
- HTML `lang=ko`, viewport, 문서 제목, 단일 h1, 유효한 http(s) 링크를 검사한다.
- Jinja autoescape를 사용하고 입력 HTML을 본문에 직접 삽입하지 않는다.
- 비밀값, SQLite DB, 원본 JSON을 `docs/`와 Git에 포함하지 않는다.

## 10. 테스트 전략

- 스키마 변형: 선택 필드 누락, 추가 필드, 날짜 표현, 관련 기사 유무
- 멱등 import: 같은 파일 두 번, 같은 날짜의 수정 파일, transaction rollback
- 정규화: URL tracking parameter, Unicode, 제목 공백, 전각 콜론
- 클러스터: 동일 표현, alias, 반대 방향, 일반어만 같은 경우, 입력 순서 변경
- 날짜: 월말, 연말, 윤년, 일요일 주차 경계
- 안전성: HTML escape, `javascript:` URL 차단, 투자 권유형 문구 부재
- renderer: 고정 URL, archive, 최신판, 내부 링크 존재
- Telegram: mock 요청, 기본 dry-run, 중복 전송 차단
- 실제 Morning News 7일을 읽는 로컬 smoke test

모든 변경은 `ruff check`, `ruff format --check`, `mypy`, `pytest`, sample build 및 HTML/link checker를 통과해야 한다.

## 11. 단계별 구현

### Phase 1A — 기반

- Git `main`, 패키지·tests·config·docs 구조
- 설정, DB session, Alembic baseline
- Morning News read-only adapter와 fixtures

### Phase 1B — 주간 분석

- 7일 import, 정규화, deduplication
- 이슈 클러스터와 entity/domain extraction
- 구조화 context 모델과 결정론적 scoring

### Phase 1C — 표현과 발행 안전장치

- Jinja2 Quick Read
- 주차별 URL, latest, archive
- Telegram preview와 duplicate protection
- local systemd unit 예시(비활성 상태)

### Phase 1D — 검증과 로컬 commit

- 전체 정적 검사와 테스트
- 실제 데이터 sample 생성
- 기존 두 저장소가 수정되지 않았는지 확인
- secret 및 산출물 검사
- 로컬 초기 commit

## 12. Phase 1 완료 기준

- 독립 설치와 CLI 실행이 가능하다.
- 최근 7일 Morning News를 읽기 전용으로 가져온다.
- 재실행해도 기사와 발행 이력이 중복되지 않는다.
- 3~5개 핵심 이슈와 별도 요즘 흐름을 생성한다.
- 인물, 장소, 정책, 기업, 시장 영역을 구조화해 노출한다.
- 사실, 공식 주장, 해석, 시나리오를 명시적으로 구분한다.
- 3~5분 HTML, 최신판, 주차별 archive가 생성된다.
- Telegram 기본 동작은 dry-run이며 실제 전송은 명시적 옵션이 필요하다.
- Ruff, mypy, pytest, sample build, HTML/link 검사를 통과한다.
- `/data/projects/morningnews`와 `/data/projects/start-page`에는 변경이 없다.
- GitHub 원격 연결 전 로컬 `main`에 검증된 초기 commit이 존재한다.

## 13. 후속 단계

Phase 2에서 공식 정부·공공기관·기업 원문, Google Trends KR/US, 음악 차트를 추가한다. Hacker News와 GitHub는 실제 채택 신호의 보조 자료로만 쓴다. Gemini는 구조화 후보 처리, OpenAI는 최종 한국어 문장 편집에 제한적으로 사용하되 월 목표 ₩10,000, 강제 상한 ₩30,000 상당을 넘지 않도록 호출량과 비용을 기록한다.
