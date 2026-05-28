from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.db import Instrument, Version, VersionSource
from app.ingest.types import VersionCreateResult
from app.normalize import content_hash, normalize_text


def create_manual_version(
    db: Session,
    instrument: Instrument,
    raw_text: str,
    version_label: str,
    effective_date: date | None = None,
    source_url: str = "",
    source_type: str = "manual",
) -> VersionCreateResult:
    normalized = normalize_text(raw_text)
    if not normalized:
        return VersionCreateResult(None, False)

    digest = content_hash(normalized)
    existing = (
        db.query(Version)
        .filter(Version.instrument_id == instrument.id, Version.content_hash == digest)
        .first()
    )
    if existing:
        return VersionCreateResult(existing, False)

    version = Version(
        instrument_id=instrument.id,
        version_label=version_label,
        effective_date=effective_date,
        normalized_text=normalized,
        content_hash=digest,
        fetch_status="manual",
    )
    db.add(version)
    db.flush()

    db.add(
        VersionSource(
            version_id=version.id,
            source_url=source_url or f"manual://{instrument.slug}/{version_label}",
            source_type=source_type,
            retrieved_at=datetime.utcnow(),
        )
    )
    instrument.last_fetch_at = datetime.utcnow()
    db.commit()
    db.refresh(version)
    return VersionCreateResult(version, True)
