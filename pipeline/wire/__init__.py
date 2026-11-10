"""Licensed wire-agency photo adapters for the official image lane (resolver `licensed_wire`).

    from pipeline import wire
    wire.get_adapter("ap").search("Virat Kohli Perth Test", since)   # -> [Candidate]
    wire.get_adapter("ap").download(item_id)                          # -> (bytes, "AP Photo/<Photographer>")

ap   AP Media API: implemented (secret AP_MEDIA_API_KEY).
pti, ani, ians: stubs that raise NotConfigured: none of them publishes a documented API we could confirm.
Reuters (Connect) and Getty: never (idly has no licence); there is no adapter and none may be added.
"""
from __future__ import annotations

from .ani import ANIAdapter
from .ap import APAdapter
from .base import AGENCY_CREDIT, AGENCY_NAMES, DENIED_CREDIT, Candidate, NotConfigured, WireAdapter, WireError
from .ians import IANSAdapter
from .pti import PTIAdapter

ADAPTERS: dict[str, type[WireAdapter]] = {"ap": APAdapter, "pti": PTIAdapter, "ani": ANIAdapter,
                                          "ians": IANSAdapter}
ORDER = ("ap", "pti", "ani", "ians")
NEVER = ("reuters", "getty")


def get_adapter(name: str) -> WireAdapter:
    name = (name or "").lower().strip()
    if any(n in name for n in NEVER):
        raise NotConfigured(name, "idly has no licence for Reuters or Getty: never used")
    if name not in ADAPTERS:
        raise NotConfigured(name, "unknown agency")
    return ADAPTERS[name]()


__all__ = ["ADAPTERS", "AGENCY_CREDIT", "AGENCY_NAMES", "Candidate", "DENIED_CREDIT", "NotConfigured", "ORDER",
           "WireAdapter", "WireError", "get_adapter"]
