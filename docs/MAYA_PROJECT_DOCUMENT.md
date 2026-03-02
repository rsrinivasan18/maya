# MAYA — Project Requirements & Technical Architecture Document

**Version:** 1.2
**Date:** 2026-03-02
**Author:** Srinivasan (rsrinivasan18)
**Status:** Active Development — Session 9 complete (Laptop Phase)

---

## 1. Project Overview

### 1.1 What Is MAYA?

MAYA (Multi-Agent hYbrid Assistant) is a bilingual Hindi/English STEM companion for children, built on a multi-agent LangGraph architecture. It listens to a child's voice, understands the question in Hindi, English, or Hinglish, routes it to the appropriate specialist agent, generates a contextually-aware response, speaks the answer aloud, and remembers past conversations across sessions.

MAYA is designed to run fully offline on edge hardware (Raspberry Pi 5 + Hailo AI HAT), making it private, low-latency, and suitable for homes with intermittent internet.

### 1.2 Primary User

**Srinika** — a 10-year-old girl in India, curious about science and math, speaks a natural mix of Hindi and English (Hinglish).

### 1.3 Goals

| Goal | Description |
|------|-------------|
| Functional | Answer STEM questions in Hinglish/Hindi/English using a tiered LLM chain |
| Educational | Step-by-step math tutoring with Indian everyday analogies |
| Persistent | Remember past sessions with semantic topics + episodic summaries |
| Multimodal | Accept voice input (Whisper STT), produce voice output (Piper TTS) |
| Observable | Every graph run traced in LangSmith; visual debugging via LangGraph Studio |
| Portable | Runs on Windows laptop today; Raspberry Pi 5 in Phase 2 |
| Offline-first | Core STEM Q&A works with no internet (Ollama + SQLite + Piper) |
| Online-smart | When online: Sarvam → Claude → OpenAI tiered fallback for best quality |

### 1.4 Non-Goals (current phase)

- Web or mobile frontend (planned Phase 3)
- Cloud-hosted deployment
- Multi-user support
- Wake-word detection (planned)
- Animated face display (next session)

---

## 2. Functional Requirements

### 2.1 Conversation Requirements

| ID | Requirement |
|----|-------------|
| FR-01 | Detect input language: English, Hindi, or Hinglish |
| FR-02 | Classify intent: greeting, farewell, math, question, general |
| FR-03 | Route to specialist agent based on intent |
| FR-04 | Generate contextually appropriate response via LLM |
| FR-05 | Maintain multi-turn conversation history within a session |
| FR-06 | Exit conversation gracefully on farewell intent |

### 2.2 Memory Requirements

| ID | Requirement |
|----|-------------|
| MR-01 | Persist user profile (name, session count, total turns) across restarts |
| MR-02 | Log each user turn (raw message + LLM-extracted semantic topic + intent) |
| MR-03 | Load recent semantic topics at session start; inject into LLM context |
| MR-04 | Welcome returning users with episodic session summary (or semantic topics as fallback) |
| MR-05 | Provide `!reset-memory` command to wipe all data |
| MR-06 | Farewell turns must NOT be stored as topics |
| MR-07 | Generate 1-sentence episodic session summary on farewell (background, non-blocking) |
| MR-08 | Show episodic summary in next session greeting: "Srinika explored gravity and the water cycle." |

### 2.3 Voice I/O Requirements

| ID | Requirement |
|----|-------------|
| VR-01 | Transcribe microphone input using Whisper (offline STT) |
| VR-02 | Handle Hindi, English, and Hinglish transcription correctly |
| VR-03 | Synthesize text responses to audio using Piper TTS (offline) |
| VR-04 | Graceful fallback to keyboard if no microphone detected |

### 2.4 Observability Requirements

| ID | Requirement |
|----|-------------|
| OR-01 | Every graph invocation traced to LangSmith with node-level spans |
| OR-02 | Each trace labelled with run_name, session_id, turn count, user_name |
| OR-03 | LangGraph Studio support via `langgraph.json` and `langgraph-cli` |
| OR-04 | Tracing disabled by default (env var off) — no performance impact in tests |

