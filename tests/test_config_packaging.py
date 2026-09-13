from pathlib import Path
import tomllib

from packaging.requirements import Requirement
from playwright_stealth import Stealth
import pytest

from wraith.config import mask_email


@pytest.mark.parametrize("value", ["@example.com", "@", "user@", "user@.com", "", "not-an-email"])
def test_malformed_email_masks_safely(value):
    assert mask_email(value) == "***"


@pytest.mark.parametrize("value, expected", [("user@example.com", "u***r@e*****e.com"), ("a@b.io", "a***@b.io")])
def test_valid_email_masking_unchanged(value, expected):
    assert mask_email(value) == expected


def test_stealth_requirement_excludes_incompatible_v1():
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    req = next(Requirement(r) for r in project["project"]["dependencies"] if r.startswith("playwright-stealth"))
    assert "1.0.6" not in req.specifier
    assert "2.0.0" in req.specifier
    assert callable(Stealth().apply_stealth_async)
