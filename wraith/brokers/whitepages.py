"""Whitepages opt-out automation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wraith.brokers.base import BrokerBase, SubmissionResult, SubmissionStatus

if TYPE_CHECKING:
    from playwright.async_api import Page

    from wraith.config import Profile


class Whitepages(BrokerBase):
    name = "whitepages"
    opt_out_url = "https://www.whitepages.com/suppression-requests"
    manual_only = False

    async def check_presence(self, profile: Profile, page: Page) -> bool | None:
        url = (
            f"https://www.whitepages.com/name/"
            f"{profile.first_name}-{profile.last_name}/"
            f"{profile.primary_city}-{profile.primary_state}"
        ).lower().replace(" ", "-")

        if not await self._safe_goto(page, url):
            return None

        try:
            results = await page.query_selector_all('[data-testid="person-link"]')
            return len(results) > 0
        except Exception:
            return None

    async def submit_opt_out(
        self, profile: Profile, page: Page, dry_run: bool = False
    ) -> SubmissionResult:
        if not await self._safe_goto(page, self.opt_out_url):
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes="Could not load Whitepages suppression page.",
            )

        # Navigate to the opt-out form
        try:
            # Search for the listing first
            search_url = (
                f"https://www.whitepages.com/name/"
                f"{profile.first_name}-{profile.last_name}/"
                f"{profile.primary_city}-{profile.primary_state}"
            ).lower().replace(" ", "-")

            if not await self._safe_goto(page, search_url):
                return SubmissionResult(
                    status=SubmissionStatus.FAILED,
                    notes="Could not load search results.",
                )

            if dry_run:
                return SubmissionResult(
                    status=SubmissionStatus.DRY_RUN,
                    notes="Navigated to search results. Would proceed with removal.",
                )

            # Whitepages requires phone verification — mark manual
            return SubmissionResult(
                status=SubmissionStatus.MANUAL_REQUIRED,
                notes="Phone verification required to complete removal.",
                manual_steps=[
                    f"Go to: {self.opt_out_url}",
                    f"Search for your name: {profile.primary_name}",
                    "Find your listing and click 'Remove me'.",
                    "Enter your phone number for verification.",
                    "Answer the automated verification call.",
                    "Confirm removal.",
                ],
            )
        except Exception as e:
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes=f"Automation error: {e}",
            )
