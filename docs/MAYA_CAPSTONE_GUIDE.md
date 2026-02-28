# MAYA — Capstone Project Guide for Agentic Engineering Enthusiasts

**A practical reference for building a production-grade multi-agent AI system from scratch**

---

## Who This Guide Is For

You are an engineer or student who wants to go beyond "call an LLM API and print the result." You want to understand how real agentic systems are designed — with state machines, multi-agent routing, persistent memory, observability, and offline-first deployment.

MAYA (Multi-Agent hYbrid Assistant) is a bilingual STEM companion for children built on LangGraph. It is small enough to understand completely yet rich enough to demonstrate every key concept in agentic AI engineering.

Reading this guide, you will understand:
- Why LangGraph, not just LangChain
- How state flows through a graph
- How to design agents that stay focused
- How to build persistent memory correctly
- How to test agents without calling real LLMs every time
- How to observe what your agent is actually doing

---

## Part 1: The Problem MAYA Solves

### Why Not Just Call ChatGPT?

The naive approach to a "AI homework helper":
```python
response = openai.chat("Answer this question: " + question)
print(response)
```

This works for demos. It fails for real products because:
- **No routing** — a single LLM handles everything equally badly
- **No memory** — forgets the child's name every session
- **No structure** — can't ensure math questions get step-by-step answers
- **No offline** — breaks without internet
- **No observability** — no idea what prompt actually ran
- **No testability** — can't write a unit test for "did it route correctly?"

MAYA solves all of these with a proper agentic architecture.

### The Core Insight: Agents Are Not Just LLMs

An agent is **any callable that takes state and returns updated state**. In MAYA:
- `detect_language` is an agent. It uses zero LLM calls — just word matching.
- `load_memory` is an agent. It reads SQLite.
- `math_tutor_response` is an agent. It calls an LLM with a specific math-focused prompt.
- `save_memory` is an agent. It writes to SQLite.

The LLM is one tool among many. The graph is the brain.

---

## Part 2: Core Concepts

### 2.1 LangGraph — Why a State Machine?

LangGraph models conversation as a **directed graph** where:
- **Nodes** are functions that process state
- **Edges** are the wiring between nodes
- **Conditional edges** are the routing logic (if-else as a graph edge)
- **State** is a TypedDict that every node reads from and writes to

The key insight: conversation *is* a state machine. Every message moves the conversation from one state to another. LangGraph makes this explicit and testable.

```python
graph = StateGraph(MayaState)
graph.add_node("detect_language", detect_language)
graph.add_node("understand_intent", understand_intent)
graph.add_edge("detect_language", "understand_intent")
graph.add_conditional_edges("understand_intent", route_by_intent, {...})
maya_graph = graph.compile()
```

Once compiled, `maya_graph.invoke(state)` runs the entire conversation turn.

### 2.2 State — The Single Source of Truth

The state TypedDict is the "baton" passed between every node. Each node:
1. Reads only what it needs from state
2. Returns a **partial dict** with only the keys it changed
3. LangGraph merges the partial dict back into the full state

```python
def detect_language(state: MayaState) -> dict:
    # Reads: state["user_input"]
    # Returns: only "language" and "steps" — everything else unchanged
    return {"language": "hindi", "steps": state["steps"] + ["[detect_language] → hindi"]}
```

This is **separation of concerns at the data level**: nodes don't know about each other, only about state.

### 2.3 Reducers — Smart State Merging

The default LangGraph merge is "last write wins." But for `message_history`, you want to **accumulate**, not replace:

```python
message_history: Annotated[list[dict], operator.add]
```

`operator.add` on lists = concatenation. When any node returns `{"message_history": [new_msg]}`, LangGraph appends `new_msg` to the existing list instead of replacing it.

This is how multi-turn conversation works:
- Turn 1: history = [user_msg_1, assistant_msg_1]
- Turn 2: history = [user_msg_1, assistant_msg_1, user_msg_2, assistant_msg_2]
- Ollama sees the full context each time

### 2.4 Multi-Agent Pattern

The most important lesson: **same model, different system prompts = different agents**.

```python
# Agent 1: General STEM helper
def help_response(state):
    system = "You are MAYA, a warm STEM companion for a 10-year-old..."
    # → conversational, analogies, curious follow-up questions

# Agent 2: Math tutor
def math_tutor_response(state):
    system = "You are MAYA's Math Tutor mode. Always solve first, then explain each step..."
    # → structured, step-by-step, ends with practice problem
```

