"""Indo-Asian News Service (IANS) adapter: a stub until IANS gives us a documented API.

IANS publishes no public API documentation that we could find (checked 10 Nov 2026: ianslive.in and web searches for an IANS API).
This adapter therefore always raises NotConfigured and the lane moves on to the next image source.
It never scrapes IANS's subscriber web portal: only an official API or feed, with credentials as secrets.

To switch it on: ask IANS's subscription desk for their photo API or feed documentation (endpoint, auth
method, search parameters, credit terms). Then add the secrets below in GitHub
(docs/SETUP-GITHUB-SECRETS.md) and have a developer session implement search() and download() here,
following pipeline/wire/ap.py, with tests that mock the API.

Secrets it will read: IANS_API_BASE, IANS_API_KEY
Credit line: "Photo: IANS"
"""
from __future__ import annotations

from .base import AGENCY_CREDIT, StubAdapter


class IANSAdapter(StubAdapter):
    name = "ians"
    secrets = ("IANS_API_BASE", "IANS_API_KEY")
    credit = AGENCY_CREDIT["ians"]
    why = ("no documented IANS API is built in yet: ask IANS for their photo API/feed documentation, "
           "then implement pipeline/wire/ians.py (secrets IANS_API_BASE, IANS_API_KEY)")
