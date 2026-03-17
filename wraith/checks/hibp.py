"""HaveIBeenPwned v3 API integration."""

from __future__ import annotations

from typing import Any

import httpx

HIBP_API_BASE = "https://haveibeenpwned.com/api/v3"
HIBP_USER_AGENT = "wraith-privacy-tool"


async def check_breaches(
    email: str, api_key: str, timeout: float = 15.0
) -> list[dict[str, Any]]:
    """Check a single email against the HIBP breach database.

    Requires a valid HIBP API key (https://haveibeenpwned.com/API/Key).

    Returns a list of breach dicts, each with keys like:
        Name, Title, Domain, BreachDate, DataClasses, etc.
    Returns empty list if no breaches found.
    Raises httpx.HTTPStatusError on API errors.
    """
    headers = {
        "hibp-api-key": api_key,
        "user-agent": HIBP_USER_AGENT,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(
            f"{HIBP_API_BASE}/breachedaccount/{email}",
            headers=headers,
            params={"truncateResponse": "false"},
        )

        if resp.status_code == 404:
            return []  # No breaches found
        if resp.status_code == 401:
            raise PermissionError(
                "Invalid HIBP API key. Get one at https://haveibeenpwned.com/API/Key"
            )
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after", "2")
            raise RuntimeError(
                f"HIBP rate limited. Retry after {retry_after} seconds."
            )

        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]


async def check_all_emails(
    emails: list[str], api_key: str
) -> dict[str, list[dict[str, Any]]]:
    """Check multiple emails, returning {email: [breaches]}.

    Adds a 1.6s delay between requests to respect HIBP rate limits.
    """
    import asyncio

    results: dict[str, list[dict[str, Any]]] = {}

    for i, email in enumerate(emails):
        if i > 0:
            await asyncio.sleep(1.6)  # HIBP rate limit: ~1 req per 1.5s
        try:
            breaches = await check_breaches(email, api_key)
            results[email] = breaches
        except Exception as e:
            results[email] = [{"Name": f"ERROR: {e}", "BreachDate": "", "DataClasses": []}]

    return results


def format_hibp_instructions() -> str:
    """Return instructions for obtaining an HIBP API key."""
    return (
        "To use breach monitoring, you need a HaveIBeenPwned API key.\n\n"
        "1. Go to https://haveibeenpwned.com/API/Key\n"
        "2. Purchase an API key (supports the service)\n"
        "3. Run: wraith init  (and enter the key when prompted)\n"
        "   Or edit ~/.wraith/config.toml and set:\n"
        "   [api_keys]\n"
        '   hibp = "your-api-key-here"'
    )
