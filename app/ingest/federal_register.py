"""Fetch executive order text from the Federal Register API."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.config import FEDERAL_REGISTER_API_KEY, TRACKED_SLUGS
from app.db import Instrument, Version
from app.ingest.manual import create_manual_version
from app.normalize import normalize_text

FR_BASE = "https://www.federalregister.gov/api/v1"

EO_DOCUMENTS: dict[str, list[dict[str, str]]] = {
    "14024": [
        {
            "document_number": "2022-03759",
            "version_label": "FR API — 2022-02-21 Original signing",
            "effective_date": "2022-02-21",
        },
    ],
    "14066": [
        {
            "document_number": "2022-04347",
            "version_label": "FR API — 2022-03-08 Energy imports ban",
            "effective_date": "2022-03-08",
        },
    ],
    "14068": [
        {
            "document_number": "2022-04348",
            "version_label": "FR API — 2022-03-08 Import restrictions",
            "effective_date": "2022-03-08",
        },
    ],
}


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if FEDERAL_REGISTER_API_KEY:
        headers["X-Api-Key"] = FEDERAL_REGISTER_API_KEY
    return headers


def _xml_to_text(xml_content: str) -> str:
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return ""
    parts = [part.strip() for part in root.itertext() if part and part.strip()]
    return "\n".join(parts)


def fetch_document_text(document_number: str) -> tuple[str, str]:
    """Return (full_text, source_url)."""
    url = f"{FR_BASE}/documents/{document_number}.json"
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(url, headers=_headers())
        resp.raise_for_status()
        data = resp.json()

    source_url = data.get("html_url") or data.get("pdf_url") or url
    text = data.get("full_text") or data.get("body") or ""

    if not text:
        xml_url = data.get("full_text_xml_url")
        if xml_url:
            with httpx.Client(timeout=60.0) as client:
                xml_resp = client.get(xml_url, headers=_headers())
                if xml_resp.status_code == 200:
                    text = _xml_to_text(xml_resp.text)

    if not text:
        body_url = data.get("body_html_url") or data.get("html_url")
        if body_url:
            with httpx.Client(timeout=60.0) as client:
                html_resp = client.get(body_url, headers=_headers())
                if html_resp.status_code == 200:
                    text = normalize_text(html_resp.text)

    if not text:
        abstract = data.get("abstract", "")
        title = data.get("title", document_number)
        text = f"{title}\n\n{abstract}\n\n[Full text not available via API — upload manually from Federal Register.]"

    return text, source_url


def ingest_executive_order(db: Session, instrument: Instrument) -> tuple[int, int, str | None]:
    """Returns (new_versions, deduped_versions, error_message)."""
    eo_number = instrument.source_ref.replace("EO", "").strip()
    snapshots = EO_DOCUMENTS.get(eo_number, [])
    if not snapshots:
        instrument.last_fetch_status = "failed"
        instrument.last_fetch_message = "No Federal Register document numbers configured"
        instrument.last_fetch_at = datetime.utcnow()
        db.commit()
        return 0, 0, instrument.last_fetch_message

    new_count = 0
    deduped_count = 0
    last_error: str | None = None

    for snap in snapshots:
        try:
            raw, source_url = fetch_document_text(snap["document_number"])
            from datetime import date as date_cls

            eff = date_cls.fromisoformat(snap["effective_date"]) if snap.get("effective_date") else None
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


def fetch_all_executive_orders(db: Session) -> dict[str, str]:
    results: dict[str, str] = {}
    instruments = (
        db.query(Instrument)
        .filter(
            Instrument.instrument_type == "executive_order",
            Instrument.slug.in_(TRACKED_SLUGS),
        )
        .order_by(Instrument.slug)
        .all()
    )
    for inst in instruments:
        eo_number = inst.source_ref.replace("EO", "").strip()
        if eo_number not in EO_DOCUMENTS:
            results[inst.slug] = "skipped"
            continue
        try:
            new_count, deduped, err = ingest_executive_order(db, inst)
            if inst.last_fetch_status == "failed":
                results[inst.slug] = f"failed: {inst.last_fetch_message or err}"
            else:
                results[inst.slug] = f"ok ({new_count} new, {deduped} unchanged)"
        except Exception as exc:
            inst.last_fetch_status = "failed"
            inst.last_fetch_message = str(exc)[:500]
            inst.last_fetch_at = datetime.utcnow()
            db.commit()
            results[inst.slug] = f"failed: {exc}"
    return results
