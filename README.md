# PolicyDrift

A local web app for tracking versioned U.S. federal policy text—executive orders, public laws—with redline diffs and IR-style analyst notes.

A local web app for tracking versioned text of U.S. federal policy instruments (executive orders and public laws), viewing redline diffs, and attaching IR-style analyst notes.

**Disclaimer:** Research and education only — not legal advice.

## Features

- Dashboard of tracked instruments with fetch status
- Version timeline per instrument
- Unified, side-by-side, and section-aware redline diffs
- Analyst notes (summary, policy implications, tags, caveats)
- Manual text upload
- Optional Federal Register and GovInfo ingestion
- Change digest and Markdown export

See [METHODOLOGY.md](METHODOLOGY.md) for sourcing and limitations.

## Quick start

```bash
cd first_project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed_instruments.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## API keys (optional)

Copy `.env.example` to `.env` and add keys:

- [Federal Register API](https://www.federalregister.gov/developers/documentation/api/v1)
- [GovInfo API](https://api.govinfo.gov/docs/)

Then run:

```bash
python scripts/fetch_all.py
```

Or use **Fetch from APIs** on the dashboard.

## Demo script (3 minutes)

See [DEMO.md](DEMO.md).

## Tests

```bash
pytest -q
```

## Project layout

```
app/           FastAPI app, models, diff engine, ingestion
scripts/       seed_instruments.py, fetch_all.py
tests/         unit tests
data/          SQLite DB and raw downloads
```

## Personalize the site

Edit [`app/site_profile.py`](app/site_profile.py) with your name, Georgetown line, bio, and optional GitHub link.

**Your logo:** replace [`app/static/logo.svg`](app/static/logo.svg) with your file (or add `logo.png` and set `LOGO_PATH = "/static/logo.png"` in `site_profile.py`). Hard-refresh the browser after swapping.

## Portfolio tips

1. Replace seed excerpts with full Federal Register / GovInfo text.
2. Write analyst notes for 3+ meaningful version pairs (seed includes examples).
3. Record a Loom walking EO 14024 original → amended diff.
4. Export Markdown from a diff page for a one-page policy memo.
