"""Fetch multi-document Federal Register series for one instrument (revisions over time)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import TRACKED_SLUGS
from app.db import Instrument
from app.ingest.federal_register import fetch_document_text
from app.ingest.manual import create_manual_version

# Each instrument slug maps to ordered FR publications (oldest → newest).
FR_SERIES_BY_SLUG: dict[str, list[dict[str, str]]] = {
    # EO 14024 / Directive 4 — administrative transactions license lineage
    "russia-gl-13": [
        {
            "document_number": "2022-27238",
            "version_label": "FR — 2022-12-16 GL 13C (web issuance 2022-11-21)",
            "effective_date": "2022-11-21",
        },
        {
            "document_number": "2023-05648",
            "version_label": "FR — 2023-03-21 GL 13D supersedes 13C (web 2023-02-24)",
            "effective_date": "2023-02-24",
        },
    ],
    # Directive 4 under EO 14024 — original publication vs amended text
    "directive-4-eo14024": [
        {
            "document_number": "2022-11608",
            "version_label": "FR — 2022-05-31 Directives 1A–4 (original Directive 4)",
            "effective_date": "2022-05-31",
        },
        {
            "document_number": "2023-11980",
            "version_label": "FR — 2023-06-05 Directive 4 (as amended)",
            "effective_date": "2023-06-05",
        },
    ],
}


def ingest_fr_series(db: Session, instrument: Instrument) -> tuple[int, int, str | None]:
    """Returns (new_versions, unchanged_versions, error_message)."""
    snapshots = FR_SERIES_BY_SLUG.get(instrument.slug, [])
    if not snapshots:
        instrument.last_fetch_status = "failed"
        instrument.last_fetch_message = "No Federal Register series configured"
        instrument.last_fetch_at = datetime.utcnow()
        db.commit()
        return 0, 0, instrument.last_fetch_message

    new_count = 0
    deduped_count = 0
    last_error: str | None = None

    for snap in snapshots:
        try:
            raw, source_url = fetch_document_text(snap["document_number"])
            eff = None
            if snap.get("effective_date"):
                eff = date.fromisoformat(snap["effective_date"])
            result = create_manual_version(
                db,
                instrument,
                raw_text=raw,
                version_label=snap["version_label"],
                effective_date=eff,
                source_url=source_url,
                source_type="federal_register",
            )
            if not result.version:
                last_error = "Empty text after normalization"
                continue
            if result.created:
                result.version.fetch_status = "ok"
                db.commit()
                new_count += 1
            else:
                deduped_count += 1
        except Exception as exc:
            last_error = str(exc) or exc.__class__.__name__

    instrument.last_fetch_at = datetime.utcnow()
    if last_error and new_count == 0 and deduped_count == 0:
        instrument.last_fetch_status = "failed"
        instrument.last_fetch_message = last_error[:500]
    else:
        instrument.last_fetch_status = "ok"
        instrument.last_fetch_message = f"{new_count} new, {deduped_count} unchanged"
    db.commit()
    return new_count, deduped_count, last_error


def fetch_all_fr_series(db: Session) -> dict[str, str]:
    results: dict[str, str] = {}
    for slug in FR_SERIES_BY_SLUG:
        if slug not in TRACKED_SLUGS:
            continue
        inst = db.query(Instrument).filter(Instrument.slug == slug).first()
        if not inst:
            results[slug] = "instrument not found"
            continue
        new_count, deduped, err = ingest_fr_series(db, inst)
        if inst.last_fetch_status == "failed":
            results[slug] = f"failed: {inst.last_fetch_message or err}"
        else:
            results[slug] = f"ok ({new_count} new, {deduped} unchanged)"
    return results
