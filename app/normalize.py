import hashlib
import re
from html import unescape

import html2text
from bs4 import BeautifulSoup


def normalize_text(raw: str) -> str:
    """Normalize document text for consistent diffing."""
    if not raw or not raw.strip():
        return ""

    text = raw.strip()
    if "<" in text and ">" in text:
        text = _html_to_text(text)

    text = unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = _strip_page_artifacts(text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.body_width = 0
    return converter.handle(str(soup))


def _strip_page_artifacts(text: str) -> str:
    text = re.sub(r"(?m)^\s*Page \d+ of \d+\s*$", "", text)
    text = re.sub(r"(?m)^\s*\[\s*Page \d+\s*\]\s*$", "", text)
    return text


def content_hash(text: str) -> str:
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def split_sections(text: str) -> list[tuple[str, str]]:
    """Split statute-style text into (section_id, body) chunks."""
    pattern = re.compile(r"(?m)^(SEC\.|Sec\.|SECTION)\s+(\d+[A-Za-z0-9.-]*)", re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if not matches:
        return [("full", text)]

    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_id = f"{match.group(1)} {match.group(2)}".strip()
        body = text[start:end].strip()
        sections.append((section_id, body))
    return sections
