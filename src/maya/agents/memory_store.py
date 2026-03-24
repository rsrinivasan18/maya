"""
MAYA Memory Store - Session 10 Update
======================================
Persistent SQLite memory for MAYA.

Stores:
  - User profile: user name, session count, total turns
  - Topic log: every user message + semantic topic (extracted by LLM) + intent
  - Session summaries: one-sentence episodic summary per session (from farewell node)
  - Mastery log: how many times Srinika has explored each topic (procedural memory)
  - Persona config: editable MAYA behaviour settings (Session 14)
  - Todos: Srinika's reminders and task list (Session 17)

DB location: ~/.maya/memory.db (SQLite) or DATABASE_URL (PostgreSQL)

LEARNING NOTES for Srinivasan:
---------------------------------
Why SQLAlchemy instead of sqlite3?
  - One interface for BOTH SQLite (local/offline) and PostgreSQL (cloud/AWS)
  - create_engine() picks the right driver from the connection URL
  - text() lets us write raw SQL — familiar, readable, no magic ORM
  - engine.begin() = auto-commit on success, auto-rollback on exception

Why DATABASE_URL?
  - The standard way to pass a DB connection string in 12-factor apps
  - AWS App Runner / Heroku / Railway all use DATABASE_URL
  - Local dev / tests just don't set it → falls back to SQLite (zero config)

Why ON CONFLICT DO NOTHING instead of INSERT OR IGNORE?
  - SQLite 3.24+ (2018) and PostgreSQL both support this ANSI syntax
  - INSERT OR IGNORE is SQLite-only; ON CONFLICT is portable
  - Python 3.10+ ships with SQLite 3.37+ — safe on every supported platform
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    CheckConstraint,
    Column,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy import text as sa_text

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_think_tags(t: str) -> str:
    """Remove <think>...</think> blocks that some LLMs leak into output."""
    return _THINK_RE.sub("", t).strip()


DEFAULT_DB_PATH = Path.home() / ".maya" / "memory.db"
DEFAULT_USER_NAME = "Srinika"  # Week 6: replace with voice-based name detection


def _mastery_level(count: int) -> str:
    """
    Map an exploration count to a human-readable mastery level.

    These thresholds are intentionally low — for a 10-year-old, revisiting
    a topic 3 times already shows meaningful curiosity and familiarity.
    """
    if count >= 5:
        return "expert"
    if count >= 3:
        return "practiced"
    if count >= 2:
        return "learning"
    return "curious"


def _now() -> str:
    """Current UTC time as ISO string — passed explicitly to avoid dialect differences."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class MemoryStore:
    """
    SQLAlchemy-backed persistent memory for MAYA.

    Supports SQLite (local dev / Raspberry Pi) and PostgreSQL (AWS RDS).
    Connection controlled by DATABASE_URL env var; falls back to db_path for tests.

    Tables
    ------
    profile:       Exactly one row — user_name, session_count, total_turns
    topics:        Append-only turn log — session_id, message, topic, intent, timestamp
    sessions:      One row per session — session_id, summary (episodic)
    mastery:       Exploration counts per topic (procedural memory)
    persona_config: Editable MAYA behaviour settings (tone, language, grade_level…)
    todos:         Srinika's reminders and task list

    Usage
    -----
        store = MemoryStore()
        session_id = store.start_session()                  # once at startup
        profile = store.get_profile()                       # {user_name, session_count, total_turns}
        recent = store.get_recent_topics(3)                 # ["photosynthesis", "Newton laws", ...]
        store.log_turn("What is gravity?", "question", session_id, topic="gravity")
        store.update_mastery("gravity")                     # increments count for this topic
        mastery = store.get_mastery_summary(limit=5)        # [{topic, count, level}, ...]
        store.save_session_summary(session_id, "Srinika explored gravity and light.")
        summary = store.get_last_session_summary()          # "Srinika explored gravity and light."
    """

    def __init__(self, db_path: str | None = None) -> None:
        database_url = os.getenv("DATABASE_URL")

        if database_url:
            # Production: PostgreSQL on AWS RDS (or any other DATABASE_URL)
            self._engine = create_engine(database_url)
        elif db_path:
            # Tests / explicit override: SQLite at the given path
            path = Path(db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._engine = create_engine(
                f"sqlite:///{path}",
                connect_args={"check_same_thread": False},
            )
        else:
            # Default: SQLite at ~/.maya/memory.db
            DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._engine = create_engine(
                f"sqlite:///{DEFAULT_DB_PATH}",
                connect_args={"check_same_thread": False},
            )

        self._init_db()

    # ── Private helpers ──────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """
        Create tables using SQLAlchemy metadata (dialect-aware DDL).

        SQLAlchemy generates correct CREATE TABLE statements for each database
        engine — INTEGER PRIMARY KEY becomes SERIAL in PostgreSQL automatically.
        checkfirst=True means existing tables are never dropped or modified.
        """
        meta = MetaData()

        Table(
            "profile", meta,
            Column("id", Integer, primary_key=True, autoincrement=False),
            Column("user_name", Text, nullable=False, server_default="Srinika"),
            Column("session_count", Integer, nullable=False, server_default="0"),
            Column("total_turns", Integer, nullable=False, server_default="0"),
            CheckConstraint("id = 1", name="ck_profile_singleton"),
        )
        Table(
            "topics", meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_id", Integer, nullable=False, server_default="0"),
            Column("message", Text, nullable=False),
            Column("topic", Text, nullable=False, server_default=""),
            Column("intent", Text, nullable=False, server_default="general"),
            Column("timestamp", Text, nullable=False, server_default="CURRENT_TIMESTAMP"),
        )
        Table(
            "sessions", meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_id", Integer, nullable=False, server_default="0"),
            Column("summary", Text, nullable=False, server_default=""),
            Column("timestamp", Text, nullable=False, server_default="CURRENT_TIMESTAMP"),
        )
        Table(
            "mastery", meta,
            Column("topic_key", Text, primary_key=True),
            Column("display", Text, nullable=False),
            Column("count", Integer, nullable=False, server_default="1"),
            Column("first_seen", Text, nullable=False, server_default="CURRENT_TIMESTAMP"),
            Column("last_seen", Text, nullable=False, server_default="CURRENT_TIMESTAMP"),
        )
        Table(
            "persona_config", meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("persona_name", Text, nullable=False, server_default="srinika"),
            Column("field_key", Text, nullable=False),
            Column("field_value", Text, nullable=False),
            Column("updated_at", Text, server_default="CURRENT_TIMESTAMP"),
            UniqueConstraint("persona_name", "field_key", name="uq_persona_field"),
        )
        Table(
            "todos", meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("text", Text, nullable=False),
            Column("created_at", Text, nullable=False, server_default="CURRENT_TIMESTAMP"),
            Column("done", Integer, nullable=False, server_default="0"),
            Column("done_at", Text),
            Column("due_date", Text),
            Column("recurrence", Text),
        )

        meta.create_all(self._engine, checkfirst=True)

        # Backward compat: add topic column to existing SQLite DBs that predate Session 9.
        # create_all(checkfirst=True) skips existing tables — it won't add missing columns.
        # ALTER TABLE ADD COLUMN fails silently if the column already exists.
        with self._engine.begin() as conn:
            try:
                conn.execute(sa_text(
                    "ALTER TABLE topics ADD COLUMN topic TEXT NOT NULL DEFAULT ''"
                ))
            except Exception:
                pass  # Column already exists — ignore

        # Seed exactly one profile row on first run.
        # Seed default persona config for 'srinika' on first run.
        with self._engine.begin() as conn:
            conn.execute(sa_text(
                "INSERT INTO profile (id, user_name, session_count, total_turns) "
                "VALUES (1, :name, 0, 0) ON CONFLICT DO NOTHING"
            ), {"name": DEFAULT_USER_NAME})

            _srinika_defaults = [
                ("srinika", "tone",           "warm and playful didi, never formal"),
                ("srinika", "language",       "Hindi and English mixed — Hinglish OK"),
                ("srinika", "grade_level",    "Grade 4, age 9"),
                ("srinika", "greeting_style", "Short and warm. Never mention session numbers, mastery counts, or past learning history. Just say hello and ask what to explore today."),
                ("srinika", "response_style", "Use Indian analogies (chai, roti, cricket). Keep responses short. Always end with one fun question."),
                ("srinika", "avoid",          "Never say session number. Never say mastery count. Never summarize past sessions in greeting. Sidebar handles metadata — not you."),
            ]
            for pn, fk, fv in _srinika_defaults:
                conn.execute(sa_text(
                    "INSERT INTO persona_config (persona_name, field_key, field_value) "
                    "VALUES (:pn, :fk, :fv) ON CONFLICT DO NOTHING"
                ), {"pn": pn, "fk": fk, "fv": fv})

    # ── Public API ───────────────────────────────────────────────────────────

    def start_session(self) -> int:
        """
        Increment session_count and return the new value (= current session ID).
        Call exactly ONCE at chat_loop startup, not per turn.
        """
        with self._engine.begin() as conn:
            conn.execute(sa_text(
                "UPDATE profile SET session_count = session_count + 1 WHERE id = 1"
            ))
            row = conn.execute(sa_text(
                "SELECT session_count FROM profile WHERE id = 1"
            )).mappings().fetchone()
            return row["session_count"]

    def get_profile(self) -> dict:
        """Return {user_name, session_count, total_turns}."""
        with self._engine.begin() as conn:
            row = conn.execute(sa_text(
                "SELECT user_name, session_count, total_turns FROM profile WHERE id = 1"
            )).mappings().fetchone()
            if row is None:
                return {
                    "user_name": DEFAULT_USER_NAME,
                    "session_count": 0,
                    "total_turns": 0,
                }
            return dict(row)

    def get_recent_topics(self, limit: int = 3) -> list[str]:
        """
        Return the last `limit` semantic topics, most recent first.

        Returns the LLM-extracted topic if available (non-empty), otherwise
        falls back to the raw message. This gives human-readable topics like
        "photosynthesis" instead of verbatim "What is photosynthesis exactly?".
        """
        with self._engine.begin() as conn:
            rows = conn.execute(sa_text(
                "SELECT message, topic FROM topics ORDER BY id DESC LIMIT :lim"
            ), {"lim": limit}).mappings().fetchall()
            return [
                _strip_think_tags(row["topic"] if row["topic"] else row["message"])
                for row in rows
                if _strip_think_tags(row["topic"] if row["topic"] else row["message"])
            ]

    def log_turn(
        self,
        message: str,
        intent: str,
        session_id: int = 0,
        topic: str = "",
    ) -> None:
        """
        Append a user turn to the topics log and increment total_turns.

        Args:
            message:    Raw user input (always stored for audit / fallback display).
            intent:     Classified intent (question, math, general, etc.).
            session_id: Current session number from start_session().
            topic:      LLM-extracted 2-4 word semantic summary (e.g. "gravity waves").
                        If blank, get_recent_topics() will fall back to message.
        """
        with self._engine.begin() as conn:
            conn.execute(sa_text(
                "INSERT INTO topics (session_id, message, topic, intent) "
                "VALUES (:sid, :msg, :topic, :intent)"
            ), {"sid": session_id, "msg": message, "topic": topic, "intent": intent})
            conn.execute(sa_text(
                "UPDATE profile SET total_turns = total_turns + 1 WHERE id = 1"
            ))

    def save_session_summary(self, session_id: int, summary: str) -> None:
        """
        Save a one-sentence episodic summary of the session.

        Called from a background thread in farewell_response after Srinika
        says goodbye. The summary is loaded next session in load_memory and
        shown in greet_response so she sees what she explored last time.
        """
        with self._engine.begin() as conn:
            conn.execute(sa_text(
                "INSERT INTO sessions (session_id, summary) VALUES (:sid, :summary)"
            ), {"sid": session_id, "summary": summary})

    def update_mastery(self, topic: str) -> None:
        """
        Increment the exploration count for a topic (procedural memory).

        Uses a portable UPSERT (ON CONFLICT ... DO UPDATE):
        - If topic_key not seen before → insert with count=1
        - If already seen → increment count + update last_seen + update display

        topic_key is lowercased for case-insensitive deduplication:
        "Photosynthesis" and "photosynthesis" are the same concept.
        display preserves the most-recent LLM extraction form (mixed case, natural).
        """
        if not topic or not topic.strip():
            return
        topic_key = topic.lower().strip()
        now = _now()
        with self._engine.begin() as conn:
            conn.execute(sa_text(
                """
                INSERT INTO mastery (topic_key, display, count, first_seen, last_seen)
                VALUES (:key, :display, 1, :now, :now)
                ON CONFLICT(topic_key) DO UPDATE SET
                    count     = mastery.count + 1,
                    last_seen = :now,
                    display   = excluded.display
                """
            ), {"key": topic_key, "display": topic, "now": now})

    def get_mastery_summary(self, limit: int = 5) -> list[dict]:
        """
        Return top topics by exploration count, most explored first.

        Each entry: {"topic": str, "count": int, "level": str}
        Levels: "curious" (1x) | "learning" (2x) | "practiced" (3-4x) | "expert" (5+x)

        Used by:
          - load_memory → injects into state as mastered_topics
          - greet_response → "You've explored photosynthesis 4 times!"
          - help_response → LLM context: "she knows the basics, go deeper"
          - chat_loop !mastery command → pretty table display
        """
        with self._engine.begin() as conn:
            rows = conn.execute(sa_text(
                "SELECT display, count FROM mastery ORDER BY count DESC LIMIT :lim"
            ), {"lim": limit}).mappings().fetchall()
            return [
                {
                    "topic": row["display"],
                    "count": row["count"],
                    "level": _mastery_level(row["count"]),
                }
                for row in rows
            ]

    def get_last_session_summary(self) -> str:
        """
        Return the most recent session summary, or '' if none exists yet.

        The first session never has a summary (no farewell happened before it).
        Subsequent sessions return the summary written when the previous session ended.
        """
        with self._engine.begin() as conn:
            row = conn.execute(sa_text(
                "SELECT summary FROM sessions ORDER BY id DESC LIMIT 1"
            )).mappings().fetchone()
            return row["summary"] if row else ""

    def load_persona_config(self, persona_name: str = "srinika") -> dict[str, str]:
        """Return all persona config fields as {field_key: field_value}."""
        with self._engine.begin() as conn:
            rows = conn.execute(sa_text(
                "SELECT field_key, field_value FROM persona_config WHERE persona_name = :pn"
            ), {"pn": persona_name}).mappings().fetchall()
            return {row["field_key"]: row["field_value"] for row in rows}

    def save_persona_config(self, persona_name: str, field_key: str, field_value: str) -> None:
        """Upsert a single persona config field."""
        now = _now()
        with self._engine.begin() as conn:
            conn.execute(sa_text(
                """
                INSERT INTO persona_config (persona_name, field_key, field_value, updated_at)
                VALUES (:pn, :fk, :fv, :now)
                ON CONFLICT(persona_name, field_key) DO UPDATE SET
                    field_value = excluded.field_value,
                    updated_at  = :now
                """
            ), {"pn": persona_name, "fk": field_key, "fv": field_value, "now": now})

    # ── Todos (Session 17) ───────────────────────────────────────────────────

    def add_todo(
        self,
        text: str,
        due_date: str | None = None,
        recurrence: str | None = None,
    ) -> int:
        """
        Insert a new todo item and return its id.

        Uses RETURNING id which is supported by PostgreSQL (native) and
        SQLite 3.35+ (Python 3.10 ships with SQLite 3.37+).

        Args:
            text:       What to remember / do (e.g. "finish science project").
            due_date:   Optional date string (e.g. "2026-03-15" or "tomorrow").
            recurrence: Optional repeat cadence ("daily" | "weekly" | None).
        """
        with self._engine.begin() as conn:
            result = conn.execute(sa_text(
                "INSERT INTO todos (text, due_date, recurrence) "
                "VALUES (:text, :due, :recur) RETURNING id"
            ), {"text": text.strip(), "due": due_date, "recur": recurrence})
            return result.scalar()

    def get_pending_todos(self) -> list[dict]:
        """
        Return all undone todos, oldest first.

        Each entry: {id, text, created_at, due_date, recurrence}
        """
        with self._engine.begin() as conn:
            rows = conn.execute(sa_text(
                "SELECT id, text, created_at, due_date, recurrence "
                "FROM todos WHERE done = 0 ORDER BY id ASC"
            )).mappings().fetchall()
            return [dict(row) for row in rows]

    def mark_todo_done(self, todo_id: int) -> None:
        """Mark a todo as done (sets done=1 and records done_at timestamp)."""
        now = _now()
        with self._engine.begin() as conn:
            conn.execute(sa_text(
                "UPDATE todos SET done = 1, done_at = :now WHERE id = :id"
            ), {"now": now, "id": todo_id})

    def delete_todo(self, todo_id: int) -> None:
        """Permanently delete a todo by id."""
        with self._engine.begin() as conn:
            conn.execute(sa_text(
                "DELETE FROM todos WHERE id = :id"
            ), {"id": todo_id})

    def delete_topic_entry(self, topic_text: str) -> None:
        """Delete all topic log entries matching the given display text."""
        with self._engine.begin() as conn:
            conn.execute(sa_text(
                "DELETE FROM topics WHERE topic = :t OR (topic = '' AND message = :t)"
            ), {"t": topic_text})

    def delete_mastery_entry(self, topic_key: str) -> None:
        """Delete a mastery record by topic key (case-insensitive)."""
        with self._engine.begin() as conn:
            conn.execute(sa_text(
                "DELETE FROM mastery WHERE topic_key = :key"
            ), {"key": topic_key.lower().strip()})

    def clear_all_history(self) -> None:
        """Wipe topics, sessions, and mastery — keeps profile and persona config."""
        with self._engine.begin() as conn:
            conn.execute(sa_text("DELETE FROM topics"))
            conn.execute(sa_text("DELETE FROM sessions"))
            conn.execute(sa_text("DELETE FROM mastery"))

    def reset(self) -> None:
        """
        Wipe all memory and reset counters — keeps the DB file open (Windows-safe).
        Used by !reset-memory in chat_loop; avoids the PermissionError from
        trying to delete a file that SQLAlchemy still has open on Windows.
        """
        with self._engine.begin() as conn:
            conn.execute(sa_text("DELETE FROM topics"))
            conn.execute(sa_text("DELETE FROM sessions"))
            conn.execute(sa_text("DELETE FROM mastery"))
            conn.execute(sa_text(
                "UPDATE profile SET session_count = 0, total_turns = 0 WHERE id = 1"
            ))