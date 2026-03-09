"""
MAYA Memory Store - Session 10 Update
======================================
Persistent SQLite memory for MAYA.

Stores:
  - User profile: user name, session count, total turns
  - Topic log: every user message + semantic topic (extracted by LLM) + intent
  - Session summaries: one-sentence episodic summary per session (from farewell node)
  - Mastery log: how many times Srinika has explored each topic (procedural memory)

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

Session 9 — Three memory improvements:
  1. Semantic memory (topic column):
     Each turn stores a 2-4 word LLM-extracted topic (e.g. "photosynthesis",
     "Newton laws motion") instead of the raw user_input verbatim.
     get_recent_topics() returns topic (or falls back to message if blank).

  2. Episodic memory (sessions table):
     On farewell, a background thread generates a 1-sentence session summary
     (e.g. "Srinika explored gravity and the water cycle").
     Loaded next session and shown in the greeting: Srinika sees what she
     studied last time, not a mechanical transcript of her own words.

  3. Procedural memory (mastery table):
     Each time a topic is extracted, its count is incremented in the mastery table.
     Levels: curious (1x) → learning (2x) → practiced (3-4x) → expert (5+x).
     Surfaced in greet_response ("You've explored photosynthesis 4 times!") and
     injected into LLM system prompts so MAYA builds on prior knowledge.
"""

