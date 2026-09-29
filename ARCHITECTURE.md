# Architecture

## 경계

`sunday_radar.adapters`만 외부 형식을 알고 있습니다. Morning News adapter는 `/data/projects/morningnews`의 JSON을 읽되 해당 저장소를 수정하지 않습니다. 한국은행 adapter는 명시적인 수집 명령에서 공식 RSS를 로컬 캐시에 저장하고, 발행 빌드에서는 캐시만 읽습니다.

`domain.py`의 Pydantic 모델은 저장소와 renderer 사이의 안정된 계약입니다. `db.py`는 SQLAlchemy persistence, `analysis.py`는 순수하고 결정론적인 규칙, `rendering.py`는 Jinja2 출력, `telegram.py`는 명시적으로 활성화되는 delivery boundary입니다.

`editorial.py`는 선택된 핵심 이슈와 출처를 evidence packet으로 제한한 뒤 OpenAI Responses API에 문장 편집을 요청합니다. 응답은 strict JSON Schema와 Pydantic 모델을 모두 통과해야 하며, 이슈 순서·출처 ID·숫자 검사를 추가로 거칩니다. 편집기는 이슈 선택이나 링크를 변경하지 못합니다.

분석기는 각 Morning News 군집을 `real_world_chain`, `operational_risk`, `game_changer`,
`standard` 중 하나로 분류합니다. 반복 일수와 원래 trend score는 보조 지표이며, 본편 세 자리는
가능하면 Game-changer, 생활비 전달 경로, 현장 실무 리스크를 하나씩 배당합니다. 협약·행사·
단순 전망 같은 저신호성 표현은 감점하고, 기술·과학·의료 뉴스는 분야 표지와 구체적인 돌파
표지가 동시에 있을 때만 Game-changer로 인정합니다.

분석기는 Morning News 신호를 먼저 군집화한 뒤 한국은행 자료를 처리합니다. 공식 자료는 허용 목록에 있는 좁은 주제가 정확히 하나의 뉴스 군집과 일치할 때만 근거로 연결하며, 모호한 경우 독립 군집으로 남깁니다. 결합된 공식 자료는 evidence와 source link를 보강하지만 본편의 대표 제목, 점수, 포착 기간에는 영향을 주지 않습니다.

```text
CLI -> source adapters -> SourceDay -> SQLite
                    |                 |
                    +-> analysis <----+
                          |
                     WeeklyBrief
                           +-> optional LLM editorial -> EditorialDraft
                           |                              |
                           +------------------------------+
                                          |
                Jinja2 static renderer
                          |
                        docs/
```

## 신뢰 경계

- 기사 제목, 요약, URL은 신뢰할 수 없는 입력으로 보고 escape·scheme 검증을 적용합니다.
- Morning News의 AI 요약은 보조 신호이며 독립 검증된 사실로 간주하지 않습니다.
- 한국은행 링크는 공식 1차 자료로 구분하지만, RSS 설명에 없는 내용을 추론하지 않습니다.
- 외부 네트워크 I/O는 `collect-sources`, LLM 편집 모드의 `build`, Telegram `--send`에서만 발생합니다.
- LLM에는 공개 기사 제목·요약·출처 메타데이터와 규칙 기반 evidence만 전달하며 환경 변수, DB, 원본 파일은 전달하지 않습니다.
- LLM 응답은 신뢰할 수 없는 입력으로 취급하고 구조·출처 ID·숫자를 검증한 뒤에만 렌더링합니다.
- 공개 산출물에는 DB, 원본 JSON, 환경 변수, API 응답을 포함하지 않습니다.

## 결정성

모든 조회와 컬렉션을 명시적으로 정렬하고 보고서 날짜를 외부 입력으로 받습니다. content hash는 canonical JSON으로 계산하며 생성 시각은 hash 대상에서 제외합니다.

LLM 원고는 evidence packet, prompt version, model을 묶은 hash로 `var/editorial-cache/`에 저장합니다. 같은 조합은 캐시를 재사용하며 최종 publication hash에는 검증된 원고가 포함됩니다.