---

## 3. Architecture

### 3.1 Core Design Principles

1. **Graph as brain** — all conversation logic lives in LangGraph nodes and edges. The chat loop is a thin REPL that only manages I/O.
2. **State as baton** — a single `MayaState` TypedDict flows through every node. Nodes read what they need, write only what they change.
3. **Offline-first** — every component has an offline fallback. Ollama, Piper TTS, Whisper STT, and SQLite all run locally with no internet dependency.
4. **Separation of concerns** — language detection, intent classification, routing, response generation, and memory are distinct nodes with no cross-cutting logic.
5. **Testability by design** — no global state, no singletons. `memory_db_path` is injectable via state for test isolation.

### 3.2 Graph Topology (Current — Session 9)

```
START
  │
  ▼
[load_memory]            ← SQLite: profile + semantic topics + episodic summary
  │
  ▼
[check_connectivity]     ← TCP probe 8.8.8.8:53 → is_online bool in state (Session 8)
  │
  ▼
[detect_language]        ← hindi / english / hinglish (word-set matching)
  │
  ▼
[understand_intent]      ← farewell > greeting > math > question > general
  │
  ├──── greeting  ──► [greet_response]       ── episodic summary or semantic topics
  │
  ├──── farewell  ──► [farewell_response]    ── goodbye + background summary thread
  │
  ├──── math      ──► [math_tutor_response]  ── tiered LLM math agent
  │
  └──── *         ──► [help_response]        ── tiered LLM STEM agent
                              │
                              ▼
                        [save_memory]        ← extract topic via LLM + log to SQLite
                              │
                              ▼
                             END
```

**Session 8 addition:** `check_connectivity` injects `is_online` so LLM nodes pick the right provider tier without re-probing the network.

**Session 9 addition:** `save_memory` now runs a short LLM call to extract a 2-4 word semantic topic. `farewell_response` fires a daemon thread that generates a 1-sentence episodic summary after the goodbye message is shown.

### 3.3 Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Layer 4: I/O Interface                                 │
│  chat_loop.py (REPL) — keyboard + voice + TTS output    │
│  Connectivity check at startup; rich spinner on invoke  │
├─────────────────────────────────────────────────────────┤
│  Layer 3: Graph Orchestration                           │
│  hello_world_graph.py — LangGraph StateGraph            │
│  Nodes: load_memory, check_connectivity, detect_lang    │
│         understand_intent, greet/farewell/math/help,    │
│         save_memory (+ background summary thread)       │
├─────────────────────────────────────────────────────────┤
│  Layer 2: Agent Modules                                 │
│  memory_store.py        — SQLite: profile, topics,      │
│                           sessions (semantic+episodic)  │
│  connectivity_checker.py — TCP probe (socket, stdlib)   │
│  llm_router.py          — Tiered LLM fallback chain     │
│  transcriber.py         — Whisper STT (STTEngine)       │
│  speaker.py             — Piper TTS (TTSEngine)         │
├─────────────────────────────────────────────────────────┤
│  Layer 1: Foundation                                    │
│  state.py     — MayaState TypedDict                     │
│  settings.py  — env-var config (Settings singleton)     │
├─────────────────────────────────────────────────────────┤
│  Layer 0: Runtime                                       │
│  Online:  Sarvam API → Claude API → OpenAI API          │
│  Offline: Ollama (llama3.2:3b) — local LLM inference    │
│  SQLite (~/.maya/memory.db) — persistence               │
│  Piper TTS / Whisper — offline audio I/O                │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Data Model

### 4.1 MayaState — The Graph's Shared State

