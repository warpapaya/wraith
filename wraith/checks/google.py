"""Google removal URL generator and checklist."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus

from wraith.config import Profile, mask_name


@dataclass
class GoogleAction:
    title: str
    url: str
    description: str


def generate_removal_checklist(profile: Profile) -> list[GoogleAction]:
    """Generate a checklist of Google removal/privacy actions."""
    actions: list[GoogleAction] = []

    # Outdated content removal
    actions.append(GoogleAction(
        title="Remove Outdated Content",
        url="https://search.google.com/search-console/remove-outdated-content",
        description="Request removal of cached pages that have already been updated or deleted at source.",
    ))

    # Personal information removal request
    actions.append(GoogleAction(
        title="Personal Info Removal Request",
        url="https://support.google.com/websearch/troubleshooter/9685456",
        description=(
            "Request removal of personal info (phone, email, address) "
            "from Google Search results."
        ),
    ))

    # Google Search result removal (legal)
    actions.append(GoogleAction(
        title="Legal Removal Request",
        url="https://support.google.com/legal/troubleshooter/1114905",
        description="Request removal of content for legal reasons (defamation, copyright, etc.).",
    ))

    # Street View blur request
    actions.append(GoogleAction(
        title="Google Street View Blur Request",
        url="https://support.google.com/maps/answer/7011973",
        description="Request blurring of your home, face, or vehicle on Google Street View.",
    ))

    # Google Alerts for monitoring
    for name in profile.names[:2]:  # Primary + first alternate
        quoted = quote_plus(f'"{name}"')
        actions.append(GoogleAction(
            title=f"Google Alert: {mask_name(name)}",
            url=f"https://www.google.com/alerts#1:1:d:f:0:0:{quoted}",
            description=f"Set up a Google Alert to monitor when your name appears online.",
        ))

    # Phone alerts
    for phone in profile.phones[:1]:
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) >= 10:
            quoted = quote_plus(f'"{digits[-10:]}"')
            actions.append(GoogleAction(
                title="Google Alert: Phone Number",
                url=f"https://www.google.com/alerts#1:1:d:f:0:0:{quoted}",
                description="Monitor when your phone number appears in new search results.",
            ))

    # Address alerts
    for addr in profile.addresses[:1]:
        addr_str = f"{addr.street}, {addr.city}, {addr.state}"
        quoted = quote_plus(f'"{addr_str}"')
        actions.append(GoogleAction(
            title="Google Alert: Address",
            url=f"https://www.google.com/alerts#1:1:d:f:0:0:{quoted}",
            description="Monitor when your address appears in new search results.",
        ))

    # Google Activity controls
    actions.append(GoogleAction(
        title="Google Activity Controls",
        url="https://myactivity.google.com/activitycontrols",
        description="Review and manage what Google tracks about your activity.",
    ))

    # Google Dashboard
    actions.append(GoogleAction(
        title="Google Dashboard",
        url="https://myaccount.google.com/dashboard",
        description="Review all data Google has associated with your account.",
    ))

    return actions
