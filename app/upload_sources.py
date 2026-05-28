"""Official source links and upload hints per instrument."""

UPLOAD_SOURCES: dict[str, dict[str, str]] = {
    "eo-14024": {
        "title": "EO 14024",
        "fr_url": "https://www.federalregister.gov/documents/2022/02/24/2022-03759/blocking-property-with-respect-to-specified-harmful-foreign-activities-of-the-government-of-the",
        "default_label": "2022-02-21 — Full text (Federal Register)",
        "default_date": "2022-02-21",
        "type": "executive_order",
    },
    "eo-14066": {
        "title": "EO 14066",
        "fr_url": "https://www.federalregister.gov/documents/2022/03/11/2022-04347/prohibiting-certain-imports-and-new-investments-with-respect-to-continued-russian-federation",
        "default_label": "2022-03-08 — Full text (Federal Register)",
        "default_date": "2022-03-08",
        "type": "executive_order",
    },
    "eo-14068": {
        "title": "EO 14068",
        "fr_url": "https://www.federalregister.gov/documents/2022/03/11/2022-04348/prohibiting-certain-imports-exports-and-new-investment-with-respect-to-continued-russian",
        "default_label": "2022-03-08 — Full text (Federal Register)",
        "default_date": "2022-03-08",
        "type": "executive_order",
    },
    "ukraine-supplemental-118-50": {
        "title": "PL 118-50",
        "fr_url": "https://www.govinfo.gov/app/details/PLAW-118publ50",
        "default_label": "2024-04-24 — PL 118-50 enrolled text",
        "default_date": "2024-04-24",
        "type": "public_law",
    },
    "repo-act-118-68": {
        "title": "PL 118-68 (REPO Act)",
        "fr_url": "https://www.govinfo.gov/app/details/PLAW-118publ68",
        "default_label": "2024-04-24 — REPO Act enrolled text",
        "default_date": "2024-04-24",
        "type": "public_law",
    },
    "ofac-sdn": {
        "title": "OFAC SDN List",
        "fr_url": "https://sanctionslist.ofac.treas.gov/",
        "default_label": "Latest snapshot (OFAC Sanctions List Service)",
        "default_date": "",
        "type": "ofac_sdn",
    },
}
