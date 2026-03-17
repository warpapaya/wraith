"""Radaris opt-out — manual due to account requirement."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wraith.brokers.base import BrokerBase, SubmissionResult, SubmissionStatus

if TYPE_CHECKING:
    from playwright.async_api import Page

    from wraith.config import Profile


class Radaris(BrokerBase):
    name = "radaris"
    opt_out_url = "https://radaris.com/page/how-to-remove"
    manual_only = True

    async def check_presence(self, profile: Profile, page: Page) -> bool | None:
        search_url = (
            f"https://radaris.com/p/"
            f"{profile.first_name}/{profile.last_name}/"
        ).lower()

        if not await self._safe_goto(page, search_url):
            return None

        try:
            results = await page.query_selector_all(".card-block, .person-item")
            return len(results) > 0
        except Exception:
            return None

    async def submit_opt_out(
        self, profile: Profile, page: Page, dry_run: bool = False
    ) -> SubmissionResult:
        if not await self._safe_goto(page, self.opt_out_url):
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes="Could not load Radaris removal page.",
            )

        if dry_run:
            return SubmissionResult(
                status=SubmissionStatus.DRY_RUN,
                notes="Navigated to Radaris removal instructions. Manual process required.",
            )

        return SubmissionResult(
            status=SubmissionStatus.MANUAL_REQUIRED,
            notes="Radaris requires account creation or email-based removal.",
            manual_steps=[
                f"Go to: {self.opt_out_url}",
                "Option 1: Create a free Radaris account, find your profile, and request removal.",
                "Option 2: Email privacy@radaris.com with your full name and request removal.",
                "Include the URL of your Radaris profile if possible.",
                "Allow 24-48 hours for processing.",
                "Verify removal after 48 hours.",
            ],
        )
