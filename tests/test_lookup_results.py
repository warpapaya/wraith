import asyncio
from io import StringIO

import pytest
from rich.console import Console
from typer.testing import CliRunner

from wraith import audit, cli
from wraith.checks import hibp, whois_check
from wraith.config import ApiKeys, Profile, Settings, WraithConfig
from wraith.db import WraithDB

EMAIL = "synthetic@example.invalid"
DOMAIN = "example.invalid"
OLD = {"Name": "PriorBreach", "BreachDate": "2000-01-01", "DataClasses": ["Passwords"]}
ERROR = {"Name": "ERROR: unavailable", "DataClasses": []}


@pytest.fixture
def configured(tmp_path, monkeypatch):
    cfg = WraithConfig(Profile(names=["Synthetic Person"], emails=[EMAIL], domains=[DOMAIN]), ApiKeys("synthetic-key"), Settings(db_path=str(tmp_path / "state.db")))
    monkeypatch.setattr(cli, "_get_config", lambda: cfg)
    return cfg


async def with_db(cfg, callback):
    db = WraithDB(cfg.settings.resolved_db_path)
    await db.connect()
    try:
        return await callback(db)
    finally:
        await db.close()


@pytest.mark.parametrize("entry", ["audit", "cli"])
@pytest.mark.parametrize("lookup", [[ERROR], [{"Name": "PartialNewBreach"}, ERROR], [], [{"Name": "NewBreach"}]])
def test_hibp_preserves_on_failure_replaces_on_success(configured, monkeypatch, entry, lookup):
    async def fake(*args):
        return {EMAIL: lookup}
    monkeypatch.setattr(hibp, "check_all_emails", fake)
    asyncio.run(with_db(configured, lambda db: db.save_breach_results(EMAIL, [OLD])))
    if entry == "audit":
        asyncio.run(with_db(configured, lambda db: audit.run_hibp_check(configured, db)))
    else:
        result = CliRunner().invoke(cli.app, ["hibp"])
        assert result.exit_code == 0, result.output
    rows = asyncio.run(with_db(configured, lambda db: db.get_breach_results(EMAIL)))
    expected = ["PriorBreach"] if ERROR in lookup else [b["Name"] for b in lookup]
    assert [r["breach_name"] for r in rows] == expected


@pytest.mark.parametrize("entry", ["audit", "cli"])
@pytest.mark.parametrize("error", ["Lookup failed", ""])
def test_whois_preserves_only_on_failure(configured, monkeypatch, entry, error):
    result = whois_check.WhoisResult(DOMAIN, False, ["name"], error=error)
    monkeypatch.setattr(whois_check, "check_all_domains", lambda domains: [result])
    asyncio.run(with_db(configured, lambda db: db.save_whois_result(DOMAIN, True, [])))
    if entry == "audit":
        asyncio.run(with_db(configured, lambda db: audit.run_whois_check(configured, db)))
    else:
        invoked = CliRunner().invoke(cli.app, ["whois"])
        assert invoked.exit_code == 0, invoked.output
    rows = asyncio.run(with_db(configured, lambda db: db.get_whois_results()))
    assert bool(rows[0]["privacy_protected"]) is bool(error)
    assert rows[0]["exposed_fields"] == ('[]' if error else '["name"]')


@pytest.mark.parametrize("entry", ["audit", "cli"])
@pytest.mark.parametrize("kind", ["hibp", "whois"])
def test_lookup_failure_is_rendered_unavailable(configured, monkeypatch, entry, kind):
    async def fake(*args):
        return {EMAIL: [ERROR]}
    wr = whois_check.WhoisResult(DOMAIN, False, error="Lookup failed")
    monkeypatch.setattr(hibp, "check_all_emails", fake)
    monkeypatch.setattr(whois_check, "check_all_domains", lambda domains: [wr])
    output = StringIO()
    monkeypatch.setattr(audit if entry == "audit" else cli, "console", Console(file=output, width=140, color_system=None))
    if entry == "audit":
        audit.display_audit_results(audit.AuditResult(breach_results={EMAIL: [ERROR]} if kind == "hibp" else {}, whois_results=[wr] if kind == "whois" else []))
    else:
        result = CliRunner().invoke(cli.app, [kind])
        assert result.exit_code == 0, result.output
    text = output.getvalue()
    assert "unavailable" in text.lower()
    assert "No breaches found" not in text
    assert "1 breach(es) found" not in text
    assert "Change passwords" not in text
