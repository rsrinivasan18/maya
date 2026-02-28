# MAYA — Project Requirements & Technical Architecture Document

**Version:** 1.0
**Date:** 2026-02-28
**Author:** Srinivasan (rsrinivasan18)
**Status:** Active Development — Week 4 of 6 (Laptop Phase)

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
| Functional | Answer STEM questions in Hinglish/Hindi/English using a local LLM |
| Educational | Step-by-step math tutoring with Indian everyday analogies |
| Persistent | Remember the child's name, session count, and past topics across restarts |
| Multimodal | Accept voice input (Whisper STT), produce voice output (Piper TTS) |
| Observable | Every graph run traced in LangSmith; visual debugging via LangGraph Studio |
| Portable | Runs on Windows laptop today; Raspberry Pi 5 in Phase 2 |
| Offline-first | Core STEM Q&A works with no internet (Ollama + SQLite + Piper) |

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
| MR-02 | Log each user turn (message, intent, session_id) to persistent store |
| MR-03 | Load recent topics at session start; inject into LLM context |
| MR-04 | Welcome returning users with name + last topic recall |
| MR-05 | Provide `!reset-memory` command to wipe all data |
| MR-06 | Farewell turns must NOT be stored as topics |

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

### 3.2 Graph Topology (Current — Session 7)

```
START
  │
  ▼
[load_memory]          ← reads SQLite: profile + recent topics
  │
  ▼
[detect_language]      ← hindi / english / hinglish (word-set matching)
  │
  ▼
[understand_intent]    ← farewell > greeting > math > question > general
  │
  ├──── greeting  ──► [greet_response]       ── "Welcome back, Srinika!"
  │
  ├──── farewell  ──► [farewell_response]    ── "Goodbye! X turns today."
  │
  ├──── math      ──► [math_tutor_response]  ── step-by-step Ollama agent
  │
  └──── *         ──► [help_response]        ── general STEM Ollama agent
                              │
                              ▼
                        [save_memory]        ← logs turn to SQLite (skips farewell)
                              │
                              ▼
                             END
```

### 3.3 Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Layer 4: I/O Interface                                 │
│  chat_loop.py (REPL) — keyboard + voice + TTS output    │
├─────────────────────────────────────────────────────────┤
│  Layer 3: Graph Orchestration                           │
│  hello_world_graph.py — LangGraph StateGraph            │
│  Nodes: load_memory, detect_language, understand_intent  │
│         greet/farewell/math/help response, save_memory  │
├─────────────────────────────────────────────────────────┤
│  Layer 2: Agent Modules                                 │
│  memory_store.py — SQLite persistence (MemoryStore)     │
│  transcriber.py  — Whisper STT (STTEngine)              │
│  speaker.py      — Piper TTS (TTSEngine)                │
├─────────────────────────────────────────────────────────┤
│  Layer 1: Foundation                                    │
│  state.py     — MayaState TypedDict                     │
│  settings.py  — env-var config (Settings singleton)     │
├─────────────────────────────────────────────────────────┤
│  Layer 0: Runtime                                       │
│  Ollama (llama3.2:3b) — local LLM inference             │
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
    recent_topics:  NotRequired[list[str]]  # last 3 user messages
    session_id:     NotRequired[int]        # current session number
    memory_db_path: NotRequired[str]        # override for test isolation

    # ── Debug ─────────────────────────────────────────────
    steps: list[str]         # trace log: "[node_name] → result"
```

**Key design decisions:**
- `Annotated[list, operator.add]` — LangGraph reducer. Nodes return `[new_msg]`, LangGraph concatenates automatically. No manual append logic.
- `NotRequired` fields — added in Session 5 without breaking any of the 30 existing tests.
- `memory_db_path` — allows tests to inject a temp SQLite path, achieving full isolation from production DB.

### 4.2 SQLite Schema (`~/.maya/memory.db`)

```sql
-- Exactly one row, enforced by CHECK constraint
CREATE TABLE profile (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    user_name     TEXT    NOT NULL DEFAULT 'Srinika',
    session_count INTEGER NOT NULL DEFAULT 0,
    total_turns   INTEGER NOT NULL DEFAULT 0
);

