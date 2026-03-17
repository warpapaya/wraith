"""Orchestrates full audit runs across all brokers and checks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from playwright.async_api import async_playwright

from wraith.brokers import ALL_BROKERS, BrokerBase
from wraith.checks import hibp as hibp_check
from wraith.checks import whois_check
from wraith.config import WraithConfig, mask_email
from wraith.console import console
from wraith.db import WraithDB

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID
from rich.table import Table


@dataclass
class AuditResult:
    broker_results: dict[str, str | None] = field(default_factory=dict)
    breach_results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    whois_results: list[whois_check.WhoisResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


async def run_broker_checks(
    cfg: WraithConfig, headless: bool = True
) -> dict[str, str | None]:
    """Check presence across all data brokers.

    Returns {broker_name: "found" | "not_found" | "unknown" | "error: ..."}
    """
    results: dict[str, str | None] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("Checking data brokers...", total=len(ALL_BROKERS))

            for broker_cls in ALL_BROKERS:
                broker = broker_cls()
                progress.update(task, description=f"Checking {broker.name}...")

                if broker.manual_only:
                    results[broker.name] = "unknown"
                    progress.advance(task)
                    continue

                ctx = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                )
                page = await ctx.new_page()

                try:
                    presence = await broker.check_presence(cfg.profile, page)
                    if presence is True:
                        results[broker.name] = "found"
                    elif presence is False:
                        results[broker.name] = "not_found"
                    else:
                        results[broker.name] = "unknown"
                except Exception as e:
                    results[broker.name] = f"error: {e}"
                finally:
                    await ctx.close()

                progress.advance(task)

        await browser.close()

    return results


async def run_hibp_check(
    cfg: WraithConfig, db: WraithDB
) -> dict[str, list[dict[str, Any]]]:
    """Run HIBP breach check across all configured emails."""
    if not cfg.api_keys.hibp:
        console.print(
            "[yellow]No HIBP API key configured.[/yellow]\n"
            + hibp_check.format_hibp_instructions()
        )
        return {}

    results = await hibp_check.check_all_emails(
        cfg.profile.emails, cfg.api_keys.hibp
    )

    # Save to DB
    for email, breaches in results.items():
        # Filter out error entries for DB storage
        real_breaches = [b for b in breaches if not b.get("Name", "").startswith("ERROR:")]
        await db.save_breach_results(email, real_breaches)

    return results


async def run_whois_check(
    cfg: WraithConfig, db: WraithDB
) -> list[whois_check.WhoisResult]:
    """Run WHOIS privacy check across all configured domains."""
    if not cfg.profile.domains:
        return []

    results = whois_check.check_all_domains(cfg.profile.domains)

    # Save to DB
    for r in results:
        await db.save_whois_result(r.domain, r.privacy_protected, r.exposed_fields)

    return results


async def run_full_audit(cfg: WraithConfig, db: WraithDB) -> AuditResult:
    """Run complete audit: brokers + HIBP + WHOIS."""
    result = AuditResult()

    console.print("\n[bold]Running full privacy audit...[/bold]\n")

    # Run broker checks
    console.rule("[bold blue]Data Broker Checks[/bold blue]")
    result.broker_results = await run_broker_checks(cfg, headless=cfg.settings.headless)

    # Run HIBP
    console.rule("[bold blue]Breach Monitoring[/bold blue]")
    result.breach_results = await run_hibp_check(cfg, db)

    # Run WHOIS
    console.rule("[bold blue]WHOIS Privacy Audit[/bold blue]")
    result.whois_results = await run_whois_check(cfg, db)

    return result


def display_audit_results(result: AuditResult) -> None:
    """Display audit results as Rich tables."""
    console.print()

    # Broker results table
    broker_table = Table(title="Data Broker Exposure", show_lines=True)
    broker_table.add_column("Source", style="bold")
    broker_table.add_column("Status")
    broker_table.add_column("Action Needed")

    for broker_name, status in sorted(result.broker_results.items()):
        if status == "found":
            style = "red"
            action = "Opt-out recommended"
        elif status == "not_found":
            style = "green"
            action = "None"
        elif status == "unknown":
            style = "blue"
            action = "Manual check needed"
        else:
            style = "yellow"
            action = "Check failed — retry"

        broker_table.add_row(broker_name, f"[{style}]{status}[/{style}]", action)

    console.print(broker_table)

    # Breach results
    if result.breach_results:
        console.print()
        breach_table = Table(title="Breach Exposure", show_lines=True)
        breach_table.add_column("Email", style="bold")
        breach_table.add_column("Breaches Found")
        breach_table.add_column("Action Needed")

        for email, breaches in result.breach_results.items():
            masked = mask_email(email)
            count = len(breaches)
            if count > 0:
                style = "red" if count > 3 else "yellow"
                names = ", ".join(b.get("Name", "?")[:20] for b in breaches[:5])
                if count > 5:
                    names += f" (+{count - 5} more)"
                action = "Change passwords, enable 2FA"
            else:
                style = "green"
                names = "None"
                action = "None"

            breach_table.add_row(masked, f"[{style}]{names}[/{style}]", action)

        console.print(breach_table)

    # WHOIS results
    if result.whois_results:
        console.print()
        whois_table = Table(title="WHOIS Privacy", show_lines=True)
        whois_table.add_column("Domain", style="bold")
        whois_table.add_column("Protected")
        whois_table.add_column("Exposed Fields")
        whois_table.add_column("Action Needed")

        for r in result.whois_results:
            if r.error:
                whois_table.add_row(r.domain, "[yellow]Error[/yellow]", r.error, "Retry")
            elif r.privacy_protected:
                whois_table.add_row(r.domain, "[green]Yes[/green]", "None", "None")
            else:
                exposed = ", ".join(r.exposed_fields[:5]) if r.exposed_fields else "Unknown"
                whois_table.add_row(
                    r.domain,
                    "[red]No[/red]",
                    exposed,
                    "Enable WHOIS privacy with registrar",
                )

        console.print(whois_table)

    console.print()
