# Methodology — PolicyDrift

## Purpose

This tool tracks **versioned text** of selected U.S. federal instruments across policy topics and regions. It produces **textual redline diffs** and supports **analyst notes** that interpret changes for policy audiences. It does not provide legal advice.

## Instrument selection (v1)

| Instrument | Rationale |
|------------|-----------|
| EO 14024 | Foundational sanctions emergency authorities (example instrument) |
| EO 14066 | Energy import restrictions (2022) |
| EO 14068 | Broader import/export restrictions (2022) |
| PL 118-50 (supplemental) | Security assistance appropriations (example instrument) |
| PL 118-68 (REPO Act) | Sovereign asset seizure / reconstruction funding |

Instruments are chosen for **IR salience**, **public availability**, and **observable version history**—not for exhaustive coverage of any single topic.

## Sources (in priority order)

1. **Federal Register** — executive orders ([API v1](https://www.federalregister.gov/developers/documentation/api/v1))
2. **GovInfo** — public laws and enrolled bill packages ([API](https://api.govinfo.gov/docs/))
3. **Manual upload** — full text pasted from official HTML/PDF when APIs return abstracts only

Every stored version includes a `VersionSource` row: URL, source type, and retrieval timestamp.

## Normalization rules

- UTF-8 encoding throughout
- HTML converted to plain text (scripts/nav stripped)
- Line endings unified to `\n`
- Repeated whitespace collapsed; max two consecutive newlines
- Page artifacts removed where regex-detectable (`Page N of M`)
- **No correction** of typos or numbering in source documents

Differences between GovInfo XML and Federal Register HTML may cause **formatting-only** diff noise. Analyst notes should flag substantive vs. cosmetic changes.

## Version semantics

- Each **Version** is a **point-in-time snapshot** of text (effective date + label).
- Amendatory executive orders may not replace full EO text on the Federal Register; labels document what the snapshot represents.
- Duplicate text (same SHA-256 hash per instrument) is rejected automatically.

## Diff modes

- **Unified** — default line-level redline (`<ins>` / `<del>`)
- **Side-by-side** — older vs. newer columns
- **Section-aware** — splits on `SEC.` / `SECTION` headers before diffing (recommended for long statutes)

Percent changed is a rough line-count heuristic, not a legal materiality score.

## Limitations

- **Textual only** — does not capture classified guidance, interagency memos, or OFAC FAQs unless pasted manually.
- **No automated legal interpretation** — analyst notes are human-authored.
- **API gaps** — Federal Register may return abstracts; GovInfo requires an API key; failed fetches are marked `failed` on the instrument.
- **Phase 2** — EU/UK instruments, 31 CFR OFAC rules, and full NDAA titles are out of scope for v1.

## Ethics

- Public documents only; no paywall circumvention.
- Local deployment (`127.0.0.1`) by default.
- API keys stored in `.env`, never committed.

## Recommended workflow

1. Run `python scripts/seed_instruments.py` for demo data.
2. Paste official full text via **Upload version** when API text is incomplete.
3. Compare versions on the instrument timeline; add analyst notes on meaningful pairs.
4. Export Markdown for memos or portfolio PDFs.
5. Run `python scripts/fetch_all.py` when API keys are configured.
