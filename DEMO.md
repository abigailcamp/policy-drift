# 3-minute demo script

Use this when recording a portfolio Loom or live demo.

## Setup (before recording)

```bash
source .venv/bin/activate
python scripts/seed_instruments.py
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Script

**0:00 — Dashboard**  
Open `http://127.0.0.1:8000`.  
Say: “This is PolicyDrift—it tracks how U.S. federal policy instruments change over time, with versioned text and redline diffs.”  
Point at fetch status badges and version counts.

**0:30 — EO 14024 timeline**  
Click **EO 14024**.  
Say: “Each row is a point-in-time snapshot, not a guess at consolidated law.”  
Select earlier → later versions; click **View redline**.

**1:15 — Redline + note**  
On the diff page, point at line stats and red highlights.  
Toggle **Section-aware** if comparing a long statute later.  
Scroll to the **Analyst note** — explain your IR interpretation (expansion of sectors, OFAC licensing, allied mirroring).

**2:00 — Upload path**  
Go to **Upload version**.  
Say: “When APIs only return abstracts, I paste full text from Federal Register or GovInfo—sourcing is documented per version.”

**2:30 — Digest + export**  
Open **Change digest** — quick view of latest vs. previous per instrument.  
From any diff, click **Export Markdown** for a memo-ready report.

**2:50 — Close**  
Say: “Methodology and limitations are in METHODOLOGY.md; this is research tooling, not legal advice.”

## Optional: live API fetch

If `.env` has keys, click **Fetch from APIs** on the dashboard and show a new version appearing (or `failed` status if key missing—explain honest error states).
