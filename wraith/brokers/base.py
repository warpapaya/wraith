"""Abstract base class for data broker opt-out modules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

    from wraith.config import Profile


class SubmissionStatus(str, Enum):
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    MANUAL_REQUIRED = "manual_required"
    DRY_RUN = "dry_run"
    NOT_FOUND = "not_found"


@dataclass
class SubmissionResult:
    status: str
    notes: str = ""
    manual_steps: list[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return self.status in (SubmissionStatus.SUBMITTED, SubmissionStatus.NOT_FOUND)


class BrokerBase(ABC):
    """Base class all broker modules must implement."""

    name: str = "unknown"
    opt_out_url: str = ""
    manual_only: bool = False
    search_url: str = ""

    async def check_presence(self, profile: Profile, page: Page) -> bool | None:
        """Check if profile data is listed on this broker.

        Returns True if found, False if not found, None if unable to determine.
        """
        return None

    @abstractmethod
    async def submit_opt_out(
        self, profile: Profile, page: Page, dry_run: bool = False
    ) -> SubmissionResult:
        """Submit an opt-out request.

        If dry_run=True, navigate to the form but do NOT submit.
        """
        ...

    async def _safe_goto(self, page: Page, url: str, timeout: int = 30000) -> bool:
        """Navigate to a URL with timeout handling. Returns True on success."""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            return True
        except Exception:
            return False

    async def _safe_click(self, page: Page, selector: str, timeout: int = 10000) -> bool:
        """Click an element, returning False on timeout/missing element."""
        try:
            await page.click(selector, timeout=timeout)
            return True
        except Exception:
            return False

    async def _safe_fill(self, page: Page, selector: str, value: str, timeout: int = 10000) -> bool:
        """Fill an input field, returning False on timeout/missing element."""
        try:
            await page.fill(selector, value, timeout=timeout)
            return True
        except Exception:
            return False

    async def _safe_wait(self, page: Page, selector: str, timeout: int = 10000) -> bool:
        """Wait for a selector to appear. Returns False on timeout."""
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False
