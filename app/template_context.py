"""Shared variables for every Jinja template."""

from __future__ import annotations

from datetime import date, datetime

from app import site_profile


def _fmt_month_day_year(d: date) -> str:
    # "May 27, 2026" (no leading zero on day)
    return d.strftime("%B %d, %Y").replace(" 0", " ")


def fmt_date(d: date | datetime | None) -> str:
    if not d:
        return ""
    if isinstance(d, datetime):
        d = d.date()
    return _fmt_month_day_year(d)


def fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%B %d, %Y %H:%M").replace(" 0", " ")


def site_context() -> dict:
    return {
        "site_name": site_profile.SITE_NAME,
        "brand_tagline": site_profile.BRAND_TAGLINE,
        "site_full_title": site_profile.SITE_FULL_TITLE,
        "site_tagline": site_profile.SITE_TAGLINE,
        "deck_lead": getattr(site_profile, "DECK_LEAD", site_profile.SITE_TAGLINE),
        "logo_path": site_profile.LOGO_PATH,
        "wordmark_path": site_profile.WORDMARK_PATH,
        "author_name": site_profile.AUTHOR_NAME,
        "author_line": site_profile.AUTHOR_LINE,
        "author_bio": site_profile.AUTHOR_BIO,
        "project_link": site_profile.PROJECT_LINK,
        "project_link_label": site_profile.PROJECT_LINK_LABEL,
        "footer_byline": getattr(site_profile, "FOOTER_BYLINE", ""),
        "footer_email": getattr(site_profile, "FOOTER_EMAIL", ""),
        "footer_description": getattr(site_profile, "FOOTER_DESCRIPTION", ""),
        "footer_shadow_fleet_url": getattr(site_profile, "FOOTER_SHADOW_FLEET_URL", ""),
        "fmt_date": fmt_date,
        "fmt_dt": fmt_dt,
    }