import re
import sqlite3
from pathlib import Path

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks that some LLMs leak into output."""
    return _THINK_RE.sub("", text).strip()

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


class MemoryStore:
    """
    SQLite-backed persistent memory for MAYA.

    Tables
    ------
    profile:  Exactly one row — user_name, session_count, total_turns
    topics:   Append-only turn log — session_id, message, topic, intent, timestamp
    sessions: One row per session — session_id, summary (episodic)

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
                    topic      TEXT    NOT NULL DEFAULT '',
                    intent     TEXT    NOT NULL DEFAULT 'general',
                    timestamp  TEXT    NOT NULL DEFAULT (datetime('now'))
                )
            """)
            # Session 9: safe migration for existing DBs that predate the topic column.
            # ALTER TABLE ADD COLUMN fails silently if the column already exists.
            try:
                conn.execute(
                    "ALTER TABLE topics ADD COLUMN topic TEXT NOT NULL DEFAULT ''"
                )
            except Exception:
                pass  # Column already exists — ignore

            # Session 9: episodic session summaries table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL DEFAULT 0,
                    summary    TEXT    NOT NULL DEFAULT '',
                    timestamp  TEXT    NOT NULL DEFAULT (datetime('now'))
                )
            """)

            # Session 10: procedural memory — how many times each topic was explored
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mastery (
                    topic_key  TEXT    PRIMARY KEY,
                    display    TEXT    NOT NULL,
                    count      INTEGER NOT NULL DEFAULT 1,
                    first_seen TEXT    NOT NULL DEFAULT (datetime('now')),
                    last_seen  TEXT    NOT NULL DEFAULT (datetime('now'))
                )
            """)

            # Session 14: editable persona configuration
            conn.execute("""
                CREATE TABLE IF NOT EXISTS persona_config (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    persona_name TEXT NOT NULL DEFAULT 'srinika',
                    field_key    TEXT NOT NULL,
                    field_value  TEXT NOT NULL,
                    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(persona_name, field_key)
                )
            """)

            # Seed exactly one profile row if the DB is brand new.
            # INSERT OR IGNORE: if id=1 already exists, does nothing.
            conn.execute("""
                INSERT OR IGNORE INTO profile (id, user_name, session_count, total_turns)
                VALUES (1, ?, 0, 0)
            """, (DEFAULT_USER_NAME,))

            # Seed default persona config for 'srinika' on first run.
            _srinika_defaults = [
                ('srinika', 'tone',           'warm and playful didi, never formal'),
                ('srinika', 'language',       'Hindi and English mixed — Hinglish OK'),
                ('srinika', 'grade_level',    'Grade 4, age 9'),
                ('srinika', 'greeting_style', 'Short and warm. Never mention session numbers, mastery counts, or past learning history. Just say hello and ask what to explore today.'),
                ('srinika', 'response_style', 'Use Indian analogies (chai, roti, cricket). Keep responses short. Always end with one fun question.'),
                ('srinika', 'avoid',          'Never say session number. Never say mastery count. Never summarize past sessions in greeting. Sidebar handles metadata — not you.'),
            ]
            for persona_name, field_key, field_value in _srinika_defaults:
                conn.execute(
                    "INSERT OR IGNORE INTO persona_config (persona_name, field_key, field_value) VALUES (?, ?, ?)",
                    (persona_name, field_key, field_value),
                )
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
        """
        Return the last `limit` semantic topics, most recent first.

        Returns the LLM-extracted topic if available (non-empty), otherwise
        falls back to the raw message. This gives human-readable topics like
        "photosynthesis" instead of verbatim "What is photosynthesis exactly?".
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT message, topic FROM topics ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
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
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO topics (session_id, message, topic, intent) VALUES (?, ?, ?, ?)",
                (session_id, message, topic, intent),
            )
            conn.execute(
                "UPDATE profile SET total_turns = total_turns + 1 WHERE id = 1"
            )
            conn.commit()

    def save_session_summary(self, session_id: int, summary: str) -> None:
        """
        Save a one-sentence episodic summary of the session.

        Called from a background thread in farewell_response after Srinika
        says goodbye. The summary is loaded next session in load_memory and
        shown in greet_response so she sees what she explored last time.
        """
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, summary) VALUES (?, ?)",
                (session_id, summary),
            )
            conn.commit()

    def update_mastery(self, topic: str) -> None:
        """
        Increment the exploration count for a topic (procedural memory).

        Uses SQLite's UPSERT (INSERT OR REPLACE equivalent) via ON CONFLICT:
        - If topic_key not seen before → insert with count=1
        - If already seen → increment count + update last_seen + update display

        topic_key is lowercased for case-insensitive deduplication:
        "Photosynthesis" and "photosynthesis" are the same concept.
        display preserves the most-recent LLM extraction form (mixed case, natural).
        """
        if not topic or not topic.strip():
            return
        topic_key = topic.lower().strip()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mastery (topic_key, display)
                VALUES (?, ?)
                ON CONFLICT(topic_key) DO UPDATE SET
                    count     = count + 1,
                    last_seen = datetime('now'),
                    display   = excluded.display
                """,
                (topic_key, topic),
            )
            conn.commit()

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
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT display, count FROM mastery ORDER BY count DESC LIMIT ?",
                (limit,),
            ).fetchall()
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
        with self._connect() as conn:
            row = conn.execute(
                "SELECT summary FROM sessions ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return row["summary"] if row else ""

    def load_persona_config(self, persona_name: str = "srinika") -> dict[str, str]:
        """Return all persona config fields as {field_key: field_value}."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT field_key, field_value FROM persona_config WHERE persona_name = ?",
                (persona_name,),
            ).fetchall()
            return {row["field_key"]: row["field_value"] for row in rows}

    def save_persona_config(self, persona_name: str, field_key: str, field_value: str) -> None:
        """Upsert a single persona config field."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO persona_config (persona_name, field_key, field_value)
                VALUES (?, ?, ?)
                ON CONFLICT(persona_name, field_key) DO UPDATE SET
                    field_value = excluded.field_value,
                    updated_at  = datetime('now')
                """,
                (persona_name, field_key, field_value),
            )
            conn.commit()

    def delete_topic_entry(self, topic_text: str) -> None:
        """Delete all topic log entries matching the given display text."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM topics WHERE topic = ? OR (topic = '' AND message = ?)",
                (topic_text, topic_text),
            )
            conn.commit()

    def delete_mastery_entry(self, topic_key: str) -> None:
        """Delete a mastery record by topic key (case-insensitive)."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM mastery WHERE topic_key = ?",
                (topic_key.lower().strip(),),
            )
            conn.commit()

    def clear_all_history(self) -> None:
        """Wipe topics, sessions, and mastery — keeps profile and persona config."""
        with self._connect() as conn:
            conn.execute("DELETE FROM topics")
            conn.execute("DELETE FROM sessions")
            conn.execute("DELETE FROM mastery")
            conn.commit()

    def reset(self) -> None:
        """
        Wipe all memory and reset counters — keeps the DB file open (Windows-safe).
        Used by !reset-memory in chat_loop; avoids the PermissionError from
        trying to delete a file that SQLite still has locked on Windows.
        """
        with self._connect() as conn:
            conn.execute("DELETE FROM topics")
            conn.execute("DELETE FROM sessions")
            conn.execute("DELETE FROM mastery")
            conn.execute(
                "UPDATE profile SET session_count = 0, total_turns = 0 WHERE id = 1"
            )
            conn.commit()
