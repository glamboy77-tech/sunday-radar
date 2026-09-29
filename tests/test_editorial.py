import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from sunday_radar.adapters.morningnews import load_day
from sunday_radar.analysis import build_brief
from sunday_radar.domain import EditorialDraft, WeeklyBrief
from sunday_radar.editorial import EditorialError, edit_brief, evidence_packet, validate_draft
from sunday_radar.settings import Settings

FIXTURE = Path(__file__).parent / "fixtures" / "morningnews"


def _settings(tmp_path: Path, *, mode: str = "llm-with-fallback") -> Settings:
    return Settings(
        project_root=tmp_path,
        morningnews_root=FIXTURE,
        bank_of_korea_cache_dir=tmp_path / "bok",
        database_path=tmp_path / "test.db",
        output_dir=tmp_path / "docs",
        public_base_url="https://example.test/radar",
        telegram_bot_token=None,
        telegram_chat_id=None,
        editor_mode=mode,
        openai_api_key="test-key",
        openai_model="test-model",
        openai_base_url="https://api.example.test/v1",
        editorial_cache_dir=tmp_path / "editorial-cache",
    )


def _brief() -> WeeklyBrief:
    return build_brief([load_day(FIXTURE, date(2026, 9, 28))], date(2026, 9, 28))


def _draft_payload(brief: WeeklyBrief) -> dict[str, Any]:
    packet = evidence_packet(brief)
    sections: list[dict[str, Any]] = []
    for issue in packet["issues"]:
        source_id = issue["sources"][0]["source_id"]
        sections.append(
            {
                "issue_id": issue["issue_id"],
                "heading": f"{issue['title']}에서 시작된 이번 주의 질문",
                "paragraphs": [
                    {
                        "kind": "fact",
                        "text": "이번 주 보도에서 확인된 핵심 장면을 먼저 차분히 살펴봅니다.",
                        "source_ids": [source_id],
                    },
                    {
                        "kind": "interpretation",
                        "text": (
                            "이 변화가 시장과 생활에 닿는 경로를 구분해서 읽을 필요가 있습니다."
                        ),
                        "source_ids": [],
                    },
                ],
            }
        )
    return {
        "headline": "서로 다른 뉴스가 하나의 질문으로 모인 한 주",
        "overview": (
            "이번 주의 여러 장면을 확인된 근거에서 출발해 하나의 흐름으로 천천히 읽어봅니다."
        ),
        "sections": sections,
        "transitions": [
            "첫 장면에서 확인한 변화는 다음 이슈를 이해하는 배경이 됩니다."
            for _ in range(max(0, len(sections) - 1))
        ],
        "conclusion": (
            "다음 주에는 후속 발표와 실제 지표가 이 흐름을 이어가는지 확인할 필요가 있습니다."
        ),
    }


def test_editorial_generation_uses_strict_schema_and_cache(tmp_path: Path) -> None:
    brief = _brief()
    brief.issues[0].sources[0].description = "기사 설명이 evidence packet에 전달됩니다."
    settings = _settings(tmp_path)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        request_payload = json.loads(request.content)
        assert request.url == "https://api.example.test/v1/responses"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request_payload["text"]["format"]["type"] == "json_schema"
        assert request_payload["text"]["format"]["strict"] is True
        schema = request_payload["text"]["format"]["schema"]
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
        packet = json.loads(request_payload["input"])
        assert (
            packet["issues"][0]["sources"][0]["description"]
            == "기사 설명이 evidence packet에 전달됩니다."
        )
        return httpx.Response(
            200,
            request=request,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(_draft_payload(brief), ensure_ascii=False),
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 20},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = edit_brief(brief, settings, client=client)
        second = edit_brief(brief, settings, client=client)

    assert first is not None
    assert first == second
    assert len(calls) == 1
    cache_files = list((tmp_path / "editorial-cache").glob("*.json"))
    assert len(cache_files) == 1
    cached = json.loads(cache_files[0].read_text(encoding="utf-8"))
    assert cached["model"] == "test-model"
    assert cached["usage"] == {"input_tokens": 10, "output_tokens": 20}


def test_invalid_cache_is_replaced_by_a_fresh_response(tmp_path: Path) -> None:
    brief = _brief()
    settings = _settings(tmp_path)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            request=request,
            json={"output_text": json.dumps(_draft_payload(brief), ensure_ascii=False)},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = edit_brief(brief, settings, client=client)
        assert first is not None
        cache_path = next((tmp_path / "editorial-cache").glob("*.json"))
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        cached["draft"]["sections"][0]["paragraphs"][0]["source_ids"] = ["unknown"]
        cache_path.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")

        second = edit_brief(brief, settings, client=client)

    assert second == first
    assert calls == 2


def test_editorial_validation_rejects_unknown_sources_and_invented_numbers() -> None:
    brief = _brief()
    packet = evidence_packet(brief)
    payload = _draft_payload(brief)
    payload["sections"][0]["paragraphs"][0]["source_ids"] = ["unknown-source"]
    with pytest.raises(EditorialError, match="Unknown source ID"):
        validate_draft(EditorialDraft.model_validate(payload), brief, packet)

    payload = _draft_payload(brief)
    payload["conclusion"] = "근거에 없던 9999퍼센트 전망을 새로 추가한 잘못된 결론입니다."
    with pytest.raises(EditorialError, match="unsupported numbers"):
        validate_draft(EditorialDraft.model_validate(payload), brief, packet)


def test_editorial_falls_back_or_fails_according_to_mode(tmp_path: Path) -> None:
    brief = _brief()
    transport = httpx.MockTransport(lambda request: httpx.Response(500, request=request))

    with httpx.Client(transport=transport) as client:
        assert (
            edit_brief(brief, _settings(tmp_path, mode="llm-with-fallback"), client=client) is None
        )
        with pytest.raises(EditorialError, match="request failed"):
            edit_brief(
                brief,
                _settings(tmp_path, mode="llm-required"),
                client=client,
            )


def test_editorial_rejects_refusal_and_incomplete_response(tmp_path: Path) -> None:
    brief = _brief()
    responses = iter(
        [
            {
                "status": "completed",
                "output": [
                    {"content": [{"type": "refusal", "refusal": "Cannot complete this request"}]}
                ],
            },
            {"status": "incomplete", "output": []},
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=next(responses))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        settings = _settings(tmp_path, mode="llm-required")
        with pytest.raises(EditorialError, match="refused"):
            edit_brief(brief, settings, client=client)
        with pytest.raises(EditorialError, match="not completed"):
            edit_brief(brief, settings, client=client)


def test_rules_mode_does_not_require_credentials(tmp_path: Path) -> None:
    brief = _brief()
    settings = _settings(tmp_path, mode="rules")
    settings = Settings(**{**settings.__dict__, "openai_api_key": None})
    assert edit_brief(brief, settings) is None
