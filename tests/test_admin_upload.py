from fastapi.testclient import TestClient

from app.config import TRACKED_SLUGS
from app.db import Instrument, SessionLocal, init_db
from app.main import app


def _auth():
    # Admin auth uses HTTP Basic: username 'admin' and password in ADMIN_PASSWORD.
    return ("admin", "test-admin-password")


def _seed_instrument(slug: str) -> None:
    db = SessionLocal()
    try:
        inst = db.query(Instrument).filter(Instrument.slug == slug).first()
        if not inst:
            db.add(
                Instrument(
                    slug=slug,
                    title=f"Seed {slug}",
                    instrument_type="executive_order",
                    source_ref=slug,
                )
            )
            db.commit()
    finally:
        db.close()


def test_admin_upload_get_ok() -> None:
    init_db()
    client = TestClient(app)
    resp = client.get("/admin/upload", auth=_auth())
    assert resp.status_code == 200
    assert "Upload a document version" in resp.text


def test_admin_upload_post_ok() -> None:
    init_db()
    slug = next(iter(TRACKED_SLUGS))
    _seed_instrument(slug)

    client = TestClient(app)
    resp = client.post(
        "/admin/upload",
        data={
            "instrument_slug": slug,
            "version_label": "Seed version",
            "effective_date": "2026-01-02",
            "source_url": "https://example.com/source",
            "raw_text": "By the authority vested in me...\nSection 1. Stuff",
        },
        auth=_auth(),
    )
    assert resp.status_code == 200
    assert "Saved version" in resp.text or "already exists" in resp.text

