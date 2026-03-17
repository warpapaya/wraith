"""MyLife opt-out — manual-only due to complex verification."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wraith.brokers.base import BrokerBase, SubmissionResult, SubmissionStatus

if TYPE_CHECKING:
    from playwright.async_api import Page

    from wraith.config import Profile


class MyLife(BrokerBase):
    name = "mylife"
    opt_out_url = "https://www.mylife.com/privacy/remove-my-information.pubview"
    manual_only = True

    async def check_presence(self, profile: Profile, page: Page) -> bool | None:
        search_url = (
            f"https://www.mylife.com/pub/"
            f"{profile.first_name.lower()}-{profile.last_name.lower()}"
        )
        if not await self._safe_goto(page, search_url):
            return None

        try:
            # Check if a profile page loaded
            title = await page.title()
            name_lower = profile.primary_name.lower()
            return name_lower in title.lower()
        except Exception:
            return None

    async def submit_opt_out(
        self, profile: Profile, page: Page, dry_run: bool = False
    ) -> SubmissionResult:
        if not await self._safe_goto(page, self.opt_out_url):
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes="Could not load MyLife removal page.",
            )

        if dry_run:
            return SubmissionResult(
                status=SubmissionStatus.DRY_RUN,
                notes="Navigated to removal page. Manual process required.",
            )

        return SubmissionResult(
            status=SubmissionStatus.MANUAL_REQUIRED,
            notes="MyLife requires a complex verification process that cannot be automated.",
            manual_steps=[
                f"Go to: {self.opt_out_url}",
                "You may need to create an account or call their customer service.",
                "Call MyLife at (888) 704-1900 to request removal.",
                "You may be asked to verify your identity.",
                "Request full profile deletion — not just suppression.",
                "Follow up after 2 weeks if the profile is still visible.",
            ],
        )
