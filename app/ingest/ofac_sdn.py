"""Fetch the OFAC SDN List (snapshot) for diffing over time.

We treat each fetched SDN list export as a "version" of a single instrument.
When OFAC publishes additions/removals, the file content changes and the next
fetch creates a new version, enabling real diffs.
"""

from __future__ import annotations

from datetime import date, datetime

import httpx
from sqlalchemy.orm import Session

from app.db import Instrument
from app.ingest.manual import create_manual_version


SDN_EXPORT_URLS: list[str] = [
    # Sanctions List Service exports (preferred).
    "https://sanctionslistservice.ofac.treas.gov/api/download/SDN.CSV",
    "https://sanctionslistservice.ofac.treas.gov/api/download/SDN.XML",
    "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV",
    "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML",
    # Public search/download landing (fallback, not an export but better than nothing).
    "https://sanctionslist.ofac.treas.gov/",
]


def _fetch_text(url: str) -> str:
    with httpx.Client(timeout=90.0, follow_redirects=True) as client:
        resp = client.get(
            url,
            headers={
                "Accept": "*/*",
                # OFAC SLS blocks requests that omit User-Agent (see OFAC technical notice 2024-05-16).
                # Some deployments appear stricter; use a browser-like UA + referer.
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Referer": "https://sanctionslist.ofac.treas.gov/",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        if resp.status_code != 200:
            raise ValueError(f"{url} returned {resp.status_code}")
        return resp.text


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


def fetch_ofac_sdn(db: Session) -> str:
    inst = db.query(Instrument).filter(Instrument.slug == "ofac-sdn").first()
    if not inst:
        return "instrument not found"
    new_count, deduped, err = ingest_ofac_sdn(db, inst)
    if inst.last_fetch_status == "failed":
        return f"failed: {inst.last_fetch_message or err}"
    return f"ok ({new_count} new, {deduped} unchanged)"