Both call `ollama.chat(model="llama3.2:3b", messages=...)`. The model is identical. The behaviour is completely different. This is the multi-agent principle.

### 2.5 Routing — Conditional Edges

```python
def route_by_intent(state: MayaState) -> str:
    intent = state.get("intent", "general")
    if intent == "greeting":  return "greet_response"
    if intent == "farewell":  return "farewell_response"
    if intent == "math":      return "math_tutor_response"
    return "help_response"
```

This pure function is the router. It maps intent → node name. LangGraph uses the returned string to select the next node.

```python
graph.add_conditional_edges(
    "understand_intent",
    route_by_intent,
    {"greet_response": "greet_response", "math_tutor_response": "math_tutor_response", ...}
)
```

### 2.6 Persistent Memory — The Right Way

Bad approach: store conversation history in a global variable.
- Dies on process restart
- Can't test in isolation
- Not thread-safe

MAYA's approach:
1. **SQLite** for persistence (single file, no server, works offline)
2. **Load at graph start** (`load_memory` node injects into state)
3. **Save at graph end** (`save_memory` node writes to SQLite)
4. **Test isolation** via injectable `memory_db_path` state field

```python
# Production: uses ~/.maya/memory.db
maya_graph.invoke({"user_input": "Hello!"})

# Test: uses a tmp_path DB, never touches real data
maya_graph.invoke({"user_input": "Hello!", "memory_db_path": "/tmp/test.db"})
```

This pattern — injecting dependencies through state rather than global config — makes the entire graph testable without mocks.

---

## Part 3: Architecture Patterns Used

### Pattern 1: Pipeline with Conditional Branch

```
load → stage1 → stage2 → [branch A | branch B | branch C] → save → END
```

MAYA's graph is a linear pipeline (load_memory → detect_language → understand_intent) followed by a 4-way branch (greet / farewell / math / help), converging back to save_memory.

**Use this pattern when:** you have a fixed preprocessing pipeline followed by specialised handlers.

### Pattern 2: Graceful Degradation

Every node that touches an external resource (SQLite, Ollama, mic) has a try/except fallback:

```python
try:
    store = MemoryStore(db_path=db_path)
    profile = store.get_profile()
except Exception:
    profile = {"user_name": "Srinika", "session_count": 0, "total_turns": 0}
```

The graph never crashes. MAYA always produces a response. The error is logged in `steps` for debugging.

### Pattern 3: Side-Effect Node

`save_memory` does not change any user-facing state. It only writes to SQLite and returns an updated `steps` list.

```python
def save_memory(state) -> dict:
    store.log_turn(state["user_input"], state["intent"])
    return {"steps": current_steps + ["[save_memory] → logged"]}
    # No changes to response, language, intent, message_history
```

Pure side-effect nodes are important for keeping the graph's data flow clean and understandable.

### Pattern 4: NotRequired for Backward-Compatible State Extension

Adding new state fields while keeping all existing tests passing:

```python
class MayaState(TypedDict):
    user_input: str          # required — existing tests must provide this
    user_name: NotRequired[str]   # optional — existing tests don't need to provide this
```

`NotRequired` fields default to `KeyError` if accessed without `.get()`, which forces defensive coding in nodes.

### Pattern 5: The `steps` Debug Field

Every node appends a human-readable log entry to `steps`:
```python
"[detect_language] → 'hindi' (2 Hindi markers)"
"[understand_intent] → 'question'"
"[help_response/ollama] → intent='question', language='hindi'"
```

This gives you a full execution trace from the state alone — no logging framework, no external tools. Works in production, in tests, and in LangGraph Studio's state viewer.

---

## Part 4: What Makes This a Good Capstone

### Concepts Covered

| Concept | Where It Appears |
|---------|-----------------|
| State machines | LangGraph StateGraph |
| TypedDict + type hints | MayaState |
| Reducers / state merging | `Annotated[list, operator.add]` |
| Conditional routing | `route_by_intent` + `add_conditional_edges` |
| Multi-agent design | `help_response` vs `math_tutor_response` |
| Persistent memory | SQLite MemoryStore |
| Dependency injection via state | `memory_db_path` field |
| Graceful degradation | try/except in every external call |
| Offline-first architecture | Ollama + Piper + Whisper + SQLite |
| Observability | LangSmith tracing + LangGraph Studio |
| Unit testing agents | 38 tests, no real LLM calls for routing tests |
| Test isolation | `tmp_path` DB injection |
| Environment configuration | `python-dotenv` + Settings class |
| NLP without ML | Word-set matching for language + intent |
| TTS + STT | Piper + faster-whisper |
| Edge deployment | Raspberry Pi 5 + Hailo AI HAT plan |

