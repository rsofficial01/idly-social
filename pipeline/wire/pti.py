"""Press Trust of India (PTI) adapter: a stub until PTI gives us a documented API.

PTI publishes no public API documentation that we could find (checked 10 Nov 2026: ptinews.com and web searches for a PTI photo/news API).
This adapter therefore always raises NotConfigured and the lane moves on to the next image source.
It never scrapes PTI's subscriber web portal: only an official API or feed, with credentials as secrets.

To switch it on: ask PTI's subscription desk for their photo API or feed documentation (endpoint, auth
method, search parameters, credit terms). Then add the secrets below in GitHub
(docs/SETUP-GITHUB-SECRETS.md) and have a developer session implement search() and download() here,
following pipeline/wire/ap.py, with tests that mock the API.

Secrets it will read: PTI_API_BASE, PTI_API_KEY
Credit line: "Photo: PTI"
"""
from __future__ import annotations

from .base import AGENCY_CREDIT, StubAdapter


class PTIAdapter(StubAdapter):
    name = "pti"
    secrets = ("PTI_API_BASE", "PTI_API_KEY")
    credit = AGENCY_CREDIT["pti"]
    why = ("no documented PTI API is built in yet: ask PTI for their photo API/feed documentation, "
           "then implement pipeline/wire/pti.py (secrets PTI_API_BASE, PTI_API_KEY)")
