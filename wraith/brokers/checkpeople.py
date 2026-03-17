"""CheckPeople opt-out automation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wraith.brokers.base import BrokerBase, SubmissionResult, SubmissionStatus

if TYPE_CHECKING:
    from playwright.async_api import Page

    from wraith.config import Profile


class CheckPeople(BrokerBase):
    name = "checkpeople"
    opt_out_url = "https://www.checkpeople.com/opt-out"
    manual_only = False

    async def check_presence(self, profile: Profile, page: Page) -> bool | None:
        return None

    async def submit_opt_out(
        self, profile: Profile, page: Page, dry_run: bool = False
    ) -> SubmissionResult:
        if not await self._safe_goto(page, self.opt_out_url):
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes="Could not load CheckPeople opt-out page.",
            )

        try:
            # Fill out the opt-out form
            await self._safe_fill(
                page, 'input[name="firstName"], #firstName', profile.first_name
            )
            await self._safe_fill(
                page, 'input[name="lastName"], #lastName', profile.last_name
            )

            if profile.primary_email:
                await self._safe_fill(
                    page, 'input[type="email"], input[name="email"]',
                    profile.primary_email,
                )

            if profile.primary_state:
                await self._safe_fill(
                    page, 'select[name="state"], input[name="state"]',
                    profile.primary_state,
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
                    notes="Opt-out submitted.",
                    manual_steps=[
                        "Check email for any verification required.",
                    ],
                )

            return SubmissionResult(
                status=SubmissionStatus.MANUAL_REQUIRED,
                notes="Could not submit form.",
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
