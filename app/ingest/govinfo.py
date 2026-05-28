"""Fetch public law text from GovInfo."""

from __future__ import annotations

from datetime import date, datetime

import httpx
from sqlalchemy.orm import Session

from app.config import GOVINFO_API_KEY, PROJECT_ROOT
from app.db import Instrument, Version
from app.ingest.manual import create_manual_version

GOVINFO_BASE = "https://api.govinfo.gov"

LAW_PACKAGES: dict[str, dict[str, str]] = {
    "PLAW-118publ50": {
        "version_label": "GovInfo API — PL 118-50 (Ukraine supplemental)",
        "effective_date": "2024-04-24",
        "title": "Public Law 118-50",
    },
    "PLAW-118publ68": {
        "version_label": "GovInfo API — PL 118-68 (REPO Act)",
        "effective_date": "2024-04-24",
        "title": "Public Law 118-68 REPO Act",
    },
}

INSTRUMENT_PACKAGES: dict[str, str] = {
    "ukraine-supplemental-118-50": "PLAW-118publ50",
    "repo-act-118-68": "PLAW-118publ68",
}


def _api_headers() -> dict[str, str]:
    if not GOVINFO_API_KEY:
        return {}
    return {"X-Api-Key": GOVINFO_API_KEY}


def fetch_package_text(package_id: str) -> tuple[str, str]:
    if not GOVINFO_API_KEY:
        raise ValueError("GOVINFO_API_KEY not set — use manual upload or add key to .env")

    summary_url = f"{GOVINFO_BASE}/packages/{package_id}/summary"
    with httpx.Client(timeout=90.0) as client:
        summary_resp = client.get(summary_url, headers=_api_headers())
        summary_resp.raise_for_status()
        summary = summary_resp.json()

        source_url = summary.get("packageLink") or f"https://www.govinfo.gov/app/details/{package_id}"
        download = summary.get("download") or {}
        html_link = download.get("htmLink") or download.get("pdfLink") or summary.get("htmlLink")

        text = ""
        if html_link:
            doc_resp = client.get(html_link, headers=_api_headers(), follow_redirects=True)
            if doc_resp.status_code == 200:
                text = doc_resp.text

        if not text:
            title = summary.get("title", package_id)
            date_issued = summary.get("dateIssued", "")
            text = (
                f"{title}\nIssued: {date_issued}\n\n"
                "[Full text could not be downloaded automatically. "
                "Paste from https://www.govinfo.gov/ or upload via /admin/upload.]"
            )

    return text, source_url


def ingest_public_law(db: Session, instrument: Instrument, package_id: str) -> tuple[int, int, str | None]:
    try:
        raw, source_url = fetch_package_text(package_id)
        meta = LAW_PACKAGES.get(package_id, {})
        eff = date.fromisoformat(meta["effective_date"]) if meta.get("effective_date") else None

        result = create_manual_version(
            db,
            instrument,
            raw_text=raw,
            version_label=meta.get("version_label", f"GovInfo {package_id}"),
            effective_date=eff,
            source_url=source_url,
            source_type="govinfo",
        )
        new_count = 1 if result.version and result.created else 0
        deduped = 1 if result.version and not result.created else 0
        if result.version and result.created:
            result.version.fetch_status = "ok"
            db.commit()
            raw_path = PROJECT_ROOT / "data" / "raw" / f"{package_id}.txt"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(result.version.normalized_text[:50000], encoding="utf-8")

        instrument.last_fetch_at = datetime.utcnow()
        instrument.last_fetch_status = "ok"
        instrument.last_fetch_message = f"{new_count} new, {deduped} unchanged"
        db.commit()
        return new_count, deduped, None
    except Exception as exc:
        instrument.last_fetch_status = "failed"
        instrument.last_fetch_message = str(exc)[:500]
        instrument.last_fetch_at = datetime.utcnow()
        db.commit()
        return 0, 0, str(exc)


def fetch_all_public_laws(db: Session) -> dict[str, str]:
    results: dict[str, str] = {}
    if not GOVINFO_API_KEY:
        for slug in INSTRUMENT_PACKAGES:
            inst = db.query(Instrument).filter(Instrument.slug == slug).first()
            if inst:
                inst.last_fetch_status = "needs_key"
                inst.last_fetch_message = (
                    "Auto-fetch needs a free GovInfo API key in .env — or use Upload text (works now)."
                )
                inst.last_fetch_at = datetime.utcnow()
        db.commit()
        return {slug: "failed: GOVINFO_API_KEY not set" for slug in INSTRUMENT_PACKAGES}

    for slug, package_id in INSTRUMENT_PACKAGES.items():
        inst = db.query(Instrument).filter(Instrument.slug == slug).first()
        if not inst:
            results[slug] = "instrument not found"
            continue
        new_count, deduped, err = ingest_public_law(db, inst, package_id)
        if inst.last_fetch_status == "failed":
            results[slug] = f"failed: {inst.last_fetch_message or err}"
        else:
            results[slug] = f"ok ({new_count} new, {deduped} unchanged)"
    return results
