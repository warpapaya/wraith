"""Wraith CLI — Typer app entrypoint."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from wraith.console import console

app = typer.Typer(
    name="wraith",
    help="Personal privacy scrubbing engine.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _run(coro):
    """Run an async coroutine from sync Typer commands."""
    return asyncio.run(coro)


def _get_config():
    from wraith.config import load_config
    return load_config()


async def _get_db(cfg=None):
    if cfg is None:
        cfg = _get_config()
    from wraith.db import WraithDB
    db = WraithDB(cfg.settings.resolved_db_path)
    await db.connect()
    return db


# ─── wraith init ────────────────────────────────────────────────────────

@app.command()
def init():
    """Interactive setup wizard — configure your profile."""
    from wraith.config import Address, ApiKeys, Profile, Settings, WraithConfig, save_config, CONFIG_PATH

    console.print(Panel(
        "[bold]Wraith Setup Wizard[/bold]\n"
        "Configure your personal information for privacy scrubbing.\n"
        "This data is stored locally at ~/.wraith/config.toml.",
        title="wraith init",
    ))

    # Names
    primary = typer.prompt("Full name (primary)")
    alternates_raw = typer.prompt(
        "Alternate names (comma-separated, or blank)", default=""
    )
    names = [primary]
    if alternates_raw.strip():
        names.extend(n.strip() for n in alternates_raw.split(",") if n.strip())

    # DOB
    dob = typer.prompt("Date of birth (YYYY-MM-DD, or blank)", default="")

    # Phones
    phones_raw = typer.prompt("Phone numbers (comma-separated, e.g. +19125551234)")
    phones = [p.strip() for p in phones_raw.split(",") if p.strip()]

    # Emails
    emails_raw = typer.prompt("Email addresses (comma-separated)")
    emails = [e.strip() for e in emails_raw.split(",") if e.strip()]

    # Addresses
    addresses: list[Address] = []
    console.print("\n[bold]Addresses[/bold] (enter blank street to stop)")
    while True:
        street = typer.prompt("  Street address", default="")
        if not street:
            break
        city = typer.prompt("  City")
        state = typer.prompt("  State (2-letter)")
        zip_code = typer.prompt("  ZIP code")
        addresses.append(Address(street=street, city=city, state=state.upper(), zip=zip_code))
        if not typer.confirm("  Add another address?", default=False):
            break

    # Domains
    domains_raw = typer.prompt(
        "Domain names to audit WHOIS (comma-separated, or blank)", default=""
    )
    domains = [d.strip() for d in domains_raw.split(",") if d.strip()]

    # HIBP API key
    hibp_key = typer.prompt(
        "HaveIBeenPwned API key (blank to skip)", default=""
    )

    # Headless mode
    headless = typer.confirm("Run browser in headless mode?", default=True)

    profile = Profile(
        names=names, dob=dob, phones=phones, emails=emails,
        addresses=addresses, domains=domains,
    )
    api_keys = ApiKeys(hibp=hibp_key)
    settings = Settings(headless=headless)
    cfg = WraithConfig(profile=profile, api_keys=api_keys, settings=settings)

    save_config(cfg)
    console.print(f"\n[green]Configuration saved to {CONFIG_PATH}[/green]")
    console.print("Run [bold]wraith audit[/bold] to check your current exposure.")


# ─── wraith audit ───────────────────────────────────────────────────────

@app.command()
def audit():
    """Run ALL checks and report current exposure."""
    cfg = _get_config()
    if not cfg.profile.names:
        console.print("[red]No profile configured. Run 'wraith init' first.[/red]")
        raise typer.Exit(1)

    from wraith.audit import run_full_audit, display_audit_results

    async def _audit():
        db = await _get_db(cfg)
        try:
            result = await run_full_audit(cfg, db)
            display_audit_results(result)
        finally:
            await db.close()

    _run(_audit())


# ─── wraith scrub ──────────────────────────────────────────────────────

@app.command()
def scrub(
    broker: Optional[str] = typer.Option(None, "--broker", "-b", help="Single broker name"),
    all_brokers: bool = typer.Option(False, "--all", "-a", help="Run all brokers"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Navigate but do NOT submit"),
):
    """Submit opt-out requests via browser automation."""
    if not broker and not all_brokers:
        console.print("[red]Specify --broker NAME or --all[/red]")
        raise typer.Exit(1)

    cfg = _get_config()
    if not cfg.profile.names:
        console.print("[red]No profile configured. Run 'wraith init' first.[/red]")
        raise typer.Exit(1)

    from wraith.brokers import ALL_BROKERS, BROKER_MAP
    from wraith.brokers.base import SubmissionStatus
    from playwright.async_api import async_playwright
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

    if broker:
        broker_lower = broker.lower()
        if broker_lower not in BROKER_MAP:
            console.print(f"[red]Unknown broker: {broker}[/red]")
            console.print("Available: " + ", ".join(sorted(BROKER_MAP.keys())))
            raise typer.Exit(1)
        targets = [BROKER_MAP[broker_lower]]
    else:
        targets = list(ALL_BROKERS)

    async def _scrub():
        db = await _get_db(cfg)

        try:
            async with async_playwright() as pw:
                browser_instance = await pw.chromium.launch(headless=cfg.settings.headless)

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Submitting opt-outs...", total=len(targets))

                    for broker_cls in targets:
                        b = broker_cls()
                        progress.update(task, description=f"Processing {b.name}...")

                        ctx = await browser_instance.new_context(
                            user_agent=(
                                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/120.0.0.0 Safari/537.36"
                            )
                        )
                        page = await ctx.new_page()

                        try:
                            result = await b.submit_opt_out(cfg.profile, page, dry_run=dry_run)

                            # Record in DB (skip for dry runs)
                            if not dry_run:
                                await db.record_submission(
                                    broker=b.name,
                                    status=result.status,
                                    profile=cfg.profile,
                                    notes=result.notes,
                                    confirm_wait_days=cfg.settings.confirm_wait_days,
                                    resubmit_days=cfg.settings.resubmit_days,
                                )

                            # Display result
                            if result.status == SubmissionStatus.SUBMITTED:
                                console.print(f"  [green]{b.name}[/green]: Submitted")
                            elif result.status == SubmissionStatus.MANUAL_REQUIRED:
                                console.print(f"  [blue]{b.name}[/blue]: Manual steps required")
                                for step in result.manual_steps:
                                    console.print(f"    -> {step}")
                            elif result.status == SubmissionStatus.DRY_RUN:
                                console.print(f"  [cyan]{b.name}[/cyan]: Dry run — {result.notes}")
                            elif result.status == SubmissionStatus.NOT_FOUND:
                                console.print(f"  [green]{b.name}[/green]: No record found")
                            else:
                                console.print(f"  [red]{b.name}[/red]: {result.notes}")
                        except Exception as e:
                            console.print(f"  [red]{b.name}[/red]: Error — {e}")
                            if not dry_run:
                                await db.record_submission(
                                    broker=b.name,
                                    status="failed",
                                    profile=cfg.profile,
                                    notes=f"Unhandled error: {e}",
                                )
                        finally:
                            await ctx.close()

                        progress.advance(task)

                await browser_instance.close()
        finally:
            await db.close()

        if dry_run:
            console.print("\n[cyan]Dry run complete — nothing was submitted.[/cyan]")
        else:
            console.print("\n[green]Opt-out submissions complete.[/green]")
            console.print("Run [bold]wraith status[/bold] to see tracked submissions.")

    _run(_scrub())


# ─── wraith status ─────────────────────────────────────────────────────

@app.command()
def status():
    """Show status of all tracked submissions."""
    cfg = _get_config()

    async def _status():
        db = await _get_db(cfg)
        try:
            subs = await db.get_all_submissions()
        finally:
            await db.close()

        if not subs:
            console.print("[yellow]No submissions tracked yet. Run 'wraith scrub --all' first.[/yellow]")
            return

        table = Table(title="Opt-Out Submissions", show_lines=True)
        table.add_column("Broker", style="bold")
        table.add_column("Status")
        table.add_column("Submitted")
        table.add_column("Confirm By")
        table.add_column("Resubmit At")
        table.add_column("Notes", max_width=40)

        now = datetime.utcnow()

        for s in subs:
            status_val = s["status"]
            submitted = s.get("submitted_at", "")[:10] if s.get("submitted_at") else "-"
            confirm_by = s.get("confirm_by", "")[:10] if s.get("confirm_by") else "-"
            resubmit_at = s.get("resubmit_at", "")[:10] if s.get("resubmit_at") else "-"
            notes = (s.get("notes") or "")[:40]

            # Color coding
            if status_val == "confirmed":
                style = "green"
            elif status_val == "submitted":
                # Check if overdue for confirmation
                if s.get("confirm_by"):
                    try:
                        cb = datetime.fromisoformat(s["confirm_by"])
                        style = "red" if now > cb else "yellow"
                    except (ValueError, TypeError):
                        style = "yellow"
                else:
                    style = "yellow"
            elif status_val == "failed":
                style = "red"
            elif status_val == "manual_required":
                style = "blue"
            else:
                style = "dim"

            table.add_row(
                s["broker"],
                f"[{style}]{status_val}[/{style}]",
                submitted,
                confirm_by,
                resubmit_at,
                notes,
            )

        console.print(table)

    _run(_status())


# ─── wraith monitor ────────────────────────────────────────────────────

@app.command()
def monitor():
    """Re-check brokers for profile reappearance after opt-out."""
    cfg = _get_config()
    if not cfg.profile.names:
        console.print("[red]No profile configured. Run 'wraith init' first.[/red]")
        raise typer.Exit(1)

    from wraith.audit import run_broker_checks

    async def _monitor():
        db = await _get_db(cfg)
        try:
            # Get brokers where we've previously submitted opt-outs
            subs = await db.get_all_submissions()
            submitted_brokers = {s["broker"] for s in subs if s["status"] in ("submitted", "confirmed")}

            if not submitted_brokers:
                console.print("[yellow]No previous opt-outs to monitor. Run 'wraith scrub --all' first.[/yellow]")
                return

            console.print(f"\n[bold]Monitoring {len(submitted_brokers)} brokers for reappearance...[/bold]\n")

            results = await run_broker_checks(cfg, headless=cfg.settings.headless)

            # Check for reappearances
            table = Table(title="Monitor Results", show_lines=True)
            table.add_column("Broker", style="bold")
            table.add_column("Previous Status")
            table.add_column("Current Status")
            table.add_column("Action")

            reappeared = 0
            for broker_name in sorted(submitted_brokers):
                current = results.get(broker_name, "unknown")
                # Find last submission status
                broker_subs = [s for s in subs if s["broker"] == broker_name]
                prev_status = broker_subs[0]["status"] if broker_subs else "unknown"

                if current == "found":
                    style = "red"
                    action = "[red]REAPPEARED — resubmit opt-out[/red]"
                    reappeared += 1
                elif current == "not_found":
                    style = "green"
                    action = "Still removed"
                else:
                    style = "blue"
                    action = "Manual check needed"

                table.add_row(
                    broker_name, prev_status, f"[{style}]{current}[/{style}]", action
                )

            console.print(table)

            if reappeared > 0:
                console.print(
                    f"\n[red bold]{reappeared} broker(s) show profile reappearance![/red bold]"
                    "\nRun [bold]wraith scrub --all[/bold] to resubmit opt-outs."
                )
            else:
                console.print("\n[green]No reappearances detected.[/green]")
        finally:
            await db.close()

    _run(_monitor())


# ─── wraith rescan ─────────────────────────────────────────────────────

@app.command()
def rescan():
    """Resubmit opt-outs for brokers past their resubmission date."""
    cfg = _get_config()

    async def _rescan():
        db = await _get_db(cfg)
        try:
            due = await db.get_due_resubmissions()
        finally:
            await db.close()

        if not due:
            console.print("[green]No opt-outs due for resubmission.[/green]")
            return

        console.print(f"\n[bold]{len(due)} broker(s) due for resubmission:[/bold]")
        for s in due:
            console.print(f"  - {s['broker']} (submitted: {s.get('submitted_at', '')[:10]})")

        console.print()
        if typer.confirm("Resubmit these opt-outs?"):
            # Build broker list and invoke scrub
            broker_names = [s["broker"] for s in due]
            console.print(f"Resubmitting for: {', '.join(broker_names)}")
            console.print("Run: [bold]wraith scrub --all[/bold] to process these.\n")
            # Could invoke scrub programmatically, but cleaner to let user run it
            for name in broker_names:
                console.print(f"  wraith scrub --broker {name}")

    _run(_rescan())


# ─── wraith google ─────────────────────────────────────────────────────

@app.command()
def google():
    """Generate Google removal URLs and privacy checklist."""
    cfg = _get_config()
    if not cfg.profile.names:
        console.print("[red]No profile configured. Run 'wraith init' first.[/red]")
        raise typer.Exit(1)

    from wraith.checks.google import generate_removal_checklist

    actions = generate_removal_checklist(cfg.profile)

    table = Table(title="Google Privacy Actions", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Action", style="bold")
    table.add_column("URL", style="cyan")
    table.add_column("Description", max_width=50)

    for i, action in enumerate(actions, 1):
        table.add_row(str(i), action.title, action.url, action.description)

    console.print(table)
    console.print(
        "\n[dim]Open each URL in your browser to take action.[/dim]"
    )


# ─── wraith hibp ───────────────────────────────────────────────────────

@app.command()
def hibp():
    """Check all configured emails against HaveIBeenPwned."""
    cfg = _get_config()

    if not cfg.api_keys.hibp:
        from wraith.checks.hibp import format_hibp_instructions
        console.print(f"[yellow]No HIBP API key configured.[/yellow]\n")
        console.print(format_hibp_instructions())
        raise typer.Exit(1)

    if not cfg.profile.emails:
        console.print("[red]No emails configured. Run 'wraith init' first.[/red]")
        raise typer.Exit(1)

    from wraith.checks.hibp import check_all_emails
    from wraith.config import mask_email
    import json

    async def _hibp():
        db = await _get_db(cfg)
        try:
            console.print("[bold]Checking emails against HaveIBeenPwned...[/bold]\n")
            results = await check_all_emails(cfg.profile.emails, cfg.api_keys.hibp)

            for email, breaches in results.items():
                masked = mask_email(email)
                # Save to DB
                real_breaches = [b for b in breaches if not b.get("Name", "").startswith("ERROR:")]
                await db.save_breach_results(email, real_breaches)

                if not breaches:
                    console.print(f"  [green]{masked}[/green]: No breaches found")
                    continue

                console.print(f"  [red]{masked}[/red]: {len(breaches)} breach(es) found")

                breach_table = Table(show_header=True, padding=(0, 1))
                breach_table.add_column("Breach", style="bold")
                breach_table.add_column("Date")
                breach_table.add_column("Data Types", max_width=50)

                for b in breaches:
                    name = b.get("Name", "Unknown")
                    if name.startswith("ERROR:"):
                        console.print(f"    [red]{name}[/red]")
                        continue

                    date = b.get("BreachDate", "Unknown")
                    data_classes = b.get("DataClasses", [])
                    if isinstance(data_classes, str):
                        try:
                            data_classes = json.loads(data_classes)
                        except (json.JSONDecodeError, TypeError):
                            data_classes = [data_classes]
                    types_str = ", ".join(data_classes[:6])
                    if len(data_classes) > 6:
                        types_str += f" (+{len(data_classes) - 6} more)"

                    breach_table.add_row(name, date, types_str)

                console.print(breach_table)
                console.print()
        finally:
            await db.close()

    _run(_hibp())


# ─── wraith whois ──────────────────────────────────────────────────────

@app.command(name="whois")
def whois_cmd():
    """Check WHOIS privacy for all configured domains."""
    cfg = _get_config()

    if not cfg.profile.domains:
        console.print("[yellow]No domains configured. Run 'wraith init' to add domains.[/yellow]")
        raise typer.Exit(1)

    from wraith.checks.whois_check import check_all_domains

    async def _whois():
        db = await _get_db(cfg)
        try:
            console.print("[bold]Checking WHOIS records...[/bold]\n")
            results = check_all_domains(cfg.profile.domains)

            table = Table(title="WHOIS Privacy Audit", show_lines=True)
            table.add_column("Domain", style="bold")
            table.add_column("Privacy Protected")
            table.add_column("Exposed Fields", max_width=50)
            table.add_column("Action")

            for r in results:
                await db.save_whois_result(r.domain, r.privacy_protected, r.exposed_fields)

                if r.error:
                    table.add_row(r.domain, "[yellow]Error[/yellow]", r.error, "Retry later")
                elif r.privacy_protected:
                    table.add_row(r.domain, "[green]Yes[/green]", "None", "None needed")
                else:
                    exposed = ", ".join(r.exposed_fields) if r.exposed_fields else "Check manually"
                    table.add_row(
                        r.domain,
                        "[red]No[/red]",
                        exposed,
                        "Enable WHOIS privacy with your registrar",
                    )

            console.print(table)
        finally:
            await db.close()

    _run(_whois())


if __name__ == "__main__":
    app()
