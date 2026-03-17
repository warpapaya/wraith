"""Spokeo opt-out automation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wraith.brokers.base import BrokerBase, SubmissionResult, SubmissionStatus

if TYPE_CHECKING:
    from playwright.async_api import Page

    from wraith.config import Profile


class Spokeo(BrokerBase):
    name = "spokeo"
    opt_out_url = "https://www.spokeo.com/optout"
    manual_only = False

    async def check_presence(self, profile: Profile, page: Page) -> bool | None:
        search_url = (
            f"https://www.spokeo.com/"
            f"{profile.first_name}-{profile.last_name}"
        ).lower()

        if not await self._safe_goto(page, search_url):
            return None

        try:
            # Check for result listings
            results = await page.query_selector_all(".result-item, .listing")
            return len(results) > 0
        except Exception:
            return None

    async def submit_opt_out(
        self, profile: Profile, page: Page, dry_run: bool = False
    ) -> SubmissionResult:
        if not await self._safe_goto(page, self.opt_out_url):
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes="Could not load Spokeo opt-out page.",
            )

        try:
            # Spokeo opt-out requires entering the listing URL
            # First find the listing
            search_url = (
                f"https://www.spokeo.com/"
                f"{profile.first_name}-{profile.last_name}"
            ).lower()

            listing_url = search_url  # Use search URL as starting point

            # Navigate to opt-out page and fill the form
            if not await self._safe_goto(page, self.opt_out_url):
                return SubmissionResult(
                    status=SubmissionStatus.FAILED,
                    notes="Could not load opt-out form.",
                )

            # Fill in the listing URL
            filled = await self._safe_fill(
                page, 'input[name="url"], input[type="url"], input[name="listing_url"]',
                listing_url,
            )

            # Fill in email
            if profile.primary_email:
                await self._safe_fill(
                    page, 'input[name="email"], input[type="email"]',
                    profile.primary_email,
                )

            if dry_run:
                return SubmissionResult(
                    status=SubmissionStatus.DRY_RUN,
                    notes="Filled opt-out form. Would submit.",
                )

            if not filled:
                return SubmissionResult(
                    status=SubmissionStatus.MANUAL_REQUIRED,
                    notes="Could not find opt-out form fields. Site may have changed.",
                    manual_steps=[
                        f"Go to: {self.opt_out_url}",
                        f"Search for your listing at: {search_url}",
                        "Copy the URL of your listing.",
                        "Paste it into the opt-out form.",
                        "Enter your email address.",
                        "Submit and check email for verification link.",
                    ],
                )

            # Submit the form
            submitted = await self._safe_click(
                page, 'button[type="submit"], input[type="submit"]'
            )

            if submitted:
                return SubmissionResult(
                    status=SubmissionStatus.SUBMITTED,
                    notes="Opt-out submitted. Check email for verification.",
                    manual_steps=[
                        "Check your email for a verification link from Spokeo.",
                        "Click the link to confirm your opt-out request.",
                    ],
                )

            return SubmissionResult(
                status=SubmissionStatus.MANUAL_REQUIRED,
                notes="Could not submit form automatically.",
                manual_steps=[
                    f"Go to: {self.opt_out_url}",
                    "Complete the opt-out form manually.",
                ],
            )
        except Exception as e:
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes=f"Automation error: {e}",
            )
