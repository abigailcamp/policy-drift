"""Business logic for version pairs and diffs."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import AnalystNote, Instrument, Version, VersionPair
from app.diff.redline import DiffStats, compute_diff, compute_section_diff


def get_or_create_pair(db: Session, from_id: int, to_id: int, section_aware: bool = False, mode: str = "unified") -> VersionPair:
    pair = (
        db.query(VersionPair)
        .filter(VersionPair.from_version_id == from_id, VersionPair.to_version_id == to_id)
        .first()
    )
    if pair and pair.diff_html_cached and pair.diff_mode == mode:
        return pair

    from_v = db.query(Version).filter(Version.id == from_id).first()
    to_v = db.query(Version).filter(Version.id == to_id).first()
    if not from_v or not to_v:
        raise ValueError("Version not found")

    use_sections = section_aware or (
        from_v.instrument.instrument_type in ("public_law", "statute")
        and len(from_v.normalized_text) > 3000
    )

    if use_sections:
        html_out, stats = compute_section_diff(from_v.normalized_text, to_v.normalized_text, mode=mode)
    else:
        html_out, stats = compute_diff(from_v.normalized_text, to_v.normalized_text, mode=mode)

    if not pair:
        pair = VersionPair(from_version_id=from_id, to_version_id=to_id)
        db.add(pair)

    pair.diff_html_cached = html_out
    pair.diff_stats_json = stats.to_json()
    pair.diff_mode = mode
    db.commit()
    db.refresh(pair)
    return pair


def parse_stats(pair: VersionPair) -> DiffStats | None:
    if not pair.diff_stats_json:
        return None
    import json
    from app.diff.redline import DiffStats

    data = json.loads(pair.diff_stats_json)
    return DiffStats(
        lines_added=data["lines_added"],
        lines_removed=data["lines_removed"],
        lines_unchanged=data["lines_unchanged"],
        percent_changed=data["percent_changed"],
    )


def get_instrument_by_slug(db: Session, slug: str) -> Instrument | None:
    return db.query(Instrument).filter(Instrument.slug == slug).first()
