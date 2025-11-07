"""
Database setup and operations for scrape history
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any

# Database at src/ level (parent directory)
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "flights.db")


@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database schema"""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scrapes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                date TEXT NOT NULL,
                passengers INTEGER NOT NULL,
                cabin_class TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                results TEXT,
                error TEXT,
                total_flights INTEGER,
                avg_cpp REAL
            )
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_status ON scrapes(status)
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_started_at ON scrapes(started_at DESC)
        """
        )


def create_scrape(
    origin: str, destination: str, date: str, passengers: int, cabin_class: str
) -> int:
    """Create a new scrape job"""
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO scrapes (origin, destination, date, passengers, cabin_class, status, started_at)
            VALUES (?, ?, ?, ?, ?, 'queued', ?)
        """,
            (
                origin,
                destination,
                date,
                passengers,
                cabin_class,
                datetime.utcnow().isoformat(),
            ),
        )
        return cursor.lastrowid


def update_scrape_status(scrape_id: int, status: str) -> None:
    """Update scrape status"""
    with get_db() as conn:
        conn.execute(
            """
            UPDATE scrapes SET status = ? WHERE id = ?
        """,
            (status, scrape_id),
        )


def complete_scrape(scrape_id: int, results: dict[str, Any]) -> None:
    """Mark scrape as completed with results"""
    flights = results.get("flights", [])
    total_flights = len(flights)
    avg_cpp = sum(f["cpp"] for f in flights) / total_flights if total_flights > 0 else 0

    with get_db() as conn:
        conn.execute(
            """
            UPDATE scrapes
            SET status = 'completed',
                completed_at = ?,
                results = ?,
                total_flights = ?,
                avg_cpp = ?
            WHERE id = ?
        """,
            (
                datetime.utcnow().isoformat(),
                json.dumps(results),
                total_flights,
                avg_cpp,
                scrape_id,
            ),
        )


def fail_scrape(scrape_id: int, error: str) -> None:
    """Mark scrape as failed with error"""
    with get_db() as conn:
        conn.execute(
            """
            UPDATE scrapes
            SET status = 'failed',
                completed_at = ?,
                error = ?
            WHERE id = ?
        """,
            (datetime.utcnow().isoformat(), error, scrape_id),
        )


def get_scrape(scrape_id: int) -> dict[str, Any] | None:
    """Get scrape by ID"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM scrapes WHERE id = ?", (scrape_id,)
        ).fetchone()
        if row:
            return dict(row)
        return None


def get_all_scrapes(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """Get all scrapes ordered by started_at DESC"""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM scrapes
            ORDER BY started_at DESC
            LIMIT ? OFFSET ?
        """,
            (limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]


def get_latest_completed() -> dict[str, Any] | None:
    """Get latest completed scrape"""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT * FROM scrapes
            WHERE status = 'completed'
            ORDER BY completed_at DESC
            LIMIT 1
        """
        ).fetchone()
        if row:
            return dict(row)
        return None


def delete_scrape(scrape_id: int) -> bool:
    """Delete scrape by ID"""
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM scrapes WHERE id = ?", (scrape_id,))
        return cursor.rowcount > 0


def get_running_scrape() -> dict[str, Any] | None:
    """Get currently running scrape if any"""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT * FROM scrapes
            WHERE status = 'running'
            LIMIT 1
        """
        ).fetchone()
        if row:
            return dict(row)
        return None


def try_start_scrape(scrape_id: int) -> bool:
    """
    Atomically attempt to start a scrape.
    Returns True if successfully started, False if another scrape is already running.

    This implements database-only locking by:
    1. Using BEGIN IMMEDIATE to acquire write lock immediately
    2. Checking if any scrape is currently running
    3. If not, updating this scrape to 'running' status
    4. All within a single transaction (prevents race conditions)
    """
    # Use manual connection management with IMMEDIATE isolation to prevent race conditions
    # Why: Default deferred transactions don't lock until first write, allowing two
    #      transactions to both read "no running scrapes" before either writes
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # Begin immediate transaction - acquires write lock immediately
        conn.execute("BEGIN IMMEDIATE")

        # Check if any scrape is currently running
        running = conn.execute(
            "SELECT COUNT(*) FROM scrapes WHERE status = 'running'"
        ).fetchone()[0]

        if running > 0:
            conn.rollback()
            return False

        # No running scrape found, try to start this one
        cursor = conn.execute(
            """
            UPDATE scrapes
            SET status = 'running'
            WHERE id = ? AND status = 'queued'
            """,
            (scrape_id,),
        )

        success = cursor.rowcount > 0
        conn.commit()
        return success

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def is_scrape_running() -> bool:
    """Check if any scrape is currently running"""
    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM scrapes WHERE status = 'running'"
        ).fetchone()[0]
        return count > 0


def get_current_job_id() -> int | None:
    """Get the ID of the currently running job, if any"""
    scrape = get_running_scrape()
    return scrape["id"] if scrape else None
