"""ThatsThem opt-out automation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wraith.brokers.base import BrokerBase, SubmissionResult, SubmissionStatus

if TYPE_CHECKING:
    from playwright.async_api import Page

    from wraith.config import Profile


class ThatsThem(BrokerBase):
    name = "thatsthem"
    opt_out_url = "https://thatsthem.com/optout"
    manual_only = True

    async def check_presence(self, profile: Profile, page: Page) -> bool | None:
        search_url = (
            f"https://thatsthem.com/name/"
            f"{profile.first_name}-{profile.last_name}/"
            f"{profile.primary_city}-{profile.primary_state}"
        ).replace(" ", "-")

        if not await self._safe_goto(page, search_url):
            return None

        try:
            results = await page.query_selector_all(".ThatsThem-record, .result-item")
            return len(results) > 0
        except Exception:
            return None

    async def submit_opt_out(
        self, profile: Profile, page: Page, dry_run: bool = False
    ) -> SubmissionResult:
        # Site frequently times out and blocks automation. Manual opt-out only.
        return SubmissionResult(
            status=SubmissionStatus.MANUAL_REQUIRED,
            notes="ThatsThem requires manual opt-out (site blocks automation).",
            manual_steps=[
                "Go to: https://thatsthem.com/optout",
                "Fill in your name and address details.",
                "Submit the opt-out form manually.",
            ],
        )