```python
class MayaState(TypedDict):
    # ── Input ─────────────────────────────────────────────
    user_input: str          # Raw text from user this turn

    # ── Processing ────────────────────────────────────────
    language: str            # "english" | "hindi" | "hinglish"
    intent: str              # "greeting" | "farewell" | "math"
                             # "question" | "general"

    # ── Output ────────────────────────────────────────────
    response: str            # MAYA's reply

    # ── Conversation Memory (Reducer) ─────────────────────
    message_history: Annotated[list[dict], operator.add]
    # Each dict: {"role": "user"|"assistant", "content": str}
    # operator.add = LangGraph APPENDS new messages, never replaces

    # ── Persistent Memory (NotRequired = backward compat) ─
    user_name:      NotRequired[str]        # from SQLite profile
    session_count:  NotRequired[int]        # how many sessions ever
    recent_topics:  NotRequired[list[str]]  # last 3 semantic topics (Session 9)
    session_id:     NotRequired[int]        # current session number
    memory_db_path: NotRequired[str]        # override for test isolation

    # ── Connectivity (Session 8) ──────────────────────────
    is_online:      NotRequired[bool]       # set by check_connectivity node

    # ── Episodic Memory (Session 9) ───────────────────────
    last_session_summary: NotRequired[str]  # 1-sentence summary of previous session

    # ── Debug ─────────────────────────────────────────────
    steps: list[str]         # trace log: "[node_name] → result"
```

**Key design decisions:**
- `Annotated[list, operator.add]` — LangGraph reducer. Nodes return `[new_msg]`, LangGraph concatenates automatically. No manual append logic.
- `NotRequired` fields — added across sessions without breaking any existing tests. Each new field has a safe default via `.get()`.
- `memory_db_path` — allows tests to inject a temp SQLite path, achieving full isolation from production DB.
- `is_online` — set once per turn by `check_connectivity`; all LLM nodes read from state (no extra probes).
- `last_session_summary` — empty string on first-ever session; populated by `farewell_response` background thread after that.

### 4.2 SQLite Schema (`~/.maya/memory.db`)

```sql
-- Exactly one row, enforced by CHECK constraint
CREATE TABLE profile (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    user_name     TEXT    NOT NULL DEFAULT 'Srinika',
    session_count INTEGER NOT NULL DEFAULT 0,
    total_turns   INTEGER NOT NULL DEFAULT 0
);

-- Append-only turn log (Session 9: added topic column)
CREATE TABLE topics (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL DEFAULT 0,
    message    TEXT    NOT NULL,           -- raw user_input (always stored, audit trail)
    topic      TEXT    NOT NULL DEFAULT '', -- LLM-extracted 2-4 word semantic summary
    intent     TEXT    NOT NULL DEFAULT 'general',
    timestamp  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Episodic session summaries (Session 9: new table)
CREATE TABLE sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL DEFAULT 0,
    summary    TEXT    NOT NULL DEFAULT '', -- "Srinika explored gravity and the water cycle."
    timestamp  TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

**`topics.message` vs `topics.topic`:**
- `message` — verbatim user_input, always stored. Never shown to user in greeting.
- `topic` — LLM-extracted summary (e.g., "photosynthesis", "Newton laws motion"). Shown in greeting.
- `get_recent_topics()` returns `topic` if non-empty, else `message` (backward-compat fallback for rows written before Session 9).

**`sessions.summary` lifecycle:**
- Written by `farewell_response` background thread (after goodbye, non-blocking).
- Read by `load_memory` at next session start.
- Shown by `greet_response` as the primary recall message.
- Falls back to `recent_topics` if no summary exists (e.g., session was force-quit, not farewell).

**Migration:** The `topic` column is added to existing `topics` tables via `ALTER TABLE ... ADD COLUMN` wrapped in `try/except` — safe on any Python SQLite version.

**Why SQLite:**
- Single file, no server, works offline
- Python built-in `sqlite3` module (zero dependencies)
- Persists across sessions — MAYA has real long-term memory
- Trivially portable to RPi5

---

## 5. Component Specifications

### 5.1 Language Detection (`detect_language`)

**Method:** Word-set intersection (no ML, no API)

```
hindi_markers = { "kya", "hai", "main", "aap", ... }
words_in_input = {w.strip(".,!?") for w in user_input.split()}
hindi_count = len(words_in_input & hindi_markers)

