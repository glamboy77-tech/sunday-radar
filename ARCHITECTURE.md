# Architecture

## 경계

`sunday_radar.adapters`만 외부 형식을 알고 있습니다. Morning News adapter는 `/data/projects/morningnews`의 JSON을 읽되 해당 저장소를 수정하지 않습니다. 한국은행 adapter는 명시적인 수집 명령에서 공식 RSS를 로컬 캐시에 저장하고, 발행 빌드에서는 캐시만 읽습니다.

`domain.py`의 Pydantic 모델은 저장소와 renderer 사이의 안정된 계약입니다. `db.py`는 SQLAlchemy persistence, `analysis.py`는 순수하고 결정론적인 규칙, `rendering.py`는 Jinja2 출력, `telegram.py`는 명시적으로 활성화되는 delivery boundary입니다.

분석기는 Morning News 신호를 먼저 군집화한 뒤 한국은행 자료를 처리합니다. 공식 자료는 허용 목록에 있는 좁은 주제가 정확히 하나의 뉴스 군집과 일치할 때만 근거로 연결하며, 모호한 경우 독립 군집으로 남깁니다. 결합된 공식 자료는 evidence와 source link를 보강하지만 본편의 대표 제목, 점수, 포착 기간에는 영향을 주지 않습니다.

```text
CLI -> source adapters -> SourceDay -> SQLite
                    |                 |
                    +-> analysis <----+
                          |
                     WeeklyBrief
                          |
                Jinja2 static renderer
                          |
                        docs/
```

## 신뢰 경계

- 기사 제목, 요약, URL은 신뢰할 수 없는 입력으로 보고 escape·scheme 검증을 적용합니다.
- Morning News의 AI 요약은 보조 신호이며 독립 검증된 사실로 간주하지 않습니다.
- 한국은행 링크는 공식 1차 자료로 구분하지만, RSS 설명에 없는 내용을 추론하지 않습니다.
- 외부 네트워크 I/O는 `collect-sources`와 Telegram `--send`에서만 발생합니다.
- 공개 산출물에는 DB, 원본 JSON, 환경 변수, API 응답을 포함하지 않습니다.

## 결정성

모든 조회와 컬렉션을 명시적으로 정렬하고 보고서 날짜를 외부 입력으로 받습니다. content hash는 canonical JSON으로 계산하며 생성 시각은 hash 대상에서 제외합니다.
