#!/usr/bin/env python3
"""Seed instruments, sample versions, and portfolio analyst notes."""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import TRACKED_SLUGS
from app.db import AnalystNote, Instrument, SessionLocal, Version, VersionPair, init_db
from app.ingest.manual import create_manual_version
from app.services import get_or_create_pair

INSTRUMENTS = [
    {
        "slug": "eo-14024",
        "title": "EO 14024 — Blocking Property With Respect to Specified Harmful Foreign Activities of the Government of the Russian Federation",
        "instrument_type": "executive_order",
        "policy_tags": "sanctions,russia,foundation",
        "source_ref": "EO 14024",
    },
    {
        "slug": "eo-14066",
        "title": "EO 14066 — Prohibiting Certain Imports and New Investments With Respect to Continued Russian Federation Aggression",
        "instrument_type": "executive_order",
        "policy_tags": "sanctions,energy,imports",
        "source_ref": "EO 14066",
    },
    {
        "slug": "eo-14068",
        "title": "EO 14068 — Prohibiting Certain Imports, Exports, and New Investment With Respect to Continued Russian Federation Aggression",
        "instrument_type": "executive_order",
        "policy_tags": "sanctions,trade,imports",
        "source_ref": "EO 14068",
    },
    {
        "slug": "ukraine-supplemental-118-50",
        "title": "Public Law 118-50 — Ukraine Security Supplemental Appropriations (Division B)",
        "instrument_type": "public_law",
        "policy_tags": "aid,ukraine,appropriations",
        "source_ref": "PL 118-50",
    },
    {
        "slug": "repo-act-118-68",
        "title": "REPO Act — Rebuilding Economic Prosperity and Opportunity for Ukrainians Act (PL 118-68)",
        "instrument_type": "public_law",
        "policy_tags": "sovereign_assets,sanctions,ukraine",
        "source_ref": "PL 118-68",
    },
]

# Sample texts for demonstration (representative excerpts for diff demo; replace with full FR/GovInfo text via upload)
EO_14024_V1 = """EXECUTIVE ORDER 14024
BLOCKING PROPERTY WITH RESPECT TO SPECIFIED HARMFUL FOREIGN ACTIVITIES OF THE GOVERNMENT OF THE RUSSIAN FEDERATION

By the authority vested in me as President by the Constitution and the laws of the United States of America,
including the International Emergency Economic Powers Act (50 U.S.C. 1701 et seq.),
I hereby declare a national emergency to deal with the unusual and extraordinary threat to the national security
and foreign policy of the United States constituted by specified harmful foreign activities of the Government of the Russian Federation.

Sec. 1. (a) All property and interests in property of the following persons that are in the United States are blocked:
any person determined by the Secretary of the Treasury, in consultation with the Secretary of State, to operate in the technology sector in the Russian Federation economy.

Sec. 2. Nothing in this order shall prohibit transactions for the conduct of the official business of the Federal Government.
"""

EO_14024_V2 = """EXECUTIVE ORDER 14024 (AS AMENDED)
BLOCKING PROPERTY WITH RESPECT TO SPECIFIED HARMFUL FOREIGN ACTIVITIES OF THE GOVERNMENT OF THE RUSSIAN FEDERATION

By the authority vested in me as President by the Constitution and the laws of the United States of America,
including the International Emergency Economic Powers Act (50 U.S.C. 1701 et seq.),
I hereby reaffirm the national emergency declared in Executive Order 14024 of February 21, 2022,
to deal with the unusual and extraordinary threat to the national security and foreign policy of the United States
constituted by specified harmful foreign activities of the Government of the Russian Federation and its proxies.

Sec. 1. (a) All property and interests in property of the following persons that are in the United States are blocked:
any person determined by the Secretary of the Treasury, in consultation with the Secretary of State and the Attorney General,
to operate in the technology or defense sectors of the Russian Federation economy, or to have materially assisted deceptive transactions.

Sec. 1. (b) The prohibitions in subsection (a) apply except to the extent provided by statutes, or unless licensed by OFAC.

Sec. 2. Nothing in this order shall prohibit transactions for the conduct of the official business of the Federal Government or the United Nations.
"""

EO_14066_V1 = """EXECUTIVE ORDER 14066
PROHIBITING CERTAIN IMPORTS AND NEW INVESTMENTS WITH RESPECT TO CONTINUED RUSSIAN FEDERATION AGGRESSION

Sec. 1. (a) The importation into the United States of the following products of Russian Federation origin is prohibited:
crude oil; petroleum; petroleum fuels, oils, and products of their distillation; liquefied natural gas; coal; and coal products.

Sec. 2. (a) U.S. persons are prohibited from new investment in any sector of the Russian Federation economy as may be determined by the Secretary of the Treasury.
"""

