<div align="center">
  <img src="assets/banner.png" alt="wraith — vanish from the internet" width="100%"/>
</div>

<div align="center">

[![Python](https://img.shields.io/badge/python-3.11%2B-7c3aed?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-a855f7?style=flat-square)](LICENSE)
[![Playwright](https://img.shields.io/badge/powered%20by-playwright-6d28d9?style=flat-square&logo=playwright&logoColor=white)](https://playwright.dev/)
[![Status](https://img.shields.io/badge/status-active-7c3aed?style=flat-square)]()

**Take back control of your data.**

</div>

---

Wraith is an experimental command-line privacy tool: it attempts data-broker opt-outs with Playwright, checks email breach exposure through HaveIBeenPwned (HIBP), audits WHOIS privacy, and stores results and renewal dates in SQLite.

**Broker automation is unverified, not a removal guarantee.** Sites change, CAPTCHAs and verification steps can block progress, and a missing page selector does not prove your record is absent. Some flows record `submitted` after a click without verifying the site's response. Manually verify matches, submissions, email confirmations, and eventual removal; do not treat `not_found` or `submitted` as proof.

## Installation

Requires Python 3.11+ and git.

```bash
git clone https://github.com/warpapaya/wraith.git
cd wraith
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
playwright install chromium
wraith --help
```

Chromium is needed for browser commands, not for the offline test suite.

## Usage

```bash
wraith init                            # Interactive profile setup
wraith audit                           # Broker, HIBP, and WHOIS checks
wraith scrub --broker Spokeo --dry-run  # Inspect an experimental flow
wraith scrub --all                     # Attempt opt-outs; may prompt for manual action
wraith status                          # View recorded submission history
wraith monitor                         # Re-check broker presence
wraith rescan                          # Review due renewals and show instructions only
wraith hibp                            # Email breach lookup (paid HIBP key required)
wraith whois                           # WHOIS privacy checks
wraith google                          # Generate removal-action URL checklist
```

`--dry-run` avoids opt-out submission but still visits external sites. Review broker behavior before using real personal data. Included modules cover FastPeopleSearch, BeenVerified, Spokeo, Intelius, PeopleFinder, TruthFinder, InstantCheckMate, ThatsThem, CheckPeople, USPhoneBook, Radaris, Whitepages, and MyLife. Some provide manual instructions rather than automated removal.

### Renewals are manual

`wraith rescan` lists due records and can prompt before printing suggested scrub commands. It **does not automatically resubmit** anything. Review each broker and profile before running a suggested command; `scrub` uses the currently configured profile, not a historical profile from the database. Use a calendar reminder rather than unattended cron for this interactive workflow.

Only the latest attempt for each broker/profile hash is eligible for renewal, and only when its status is `submitted` or `confirmed` and its renewal date is due. Legacy records without a profile hash form a separate group per broker. History remains available; a newer failed, manual, or not-found attempt suppresses an older due success. The existing profile hash is based on names and emails, not every profile field.

## Configuration

`wraith init` saves the profile and API key in `~/.wraith/config.toml`. The default database is `~/.wraith/state.db`.

```toml
[profile]
names = ["Your Name"]
dob = ""                          # Optional
phones = ["+15555550123"]
emails = ["you@example.com"]
addresses = [
    { street = "123 Main St", city = "Anytown", state = "GA", zip = "30000" }
]
domains = ["example.com"]

[api_keys]
hibp = ""                         # Paid subscription key for email breach checks

[settings]
headless = true
resubmit_days = 90
confirm_wait_days = 30
db_path = "~/.wraith/state.db"
```

### HIBP access and failed lookups

The HIBP [`breachedaccount` API](https://haveibeenpwned.com/API/v3) requires a paid subscription key. Get one and review current terms at https://haveibeenpwned.com/API/Key. Without a key, Wraith skips HIBP checks in an audit and the standalone command shows setup instructions; this does not mean an email is breach-free.

Failed HIBP and WHOIS lookups are shown as **unavailable** and retain previously saved successful results. Those saved results may be stale. A successful empty HIBP response replaces prior breach results for that email; it only means HIBP returned no breaches for that lookup.

## Privacy and limitations

- Configuration and SQLite history are stored locally, **not encrypted by Wraith**. Treat both as sensitive files and protect access and backups yourself.
- Checks send information to external services: broker sites, HIBP (email addresses), and WHOIS services (domains). Opening generated Google URLs also contacts Google.
- Some output uses masking, but masking is not universal. Instructions, URLs, lookup errors, and third-party responses can contain personal data. Review terminal captures and logs before sharing.
- Wraith does not automatically handle all email confirmations, CAPTCHAs, phone verification, or ID requests. Do not submit identity documents without reviewing the recipient and requirements.
- WHOIS privacy detection is heuristic. Verify results with your registrar. Broker removal cannot erase source public records, court records, news articles, or all search-engine results.

## Development

```bash
pip install -e '.[dev]'
python -m pytest -q
python -m build
```

Tests use temporary HOME directories and SQLite databases, fake lookup responses, and block Python socket network access. No browser installation, credentials, or live services are needed. GitHub Actions runs the offline suite on Python 3.11 and 3.12. These tests do **not** validate live broker selectors or successful removals.

Contributions and reproducible bug reports are welcome. See `wraith/brokers/base.py` for the broker interface; omit personal information from reports.

## License

MIT © 2026

---

<div align="center">
<sub>Built for anyone who'd rather disappear than be sold.</sub>
</div>
