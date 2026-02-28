"""
MAYA Memory Store - Session 5
==============================
Persistent SQLite memory for MAYA.

Stores:
  - User profile: user name, session count, total turns
  - Topic log: every user message + intent (for recent topics recall)

DB location: ~/.maya/memory.db

LEARNING NOTES for Srinivasan:
---------------------------------
Why SQLite?
  - Single file, no server, works offline — perfect for RPi5 later
  - Python's built-in sqlite3 module (no pip install needed!)
  - The DB file persists across sessions = MAYA has real persistent memory

Why MemoryStore instantiated fresh per node call?
  - No global state, no singleton → clean, testable
  - Each instantiation opens a connection, does its work, closes it
  - Tests pass a tmp_path DB (clean slate) via memory_db_path state field
  - Production uses ~/.maya/memory.db (grows across sessions)

Why one profile row? (CHECK id = 1)
  - SQLite trick: enforce exactly one row with a CHECK constraint
  - INSERT OR IGNORE seeds it on first run, never duplicates
  - Much simpler than a key-value table for a single-user app
"""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".maya" / "memory.db"
DEFAULT_USER_NAME = "Srinika"  # Week 6: replace with voice-based name detection


class MemoryStore:
    """
    SQLite-backed persistent memory for MAYA.

    Tables
    ------
    profile:  Exactly one row — user_name, session_count, total_turns
    topics:   Append-only turn log — session_id, message, intent, timestamp

    Usage
    -----
        store = MemoryStore()
        session_id = store.start_session()      # once at startup
        profile = store.get_profile()           # {user_name, session_count, total_turns}
        recent = store.get_recent_topics(3)     # ["What is gravity?", ...]
        store.log_turn("What is gravity?", "question", session_id)
    """

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Private helpers ──────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create tables and seed the profile row on first run."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS profile (
                    id            INTEGER PRIMARY KEY CHECK (id = 1),
                    user_name     TEXT    NOT NULL DEFAULT 'Srinika',
                    session_count INTEGER NOT NULL DEFAULT 0,
                    total_turns   INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS topics (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL DEFAULT 0,
                    message    TEXT    NOT NULL,
                    intent     TEXT    NOT NULL DEFAULT 'general',
                    timestamp  TEXT    NOT NULL DEFAULT (datetime('now'))
                )
            """)
            # Seed exactly one profile row if the DB is brand new.
            # INSERT OR IGNORE: if id=1 already exists, does nothing.
            conn.execute("""
                INSERT OR IGNORE INTO profile (id, user_name, session_count, total_turns)
                VALUES (1, ?, 0, 0)
            """, (DEFAULT_USER_NAME,))
            conn.commit()

    # ── Public API ───────────────────────────────────────────────────────────

    def start_session(self) -> int:
        """
        Increment session_count and return the new value (= current session ID).
        Call exactly ONCE at chat_loop startup, not per turn.
        """
        with self._connect() as conn:
            conn.execute(
                "UPDATE profile SET session_count = session_count + 1 WHERE id = 1"
            )
            conn.commit()
            row = conn.execute(
                "SELECT session_count FROM profile WHERE id = 1"
            ).fetchone()
            return row["session_count"]

    def get_profile(self) -> dict:
        """Return {user_name, session_count, total_turns}."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_name, session_count, total_turns FROM profile WHERE id = 1"
            ).fetchone()
            if row is None:
                return {
                    "user_name": DEFAULT_USER_NAME,
                    "session_count": 0,
                    "total_turns": 0,
                }
            return dict(row)

    def get_recent_topics(self, limit: int = 3) -> list[str]:
        """Return the last `limit` user messages, most recent first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT message FROM topics ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [row["message"] for row in rows]

    def log_turn(self, message: str, intent: str, session_id: int = 0) -> None:
        """Append a user message to the topics log and increment total_turns."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO topics (session_id, message, intent) VALUES (?, ?, ?)",
                (session_id, message, intent),
            )
            conn.execute(
                "UPDATE profile SET total_turns = total_turns + 1 WHERE id = 1"
            )
            conn.commit()
