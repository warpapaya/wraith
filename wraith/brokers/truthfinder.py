"""TruthFinder opt-out automation.

TruthFinder redirects opt-outs to PeopleConnect Suppression Center.
Requires creating a PeopleConnect account to submit removal requests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wraith.brokers.base import BrokerBase, SubmissionResult, SubmissionStatus

if TYPE_CHECKING:
    from playwright.async_api import Page

    from wraith.config import Profile

PEOPLECONNECT_URL = "https://suppression.peopleconnect.us/login"


class TruthFinder(BrokerBase):
    name = "truthfinder"
    opt_out_url = "https://www.truthfinder.com/opt-out/"
    manual_only = False

    async def check_presence(self, profile: Profile, page: Page) -> bool | None:
        return None

    async def submit_opt_out(
        self, profile: Profile, page: Page, dry_run: bool = False
    ) -> SubmissionResult:
        # TruthFinder opt-out redirects to PeopleConnect Suppression Center,
        # which requires account creation. Mark as manual with clear instructions.
        return SubmissionResult(
            status=SubmissionStatus.MANUAL_REQUIRED,
            notes="TruthFinder uses PeopleConnect Suppression Center — account required.",
            manual_steps=[
                f"Go to: {PEOPLECONNECT_URL}",
                "Create a free PeopleConnect account (or log in).",
                "Search for your name and select your record.",
                "Submit the suppression/opt-out request.",
                "This covers TruthFinder, InstantCheckMate, and other PeopleConnect brands.",
            ],
        )
