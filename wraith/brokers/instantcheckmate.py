"""InstantCheckMate opt-out automation.

Same parent company as TruthFinder (PeopleConnect).
Opt-out goes through PeopleConnect Suppression Center.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wraith.brokers.base import BrokerBase, SubmissionResult, SubmissionStatus

if TYPE_CHECKING:
    from playwright.async_api import Page

    from wraith.config import Profile

PEOPLECONNECT_URL = "https://suppression.peopleconnect.us/login"


class InstantCheckMate(BrokerBase):
    name = "instantcheckmate"
    opt_out_url = "https://www.instantcheckmate.com/opt-out/"
    manual_only = False

    async def check_presence(self, profile: Profile, page: Page) -> bool | None:
        return None

    async def submit_opt_out(
        self, profile: Profile, page: Page, dry_run: bool = False
    ) -> SubmissionResult:
        # Same PeopleConnect flow as TruthFinder — requires account creation.
        return SubmissionResult(
            status=SubmissionStatus.MANUAL_REQUIRED,
            notes="InstantCheckMate uses PeopleConnect Suppression Center — account required.",
            manual_steps=[
                f"Go to: {PEOPLECONNECT_URL}",
                "Create a free PeopleConnect account (or log in).",
                "Search for your name and select your record.",
                "Submit the suppression/opt-out request.",
                "This covers InstantCheckMate, TruthFinder, and other PeopleConnect brands.",
            ],
        )
