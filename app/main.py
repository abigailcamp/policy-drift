from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import secrets

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import ADMIN_PASSWORD, RESEND_API_KEY, RESEND_FROM, TRACKED_SLUGS
from app.db import (
    AnalystNote,
    Instrument,
    Subscriber,
    Version,
    VersionPair,
    VersionSource,
    SessionLocal,
    get_db,
    init_db,
)
from app.diff.redline import export_pair_markdown
from app.ingest.federal_register import fetch_all_executive_orders
from app.ingest.govinfo import fetch_all_public_laws
from app.ingest.fr_series import fetch_all_fr_series
from app.ingest.ofac_sdn import fetch_ofac_sdn, fetch_ofac_sdn_archive
from app.ingest.manual import create_manual_version
from app.services import get_instrument_by_slug, get_or_create_pair, parse_stats
from app.upload_sources import UPLOAD_SOURCES
from app.template_context import site_context
from app.analysis import get_post, load_posts

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
ANALYSIS_DIR = Path(__file__).resolve().parent.parent / "analysis"

app = FastAPI(title="PolicyDrift")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals.update(site_context())

security = HTTPBasic()

def _fmt_dt(dt) -> str | None:
    if not dt:
        return None
    return dt.strftime("%B %d, %Y %H:%M").replace(" 0", " ")


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> bool:
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="ADMIN_PASSWORD not set")
    ok_user = secrets.compare_digest(credentials.username or "", "admin")
    ok_pass = secrets.compare_digest(credentials.password or "", ADMIN_PASSWORD)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True


