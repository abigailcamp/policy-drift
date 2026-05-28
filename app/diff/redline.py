import difflib
import html
import json
import re
from dataclasses import dataclass

from app.normalize import split_sections


@dataclass
class DiffStats:
    lines_added: int
    lines_removed: int
    lines_unchanged: int
    percent_changed: float

    def to_json(self) -> str:
        return json.dumps(
            {
                "lines_added": self.lines_added,
                "lines_removed": self.lines_removed,
                "lines_unchanged": self.lines_unchanged,
                "percent_changed": round(self.percent_changed, 2),
            }
        )


def compute_diff(old_text: str, new_text: str, mode: str = "unified") -> tuple[str, DiffStats]:
    old_lines = old_text.splitlines() if old_text else []
    new_lines = new_text.splitlines() if new_text else []

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    stats = DiffStats(lines_added=0, lines_removed=0, lines_unchanged=0, percent_changed=0.0)

    if mode == "side_by_side":
        html_out = _side_by_side_html(matcher, old_lines, new_lines, stats)
    else:
        html_out = _unified_html(matcher, stats)

    total = max(len(old_lines) + len(new_lines), 1)
    changed = stats.lines_added + stats.lines_removed
    stats.percent_changed = min(100.0, (changed / total) * 100)
    return html_out, stats


def compute_section_diff(old_text: str, new_text: str, mode: str = "unified") -> tuple[str, DiffStats]:
    old_sections = {sid: body for sid, body in split_sections(old_text)}
    new_sections = {sid: body for sid, body in split_sections(new_text)}
    all_ids = list(dict.fromkeys(list(old_sections) + list(new_sections)))

    parts: list[str] = []
    total_added = total_removed = total_unchanged = 0

    for section_id in all_ids:
        old_body = old_sections.get(section_id, "")
        new_body = new_sections.get(section_id, "")
        if old_body == new_body:
            if old_body:
                parts.append(
                    f'<div class="section-block unchanged"><h3 class="section-title">{html.escape(section_id)}</h3>'
                    f'<p class="section-unchanged">No changes in this section.</p></div>'
                )
            continue

        section_html, stats = compute_diff(old_body, new_body, mode=mode)
        total_added += stats.lines_added
        total_removed += stats.lines_removed
        total_unchanged += stats.lines_unchanged
        parts.append(
            f'<div class="section-block changed"><h3 class="section-title">{html.escape(section_id)}</h3>{section_html}</div>'
        )

    if not parts:
        return compute_diff(old_text, new_text, mode=mode)

    combined = '<div class="section-diff">' + "".join(parts) + "</div>"
    total = max(total_added + total_removed + total_unchanged, 1)
    percent = min(100.0, ((total_added + total_removed) / total) * 100)
    stats = DiffStats(
        lines_added=total_added,
        lines_removed=total_removed,
        lines_unchanged=total_unchanged,
        percent_changed=percent,
    )
    return combined, stats


def _unified_html(matcher: difflib.SequenceMatcher, stats: DiffStats) -> str:
    rows: list[str] = ['<div class="diff-unified">']
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in matcher.a[i1:i2]:
                rows.append(_line_row("equal", line))
                stats.lines_unchanged += 1
        elif tag == "delete":
            for line in matcher.a[i1:i2]:
                rows.append(_line_row("delete", line))
                stats.lines_removed += 1
        elif tag == "insert":
            for line in matcher.b[j1:j2]:
                rows.append(_line_row("insert", line))
                stats.lines_added += 1
        elif tag == "replace":
            for line in matcher.a[i1:i2]:
                rows.append(_line_row("delete", line))
                stats.lines_removed += 1
            for line in matcher.b[j1:j2]:
                rows.append(_line_row("insert", line))
                stats.lines_added += 1
    rows.append("</div>")
    return "".join(rows)


def _side_by_side_html(
    matcher: difflib.SequenceMatcher,
    old_lines: list[str],
    new_lines: list[str],
    stats: DiffStats,
) -> str:
    rows = ['<div class="diff-side-by-side"><div class="diff-col old"><h4>Earlier version</h4>']
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("equal", "delete", "replace"):
            for line in old_lines[i1:i2]:
                css = "equal" if tag == "equal" else "delete"
                rows.append(_line_row(css, line, col="old"))
                if tag == "equal":
                    stats.lines_unchanged += 1
                else:
                    stats.lines_removed += 1
    rows.append('</div><div class="diff-col new"><h4>Later version</h4>')
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("equal", "insert", "replace"):
            for line in new_lines[j1:j2]:
                css = "equal" if tag == "equal" else "insert"
                rows.append(_line_row(css, line, col="new"))
                if tag == "insert":
                    stats.lines_added += 1
    rows.append("</div></div>")
    return "".join(rows)


def _line_row(css: str, line: str, col: str = "") -> str:
    escaped = html.escape(line) or "&nbsp;"
    col_class = f" {col}" if col else ""
    tag = {"delete": "del", "insert": "ins"}.get(css, "span")
    if tag == "span":
        return f'<div class="diff-line equal{col_class}"><span>{escaped}</span></div>\n'
    return f'<div class="diff-line {css}{col_class}"><{tag}>{escaped}</{tag}></div>\n'


def export_pair_markdown(
    instrument_title: str,
    from_label: str,
    to_label: str,
    old_text: str,
    new_text: str,
    note_summary: str = "",
    note_implications: str = "",
    note_tags: str = "",
    note_caveats: str = "",
) -> str:
    md_diff = "\n".join(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile=from_label,
            tofile=to_label,
            lineterm="",
        )
    )
    sections = [
        f"# Policy Diff Report: {instrument_title}",
        "",
        f"**From:** {from_label}  ",
        f"**To:** {to_label}  ",
        "",
    ]
    if note_summary or note_implications:
        sections.extend(["## Analyst Note", ""])
        if note_summary:
            sections.extend([note_summary, ""])
        if note_implications:
            sections.extend(["### Policy Implications", "", note_implications, ""])
        if note_tags:
            sections.extend([f"**Tags:** {note_tags}", ""])
        if note_caveats:
            sections.extend([f"**Caveats:** {note_caveats}", ""])
    sections.extend(["## Unified Diff", "", "```diff", md_diff or "(no differences)", "```", ""])
    return "\n".join(sections)
