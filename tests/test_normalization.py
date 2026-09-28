from sunday_radar.normalization import canonical_url, normalize_text


def test_normalization_handles_unicode_and_unsafe_urls() -> None:
    assert normalize_text("  ＡＩ  데이터센터!! ") == "ai 데이터센터"  # noqa: RUF001
    assert canonical_url("javascript:alert(1)") == ""
    assert canonical_url("https://EXAMPLE.com/a/?utm_source=x&b=2#frag") == (
        "https://example.com/a?b=2"
    )
