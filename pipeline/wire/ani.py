"""Asian News International (ANI) adapter: a stub until ANI gives us a documented API.

ANI publishes no public API documentation that we could find (checked 10 Nov 2026: aninews.in (blocks automated requests) and web searches for an ANI API).
This adapter therefore always raises NotConfigured and the lane moves on to the next image source.
It never scrapes ANI's subscriber web portal: only an official API or feed, with credentials as secrets.

To switch it on: ask ANI's subscription desk for their photo API or feed documentation (endpoint, auth
method, search parameters, credit terms). Then add the secrets below in GitHub
(docs/SETUP-GITHUB-SECRETS.md) and have a developer session implement search() and download() here,
following pipeline/wire/ap.py, with tests that mock the API.

Secrets it will read: ANI_API_BASE, ANI_API_KEY
Credit line: "ANI Photo"
"""
from __future__ import annotations

from .base import AGENCY_CREDIT, StubAdapter


class ANIAdapter(StubAdapter):
    name = "ani"
    secrets = ("ANI_API_BASE", "ANI_API_KEY")
    credit = AGENCY_CREDIT["ani"]
    why = ("no documented ANI API is built in yet: ask ANI for their photo API/feed documentation, "
           "then implement pipeline/wire/ani.py (secrets ANI_API_BASE, ANI_API_KEY)")