hindi_count >= 2  → "hindi"
hindi_count == 1  → "hinglish"
hindi_count == 0  → "english"
```

**Why not ML:** Unnecessary complexity for a known, bounded vocabulary. Fast, offline, transparent, and 100% testable.

### 5.2 Intent Detection (`understand_intent`)

**Method:** Word-set membership with precedence chain

```
Precedence: farewell > greeting > math > question > general
```

**Key fix (Session 6):** Substring matching (`"hi" in text`) caused false positives — "hi" matched "hindi". Changed to set membership: `"hi" in words_set`. Greeting also has a 6-word length guard to prevent "namaste, photosynthesis kya hai?" being classified as a greeting.

### 5.3 Multi-Tier LLM System (`llm_router.py` + `connectivity_checker.py`)

**Session 8** replaced direct `ollama.chat()` calls with a tiered fallback chain managed by `call_llm_tiered()`.

#### Connectivity Check
`ConnectivityChecker.is_online()` performs a raw TCP connect to `8.8.8.8:53` (Google DNS) with a 2-second timeout. No DNS resolution, no HTTP — the lightest possible probe. Result injected into state once per turn by the `check_connectivity` node.

#### Tier Chain

```
is_online = True                    is_online = False
     │                                    │
     ▼                                    ▼
┌─────────────┐                    ┌─────────────┐
│  Tier 1     │  if HAS_SARVAM_KEY │  Tier 4     │
│  Sarvam AI  │──────────────────► │  Ollama     │
│  sarvam-m   │  on error ↓        │  llama3.2:3b│
│  24B model  │                    └─────────────┘
└─────────────┘
     │ on error ↓
┌─────────────┐
│  Tier 2     │  if HAS_ANTHROPIC_KEY
│  Claude     │  claude-haiku-4-5-20251001
│  max 300 tok│
└─────────────┘
     │ on error ↓
┌─────────────┐
│  Tier 3     │  if HAS_OPENAI_KEY
│  OpenAI     │  gpt-4o-mini
│  max 300 tok│
└─────────────┘
     │ on error ↓
┌─────────────┐
│  Tier 4     │  always
│  Ollama     │  llama3.2:3b (local)
└─────────────┘
```

**Key properties of the tier chain:**
- Each tier is only attempted if the corresponding API key is present in `.env`
- Any `Exception` in a tier silently falls through to the next — no crash, no user-visible error
- Lazy imports (`import anthropic as _anthropic` inside `try`) — if package not installed, tier is skipped via `ImportError`
- Returns `(response_text, provider_label)` — caller logs it as `[help_response/sarvam]`, visible in `--debug` trace

**Sarvam API details:**
- Endpoint: `https://api.sarvam.ai/v1/chat/completions`
- Auth: `api-subscription-key` header (not `Authorization: Bearer`)
- Model: `sarvam-m` (24B, optimised for Indian languages, Hindi/Hinglish quality >> other models)
- Implementation: `urllib.request` (Python stdlib, zero new dependencies)

#### Two LLM agents, same tier chain, different prompts
- `help_response` — MAYA personality: warm, analogies, STEM teacher
- `math_tutor_response` — Math tutor: solve first, explain each step, Indian analogies, end with practice problem
- `save_memory` topic extraction — ultra-short prompt: "Extract main topic in 2-4 words"
- `farewell_response` episode summary — "Summarize in one sentence starting with 'Srinika explored'"

**Per-turn language reminder in system prompt:** 3B models (and even 24B models with mixed-language inputs) need an explicit `"CRITICAL: respond in Hinglish"` every call or they drift to English.

### 5.4 Memory Store (`MemoryStore`)

**Design:** Instantiated fresh per node call. No singleton, no global state.