### Why MAYA Is Better Than "Build a Chatbot"

Most chatbot tutorials end at "call the API." MAYA demonstrates:
- **When to use LLM vs when not to** (language detection is word-matching, not GPT)
- **How memory should be designed** (not a list appended in RAM)
- **How routing should work** (pure function, testable, no side effects)
- **How agents should fail** (always produce output, log the error in steps)
- **How to test LLM apps** (route tests never call Ollama)

---

## Part 5: Extending MAYA

### Extension 1: Add a New Agent

To add a "Story Teller" agent:

1. Add `"story"` to intent detection in `understand_intent`
2. Write a `story_response` node with a story-focused system prompt
3. Add `"story"` → `"story_response"` to the routing function
4. Wire in `graph.add_edge("story_response", "save_memory")`
5. Write 3 tests

That's the entire change. The graph topology expands cleanly. Nothing else touches.

### Extension 2: Online/Offline Routing

Add a `connectivity_check` node between `load_memory` and `detect_language`:

```python
def connectivity_check(state) -> dict:
    is_online = ping("sarvam.ai", timeout=1)
    return {"is_online": is_online}
```

Then change the LLM nodes to check `state.get("is_online")` and switch between Sarvam API (better quality, bilingual) and Ollama (offline fallback).

### Extension 3: Replace Keyword Intent Detection with LLM

Currently `understand_intent` uses word matching. To replace with an LLM classifier:

```python
def understand_intent(state):
    result = ollama.chat(model="llama3.2:3b", messages=[{
        "role": "user",
        "content": f"Classify this as: greeting/farewell/math/question/general\n\n{state['user_input']}"
    }])
    intent = result.message.content.strip().lower()
    return {"intent": intent, ...}
```

The rest of the graph is unchanged. This is the power of separation of concerns — swap the internals of one node without touching anything else.

### Extension 4: Add Wake-Word Detection

Add a `wake_word_check` as the very first node before `load_memory`:

```python
def wake_word_check(state) -> dict:
    # Use openWakeWord or porcupine
    heard_wake_word = detect_wake_word()
    return {"wake_word_detected": heard_wake_word}

graph.add_conditional_edges("wake_word_check",
    lambda s: "load_memory" if s["wake_word_detected"] else "sleep",
    {"load_memory": "load_memory", "sleep": "sleep_node"})
```

### Extension 5: Animated Face Display

Add an `update_display` node after each response node:

```python
def update_display(state) -> dict:
    emotion = {"greeting": "happy", "farewell": "sad", "math": "thinking"}.get(state["intent"], "neutral")
    pygame_display.set_emotion(emotion)  # non-blocking
    return {}  # no state changes
```

### Extension 6: Multi-Child Profiles

Replace the single-user SQLite schema with a multi-user one. Add a `user_id` to state. `load_memory` resolves profile by user_id. MAYA becomes a family assistant.

### Extension 7: LangGraph Checkpointing

LangGraph supports persistent checkpoints (Redis, PostgreSQL). Replace in-memory state with a checkpointer:

```python
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string("~/.maya/checkpoints.db")
maya_graph = graph.compile(checkpointer=checkpointer)
```

Now `thread_id` resumes a specific conversation. The entire multi-turn history survives process restart. `message_history` in MayaState becomes unnecessary.

### Extension 8: Web API

Add FastAPI as a thin layer on top:
```python
@app.post("/chat")
async def chat(request: ChatRequest):
    result = maya_graph.invoke({"user_input": request.message, ...})
    return {"response": result["response"]}
```

MAYA becomes accessible from any browser, phone, or tablet on the home network.

---

## Part 6: Future Capabilities

### Near-Term (Weeks 5-8)

| Capability | Approach |
|-----------|----------|
| Animated face display | Pygame window, `update_display` node sets emotion per intent |
| Raspberry Pi 5 deployment | Port current code, add systemd service |
| Hailo AI HAT acceleration | Hailo TAPPAS SDK for LLM inference on dedicated NPU |
| Hindi TTS voice | When Piper adds a stable hi_IN voice model |
| Sarvam-2B model | Better bilingual quality than llama3.2:3b for Hindi |

### Medium-Term (Month 2-3)

