"""SQLite state tracking via aiosqlite."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import aiosqlite

from wraith.config import Profile

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY,
    broker TEXT NOT NULL,
    status TEXT NOT NULL,
    submitted_at DATETIME,
    confirmed_at DATETIME,
    confirm_by DATETIME,
    resubmit_at DATETIME,
    notes TEXT,
    profile_hash TEXT
);

CREATE TABLE IF NOT EXISTS breach_results (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    breach_name TEXT NOT NULL,
    breach_date DATE,
    data_types TEXT,
    checked_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS whois_results (
    id INTEGER PRIMARY KEY,
    domain TEXT NOT NULL,
    privacy_protected BOOLEAN,
    exposed_fields TEXT,
    checked_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


def _profile_hash(profile: Profile) -> str:
    raw = json.dumps({"names": profile.names, "emails": profile.emails}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class WraithDB:
    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path).expanduser()
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._path))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._db

    # --- Submissions ---

    async def record_submission(
        self,
        broker: str,
        status: str,
        profile: Profile,
        notes: str = "",
        confirm_wait_days: int = 30,
        resubmit_days: int = 90,
    ) -> int:
        now = datetime.utcnow()
        confirm_by = now + timedelta(days=confirm_wait_days)
        resubmit_at = now + timedelta(days=resubmit_days)
        cursor = await self.db.execute(
            """INSERT INTO submissions
               (broker, status, submitted_at, confirm_by, resubmit_at, notes, profile_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (broker, status, now.isoformat(), confirm_by.isoformat(),
             resubmit_at.isoformat(), notes, _profile_hash(profile)),
        )
        await self.db.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def update_submission_status(
        self, submission_id: int, status: str, notes: str | None = None
    ) -> None:
        if notes is not None:
            await self.db.execute(
                "UPDATE submissions SET status = ?, notes = ? WHERE id = ?",
                (status, notes, submission_id),
            )
        else:
            await self.db.execute(
                "UPDATE submissions SET status = ? WHERE id = ?",
                (status, submission_id),
            )
        await self.db.commit()

    async def confirm_submission(self, submission_id: int) -> None:
        now = datetime.utcnow()
        await self.db.execute(
            "UPDATE submissions SET status = 'confirmed', confirmed_at = ? WHERE id = ?",
            (now.isoformat(), submission_id),
        )
        await self.db.commit()

    async def get_all_submissions(self) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM submissions ORDER BY submitted_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_submissions_by_broker(self, broker: str) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM submissions WHERE broker = ? ORDER BY submitted_at DESC",
            (broker,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_due_resubmissions(self) -> list[dict[str, Any]]:
        now = datetime.utcnow().isoformat()
        cursor = await self.db.execute(
            """SELECT * FROM submissions
               WHERE resubmit_at <= ? AND status IN ('submitted', 'confirmed')
               ORDER BY resubmit_at ASC""",
            (now,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_latest_submission(self, broker: str) -> dict[str, Any] | None:
        cursor = await self.db.execute(
            "SELECT * FROM submissions WHERE broker = ? ORDER BY submitted_at DESC LIMIT 1",
            (broker,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    # --- Breach results ---

    async def save_breach_results(
        self, email: str, breaches: list[dict[str, Any]]
    ) -> None:
        # Clear old results for this email
        await self.db.execute("DELETE FROM breach_results WHERE email = ?", (email,))
        for b in breaches:
            data_types = json.dumps(b.get("DataClasses", []))
            await self.db.execute(
                """INSERT INTO breach_results (email, breach_name, breach_date, data_types)
                   VALUES (?, ?, ?, ?)""",
                (email, b.get("Name", "Unknown"), b.get("BreachDate", ""), data_types),
            )
        await self.db.commit()

    async def get_breach_results(self, email: str | None = None) -> list[dict[str, Any]]:
        if email:
            cursor = await self.db.execute(
                "SELECT * FROM breach_results WHERE email = ? ORDER BY breach_date DESC",
                (email,),
            )
        else:
            cursor = await self.db.execute(
                "SELECT * FROM breach_results ORDER BY email, breach_date DESC"
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # --- WHOIS results ---

    async def save_whois_result(
        self, domain: str, privacy_protected: bool, exposed_fields: list[str]
    ) -> None:
        await self.db.execute("DELETE FROM whois_results WHERE domain = ?", (domain,))
        await self.db.execute(
            """INSERT INTO whois_results (domain, privacy_protected, exposed_fields)
               VALUES (?, ?, ?)""",
            (domain, privacy_protected, json.dumps(exposed_fields)),
        )
        await self.db.commit()

    async def get_whois_results(self) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM whois_results ORDER BY domain"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