```python
class MemoryStore:
    def start_session(self) -> int                          # increment + return session_count
    def get_profile(self) -> dict                           # user_name, session_count, total_turns
    def get_recent_topics(limit=3) -> list[str]            # last N semantic topics (Session 9)
    def log_turn(msg, intent, sid, topic="")               # append to topics + increment total_turns
    def save_session_summary(session_id, summary)          # store episodic summary (Session 9)
    def get_last_session_summary() -> str                  # most recent summary, or "" (Session 9)
    def reset()                                             # SQL DELETE + UPDATE (Windows-safe)
```

**Three memory types implemented:**

| Type | Storage | Written by | Read by | Example |
|------|---------|-----------|---------|---------|
| **Semantic** | `topics.topic` | `save_memory` node (hot path) | `load_memory` → `help_response`, `greet_response` | `"photosynthesis"`, `"gravity waves"` |
| **Episodic** | `sessions.summary` | `farewell_response` (background thread) | `load_memory` → `greet_response` | `"Srinika explored gravity and the water cycle."` |
| **Procedural** | (future) | — | — | concepts mastered |

**Semantic memory detail:**
`save_memory` calls `call_llm_tiered` with a one-line prompt after each non-farewell turn.
Returns 2-4 words stored in `topics.topic`. `get_recent_topics()` returns `topic` if non-empty, else `message` (fallback for rows written before Session 9 or when LLM extraction failed).

**Episodic memory detail:**
`farewell_response` fires a `threading.Thread(daemon=True)` that:
1. Builds compact conversation digest (≤ 800 chars)
2. Calls `call_llm_tiered` with summary prompt
3. Writes result to `sessions` table

`daemon=True` means: if the process exits before the thread finishes (e.g., Ctrl+C immediately after bye), the thread is auto-killed. No hanging processes, no DB corruption.

**Windows-safe reset:** `Path.unlink()` raises `PermissionError WinError 32` on Windows because SQLite holds a file lock. `reset()` uses `DELETE FROM topics`, `DELETE FROM sessions`, and `UPDATE profile SET ...` — keeps the file open, clears data in-place.

### 5.5 STT Engine (`STTEngine`)

**Model:** `faster-whisper` base (4x faster than openai-whisper, int8 on CPU)

**Bilingual strategy:** Transcribe Hindi-first. If confidence < 0.65, retry with English. Fixes faster-whisper's known bug where Hindi gets misdetected as Arabic.

### 5.6 TTS Engine (`TTSEngine`)

**Engine:** Piper TTS (offline neural, ONNX-based)

**Voice:** `en_US-lessac-medium` (stable female voice; no stable hi_IN voice in Piper catalog yet)

**In-memory synthesis:** WAV bytes generated in memory, played via `sounddevice`. No temp files.

---

## 6. Routing Logic

### 6.1 Conditional Edge: `route_by_intent`

```python
def route_by_intent(state) -> str:
    intent = state.get("intent", "general")
    if intent == "greeting":  return "greet_response"
    if intent == "farewell":  return "farewell_response"
    if intent == "math":      return "math_tutor_response"
    return "help_response"   # question + general
```

This is a **pure function** — no side effects, fully testable, returns a string key that LangGraph uses to select the next node.

---

## 7. Observability

### 7.1 LangSmith Tracing

Each `maya_graph.invoke()` call passes:
```python
config={
    "run_name": f"MAYA-turn-{turn_count}",
    "metadata": {"session_id": session_id, "turn": turn_count, "user_name": "Srinika"},
    "tags": ["maya", "production"],
}
```

Tracing is enabled only when `LANGCHAIN_TRACING_V2=true` in `.env` — tests run with it off.

### 7.2 LangGraph Studio

`langgraph.json` points Studio at `maya_graph`. Running `langgraph dev` starts a local FastAPI server on port 2024. Studio at `smith.langchain.com` connects via API key tunnel. All execution stays on the local machine.

---

## 8. Testing Strategy

### 8.1 Test Classes