| Capability | Approach |
|-----------|----------|
| Wake-word detection | openWakeWord (offline) + new graph node |
| Online/offline routing | `connectivity_check` node + hybrid LLM selection |
| Story teller agent | New node with story-focused prompt + image generation |
| Vocabulary tutor | Word-of-the-day + spaced repetition in SQLite |
| Learning progress tracker | New `progress` table in SQLite, quiz history |
| PiDog robot body | Physical emotion nodes (tail, ears, movement) |

### Long-Term (Month 4+)

| Capability | Approach |
|-----------|----------|
| Adaptive difficulty | Track child's success rate per topic; adjust prompt complexity |
| Voice-based name detection | Whisper-based speaker identification or simple name prompt |
| Family multi-user | Profile selector at startup; per-child SQLite tables |
| Sarvam API integration | Online-quality Hindi/Hinglish with Sarvam's native model |
| Home automation | Add nodes for lights, music, reminders (Home Assistant API) |
| Web dashboard | FastAPI + React; parents see session summaries |
| LangGraph Cloud deploy | Hosted inference when RPi is away; same code |

---

## Part 7: Running MAYA Yourself

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.ai) installed and running
- `ollama pull llama3.2:3b`

### Setup
```bash
git clone https://github.com/rsrinivasan18/maya
cd maya
python -m venv .venv
.venv/Scripts/activate        # Windows
source .venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
```

### Run (keyboard mode)
```bash
python chat_loop.py
```

### Run (full voice)
```bash
python chat_loop.py --voice --speak
```

### Run tests
```bash
pytest tests/ -v
```

### Enable LangSmith tracing
```bash
# Create .env from .env.example
# Add your LANGCHAIN_API_KEY from smith.langchain.com
python chat_loop.py   # traces appear in LangSmith dashboard
```

### LangGraph Studio (visual debugger)
```bash
.venv/Scripts/langgraph dev
# Open smith.langchain.com/studio → connect to localhost:2024
```

---

## Part 8: Key Takeaways for Agentic Engineers

1. **State machines beat chains for complex conversations.** When you have branching, memory, and multiple agents, a graph is the right abstraction.

2. **Not everything needs an LLM.** Language detection and intent classification in MAYA use zero LLM calls. Use the right tool for each job.

3. **Design for testability from day one.** Injectable dependencies (memory_db_path in state), pure routing functions, and deterministic nodes make 38 tests possible without mocking the LLM.

4. **The system prompt IS the agent.** Same model, different instructions = completely different behaviour. Master prompt engineering before adding model complexity.

5. **Offline-first is a feature.** Designing for offline forces you to make explicit decisions about what really needs the cloud. Most things don't.

6. **Observability is not optional.** Without LangSmith traces, debugging "why did MAYA give a weird answer?" is guesswork. Instrument from day one.

7. **Small models are often good enough.** llama3.2:3b (2GB, CPU-only) handles STEM Q&A for a 10-year-old admirably. Match model capability to actual requirements.

8. **Memory needs a schema, not a list.** A `message_history` list in RAM disappears on restart. A `topics` table in SQLite survives indefinitely.

9. **Backward compatibility matters.** `NotRequired` TypedDict fields and `.get()` defaults let you extend the system without breaking existing tests.

10. **Build the brain before the body.** MAYA works completely on a laptop first. Hardware (RPi5) comes later. Validate software before adding hardware complexity.

---

## Appendix: Quick Reference

### Graph Node Signatures
```python
def node_name(state: MayaState) -> dict:
    # Read from state
    # Do work
    # Return PARTIAL dict (only changed keys)
    return {"key_changed": new_value}
```

### Adding a New Node
```python
graph.add_node("my_node", my_node_function)
graph.add_edge("previous_node", "my_node")
graph.add_edge("my_node", "next_node")
```

### Adding a New Intent
1. `understand_intent`: add word to appropriate set
2. `route_by_intent`: add `if intent == "new_intent": return "new_node"`
3. `add_conditional_edges`: add `"new_node": "new_node"` to mapping
4. Write tests in `TestIntentDetection` and `TestConditionalRouting`

### Test a Node Directly
```python
result = maya_graph.invoke({
    "user_input": "What is gravity?",
    "language": "", "intent": "", "response": "",
    "steps": [], "message_history": [],
    "memory_db_path": str(tmp_path / "test.db"),
})
assert result["intent"] == "question"
assert any("help_response" in step for step in result["steps"])
```

### LangSmith Trace Config
```python
maya_graph.invoke(state, config={
    "run_name": "MAYA-turn-1",
    "metadata": {"session_id": 1, "turn": 1},
    "tags": ["maya", "production"],
})
```
