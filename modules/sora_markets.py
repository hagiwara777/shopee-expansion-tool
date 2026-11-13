"""Sora market profiles (DEC-0183).

This is the one place that says which markets the Sora path handles and how
complete each market's own NG settings are.  It is read only by the Sora path
(screen, run, gate, guardrail evaluation).  Existing PH/SG-only modules keep
their own constants and are intentionally not widened here.

MY has no country dictionaries and no country counterfeit-brand list yet.  Until
the Owner finishes the MY NG settings, the gate never reports a pass for MY
(see ``MARKET_NG_INCOMPLETE_REASON``).
"""
from dataclasses import dataclass
import unicodedata


MARKET_NG_INCOMPLETE_REASON = "MARKET_NG_RULES_INCOMPLETE"


@dataclass(frozen=True)
class SoraMarket:
    code: str
    # prohibited_brands_xx.csv / risk_keywords_xx.csv exist for this market.
    country_dictionaries: bool
    # guardrails/brand_monitoring/counterfeit_xx.json exists for this market.
    country_counterfeit_list: bool
    # The existing SG body/accessory confirmation applies to this market.
    sg_body_safety: bool
    # False: the Owner has not finished this market's NG settings, so the gate
    # must not report a pass.
    ng_configured: bool
    # Existing-listing CSV duplicate check is available for this market.
    inventory_check: bool


SORA_MARKETS = {
    "SG": SoraMarket("SG", True, True, True, True, True),
    "PH": SoraMarket("PH", True, True, False, True, True),
    "MY": SoraMarket("MY", False, False, False, False, False),
}
# Screen order.  The first entry is the default market and must stay SG.
SORA_MARKET_ORDER = ("SG", "PH", "MY")


def normalize_sora_market(value):
    """Return the canonical Sora market code, or None when unsupported."""
    if not isinstance(value, str):
        return None
    code = unicodedata.normalize("NFKC", value).strip().upper()
    return code if code in SORA_MARKETS else None


def market_without_country_dictionaries(value):
    code = normalize_sora_market(value)
    return code is not None and not SORA_MARKETS[code].country_dictionaries


def market_ng_incomplete(value):
    code = normalize_sora_market(value)
    return code is not None and not SORA_MARKETS[code].ng_configured