def render(
    request: Request,
    template_name: str,
    context: dict | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Always inject site branding (PolicyDrift, logo path, author) into templates."""
    ctx = {
        # Many Jinja templates expect `request` to exist in context (FastAPI docs pattern).
        "request": request,
        **site_context(),
        "upload_sources": UPLOAD_SOURCES,
        "upload_sources_json": json.dumps(UPLOAD_SOURCES),
        **(context or {}),
    }
    return templates.TemplateResponse(request, template_name, ctx, status_code=status_code)


def _send_resend_email(*, to_email: str, subject: str, text: str) -> bool:
    """Send a plain-text email through Resend. If unconfigured, do nothing."""
    if not RESEND_API_KEY:
        return False
    try:
        import httpx

        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={"from": RESEND_FROM, "to": [to_email], "subject": subject, "text": text},
            )
            resp.raise_for_status()
        return True
    except Exception:
        return False


def _notify_subscribers_for_instrument(
    *,
    db: Session,
    instrument: Instrument,
    subject: str,
    text_template: str,
) -> tuple[int, int]:
    """Return (subscriber_count, sent_count)."""
    subs = db.query(Subscriber).filter(Subscriber.instrument_id == instrument.id).all()
    sent = 0
    for s in subs:
        text = text_template.replace("{email}", s.email)
        if _send_resend_email(to_email=s.email, subject=subject, text=text):
            sent += 1
    return len(subs), sent


class SubscribeRequest(BaseModel):
    instrument_slug: str
    email: str


@app.post("/subscribe")
def subscribe(req: SubscribeRequest, db: Session = Depends(get_db)):
    email = (req.email or "").strip().lower()
    slug = (req.instrument_slug or "").strip()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")

    inst = get_instrument_by_slug(db, slug)
    if not inst:
        raise HTTPException(status_code=404, detail="Instrument not found.")

    existing = (
        db.query(Subscriber)
        .filter(Subscriber.instrument_id == inst.id, Subscriber.email == email)
        .first()
    )
    if existing:
        return {"ok": True, "message": "You’re already subscribed."}

    db.add(Subscriber(instrument_id=inst.id, email=email))
    db.commit()
    return {"ok": True, "message": "Subscribed. You’ll get an email when it changes."}


@app.get("/unsubscribe")
def unsubscribe(instrument: str, email: str, db: Session = Depends(get_db)):
    inst = get_instrument_by_slug(db, instrument)
    if not inst:
        return RedirectResponse(url="/?unsub=0", status_code=303)
    q = (
        db.query(Subscriber)
        .filter(Subscriber.instrument_id == inst.id, Subscriber.email == email.strip().lower())
    )
    sub = q.first()
    if sub:
        db.delete(sub)
        db.commit()
    return RedirectResponse(url=f"/instruments/{inst.slug}?unsub=1", status_code=303)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    # Ensure core tracked instruments exist (fresh Postgres deploys start empty).
    db = SessionLocal()
    try:
        for slug in TRACKED_SLUGS:
            if db.query(Instrument).filter(Instrument.slug == slug).first():
                continue
            src = UPLOAD_SOURCES.get(slug, {})
            title = (src.get("title") or slug).strip()
            inst_type = (src.get("type") or "executive_order").strip()
            policy_tags = (src.get("policy_tags") or "").strip()
            db.add(
                Instrument(
                    slug=slug,
                    title=title,
                    instrument_type=inst_type,
                    policy_tags=policy_tags,
                    source_ref=title,
                    last_fetch_status="manual",
                )
            )
        db.commit()
    finally:
        db.close()
    templates.env.globals.update(site_context())
    templates.env.globals.update(
        {
            "upload_sources": UPLOAD_SOURCES,
            "upload_sources_json": json.dumps(UPLOAD_SOURCES),
        }
    )


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    instruments = (
        db.query(Instrument)
        .filter(Instrument.slug.in_(TRACKED_SLUGS))
        .order_by(Instrument.title)
        .all()
    )
    rows = []
    for inst in instruments:
        version_count = db.query(Version).filter(Version.instrument_id == inst.id).count()

        # Richer status indicator for the editorial dashboard.
        status_label = "PENDING"
        status_class = "pending"
        msg = (inst.last_fetch_message or "").lower()
        if inst.last_fetch_status == "failed":
            status_label = "MONITORING FAILED"
            status_class = "monitoring_failed"
        elif inst.last_fetch_status == "needs_key":
            status_label = "PENDING"
            status_class = "pending"
        elif inst.last_fetch_status == "ok":
            # Messages look like "X new, Y unchanged".
            new_count = 0
            try:
                new_part = msg.split("new", 1)[0].strip()
                new_count = int(new_part.split()[-1])
            except Exception:
                new_count = 0

            if new_count > 0:
                # First-ever version(s) vs amendments to an existing instrument.
                if version_count <= new_count:
                    status_label = "NEW VERSION"
                    status_class = "new_version"
                else:
                    status_label = "AMENDED"
                    status_class = "amended"
            else:
                status_label = "UNCHANGED"
                status_class = "unchanged"
        elif inst.last_fetch_status == "manual":
            status_label = "NEW VERSION"
            status_class = "new_version"

        display_message = inst.last_fetch_message
        if inst.last_fetch_status == "needs_key":
            display_message = "Manual upload available — auto-fetch requires API configuration."

        rows.append(
            {
                "instrument": inst,
                "version_count": version_count,
                "last_fetch_at": inst.last_fetch_at,
                "last_fetch_status": inst.last_fetch_status or "manual",
                "last_fetch_message": display_message,
                "status_label": status_label,
                "status_class": status_class,
            }
        )

    rows_by_slug = {r["instrument"].slug: r for r in rows}

    def _cluster_rows(slugs: list[str]) -> list[dict]:
        out: list[dict] = []
        for s in slugs:
            r = rows_by_slug.get(s)
            if r:
                out.append(r)
        return out

    clusters = [
        {
            "key": "russia_ukraine",
            "title": "Russia–Ukraine",
            "deck": "Authorities • directives • licensing",
            "rows": _cluster_rows(
                [
                    "eo-14024",
                    "directive-4-eo14024",
                    "russia-gl-13",
                    "eo-14066",
                    "eo-14068",
                    "ukraine-supplemental-118-50",
                    "repo-act-118-68",
                ]
            ),
        },
        {
            "key": "china",
            "title": "China",
            "deck": "Export controls • listings • restrictions",
            "placeholders": [
                {"title": "Export controls & licensing"},
                {"title": "Entity List additions/removals"},
                {"title": "ITAR-related changes"},
            ],
        },
        {
            "key": "iran",
            "title": "Iran",
            "deck": "Authorities • designations • shipping",
            "placeholders": [
                {"title": "Iran-related executive instruments"},
                {"title": "Program designations & changes"},
            ],
        },
        {
            "key": "general",
            "title": "General",
            "deck": "NDAA • OFAC lists • cross-cutting",
            "rows": _cluster_rows(["ofac-sdn"]),
            "placeholders": [{"title": "NDAA — key provisions tracked year over year"}],
        },
    ]
    return render(
        request,
        "dashboard.html",
        {
            "clusters": clusters,
            "instruments": rows,
            "fetched": request.query_params.get("fetched"),
            "active_nav": "dashboard",
        },
    )


@app.get("/instruments/{slug}", response_class=HTMLResponse)
def instrument_detail(request: Request, slug: str, db: Session = Depends(get_db)):
    instrument = get_instrument_by_slug(db, slug)
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")
    versions = (
        db.query(Version)
        .filter(Version.instrument_id == instrument.id)
        # Timeline should read chronologically (earliest → latest).
        .order_by(Version.effective_date.asc().nullslast(), Version.id.asc())
        .all()
    )
    return render(
        request,
        "instrument_detail.html",
        {"instrument": instrument, "versions": versions, "active_nav": "dashboard"},
    )


@app.get("/diff", response_class=HTMLResponse)
def diff_view(
    request: Request,
    from_id: int = Query(..., alias="from"),
    to_id: int = Query(..., alias="to"),
    section_aware: bool = Query(False),
    mode: str = Query("unified"),
    db: Session = Depends(get_db),
):
    if from_id == to_id:
        raise HTTPException(status_code=400, detail="Select two different versions")
    from_v = db.query(Version).filter(Version.id == from_id).first()
    to_v = db.query(Version).filter(Version.id == to_id).first()
    if not from_v or not to_v:
        raise HTTPException(status_code=404, detail="Version not found")
    if from_v.instrument_id != to_v.instrument_id:
        raise HTTPException(status_code=400, detail="Versions must belong to the same instrument")

    pair = get_or_create_pair(db, from_id, to_id, section_aware=section_aware, mode=mode)
    stats = parse_stats(pair)
    note = pair.note

    return render(
        request,
        "diff.html",
        {
            "from_version": from_v,
            "to_version": to_v,
            "instrument": from_v.instrument,
            "pair": pair,
            "diff_html": pair.diff_html_cached,
            "stats": stats,
            "note": note,
            "section_aware": section_aware,
            "mode": mode,
            "active_nav": "dashboard",
        },
    )


@app.get("/notes/{pair_id}/edit", response_class=HTMLResponse)
def note_edit(request: Request, pair_id: int, db: Session = Depends(get_db)):
    pair = db.query(VersionPair).filter(VersionPair.id == pair_id).first()
    if not pair:
        raise HTTPException(status_code=404, detail="Version pair not found")
    note = pair.note
    return render(
        request,
        "note_edit.html",
        {
            "pair": pair,
            "note": note,
            "from_version": pair.from_version,
            "to_version": pair.to_version,
            "instrument": pair.from_version.instrument,
        },
    )


@app.post("/notes/{pair_id}/edit")
def note_save(
    pair_id: int,
    summary: str = Form(""),
    policy_implications: str = Form(""),
    tags: str = Form(""),
    caveats: str = Form(""),
    db: Session = Depends(get_db),
):
    pair = db.query(VersionPair).filter(VersionPair.id == pair_id).first()
    if not pair:
        raise HTTPException(status_code=404, detail="Version pair not found")

    if pair.note:
        note = pair.note
    else:
        note = AnalystNote(version_pair_id=pair_id)
        db.add(note)

    note.summary = summary.strip()
    note.policy_implications = policy_implications.strip()
    note.tags = tags.strip()
    note.caveats = caveats.strip()
    db.commit()
    return RedirectResponse(
        url=f"/diff?from={pair.from_version_id}&to={pair.to_version_id}",
        status_code=303,
    )


def _upload_template_context(
    request: Request,
    db: Session,
    *,
    message: str | None = None,
    error: str | None = None,
) -> dict:
    instruments = (
        db.query(Instrument)
        .filter(Instrument.slug.in_(TRACKED_SLUGS))
        .order_by(Instrument.title)
        .all()
    )
    return {
        **site_context(),
        "instruments": instruments,
        "upload_sources": UPLOAD_SOURCES,
        "upload_sources_json": json.dumps(UPLOAD_SOURCES),
        "preselect_slug": request.query_params.get("instrument"),
        "message": message,
        "error": error,
        "active_nav": "upload",
    }


@app.get("/admin/upload", response_class=HTMLResponse)
def admin_upload_form(request: Request, db: Session = Depends(get_db), _: bool = Depends(require_admin)):
    return render(request, "admin_upload.html", _upload_template_context(request, db))


@app.post("/admin/upload", response_class=HTMLResponse)
def admin_upload_submit(
    request: Request,
    instrument_slug: str = Form(...),
    version_label: str = Form(...),
    effective_date: str = Form(""),
    source_url: str = Form(""),
    raw_text: str = Form(...),
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    instrument = get_instrument_by_slug(db, instrument_slug)
    if not instrument:
        return render(
            request,
            "admin_upload.html",
            _upload_template_context(request, db, error="Instrument not found"),
            status_code=400,
        )

    eff = None
    if effective_date.strip():
        try:
            eff = date.fromisoformat(effective_date.strip())
        except ValueError:
            return render(
                request,
                "admin_upload.html",
                _upload_template_context(request, db, error="Invalid date — use YYYY-MM-DD"),
                status_code=400,
            )

    before_status = instrument.last_fetch_status
    before_message = instrument.last_fetch_message

    result = create_manual_version(
        db,
        instrument,
        raw_text=raw_text,
        version_label=version_label.strip(),
        effective_date=eff,
        source_url=source_url.strip(),
    )
    if not result.version:
        return render(
            request,
            "admin_upload.html",
            _upload_template_context(request, db, error="Empty text after normalization"),
            status_code=400,
        )

    msg = (
        f"Saved version “{result.version.version_label}” (id={result.version.id}). "
        f'<a href="/instruments/{instrument.slug}">View timeline →</a>'
        if result.created
        else f"That text already exists (version id={result.version.id}) — no duplicate added."
    )

    # Notify on new versions (and any status/message change).
    if result.created or before_status != instrument.last_fetch_status or before_message != instrument.last_fetch_message:
        subject = f"PolicyDrift update: {instrument.source_ref or instrument.title}"
        text_template = (
            f"{instrument.title}\n"
            f"{instrument.source_ref}\n\n"
            f"New version: {result.version.version_label}\n\n"
            f"View timeline: {request.base_url}instruments/{instrument.slug}\n"
            f"Unsubscribe: {request.base_url}unsubscribe?instrument={instrument.slug}&email={{email}}\n"
        )
        _notify_subscribers_for_instrument(
            db=db, instrument=instrument, subject=subject, text_template=text_template
        )

    return render(request, "admin_upload.html", _upload_template_context(request, db, message=msg))


@app.post("/admin/fetch")
def admin_fetch(request: Request, db: Session = Depends(get_db), _: bool = Depends(require_admin)):
    # Capture statuses before fetch so we can alert on changes.
    before = {
        inst.id: (inst.last_fetch_status, inst.last_fetch_message)
        for inst in db.query(Instrument).filter(Instrument.slug.in_(TRACKED_SLUGS)).all()
    }
    fetch_started_at = __import__("datetime").datetime.utcnow()

    fetch_all_executive_orders(db)
    fetch_all_public_laws(db)
    fetch_all_fr_series(db)
    fetch_ofac_sdn(db)

    # Detect new versions by VersionSource timestamps since the fetch started.
    from sqlalchemy import func

    new_by_instrument = dict(
        db.query(Version.instrument_id, func.count(VersionSource.id))
        .join(Version, VersionSource.version_id == Version.id)
        .filter(Version.instrument_id.in_(before.keys()))
        .filter(VersionSource.retrieved_at >= fetch_started_at)
        .group_by(Version.instrument_id)
        .all()
    )

    instruments = db.query(Instrument).filter(Instrument.slug.in_(TRACKED_SLUGS)).all()
    for inst in instruments:
        prev_status, prev_msg = before.get(inst.id, (None, None))
        status_changed = (prev_status != inst.last_fetch_status) or (prev_msg != inst.last_fetch_message)
        new_versions = 1 if inst.id in new_by_instrument else 0

        if not (status_changed or new_versions):
            continue

        subject = f"PolicyDrift update: {inst.source_ref or inst.title}"
        note = inst.last_fetch_message or inst.last_fetch_status or "Updated"
        text_template = (
            f"{inst.title}\n"
            f"{inst.source_ref}\n\n"
            f"{note}\n"
            f"{'New version detected.' if new_versions else ''}\n\n"
            f"View timeline: {request.base_url}instruments/{inst.slug}\n"
            f"Unsubscribe: {request.base_url}unsubscribe?instrument={inst.slug}&email={{email}}\n"
        )
        _notify_subscribers_for_instrument(
            db=db, instrument=inst, subject=subject, text_template=text_template
        )

    return RedirectResponse(url="/?fetched=1", status_code=303)


@app.get("/export/markdown", response_class=PlainTextResponse)
def export_markdown(
    from_id: int = Query(..., alias="from"),
    to_id: int = Query(..., alias="to"),
    db: Session = Depends(get_db),
):
    from_v = db.query(Version).filter(Version.id == from_id).first()
    to_v = db.query(Version).filter(Version.id == to_id).first()
    if not from_v or not to_v:
        raise HTTPException(status_code=404, detail="Version not found")

    pair = get_or_create_pair(db, from_id, to_id)
    note = pair.note
    md = export_pair_markdown(
        instrument_title=from_v.instrument.title,
        from_label=from_v.version_label,
        to_label=to_v.version_label,
        old_text=from_v.normalized_text,
        new_text=to_v.normalized_text,
        note_summary=note.summary if note else "",
        note_implications=note.policy_implications if note else "",
        note_tags=note.tags if note else "",
        note_caveats=note.caveats if note else "",
    )
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")


@app.get("/admin/digest", response_class=HTMLResponse)
def change_digest(request: Request, db: Session = Depends(get_db), _: bool = Depends(require_admin)):
    """Weekly-style digest of instruments with multiple versions."""
    instruments = (
        db.query(Instrument)
        .filter(Instrument.slug.in_(TRACKED_SLUGS))
        .order_by(Instrument.title)
        .all()
    )
    digest_rows = []
    for inst in instruments:
        versions = (
            db.query(Version)
            .filter(Version.instrument_id == inst.id)
            .order_by(Version.effective_date.desc().nullslast(), Version.id.desc())
            .all()
        )
        if len(versions) < 2:
            continue
        newest, previous = versions[0], versions[1]
        pair = get_or_create_pair(db, previous.id, newest.id)
        stats = parse_stats(pair)
        digest_rows.append(
            {
                "instrument": inst,
                "from_version": previous,
                "to_version": newest,
                "stats": stats,
                "has_note": pair.note is not None and bool(pair.note.summary),
            }
        )
    return render(
        request,
        "digest.html",
        {"digest_rows": digest_rows, "active_nav": "digest"},
    )


@app.get("/changelog", response_class=HTMLResponse)
def changelog(request: Request, db: Session = Depends(get_db)):
    """Reverse-chronological feed of detected changes across tracked instruments."""
    from app.db import Instrument, Version, VersionSource

    rows = (
        db.query(VersionSource, Version, Instrument)
        .join(Version, VersionSource.version_id == Version.id)
        .join(Instrument, Version.instrument_id == Instrument.id)
        .filter(Instrument.slug.in_(TRACKED_SLUGS))
        .order_by(VersionSource.retrieved_at.desc(), VersionSource.id.desc())
        .limit(250)
        .all()
    )

    items = []
    for src, v, inst in rows:
        if src.source_type == "federal_register":
            note = "Fetched from Federal Register."
        elif src.source_type == "govinfo":
            note = "Fetched from GovInfo."
        else:
            note = "Added via manual upload."

        items.append(
            {
                "retrieved_at": src.retrieved_at,
                "instrument": inst,
                "version": v,
                "note": note,
            }
        )

    return render(
        request,
        "changelog.html",
        {"items": items, "active_nav": "changelog"},
    )


@app.get("/api/search")
def api_search(q: str = "", db: Session = Depends(get_db)):
    q = (q or "").strip()
    instruments = (
        db.query(Instrument)
        .filter(Instrument.slug.in_(TRACKED_SLUGS))
        .order_by(Instrument.title)
        .all()
    )

    if not q:
        items = []
        for inst in instruments:
            version_count = db.query(Version).filter(Version.instrument_id == inst.id).count()
            items.append(
                {
                    "slug": inst.slug,
                    "title": inst.title,
                    "instrument_type": inst.instrument_type,
                    "tags": [t.strip() for t in (inst.policy_tags or "").split(",") if t.strip()],
                    "version_count": version_count,
                    "last_fetch_status": inst.last_fetch_status or "manual",
                    "last_fetch_at": _fmt_dt(inst.last_fetch_at),
                    "snippet": "",
                }
            )
        return {"items": items}

    q_like = f"%{q.lower()}%"
    items = []
    for inst in instruments:
        title_hit = q.lower() in (inst.title or "").lower()
        tags_hit = q.lower() in (inst.policy_tags or "").lower()

        snippet = ""
        content_hit = False
        # Find a matching version text snippet (cheap, stop at first hit).
        versions = (
            db.query(Version)
            .filter(Version.instrument_id == inst.id)
            .order_by(Version.effective_date.desc().nullslast(), Version.id.desc())
            .limit(8)
            .all()
        )
        for v in versions:
            txt = (v.normalized_text or "").lower()
            idx = txt.find(q.lower())
            if idx != -1:
                content_hit = True
                start = max(0, idx - 70)
                end = min(len(v.normalized_text), idx + 140)
                snippet = v.normalized_text[start:end].replace("\n", " ").strip()
                if start > 0:
                    snippet = "…" + snippet
                if end < len(v.normalized_text):
                    snippet = snippet + "…"
                break

        if not (title_hit or tags_hit or content_hit):
            continue

        version_count = db.query(Version).filter(Version.instrument_id == inst.id).count()
        items.append(
            {
                "slug": inst.slug,
                "title": inst.title,
                "instrument_type": inst.instrument_type,
                "tags": [t.strip() for t in (inst.policy_tags or "").split(",") if t.strip()],
                "version_count": version_count,
                "last_fetch_status": inst.last_fetch_status or "manual",
                "last_fetch_at": _fmt_dt(inst.last_fetch_at),
                "snippet": snippet,
            }
        )

    return {"items": items[:50]}


@app.get("/analysis", response_class=HTMLResponse)
def analysis_index(request: Request):
    posts = load_posts(ANALYSIS_DIR) if ANALYSIS_DIR.exists() else []
    return render(request, "analysis_index.html", {"posts": posts, "active_nav": "analysis"})


@app.get("/analysis/{slug}", response_class=HTMLResponse)
def analysis_post(request: Request, slug: str):
    post = get_post(ANALYSIS_DIR, slug) if ANALYSIS_DIR.exists() else None
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return render(
        request,
        "analysis_post.html",
        {"post": post, "active_nav": "analysis"},
    )


@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return render(request, "about.html", {"active_nav": "about"})


@app.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request, db: Session = Depends(get_db), _: bool = Depends(require_admin)):
    from app.ingest.fr_series import FR_SERIES_BY_SLUG

    series_status = []
    for slug in FR_SERIES_BY_SLUG:
        inst = get_instrument_by_slug(db, slug)
        if not inst:
            continue
        version_count = db.query(Version).filter(Version.instrument_id == inst.id).count()
        series_status.append(
            {
                "slug": slug,
                "title": inst.title,
                "version_count": version_count,
                "last_fetch_message": inst.last_fetch_message or "",
            }
        )

    ofac_status = None
    ofac_inst = get_instrument_by_slug(db, "ofac-sdn")
    if ofac_inst:
        ofac_versions = db.query(Version).filter(Version.instrument_id == ofac_inst.id).count()
        ofac_status = {
            "slug": ofac_inst.slug,
            "title": ofac_inst.title,
            "version_count": ofac_versions,
            "last_fetch_message": ofac_inst.last_fetch_message or "",
        }

    return render(
        request,
        "admin_home.html",
        {
            "active_nav": "",
            "series_status": series_status,
            "ofac_status": ofac_status,
            "fetch_log": request.query_params.get("fetch_log"),
        },
    )


@app.post("/admin/fetch-fr-series")
def admin_fetch_fr_series(
    request: Request, db: Session = Depends(get_db), _: bool = Depends(require_admin)
):
    """Fetch only multi-document FR series (Directive 4, GL 13) — use if full fetch missed them."""
    from urllib.parse import quote

    results = fetch_all_fr_series(db)
    log = "; ".join(f"{slug}: {msg}" for slug, msg in results.items())
    return RedirectResponse(url=f"/admin?fetch_log={quote(log)}", status_code=303)


@app.post("/admin/fetch-ofac-archive")
def admin_fetch_ofac_archive(
    request: Request, db: Session = Depends(get_db), _: bool = Depends(require_admin)
):
    """Pull a prior full SDN.CSV from bundled seed (OFAC SLS only serves the current file)."""
    from urllib.parse import quote

    msg = fetch_ofac_sdn_archive(db)
    return RedirectResponse(url=f"/admin?fetch_log={quote(f'ofac-sdn archive: {msg}')}", status_code=303)


@app.post("/admin/fetch-ofac-current")
def admin_fetch_ofac_current(
    request: Request, db: Session = Depends(get_db), _: bool = Depends(require_admin)
):
    """Pull today's live SDN.CSV from OFAC only (no full instrument fetch)."""
    from urllib.parse import quote

    msg = fetch_ofac_sdn(db)
    return RedirectResponse(url=f"/admin?fetch_log={quote(f'ofac-sdn live: {msg}')}", status_code=303)
