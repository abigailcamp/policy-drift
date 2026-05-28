from datetime import date

from app.db import Instrument, SessionLocal, init_db
from app.ingest.manual import create_manual_version


def test_manual_upload_dedup():
    init_db()
    db = SessionLocal()
    try:
        import uuid

        inst = Instrument(
            slug=f"test-dedup-{uuid.uuid4().hex}",
            title="Test",
            instrument_type="executive_order",
            policy_tags="test",
            source_ref="TEST",
        )
        db.add(inst)
        db.commit()
        r1 = create_manual_version(db, inst, "Same text.", "v1", date(2024, 1, 1))
        r2 = create_manual_version(db, inst, "Same text.", "v2", date(2024, 2, 1))
        assert r1.version is not None
        assert r2.version is not None
        assert r1.created is True
        assert r2.created is False
        assert r1.version.id == r2.version.id
    finally:
        db.close()
