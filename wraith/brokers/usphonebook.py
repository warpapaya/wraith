"""USPhoneBook opt-out automation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wraith.brokers.base import BrokerBase, SubmissionResult, SubmissionStatus

if TYPE_CHECKING:
    from playwright.async_api import Page

    from wraith.config import Profile


class USPhoneBook(BrokerBase):
    name = "usphonebook"
    opt_out_url = "https://www.usphonebook.com/opt-out"
    manual_only = False
    requires_visible_browser = True

    async def check_presence(self, profile: Profile, page: Page) -> bool | None:
        if not profile.primary_phone:
            return None

        # Search by phone number
        phone_digits = "".join(c for c in profile.primary_phone if c.isdigit())
        url = f"https://www.usphonebook.com/{phone_digits}"

        if not await self._safe_goto(page, url):
            return None

        try:
            results = await page.query_selector_all(".result-item, .listing")
            return len(results) > 0
        except Exception:
            return None

    async def submit_opt_out(
        self, profile: Profile, page: Page, dry_run: bool = False
    ) -> SubmissionResult:
        if not await self._safe_goto(page, self.opt_out_url):
            return SubmissionResult(
                status=SubmissionStatus.MANUAL_REQUIRED,
                notes="Cloudflare blocked — use visible browser mode.",
                manual_steps=[
                    "Run: wraith scrub --broker usphonebook --visible",
                    "Or visit https://www.usphonebook.com/opt-out manually.",
                ],
            )

        try:
            # Fill phone number
            if profile.primary_phone:
                await self._safe_fill(
                    page, 'input[name="phone"], input[type="tel"], #phone',
                    profile.primary_phone,
                )

            # Fill name
            await self._safe_fill(
                page, 'input[name="firstName"], input[name="name"]',
                profile.primary_name,
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
                    notes="Opt-out submitted.",
                )

            return SubmissionResult(
                status=SubmissionStatus.MANUAL_REQUIRED,
                notes="Could not submit form.",
                manual_steps=[
                    f"Go to: {self.opt_out_url}",
                    "Enter your phone number and name.",
                    "Submit the opt-out request.",
                ],
            )
        except Exception as e:
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes=f"Automation error: {e}",
            )
