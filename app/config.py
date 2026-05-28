import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data' / 'policy_tracker.db'}")
FEDERAL_REGISTER_API_KEY = os.getenv("FEDERAL_REGISTER_API_KEY", "")
GOVINFO_API_KEY = os.getenv("GOVINFO_API_KEY", "")
CONGRESS_API_KEY = os.getenv("CONGRESS_API_KEY", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
# Resend supports a shared dev sender; replace with your domain later.
RESEND_FROM = os.getenv("RESEND_FROM", "PolicyDrift <onboarding@resend.dev>")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# Core v1 instruments shown on dashboard (excludes test rows)
TRACKED_SLUGS: frozenset[str] = frozenset(
    {
        "eo-14024",
        "eo-14066",
        "eo-14068",
        "ukraine-supplemental-118-50",
        "repo-act-118-68",
        "ofac-sdn",
        "russia-gl-13",
        "directive-4-eo14024",
    }
)
