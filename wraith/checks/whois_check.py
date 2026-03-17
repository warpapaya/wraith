"""WHOIS privacy audit for domain names."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import whois


@dataclass
class WhoisResult:
    domain: str
    privacy_protected: bool
    exposed_fields: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)
    error: str = ""


# Fields that indicate personal information exposure
_SENSITIVE_FIELDS = [
    "name",
    "org",
    "address",
    "city",
    "state",
    "zipcode",
    "country",
    "emails",
    "registrant_name",
    "registrant_organization",
    "admin_name",
    "admin_email",
    "tech_name",
    "tech_email",
]

# Common privacy/proxy service keywords
_PRIVACY_KEYWORDS = [
    "privacy",
    "proxy",
    "whoisguard",
    "domains by proxy",
    "contact privacy",
    "redacted",
    "withheld",
    "data protected",
    "private",
    "identity protect",
    "perfect privacy",
    "whoisprivacycorp",
    "super privacy",
]


def check_domain(domain: str) -> WhoisResult:
    """Check WHOIS records for a single domain.

    Returns a WhoisResult indicating whether privacy protection is active
    and which fields (if any) expose personal data.
    """
    try:
        w = whois.whois(domain)
    except Exception as e:
        return WhoisResult(
            domain=domain,
            privacy_protected=False,
            error=f"WHOIS lookup failed: {e}",
        )

    if not w or not w.domain_name:
        return WhoisResult(
            domain=domain,
            privacy_protected=False,
            error="No WHOIS data returned.",
        )

    raw: dict[str, Any] = {}
    exposed: list[str] = []
    has_privacy = False

    for field_name in _SENSITIVE_FIELDS:
        value = getattr(w, field_name, None)
        if value is None:
            continue

        # Normalize to string for checking
        val_str = str(value).lower() if not isinstance(value, list) else " ".join(str(v).lower() for v in value)

        if not val_str or val_str in ("none", "null", ""):
            continue

        raw[field_name] = value

        # Check if the value indicates privacy protection
        if any(kw in val_str for kw in _PRIVACY_KEYWORDS):
            has_privacy = True
        else:
            exposed.append(field_name)

    # If any field mentions privacy service, treat as protected
    # unless there are also exposed fields
    privacy_protected = has_privacy and len(exposed) == 0

    return WhoisResult(
        domain=domain,
        privacy_protected=privacy_protected,
        exposed_fields=exposed,
        raw_data=raw,
    )


def check_all_domains(domains: list[str]) -> list[WhoisResult]:
    """Check WHOIS for multiple domains."""
    return [check_domain(d) for d in domains]
