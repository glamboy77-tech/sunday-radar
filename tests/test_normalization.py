from sunday_radar.normalization import canonical_url, clean_summary_text, normalize_text


def test_normalization_handles_unicode_and_unsafe_urls() -> None:
    assert normalize_text("  ＡＩ  데이터센터!! ") == "ai 데이터센터"  # noqa: RUF001
    assert canonical_url("javascript:alert(1)") == ""
    assert canonical_url("https://EXAMPLE.com/a/?utm_source=x&b=2#frag") == (
        "https://example.com/a?b=2"
    )


def test_clean_summary_text_removes_markup_and_collapses_whitespace() -> None:
    value = "<table><tr><td>기사&nbsp;요약</td></tr></table>\n\t 다음 문장"
    assert clean_summary_text(value) == "기사 요약 다음 문장"
