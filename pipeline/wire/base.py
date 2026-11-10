"""The interface every licensed wire-agency adapter implements (pipeline/wire/<agency>.py).

    adapter = pipeline.wire.get_adapter("ap")      # reads its credentials from the environment
    adapter.configured()                           # False: no credentials (the lane skips it)
    adapter.search(query, since) -> [Candidate]    # newest first; only items free to use under our plan
    adapter.download(id) -> (bytes, credit)        # the full-size image and the exact credit line

Rules for every adapter:
  * official APIs or feeds only, with credentials Rahul supplies as GitHub secrets; never scrape a portal's
    logged-in web pages;
  * never anything that costs extra (AP: in_my_plan=true, and priced renditions are refused);
  * never Reuters or Getty (idly has no licence), even when an agency redistributes them;
  * credentials go only in request headers, never in URLs, logs or files.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

# The exact credit line each agency asks for. AP: AP style, "AP Photo/<Photographer>". PTI, ANI, IANS
# publish no credit terms we could find; these are the forms Indian publishers use for them. Check them
# against each contract and change them here if it says otherwise.
AGENCY_CREDIT = {
    "ap": "AP Photo/{photographer}",
    "pti": "Photo: PTI",
    "ani": "ANI Photo",
    "ians": "Photo: IANS",
}
AGENCY_NAMES = {"ap": "AP (Associated Press)", "pti": "PTI (Press Trust of India)",
                "ani": "ANI (Asian News International)", "ians": "IANS (Indo-Asian News Service)"}
# Never used: idly has no licence for these, even when a licensed agency redistributes them.
DENIED_CREDIT = re.compile(r"\b(reuters|getty|afp|agence france|shutterstock|alamy|epa|imago)\b", re.I)


class NotConfigured(Exception):
    """The agency has no credentials here, or no adapter has been built for its API yet."""

    def __init__(self, agency: str, message: str):
        super().__init__(f"{agency}: {message}")
        self.agency = agency


class WireError(Exception):
    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient


@dataclass
class Candidate:
    agency: str
    id: str
    caption: str
    credit: str
    preview_url: str | None
    created_at: str | None        # ISO 8601 (UTC), when the photo was made or first published
    width: int | None = None      # of the full-size rendition, when the API says
    height: int | None = None
    headline: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class WireAdapter:
    name = ""
    secrets: tuple[str, ...] = ()        # GitHub secret / environment variable names it reads

    def configured(self) -> bool:
        raise NotImplementedError

    def search(self, query: str, since) -> list[Candidate]:
        raise NotImplementedError

    def download(self, id: str) -> tuple[bytes, str]:
        raise NotImplementedError


class StubAdapter(WireAdapter):
    """An agency whose API we could not confirm: always NotConfigured, with what is needed."""
    why = ""

    def configured(self) -> bool:
        return False

    def _refuse(self):
        raise NotConfigured(self.name, self.why)

    def search(self, query: str, since) -> list[Candidate]:
        self._refuse()

    def download(self, id: str) -> tuple[bytes, str]:
        self._refuse()