EO_14066_V2 = """EXECUTIVE ORDER 14066 (IMPLEMENTING CLARIFICATION)
PROHIBITING CERTAIN IMPORTS AND NEW INVESTMENTS WITH RESPECT TO CONTINUED RUSSIAN FEDERATION AGGRESSION

Sec. 1. (a) The importation into the United States of the following products of Russian Federation origin is prohibited:
crude oil; petroleum; petroleum fuels, oils, and products of their distillation; liquefied natural gas; coal; and coal products.
(b) Licensed imports consistent with allied price cap policies may be authorized by the Secretary of the Treasury.

Sec. 2. (a) U.S. persons are prohibited from new investment in any sector of the Russian Federation economy as may be determined by the Secretary of the Treasury, in consultation with the Secretary of State.
"""

EO_14068_V1 = """EXECUTIVE ORDER 14068
PROHIBITING CERTAIN IMPORTS, EXPORTS, AND NEW INVESTMENT

Sec. 1. (a) The importation of fish, seafood, and preparations thereof of Russian Federation origin is prohibited.
(b) The importation of alcoholic beverages of Russian Federation origin is prohibited.
(c) The importation of non-industrial diamonds of Russian Federation origin is prohibited.

Sec. 2. (a) The exportation of luxury goods to any person located in the Russian Federation is prohibited.
"""

EO_14068_V2 = """EXECUTIVE ORDER 14068 (EXPANDED IMPORT BAN)
PROHIBITING CERTAIN IMPORTS, EXPORTS, AND NEW INVESTMENT

Sec. 1. (a) The importation of fish, seafood, and preparations thereof of Russian Federation origin is prohibited.
(b) The importation of alcoholic beverages of Russian Federation origin is prohibited.
(c) The importation of non-industrial diamonds of Russian Federation origin is prohibited.
(d) The importation of gold of Russian Federation origin is prohibited.

Sec. 2. (a) The exportation of luxury goods to any person located in the Russian Federation is prohibited.
(b) The exportation of U.S. dollar-denominated banknotes to the Russian Federation is prohibited.
"""

UKRAINE_PL_V1 = """PUBLIC LAW 118-50 — DIVISION B
UKRAINE SECURITY SUPPLEMENTAL APPROPRIATIONS ACT, 2024

SEC. 101. There is appropriated to the Department of Defense for the Ukraine Security Assistance Initiative, $13,800,000,000.
SEC. 102. Funds may be used for the procurement of defense articles and defense services for the Government of Ukraine.
SEC. 103. None of the funds made available by this division may be used for purposes other than those specified in this division.
"""

UKRAINE_PL_V2 = """PUBLIC LAW 118-50 — DIVISION B (AMENDED PACKAGE)
UKRAINE SECURITY SUPPLEMENTAL APPROPRIATIONS ACT, 2024

SEC. 101. There is appropriated to the Department of Defense for the Ukraine Security Assistance Initiative, $13,800,000,000.
SEC. 101A. There is appropriated to the Department of State for Foreign Military Financing, $3,900,000,000 for Ukraine and countries impacted by the situation in Ukraine.
SEC. 102. Funds may be used for the procurement of defense articles, defense services, and training for the Government of Ukraine.
SEC. 103. The Secretary of State shall provide quarterly reports to Congress on obligation of funds under this division.
SEC. 104. None of the funds made available by this division may be used for purposes other than those specified in this division.
"""

REPO_V1 = """PUBLIC LAW 118-68 — REPO ACT
REBUILDING ECONOMIC PROSPERITY AND OPPORTUNITY FOR UKRAINIANS ACT OF 2024

SEC. 101. SHORT TITLE.
This Act may be cited as the "Rebuilding Economic Prosperity and Opportunity for Ukrainians Act of 2024" or the "REPO Act of 2024".

SEC. 102. FINDINGS.
Congress finds that sovereign assets of the Russian Federation immobilized in the United States should be available to meet Ukraine's compensation and reconstruction needs.

SEC. 201. The President may seize and vest sovereign assets of the Russian Federation held in the United States, subject to judicial review as provided in this Act.
"""

REPO_V2 = """PUBLIC LAW 118-68 — REPO ACT (ENROLLED)
REBUILDING ECONOMIC PROSPERITY AND OPPORTUNITY FOR UKRAINIANS ACT OF 2024

SEC. 101. SHORT TITLE.
This Act may be cited as the "Rebuilding Economic Prosperity and Opportunity for Ukrainians Act of 2024" or the "REPO Act of 2024".

SEC. 102. FINDINGS.
Congress finds that sovereign assets of the Russian Federation immobilized in the United States and allied jurisdictions should be available to meet Ukraine's compensation and reconstruction needs following Russian aggression.

SEC. 201. The President may seize, vest, and transfer sovereign assets of the Russian Federation held in the United States for the reconstruction of Ukraine, subject to congressional notification and judicial review.
SEC. 202. Nothing in this Act shall be construed to authorize action inconsistent with international law obligations of the United States.
"""

