"""Intelius opt-out automation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wraith.brokers.base import BrokerBase, SubmissionResult, SubmissionStatus

if TYPE_CHECKING:
    from playwright.async_api import Page

    from wraith.config import Profile


class Intelius(BrokerBase):
    name = "intelius"
    opt_out_url = "https://www.intelius.com/opt-out/submit/"
    manual_only = False

    async def check_presence(self, profile: Profile, page: Page) -> bool | None:
        return None  # Requires account to check

    async def submit_opt_out(
        self, profile: Profile, page: Page, dry_run: bool = False
    ) -> SubmissionResult:
        if not await self._safe_goto(page, self.opt_out_url):
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes="Could not load Intelius opt-out page.",
            )

        try:
            # Fill in the search form
            await self._safe_fill(
                page,
                'input[name="firstName"], #firstName',
                profile.first_name,
            )
            await self._safe_fill(
                page,
                'input[name="lastName"], #lastName',
                profile.last_name,
            )

            if profile.primary_state:
                await self._safe_fill(
                    page,
                    'select[name="state"], input[name="state"]',
                    profile.primary_state,
                )

            if dry_run:
                return SubmissionResult(
                    status=SubmissionStatus.DRY_RUN,
                    notes="Filled opt-out form. Would submit.",
                )

            # Submit search
            clicked = await self._safe_click(
                page, 'button[type="submit"], input[type="submit"]'
            )

            if not clicked:
                return SubmissionResult(
                    status=SubmissionStatus.MANUAL_REQUIRED,
                    notes="Could not submit search form.",
                    manual_steps=[
                        f"Go to: {self.opt_out_url}",
                        f"Search for: {profile.primary_name}",
                        "Select your record and complete the opt-out.",
                    ],
                )

            await page.wait_for_load_state("networkidle", timeout=15000)

            # Look for matching result to select
            result = await page.query_selector(
                '.record-card, .result-item, a:has-text("Select")'
            )

            if result:
                await result.click()
                await page.wait_for_load_state("domcontentloaded", timeout=10000)

                # Fill email
                if profile.primary_email:
                    await self._safe_fill(
                        page, 'input[type="email"]', profile.primary_email
                    )
                    await self._safe_click(page, 'button[type="submit"]')

                return SubmissionResult(
                    status=SubmissionStatus.SUBMITTED,
                    notes="Opt-out submitted. Check email for verification.",
                    manual_steps=[
                        "Check your email for verification from Intelius.",
                        "Click the confirmation link.",
                    ],
                )

            return SubmissionResult(
                status=SubmissionStatus.MANUAL_REQUIRED,
                notes="No matching records found or page layout changed.",
                manual_steps=[
                    f"Go to: {self.opt_out_url}",
                    f"Search for: {profile.primary_name}",
                    "Follow the on-screen instructions to opt out.",
                ],
            )
        except Exception as e:
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes=f"Automation error: {e}",
            )
