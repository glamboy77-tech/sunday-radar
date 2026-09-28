# Architecture

## 경계

`sunday_radar.adapters`만 외부 파일 형식을 알고 있습니다. adapter는 `/data/projects/morningnews`의 JSON을 읽지만 그 저장소에 파일을 생성하거나 모듈을 import하지 않습니다.

`domain.py`의 Pydantic 모델은 저장소와 renderer 사이의 안정된 계약입니다. `db.py`는 SQLAlchemy persistence, `analysis.py`는 순수하고 결정론적인 규칙, `rendering.py`는 Jinja2 출력, `telegram.py`는 명시적으로 활성화되는 delivery boundary입니다.

```text
CLI -> adapter -> normalized models -> SQLite
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
- 외부 네트워크 I/O는 Telegram `--send` 외에는 Phase 1 기본 파이프라인에 없습니다.
- 공개 산출물에는 DB, 원본 JSON, 환경 변수, API 응답을 포함하지 않습니다.

## 결정성

모든 조회와 컬렉션을 명시적으로 정렬하고 보고서 날짜를 외부 입력으로 받습니다. content hash는 canonical JSON으로 계산하며 생성 시각은 hash 대상에서 제외합니다.
