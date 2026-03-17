"""PeopleFinder opt-out automation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wraith.brokers.base import BrokerBase, SubmissionResult, SubmissionStatus

if TYPE_CHECKING:
    from playwright.async_api import Page

    from wraith.config import Profile


class PeopleFinder(BrokerBase):
    name = "peoplefinder"
    opt_out_url = "https://www.peoplefinder.com/optout.php"
    manual_only = False

    async def check_presence(self, profile: Profile, page: Page) -> bool | None:
        return None

    async def submit_opt_out(
        self, profile: Profile, page: Page, dry_run: bool = False
    ) -> SubmissionResult:
        if not await self._safe_goto(page, self.opt_out_url):
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes="Could not load PeopleFinder opt-out page.",
            )

        try:
            # Fill in name fields
            await self._safe_fill(
                page, 'input[name="firstName"], #firstName', profile.first_name
            )
            await self._safe_fill(
                page, 'input[name="lastName"], #lastName', profile.last_name
            )

            # Fill email
            if profile.primary_email:
                await self._safe_fill(
                    page, 'input[type="email"], input[name="email"]',
                    profile.primary_email,
                )

            if dry_run:
                return SubmissionResult(
                    status=SubmissionStatus.DRY_RUN,
                    notes="Filled opt-out form. Would submit.",
                )

            submitted = await self._safe_click(
                page, 'button[type="submit"], input[type="submit"]'
            )

            if submitted:
                return SubmissionResult(
                    status=SubmissionStatus.SUBMITTED,
                    notes="Opt-out form submitted. Check email for verification.",
                    manual_steps=[
                        "Check your email for verification from PeopleFinder.",
                    ],
                )

            return SubmissionResult(
                status=SubmissionStatus.MANUAL_REQUIRED,
                notes="Could not submit form.",
                manual_steps=[
                    f"Go to: {self.opt_out_url}",
                    "Fill in your name and email.",
                    "Submit the opt-out form.",
                ],
            )
        except Exception as e:
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes=f"Automation error: {e}",
            )
