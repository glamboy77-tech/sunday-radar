from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape

from sunday_radar.domain import WeeklyBrief


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
    context = {"brief": brief, "issue_path": issue_rel.as_posix()}
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
