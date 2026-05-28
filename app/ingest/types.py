from __future__ import annotations

from typing import NamedTuple

from app.db import Version


class VersionCreateResult(NamedTuple):
    version: Version | None
    created: bool
