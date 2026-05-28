import uuid
from unittest.mock import patch

from app.db import Instrument, SessionLocal, Version, init_db
from app.ingest.federal_register import ingest_executive_order


def test_fr_ingest_creates_new_version_when_text_differs():
    init_db()
    db = SessionLocal()
    try:
        unique = uuid.uuid4().hex[:8]
        inst = Instrument(
            slug=f"test-fr-ingest-{unique}",
            title="Test EO",
            instrument_type="executive_order",
            policy_tags="test",
            source_ref="EO 14024",
        )
        db.add(inst)
        db.commit()

        mock_text = f"EXECUTIVE ORDER 14024\nUnique API body {unique}.\nSec. 1. Block property."
        with patch("app.ingest.federal_register.fetch_document_text", return_value=(mock_text, "https://example.com/doc")):
            new_count, deduped, _ = ingest_executive_order(db, inst)
        assert new_count == 1
        assert deduped == 0
        assert db.query(Version).filter(Version.instrument_id == inst.id).count() >= 1

        with patch("app.ingest.federal_register.fetch_document_text", return_value=(mock_text, "https://example.com/doc")):
            new_count2, deduped2, _ = ingest_executive_order(db, inst)
        assert new_count2 == 0
        assert deduped2 == 1
    finally:
        db.close()