-- Append-only turn log
CREATE TABLE topics (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL DEFAULT 0,
    message    TEXT    NOT NULL,
    intent     TEXT    NOT NULL DEFAULT 'general',
    timestamp  TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

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

### 5.3 LLM Integration (Ollama)

**Model:** `llama3.2:3b` (Q4_K_M quantized, ~2GB, CPU-only)

**Pattern used for all LLM nodes:**
```python
messages = [{"role": "system", "content": system_prompt}] + message_history
result = ollama.chat(model="llama3.2:3b", messages=messages)
```

**Two LLM agents, same model, different prompts:**
- `help_response` — MAYA personality: warm, analogies, STEM teacher
- `math_tutor_response` — Math tutor: solve first, explain each step, Indian analogies, end with practice problem

**Per-turn language reminder in system prompt:** 3B models need an explicit `"CRITICAL: respond in Hinglish"` every call or they drift to English.

### 5.4 Memory Store (`MemoryStore`)

**Design:** Instantiated fresh per node call. No singleton, no global state.

```python
class MemoryStore:
    def start_session(self) -> int        # increment + return session_count
    def get_profile(self) -> dict         # user_name, session_count, total_turns
    def get_recent_topics(limit=3)        # last N messages (most recent first)
    def log_turn(message, intent, sid)    # append to topics + increment total_turns
    def reset()                           # SQL DELETE + UPDATE (Windows-safe, no file delete)
```

**Windows-safe reset:** `Path.unlink()` raises `PermissionError WinError 32` on Windows because SQLite holds a file lock. `reset()` uses `DELETE FROM topics` + `UPDATE profile SET ...` instead — keeps the file open, clears data in-place.

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
| **Total** | **38** | |

### 8.2 Test Isolation Pattern

```python
def test_save_memory_logs_turn(self, tmp_path):
    db = str(tmp_path / "test.db")
    maya_graph.invoke({..., "memory_db_path": db})
    store = MemoryStore(db_path=db)
    assert "photosynthesis" in store.get_recent_topics()
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
| `OLLAMA_BASE_URL` | http://localhost:11434 | Ollama server URL |
| `OLLAMA_MODEL` | sarvam2b:4bit | Default LLM model |
| `MAYA_OFFLINE_MODE` | false | Force offline-only operation |
| `MAYA_LANGUAGE` | hinglish | Preferred response language |

### 9.2 Security

- `.env` is gitignored — API keys never committed
- `.env.example` has placeholder values only — safe to commit
- No secrets hardcoded anywhere in source

---

## 10. Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent framework | LangGraph | Used at BNP Paribas; production-grade; state machine model fits conversation flow |
| LLM runtime | Ollama (llama3.2:3b) | Fully offline, ~2GB, good enough for STEM Q&A on CPU |
| Language detection | Word-set matching | No ML needed; fast, offline, transparent, 100% testable |
| Intent matching | Set membership, not substring | `"hi" in "hindi"` = True (bug); `"hi" in word_set` = False (correct) |
| Memory store | SQLite | Single file, no server, Python built-in, portable to RPi5 |
| Memory isolation | `memory_db_path` state field | Tests use `tmp_path`; production uses `~/.maya/memory.db` |
| MemoryStore | Fresh per call, no singleton | Clean, testable, no global state |
| Reset method | SQL DELETE + UPDATE | `Path.unlink()` fails on Windows (SQLite file lock); SQL in-place is safe |
| Multi-agent pattern | Same model, different prompts | `math_tutor_response` = same Ollama, different system prompt |
| `steps` field | `state.get("steps", [])` | LangGraph Studio sends minimal state; `.get()` is defensive |
| Farewell not saved | Early return in `save_memory` | "bye" is a command, not a topic to recall |
| `NotRequired` fields | Backward-compat state extension | 30 existing tests pass unmodified after Session 5 |
| Language prompt | Per-turn system prompt injection | 3B models drift to English without explicit per-turn reminder |
| STT language | Hindi-first, English fallback | faster-whisper misdetects Hindi as Arabic |
| TTS voice | en_US-lessac-medium | No stable Hindi voice in Piper catalog |
| Observability | LangSmith free tier | Sufficient; already a LangChain dependency |

---

## 11. File Structure

```
maya/
├── chat_loop.py                          # Main REPL (keyboard + voice)
├── langgraph.json                        # LangGraph Studio config
├── requirements.txt
├── .env.example                          # Template (safe to commit)
├── .env                                  # Real keys (gitignored)
│
├── src/maya/
│   ├── config/
│   │   └── settings.py                  # Env-var config singleton
│   ├── models/
│   │   └── state.py                     # MayaState TypedDict
│   ├── graph/
│   │   └── hello_world_graph.py         # All nodes + graph assembly
│   ├── agents/
│   │   └── memory_store.py              # SQLite MemoryStore
│   ├── stt/
│   │   └── transcriber.py              # Whisper STTEngine
│   └── tts/
│       └── speaker.py                  # Piper TTSEngine
│
├── tests/
│   └── test_hello_world.py             # 38 tests
│
└── dev_log/
    └── 2026-02-28.md                   # Session notes
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
