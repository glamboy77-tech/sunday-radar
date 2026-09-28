from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape

from sunday_radar.domain import WeeklyBrief

DOMAIN_LABELS = {
    "stocks": "주식",
    "fx": "환율",
    "rates": "금리",
    "crypto": "코인",
    "real_estate": "부동산",
    "prices": "물가",
    "jobs": "일자리",
    "daily_life": "생활",
}

CERTAINTY_LABELS = {"high": "높음", "medium": "중간", "low": "낮음"}

CHAPTER_KICKERS = ("첫 번째 장면", "두 번째 장면", "마지막 장면")


def _transitions(brief: WeeklyBrief) -> list[str]:
    transitions: list[str] = []
    for current, following in zip(brief.issues, brief.issues[1:], strict=False):
        current_domains = current.entities.market_domains
        following_domains = following.entities.market_domains
        shared = next((item for item in current_domains if item in following_domains), None)
        if shared:
            subject = DOMAIN_LABELS[shared]
            transitions.append(
                f"이 흐름은 {subject}에서 멈추지 않습니다. 이제 시선을 "
                f"「{following.title}」로 옮겨보겠습니다."
            )
        else:
            transitions.append(
                f"한편 시장의 시선은 또 다른 장면으로 이동합니다. 다음은 "
                f"「{following.title}」입니다."
            )
    return transitions


def content_hash(brief: WeeklyBrief) -> str:
    payload = brief.model_dump(mode="json", exclude={"generated_at"})
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def render_site(brief: WeeklyBrief, output_dir: Path, template_dir: Path) -> Path:
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    issue_rel = Path("issues") / brief.week_ending.isoformat() / "index.html"
    issue_path = output_dir / issue_rel
    issue_path.parent.mkdir(parents=True, exist_ok=True)
    assets = output_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    context = {
        "brief": brief,
        "issue_path": issue_rel.as_posix(),
        "domain_labels": DOMAIN_LABELS,
        "certainty_labels": CERTAINTY_LABELS,
        "chapter_kickers": CHAPTER_KICKERS,
        "transitions": _transitions(brief),
    }
    html = env.get_template("issue.html.j2").render(**context)
    issue_path.write_text(html, encoding="utf-8")
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    shutil.copyfile(template_dir / "style.css", assets / "style.css")
    render_archive(output_dir)
    return issue_path


def render_archive(output_dir: Path) -> None:
    entries = sorted(
        (path.parent.name for path in (output_dir / "issues").glob("*/index.html")), reverse=True
    )
    links = "\n".join(
        f'<li><a href="issues/{entry}/">{entry} Sunday Radar</a></li>' for entry in entries
    )
    html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sunday Radar Archive</title>
<link rel="stylesheet" href="assets/style.css"></head><body><main class="shell">
<h1>Sunday Radar Archive</h1><ul class="archive">{links}</ul><a href="./">최신판</a>
</main></body></html>"""
    (output_dir / "archive.html").write_text(html, encoding="utf-8")


def check_html(root: Path) -> list[str]:
    errors: list[str] = []
    for path in sorted(root.rglob("*.html")):
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        if soup.html is None or soup.html.get("lang") != "ko":
            errors.append(f"{path}: missing lang=ko")
        if len(soup.find_all("h1")) != 1:
            errors.append(f"{path}: expected exactly one h1")
        if soup.find("meta", attrs={"name": "viewport"}) is None:
            errors.append(f"{path}: missing viewport")
        for anchor in soup.find_all("a"):
            href = str(anchor.get("href", ""))
            if href.lower().startswith(("javascript:", "data:")):
                errors.append(f"{path}: unsafe link {href}")
    return errors
