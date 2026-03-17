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
    manual_only = False

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
        if not await self._safe_goto(page, self.opt_out_url):
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes="Could not load ThatsThem opt-out page.",
            )

        try:
            # Fill in the opt-out form
            await self._safe_fill(
                page, 'input[name="firstName"], #first-name', profile.first_name
            )
            await self._safe_fill(
                page, 'input[name="lastName"], #last-name', profile.last_name
            )

            # Fill address fields if available
            if profile.addresses:
                addr = profile.addresses[0]
                await self._safe_fill(
                    page, 'input[name="street"], input[name="address"]', addr.street
                )
                await self._safe_fill(
                    page, 'input[name="city"]', addr.city
                )
                await self._safe_fill(
                    page, 'select[name="state"], input[name="state"]', addr.state
                )
                await self._safe_fill(
                    page, 'input[name="zip"], input[name="zipCode"]', addr.zip
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
                    notes="Opt-out form submitted.",
                )

            return SubmissionResult(
                status=SubmissionStatus.MANUAL_REQUIRED,
                notes="Could not submit form.",
                manual_steps=[
                    f"Go to: {self.opt_out_url}",
                    "Fill in your name and address details.",
                    "Submit the opt-out form.",
                ],
            )
        except Exception as e:
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes=f"Automation error: {e}",
            )
