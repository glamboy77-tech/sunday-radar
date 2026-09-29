from __future__ import annotations

import hashlib
import re
import unicodedata
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

TRACKING_PARAMS = {"fbclid", "gclid", "oc", "ref", "source"}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower().strip()
    value = re.sub(r"[^0-9a-z가-힣%+]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_summary_text(value: str) -> str:
    text = BeautifulSoup(unescape(value), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def canonical_url(value: str) -> str:
    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    query = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def stable_hash(*parts: str) -> str:
    content = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(content).hexdigest()
