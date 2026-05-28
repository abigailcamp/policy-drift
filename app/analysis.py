from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import markdown2


@dataclass(frozen=True)
class AnalysisPost:
    slug: str
    title: str
    published: date
    author: str
    html: str


def _parse_frontmatter(md: str) -> tuple[dict[str, str], str]:
    md = md.lstrip("\ufeff")
    if not md.startswith("---"):
        return {}, md

    parts = md.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, md

    header = parts[0].splitlines()[1:]
    body = parts[1]
    meta: dict[str, str] = {}
    for line in header:
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip().lower()] = v.strip()
    return meta, body


def load_posts(analysis_dir: Path) -> list[AnalysisPost]:
    posts: list[AnalysisPost] = []
    for p in sorted(analysis_dir.glob("*.md")):
        slug = p.stem
        raw = p.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        title = meta.get("title", slug.replace("-", " ").title())
        author = meta.get("author", "")
        published_str = meta.get("date", "")
        published = date.fromisoformat(published_str) if published_str else date.today()
        html = markdown2.markdown(body, extras=["fenced-code-blocks", "tables", "strike", "footnotes"])
        posts.append(AnalysisPost(slug=slug, title=title, published=published, author=author, html=html))

    posts.sort(key=lambda x: (x.published, x.slug), reverse=True)
    return posts


def get_post(analysis_dir: Path, slug: str) -> AnalysisPost | None:
    for post in load_posts(analysis_dir):
        if post.slug == slug:
            return post
    return None

