import uuid

from fastapi.testclient import TestClient

from app.db import Instrument, SessionLocal, Version, VersionPair, init_db
from app.main import app
from app.services import get_or_create_pair


def _auth():
    return ("admin", "test-admin-password")


def _seed_pair() -> int:
    slug = f"test-note-auth-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        inst = Instrument(
            slug=slug,
            title="Test instrument",
            instrument_type="executive_order",
            source_ref="Test",
        )
        db.add(inst)
        db.flush()
        v1 = Version(
            instrument_id=inst.id,
            version_label="v1",
            normalized_text="Section 1. Alpha.",
            content_hash="hash1",
        )
        v2 = Version(
            instrument_id=inst.id,
            version_label="v2",
            normalized_text="Section 1. Beta.",
            content_hash="hash2",
        )
        db.add_all([v1, v2])
        db.flush()
        pair = get_or_create_pair(db, v1.id, v2.id)
        db.commit()
        return pair.id
    finally:
        db.close()


def test_analyst_note_edit_requires_admin() -> None:
    init_db()
    pair_id = _seed_pair()
    client = TestClient(app)

    assert client.get(f"/notes/{pair_id}/edit").status_code == 401
    assert (
        client.post(
            f"/notes/{pair_id}/edit",
            data={"summary": "Public edit attempt", "policy_implications": "", "tags": "", "caveats": ""},
        ).status_code
        == 401
    )

    resp = client.get(f"/notes/{pair_id}/edit", auth=_auth())
    assert resp.status_code == 200
    assert "Analyst note" in resp.text

    save = client.post(
        f"/notes/{pair_id}/edit",
        data={"summary": "Admin summary", "policy_implications": "Impact", "tags": "test", "caveats": ""},
        auth=_auth(),
        follow_redirects=False,
    )
    assert save.status_code == 303


def test_diff_hides_note_button_for_public() -> None:
    init_db()
    pair_id = _seed_pair()
    db = SessionLocal()
    try:
        pair = db.query(VersionPair).filter(VersionPair.id == pair_id).first()
        from_id, to_id = pair.from_version_id, pair.to_version_id
    finally:
        db.close()

    client = TestClient(app)
    public = client.get(f"/diff?from={from_id}&to={to_id}")
    assert public.status_code == 200
    assert "Add analyst note" not in public.text
    assert "Edit note" not in public.text

    admin = client.get(f"/diff?from={from_id}&to={to_id}", auth=_auth())
    assert admin.status_code == 200
    assert "Add analyst note" in admin.text or "Edit note" in admin.text
