import uuid
from unittest.mock import patch

from app.db import Instrument, SessionLocal, Version, init_db
from app.ingest.ofac_sdn import ingest_ofac_sdn, ingest_ofac_sdn_archive


def test_ofac_archive_ingest_creates_distinct_version():
    init_db()
    db = SessionLocal()
    try:
        unique = uuid.uuid4().hex[:8]
        inst = Instrument(
            slug=f"test-ofac-{unique}",
            title="Test OFAC SDN",
            instrument_type="ofac_sdn",
            policy_tags="test",
            source_ref="OFAC SDN",
        )
        db.add(inst)
        db.commit()

        archive_body = f"36,\"TEST ENTITY {unique}\",-0- ,\"CUBA\",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- \n"
        current_body = f"36,\"OTHER ENTITY {unique}\",-0- ,\"IRAN\",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- \n"

        with patch("app.ingest.ofac_sdn._load_archive_snapshot", return_value=(archive_body, "seed://test.csv")):
            new_count, deduped, err = ingest_ofac_sdn_archive(db, inst)
        assert err is None
        assert new_count == 1
        assert deduped == 0

        with patch("app.ingest.ofac_sdn.fetch_sdn_snapshot", return_value=(current_body, "https://example.com/sdn.csv")):
            new_count2, deduped2, err2 = ingest_ofac_sdn(db, inst)
        assert err2 is None
        assert new_count2 == 1
        assert deduped2 == 0
        assert db.query(Version).filter(Version.instrument_id == inst.id).count() == 2
    finally:
        db.close()
