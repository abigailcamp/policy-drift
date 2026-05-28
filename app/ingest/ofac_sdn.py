"""Fetch the OFAC SDN List (snapshot) for diffing over time.

We treat each fetched SDN list export as a "version" of a single instrument.
When OFAC publishes additions/removals, the file content changes and the next
fetch creates a new version, enabling real diffs.

OFAC's Sanctions List Service only serves the *current* full SDN.CSV; publication
IDs do not return historical full files. For an immediate second snapshot, use
``ingest_ofac_sdn_archive`` (Internet Archive copies of treasury.gov downloads).
"""

from __future__ import annotations

from datetime import date, datetime

import httpx
from sqlalchemy.orm import Session

from app.db import Instrument
from app.ingest.manual import create_manual_version

SLS_BASE = "https://sanctionslistservice.ofac.treas.gov"

SDN_EXPORT_URLS: list[str] = [
    f"{SLS_BASE}/api/download/SDN.CSV",
    f"{SLS_BASE}/api/download/SDN.XML",
    f"{SLS_BASE}/api/PublicationPreview/exports/SDN.CSV",
    f"{SLS_BASE}/api/PublicationPreview/exports/SDN.XML",
    "https://sanctionslist.ofac.treas.gov/",
]

# Prior full-list snapshots (not available from SLS). Ordered oldest → newest.
OFAC_SDN_ARCHIVE_SNAPSHOTS: list[dict[str, str]] = [
    {
        "source_url": (
            "https://web.archive.org/web/20260520120000/"
            "https://www.treasury.gov/ofac/downloads/sdn.csv"
        ),
        "version_label": "OFAC SDN snapshot — 2026-05-20 (Internet Archive)",
        "effective_date": "2026-05-20",
    },
]

_HTTP_HEADERS = {
    "Accept": "*/*",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://sanctionslist.ofac.treas.gov/",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_bytes(url: str, *, timeout: float = 120.0) -> bytes:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url, headers=_HTTP_HEADERS)
        if resp.status_code != 200:
            raise ValueError(f"{url} returned {resp.status_code}")
        if not resp.content or len(resp.content) < 1000:
            raise ValueError(f"{url} returned empty or truncated body")
        return resp.content


def _fetch_text(url: str) -> str:
    return _fetch_bytes(url).decode("utf-8", errors="replace")


def fetch_sdn_snapshot() -> tuple[str, str]:
    """Return (raw_text, source_url)."""
    last_err: Exception | None = None
    for url in SDN_EXPORT_URLS:
        try:
            return _fetch_text(url), url
        except Exception as exc:
            last_err = exc
            continue
    raise ValueError(str(last_err) if last_err else "Unable to download SDN export")


def ingest_ofac_sdn(db: Session, instrument: Instrument) -> tuple[int, int, str | None]:
    """Returns (new_versions, unchanged_versions, error_message)."""
    try:
        raw, source_url = fetch_sdn_snapshot()
        today = date.today()
        label = f"OFAC SDN snapshot — {today.isoformat()}"
        result = create_manual_version(
            db,
            instrument,
            raw_text=raw,
            version_label=label,
            effective_date=today,
            source_url=source_url,
            source_type="ofac_sdn",
        )
        new_count = 1 if result.version and result.created else 0
        deduped = 1 if result.version and not result.created else 0
        if result.version and result.created:
            result.version.fetch_status = "ok"
            db.commit()

        instrument.last_fetch_at = datetime.utcnow()
        instrument.last_fetch_status = "ok"
        instrument.last_fetch_message = f"{new_count} new, {deduped} unchanged"
        db.commit()
        return new_count, deduped, None
    except Exception as exc:
        instrument.last_fetch_at = datetime.utcnow()
        instrument.last_fetch_status = "failed"
        instrument.last_fetch_message = str(exc)[:500]
        db.commit()
        return 0, 0, str(exc)


def ingest_ofac_sdn_archive(db: Session, instrument: Instrument) -> tuple[int, int, str | None]:
    """Ingest configured archive snapshots (for a second full-list version)."""
    new_count = 0
    deduped_count = 0
    snap_errors: list[str] = []

    for snap in OFAC_SDN_ARCHIVE_SNAPSHOTS:
        try:
            raw = _fetch_text(snap["source_url"])
            eff = None
            if snap.get("effective_date"):
                eff = date.fromisoformat(snap["effective_date"])
            result = create_manual_version(
                db,
                instrument,
                raw_text=raw,
                version_label=snap["version_label"],
                effective_date=eff,
                source_url=snap["source_url"],
                source_type="ofac_sdn_archive",
            )
            if not result.version:
                snap_errors.append(f"{snap.get('effective_date', '?')}: empty after normalization")
                continue
            if result.created:
                result.version.fetch_status = "ok"
                db.commit()
                new_count += 1
            else:
                deduped_count += 1
        except Exception as exc:
            snap_errors.append(f"{snap.get('effective_date', '?')}: {exc}")

    instrument.last_fetch_at = datetime.utcnow()
    if snap_errors and new_count == 0 and deduped_count == 0:
        instrument.last_fetch_status = "failed"
        instrument.last_fetch_message = "; ".join(snap_errors)[:500]
        db.commit()
        return 0, 0, instrument.last_fetch_message

    instrument.last_fetch_status = "ok"
    parts = [f"{new_count} new", f"{deduped_count} unchanged"]
    if snap_errors:
        parts.append(f"errors: {'; '.join(snap_errors)[:200]}")
    instrument.last_fetch_message = ", ".join(parts)
    db.commit()
    err = "; ".join(snap_errors) if snap_errors else None
    return new_count, deduped_count, err


def fetch_ofac_sdn(db: Session) -> str:
    inst = db.query(Instrument).filter(Instrument.slug == "ofac-sdn").first()
    if not inst:
        return "instrument not found"
    new_count, deduped, err = ingest_ofac_sdn(db, inst)
    if inst.last_fetch_status == "failed":
        return f"failed: {inst.last_fetch_message or err}"
    return f"ok ({new_count} new, {deduped} unchanged)"


def fetch_ofac_sdn_archive(db: Session) -> str:
    inst = db.query(Instrument).filter(Instrument.slug == "ofac-sdn").first()
    if not inst:
        return "instrument not found"
    new_count, deduped, err = ingest_ofac_sdn_archive(db, inst)
    if inst.last_fetch_status == "failed":
        return f"failed: {inst.last_fetch_message or err}"
    return f"ok ({new_count} new, {deduped} unchanged)"
