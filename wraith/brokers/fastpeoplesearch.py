"""FastPeopleSearch opt-out automation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wraith.brokers.base import BrokerBase, SubmissionResult, SubmissionStatus

if TYPE_CHECKING:
    from playwright.async_api import Page

    from wraith.config import Profile


class FastPeopleSearch(BrokerBase):
    name = "fastpeoplesearch"
    opt_out_url = "https://www.fastpeoplesearch.com/removal"
    search_url = "https://www.fastpeoplesearch.com/name/{name}_{state}"
    manual_only = False
    requires_visible_browser = True

    async def check_presence(self, profile: Profile, page: Page) -> bool | None:
        name_slug = profile.primary_name.lower().replace(" ", "-")
        state_slug = profile.primary_state.lower()
        url = f"https://www.fastpeoplesearch.com/name/{name_slug}_{state_slug}"

        if not await self._safe_goto(page, url):
            return None

        # Look for result cards containing the name
        try:
            results = await page.query_selector_all(".card.card-block")
            return len(results) > 0
        except Exception:
            return None

    async def submit_opt_out(
        self, profile: Profile, page: Page, dry_run: bool = False
    ) -> SubmissionResult:
        # FastPeopleSearch uses Cloudflare — headless browsers are blocked.
        # Check if we appear to be blocked (page won't load properly headless).
        if not await self._safe_goto(page, self.opt_out_url):
            return SubmissionResult(
                status=SubmissionStatus.MANUAL_REQUIRED,
                notes="Cloudflare blocked — use visible browser mode.",
                manual_steps=[
                    "Run: wraith scrub --broker fastpeoplesearch --visible",
                    "Or visit https://www.fastpeoplesearch.com/removal manually.",
                ],
            )

        # Step 1: Search for the record on the removal page
        name_slug = profile.primary_name.lower().replace(" ", "-")
        state_slug = profile.primary_state.lower()
        search_url = f"https://www.fastpeoplesearch.com/name/{name_slug}_{state_slug}"

        if not await self._safe_goto(page, search_url):
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes="Could not load search results.",
            )

        # Step 2: Find matching record and click remove
        try:
            remove_links = await page.query_selector_all('a[href*="/removal"]')
            if not remove_links:
                return SubmissionResult(
                    status=SubmissionStatus.NOT_FOUND,
                    notes="No matching records found to remove.",
                )

            if dry_run:
                return SubmissionResult(
                    status=SubmissionStatus.DRY_RUN,
                    notes=f"Found {len(remove_links)} potential records. Would click remove.",
                )

            # Click the first removal link
            await remove_links[0].click()
            await page.wait_for_load_state("domcontentloaded", timeout=15000)

            return SubmissionResult(
                status=SubmissionStatus.SUBMITTED,
                notes="Removal requested. Check email for verification link.",
                manual_steps=[
                    "Check your email for a verification link from FastPeopleSearch.",
                    "Click the verification link to confirm removal.",
                    "Removal typically takes 24-48 hours after confirmation.",
                ],
            )
        except Exception as e:
            return SubmissionResult(
                status=SubmissionStatus.FAILED,
                notes=f"Automation error: {e}",
            )
