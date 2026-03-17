"""Load and save ~/.wraith/config.toml."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli_w

CONFIG_DIR = Path.home() / ".wraith"
CONFIG_PATH = CONFIG_DIR / "config.toml"


@dataclass
class Address:
    street: str
    city: str
    state: str
    zip: str

    def to_dict(self) -> dict[str, str]:
        return {"street": self.street, "city": self.city, "state": self.state, "zip": self.zip}

    def short(self) -> str:
        return f"{self.city}, {self.state} {self.zip}"


@dataclass
class Profile:
    names: list[str] = field(default_factory=list)
    dob: str = ""
    phones: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    addresses: list[Address] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)

    @property
    def primary_name(self) -> str:
        return self.names[0] if self.names else ""

    @property
    def first_name(self) -> str:
        parts = self.primary_name.split()
        return parts[0] if parts else ""

    @property
    def last_name(self) -> str:
        parts = self.primary_name.split()
        return parts[-1] if len(parts) > 1 else ""

    @property
    def primary_state(self) -> str:
        return self.addresses[0].state if self.addresses else ""

    @property
    def primary_city(self) -> str:
        return self.addresses[0].city if self.addresses else ""

    @property
    def primary_email(self) -> str:
        return self.emails[0] if self.emails else ""

    @property
    def primary_phone(self) -> str:
        return self.phones[0] if self.phones else ""


@dataclass
class Settings:
    headless: bool = True
    resubmit_days: int = 90
    confirm_wait_days: int = 30
    db_path: str = "~/.wraith/state.db"

    @property
    def resolved_db_path(self) -> Path:
        return Path(self.db_path).expanduser()


@dataclass
class ApiKeys:
    hibp: str = ""


@dataclass
class WraithConfig:
    profile: Profile = field(default_factory=Profile)
    api_keys: ApiKeys = field(default_factory=ApiKeys)
    settings: Settings = field(default_factory=Settings)


def _parse_addresses(raw: list[dict[str, str]]) -> list[Address]:
    return [Address(**a) for a in raw]


def load_config() -> WraithConfig:
    """Load config from ~/.wraith/config.toml. Returns defaults if missing."""
    if not CONFIG_PATH.exists():
        return WraithConfig()

    with open(CONFIG_PATH, "rb") as f:
        data = tomllib.load(f)

    prof = data.get("profile", {})
    profile = Profile(
        names=prof.get("names", []),
        dob=prof.get("dob", ""),
        phones=prof.get("phones", []),
        emails=prof.get("emails", []),
        addresses=_parse_addresses(prof.get("addresses", [])),
        domains=prof.get("domains", []),
    )

    keys_raw = data.get("api_keys", {})
    api_keys = ApiKeys(hibp=keys_raw.get("hibp", ""))

    sett_raw = data.get("settings", {})
    settings = Settings(
        headless=sett_raw.get("headless", True),
        resubmit_days=sett_raw.get("resubmit_days", 90),
        confirm_wait_days=sett_raw.get("confirm_wait_days", 30),
        db_path=sett_raw.get("db_path", "~/.wraith/state.db"),
    )

    return WraithConfig(profile=profile, api_keys=api_keys, settings=settings)


def save_config(cfg: WraithConfig) -> None:
    """Write config to ~/.wraith/config.toml."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {
        "profile": {
            "names": cfg.profile.names,
            "dob": cfg.profile.dob,
            "phones": cfg.profile.phones,
            "emails": cfg.profile.emails,
            "addresses": [a.to_dict() for a in cfg.profile.addresses],
            "domains": cfg.profile.domains,
        },
        "api_keys": {
            "hibp": cfg.api_keys.hibp,
        },
        "settings": {
            "headless": cfg.settings.headless,
            "resubmit_days": cfg.settings.resubmit_days,
            "confirm_wait_days": cfg.settings.confirm_wait_days,
            "db_path": cfg.settings.db_path,
        },
    }

    with open(CONFIG_PATH, "wb") as f:
        tomli_w.dump(data, f)


# --- Masking utilities ---

def mask_name(name: str) -> str:
    """Mask a name: 'Peter Clark' -> 'P***r C***k'."""
    parts = name.split()
    masked: list[str] = []
    for part in parts:
        if len(part) <= 2:
            masked.append(part[0] + "*")
        else:
            masked.append(part[0] + "*" * (len(part) - 2) + part[-1])
    return " ".join(masked)


def mask_email(email: str) -> str:
    """Mask an email: 'user@example.com' -> 'u***r@e*****e.com'."""
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    domain_parts = domain.split(".", 1)
    masked_local = local[0] + "***" + local[-1] if len(local) > 1 else local[0] + "***"
    masked_domain = domain_parts[0][0] + "*" * (len(domain_parts[0]) - 2) + domain_parts[0][-1] if len(domain_parts[0]) > 1 else domain_parts[0]
    suffix = "." + domain_parts[1] if len(domain_parts) > 1 else ""
    return f"{masked_local}@{masked_domain}{suffix}"


def mask_phone(phone: str) -> str:
    """Mask a phone: '+19122884891' -> '+1 (***) ***-4891'."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 10:
        return f"+{digits[0]} (***) ***-{digits[-4:]}"
    return "***-" + digits[-4:] if len(digits) >= 4 else "****"


def mask_address(addr: Address) -> str:
    """Mask an address, keeping city/state."""
    return f"***, {addr.city}, {addr.state} {addr.zip}"
