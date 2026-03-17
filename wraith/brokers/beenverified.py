"""BeenVerified opt-out automation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wraith.brokers.base import BrokerBase, SubmissionResult, SubmissionStatus

if TYPE_CHECKING:
    from playwright.async_api import Page

    from wraith.config import Profile


class BeenVerified(BrokerBase):
    name = "beenverified"
    opt_out_url = "https://www.beenverified.com/app/optout/search"
    manual_only = False

    async def check_presence(self, profile: Profile, page: Page) -> bool | None:
        return None  # Requires login to check

    async def submit_opt_out(
        self, profile: Profile, page: Page, dry_run: bool = False
    ) -> SubmissionResult:
        if not await self._safe_goto(page, self.opt_out_url):
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes="Could not load BeenVerified opt-out page.",
            )

        try:
            # Fill in first name
            await self._safe_fill(
                page,
                'input[name="firstName"], #firstName',
                profile.first_name,
            )

            # Fill in last name
            await self._safe_fill(
                page,
                'input[name="lastName"], #lastName',
                profile.last_name,
            )

            # Fill in state if available
            if profile.primary_state:
                await self._safe_fill(
                    page,
                    'select[name="state"], input[name="state"]',
                    profile.primary_state,
                )

            if dry_run:
                return SubmissionResult(
                    status=SubmissionStatus.DRY_RUN,
                    notes="Filled search form. Would search and submit opt-out.",
                )

            # Click search
            clicked = await self._safe_click(
                page, 'button[type="submit"], .btn-search, button:has-text("Search")'
            )

            if not clicked:
                return SubmissionResult(
                    status=SubmissionStatus.MANUAL_REQUIRED,
                    notes="Could not click search button.",
                    manual_steps=[
                        f"Go to: {self.opt_out_url}",
                        f"Search for: {profile.primary_name}",
                        "Select your record from the results.",
                        "Enter your email to complete the opt-out.",
                    ],
                )

            # Wait for results
            await page.wait_for_load_state("networkidle", timeout=15000)

            # Look for matching records and click opt-out
            opt_out_btn = await page.query_selector(
                'button:has-text("opt out"), a:has-text("opt out"), button:has-text("remove")'
            )

            if opt_out_btn:
                await opt_out_btn.click()
                await page.wait_for_load_state("domcontentloaded", timeout=10000)

                # Fill email if prompted
                if profile.primary_email:
                    await self._safe_fill(
                        page,
                        'input[type="email"], input[name="email"]',
                        profile.primary_email,
                    )
                    await self._safe_click(
                        page, 'button[type="submit"]'
                    )

                return SubmissionResult(
                    status=SubmissionStatus.SUBMITTED,
                    notes="Opt-out submitted. Check email for confirmation.",
                    manual_steps=[
                        "Check your email for a confirmation link from BeenVerified.",
                        "Click the link to finalize your opt-out.",
                    ],
                )

            return SubmissionResult(
                status=SubmissionStatus.MANUAL_REQUIRED,
                notes="Could not find opt-out button in results.",
                manual_steps=[
                    f"Go to: {self.opt_out_url}",
                    f"Search for: {profile.primary_name}",
                    "Select your record and follow the opt-out process.",
                ],
            )
        except Exception as e:
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes=f"Automation error: {e}",
            )