| Class | Tests | What It Covers |
|-------|-------|----------------|
| `TestLanguageDetection` | 5 | English / Hindi / Hinglish detection |
| `TestIntentDetection` | 12 | All intents + edge cases + precedence |
| `TestConditionalRouting` | 4 | Each intent routes to correct node |
| `TestMessageHistory` | 4 | Accumulation, reducer, turn count |
| `TestEndToEnd` | 4 | Full graph invocation, all fields populated |
| `TestMemoryNodes` | 4 | SQLite load/save, defaults, farewell skip |
| `TestMathTutorAgent` | 4 | Math routing, non-math exclusion |
| `TestConnectivityRouting` | 4 | is_online bool, check_connectivity step, tier routing, provider label |
| **Total** | **42** | |

### 8.2 Test Isolation Pattern

```python
def test_save_memory_logs_turn(self, tmp_path):
    db = str(tmp_path / "test.db")
    maya_graph.invoke({..., "memory_db_path": db})
    store = MemoryStore(db_path=db)
    # Session 9: get_recent_topics() returns semantic topic, not verbatim message
    assert len(store.get_recent_topics()) >= 1
```

`tmp_path` is a pytest fixture that provides a unique temp directory per test. Injecting `memory_db_path` into state means tests never touch `~/.maya/memory.db`.

---

## 9. Configuration

### 9.1 Settings (`src/maya/config/settings.py`)

All configuration from environment variables, loaded via `python-dotenv`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `LANGCHAIN_TRACING_V2` | false | Enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | — | LangSmith API key (from `.env`, gitignored) |
| `LANGCHAIN_PROJECT` | maya-assistant | LangSmith project name |
| `SARVAM_API_KEY` | — | Sarvam AI key — enables Tier 1 LLM |
| `ANTHROPIC_API_KEY` | — | Claude API key — enables Tier 2 LLM |
| `OPENAI_API_KEY` | — | OpenAI API key — enables Tier 3 LLM |
| `OLLAMA_BASE_URL` | http://localhost:11434 | Ollama server URL |
| `OLLAMA_MODEL` | llama3.2:3b | Default local LLM model |
| `MAYA_OFFLINE_MODE` | false | Force offline-only (skip Tiers 1–3) |
| `MAYA_CONNECTIVITY_HOST` | 8.8.8.8 | Host to probe for internet check |
| `MAYA_CONNECTIVITY_PORT` | 53 | Port to probe (DNS) |
| `MAYA_CONNECTIVITY_TIMEOUT` | 2.0 | TCP probe timeout (seconds) |
| `MAYA_LANGUAGE` | hinglish | Preferred response language |

**`HAS_*_KEY` flags:** `settings.HAS_SARVAM_KEY`, `settings.HAS_ANTHROPIC_KEY`, `settings.HAS_OPENAI_KEY` are computed bools — True only if the corresponding key env var is non-empty. LLM router checks these before attempting each tier. Keys are never stored as strings in Settings.

### 9.2 Security

- `.env` is gitignored — API keys never committed
- `.env.example` has placeholder values only — safe to commit
- No secrets hardcoded anywhere in source

---

