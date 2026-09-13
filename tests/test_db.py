import asyncio

import pytest

from wraith.db import WraithDB


async def insert(db, broker="A", profile="p", status="submitted", submitted="2000-01-01", due="2001-01-01"):
    cursor = await db.db.execute(
        "INSERT INTO submissions (broker, profile_hash, status, submitted_at, resubmit_at) VALUES (?, ?, ?, ?, ?)",
        (broker, profile, status, submitted, due),
    )
    await db.db.commit()
    return cursor.lastrowid


@pytest.mark.parametrize("status", ["failed", "manual_required", "not_found", "submitted", "confirmed"])
@pytest.mark.parametrize("profile", ["p", None])
def test_latest_attempt_suppresses_old_due(tmp_path, status, profile):
    async def scenario():
        db = WraithDB(tmp_path / "state.db")
        await db.connect()
        try:
            await insert(db, profile=profile)
            await insert(db, profile=profile, status=status, submitted="2002-01-01", due="9999-01-01")
            assert await db.get_due_resubmissions() == []
        finally:
            await db.close()
    asyncio.run(scenario())


def test_due_partition_and_tie_ordering(tmp_path):
    async def scenario():
        db = WraithDB(tmp_path / "state.db")
        await db.connect()
        try:
            await insert(db)
            latest = await insert(db, status="confirmed")
            other_profile = await insert(db, profile="q")
            legacy = await insert(db, profile=None)
            empty_hash = await insert(db, profile="")
            other_broker = await insert(db, broker="B")
            await insert(db, profile="future", submitted="2003-01-01", due="9999-01-01")
            await insert(db, profile="no-due", due=None)
            rows = await db.get_due_resubmissions()
            assert [r["id"] for r in rows] == [other_broker, empty_hash, legacy, other_profile, latest]
        finally:
            await db.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("getter", ["get_latest_submission", "get_submissions_by_broker", "get_all_submissions"])
def test_history_ties_use_descending_id(tmp_path, getter):
    async def scenario():
        db = WraithDB(tmp_path / "state.db")
        await db.connect()
        try:
            first = await insert(db)
            second = await insert(db)
            rows = await getattr(db, getter)(*(() if getter == "get_all_submissions" else ("A",)))
            if getter == "get_latest_submission":
                assert rows["id"] == second
            else:
                assert [r["id"] for r in rows] == [second, first]
        finally:
            await db.close()
    asyncio.run(scenario())


def test_null_timestamps_are_older_and_ties_still_resolve(tmp_path):
    async def scenario():
        db = WraithDB(tmp_path / "state.db")
        await db.connect()
        try:
            await insert(db, submitted=None)
            await insert(db, submitted=None, status="failed")
            await insert(db, profile="q", submitted=None)
            latest = await insert(db, profile="q")
            assert [r["id"] for r in await db.get_due_resubmissions()] == [latest]
        finally:
            await db.close()
    asyncio.run(scenario())