ANALYST_NOTES = [
    {
        "instrument_slug": "eo-14024",
        "from_label_contains": "2022-02-21",
        "to_label_contains": "amended",
        "summary": "EO 14024 was expanded to cover defense-sector operators and deceptive transaction facilitators, with OFAC licensing language made explicit. Attorney General was added to the determination process.",
        "policy_implications": "Broadens the sanctions foundation for subsequent designations and signals intent to target evasion networks, not only direct Russian state actors. Allied jurisdictions often mirror foundational EOs.",
        "tags": "sanctions,russia,evasion",
        "caveats": "Sample excerpt for demo; compare full Federal Register text for legal analysis.",
    },
    {
        "instrument_slug": "ukraine-supplemental-118-50",
        "from_label_contains": "2024-04-24 PL 118-50",
        "to_label_contains": "AMENDED",
        "summary": "The supplemental package adds State FMF funding, training authority, and quarterly congressional reporting while retaining core USAI appropriations.",
        "policy_implications": "Shifts part of the assistance burden to State authorities and increases oversight—relevant for congressional politics and allied burden-sharing debates.",
        "tags": "aid,ukraine,oversight",
        "caveats": "Section numbers are illustrative; verify against enrolled statute on GovInfo.",
    },
    {
        "instrument_slug": "repo-act-118-68",
        "from_label_contains": "REPO ACT",
        "to_label_contains": "ENROLLED",
        "summary": "REPO language tightens the purpose of seized sovereign assets toward Ukraine reconstruction and adds international-law consistency and congressional notification guardrails.",
        "policy_implications": "Moves the U.S. toward utilization of immobilized Russian reserves while attempting to manage G7 legal coordination risks.",
        "tags": "sovereign_assets,sanctions,ukraine",
        "caveats": "Implementing regulations and allied reciprocity not captured in statute text alone.",
    },
]


def _cleanup_non_tracked(db) -> None:
    """Remove test instruments created during pytest runs."""
    extras = db.query(Instrument).filter(~Instrument.slug.in_(TRACKED_SLUGS)).all()
    for inst in extras:
        version_ids = [v.id for v in inst.versions]
        if version_ids:
            pairs = (
                db.query(VersionPair)
                .filter(
                    (VersionPair.from_version_id.in_(version_ids))
                    | (VersionPair.to_version_id.in_(version_ids))
                )
                .all()
            )
            for pair in pairs:
                if pair.note:
                    db.delete(pair.note)
                db.delete(pair)
        for v in list(inst.versions):
            for src in v.sources:
                db.delete(src)
            db.delete(v)
        db.delete(inst)
    db.commit()


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        _cleanup_non_tracked(db)
        for data in INSTRUMENTS:
            inst = db.query(Instrument).filter(Instrument.slug == data["slug"]).first()
            if not inst:
                inst = Instrument(**data)
                db.add(inst)
        db.commit()

        samples = {
            "eo-14024": [
                ("2022-02-21 Original signing", date(2022, 2, 21), EO_14024_V1),
                ("2024-12-19 Expanded authorities (amended snapshot)", date(2024, 12, 19), EO_14024_V2),
            ],
            "eo-14066": [
                ("2022-03-08 Energy imports ban", date(2022, 3, 8), EO_14066_V1),
                ("2022-06-01 Price cap licensing clarification", date(2022, 6, 1), EO_14066_V2),
            ],
            "eo-14068": [
                ("2022-03-08 Import restrictions", date(2022, 3, 8), EO_14068_V1),
                ("2022-03-11 Expanded import and export bans", date(2022, 3, 11), EO_14068_V2),
            ],
            "ukraine-supplemental-118-50": [
                ("2024-04-24 PL 118-50 (base text)", date(2024, 4, 24), UKRAINE_PL_V1),
                ("2024-04-24 PL 118-50 (AMENDED package)", date(2024, 4, 24), UKRAINE_PL_V2),
            ],
            "repo-act-118-68": [
                ("2024 REPO Act (introduced text)", date(2024, 4, 1), REPO_V1),
                ("2024 REPO Act (ENROLLED)", date(2024, 4, 24), REPO_V2),
            ],
        }

        version_ids: dict[str, list] = {}
        for slug, versions in samples.items():
            inst = db.query(Instrument).filter(Instrument.slug == slug).first()
            version_ids[slug] = []
            for label, eff, text in versions:
                result = create_manual_version(
                    db,
                    inst,
                    raw_text=text,
                    version_label=label,
                    effective_date=eff,
                    source_url=f"https://seed.local/{slug}/{label}",
                )
                if result.version:
                    version_ids[slug].append(result.version)

        for note_cfg in ANALYST_NOTES:
            slug = note_cfg["instrument_slug"]
            vers = version_ids.get(slug, [])
            if len(vers) < 2:
                continue
            from_v = next((v for v in vers if note_cfg["from_label_contains"].lower() in v.version_label.lower()), vers[0])
            to_v = next((v for v in vers if note_cfg["to_label_contains"].lower() in v.version_label.lower()), vers[-1])
            pair = get_or_create_pair(db, from_v.id, to_v.id)
            if pair.note:
                continue
            note = AnalystNote(
                version_pair_id=pair.id,
                summary=note_cfg["summary"],
                policy_implications=note_cfg["policy_implications"],
                tags=note_cfg["tags"],
                caveats=note_cfg["caveats"],
            )
            db.add(note)
        db.commit()
        print("Seed complete: instruments, versions, and analyst notes.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