## 10. Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent framework | LangGraph | Used at BNP Paribas; production-grade; state machine model fits conversation flow |
| LLM runtime | Tiered chain (Session 8) | Sarvam best for Hindi/Hinglish; Claude/OpenAI as fallback; Ollama always available offline |
| Online LLM default | Sarvam (Tier 1) | 24B model purpose-built for Indian languages; best Hinglish quality |
| Offline LLM | Ollama (llama3.2:3b) | Fully offline, ~2GB, good enough for STEM Q&A on CPU |
| Connectivity probe | TCP to 8.8.8.8:53 | No DNS, no HTTP; lightest possible check; instant (< 2s) |
| Connectivity check | Once per turn, injected into state | LLM nodes read `is_online` from state — no redundant probes |
| Lazy imports | `import anthropic as _anthropic` inside try | If package not installed, tier is skipped via ImportError; graceful degradation |
| Sarvam HTTP | `urllib.request` (stdlib) | No new pip dependency; just a JSON POST |
| Language detection | Word-set matching | No ML needed; fast, offline, transparent, 100% testable |
| Intent matching | Set membership, not substring | `"hi" in "hindi"` = True (bug); `"hi" in word_set` = False (correct) |
| Memory store | SQLite | Single file, no server, Python built-in, portable to RPi5 |
| Memory isolation | `memory_db_path` state field | Tests use `tmp_path`; production uses `~/.maya/memory.db` |
| MemoryStore | Fresh per call, no singleton | Clean, testable, no global state |
| Reset method | SQL DELETE + UPDATE | `Path.unlink()` fails on Windows (SQLite file lock); SQL in-place is safe |
| Semantic memory | LLM extraction in `save_memory` | 2-4 word topic is human-readable in greeting; verbatim message is mechanical |
| Episodic summary | Background daemon thread | Must never block UX; farewell message appears instantly |
| Background thread | `daemon=True` | Auto-killed if process exits; no hanging threads or DB corruption |
| Topic fallback | `message` if `topic` blank | Backward-compat for rows written before Session 9 or on LLM failure |
| Multi-agent pattern | Same tier chain, different prompts | `math_tutor_response` = same router, different system prompt |
| `steps` field | `state.get("steps", [])` | LangGraph Studio sends minimal state; `.get()` is defensive |
| Farewell not saved | Early return in `save_memory` | "bye" is a command, not a topic to recall |
| `NotRequired` fields | Backward-compat state extension | All existing tests pass unmodified when new fields added |
| Language prompt | Per-turn system prompt injection | 3B models (and larger) drift to English without explicit per-turn reminder |
| STT language | Hindi-first, English fallback | faster-whisper misdetects Hindi as Arabic |
| TTS voice | en_US-lessac-medium | No stable Hindi voice in Piper catalog |
| Observability | LangSmith free tier | Sufficient; already a LangChain dependency |

---

## 11. File Structure

```
maya/
├── chat_loop.py                          # Main REPL (keyboard + voice + spinner)
├── langgraph.json                        # LangGraph Studio config
├── requirements.txt
├── .env.example                          # Template (safe to commit)
├── .env                                  # Real keys (gitignored)
│
├── src/maya/
│   ├── config/
│   │   └── settings.py                  # Env-var config + HAS_*_KEY flags
│   ├── models/
│   │   └── state.py                     # MayaState TypedDict
│   ├── graph/
│   │   └── hello_world_graph.py         # All nodes + graph assembly
│   ├── agents/
│   │   ├── memory_store.py              # SQLite: profile, topics, sessions
│   │   ├── connectivity_checker.py      # TCP probe → is_online (Session 8)
│   │   └── llm_router.py               # Tiered LLM fallback chain (Session 8)
│   ├── stt/
│   │   └── transcriber.py              # Whisper STTEngine
│   └── tts/
│       └── speaker.py                  # Piper TTSEngine
│
├── tests/
│   └── test_hello_world.py             # 42 tests
│
└── dev_log/
    ├── 2026-02-28.md                   # Sessions 4–7
    └── 2026-03-02.md                   # Sessions 8–9
```

---

## 12. Deployment Plan

### Phase 1 (Current): Windows Laptop
- Python 3.13.2 + `.venv`
- Ollama running as background service
- `python chat_loop.py [--voice] [--speak]`

### Phase 2: Raspberry Pi 5
- RPi5 8GB + Hailo AI HAT+ 2 (40 TOPS)
- Same Python code, same `requirements.txt`
- Ollama on RPi or Hailo-accelerated inference
- Autostart on boot (systemd service)
- `langgraph build` → Docker container deployment

### Phase 3: Physical Robot
- SunFounder PiDog V2 body
- Same MAYA brain; add movement nodes to graph
- Physical emotion expression (tail wag = excited, etc.)
