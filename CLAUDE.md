# 🤖 MAYA — CLAUDE.md
## Persistent Instructions for Claude Code
**Read this at the start of every session. No exceptions.**

---

## Who You Are Working With

**Project:** MAYA — Multi-Agent hYbrid Assistant
**Owner:** Srinivasan (AI Architect, BNP Paribas Singapore)
**End user:** Srinika, age 9, Bhopal — Papa's daughter
**Deadline:** April 3, 2026 — Srinika must say "WOW"
**Mission:** Bilingual Hindi/English STEM tutor running on Raspberry Pi

**Your role:** Head Chef 🍳 — you cook, Srinivasan tastes and approves
**Claude.ai role:** Kitchen advisor — architecture, design, strategy
**Srinivasan role:** Restaurant owner — final word on everything

---

## 🔴 Non-Negotiable Rules

1. **Never break existing tests.** Currently 38+ tests passing. Zero regressions — always.
2. **One step at a time.** Implement exactly what the directive says for this step. Stop. Wait for approval.
3. **No React. No Node.js.** Web stack is plain HTML/CSS/Vanilla JS — must run on Raspberry Pi.
4. **No vLLM.** Single user system. Not needed yet.
5. **Never touch p5.js RoboEyes** unless the directive explicitly says so.
6. **Minimal impact.** Change only what is necessary. Avoid touching unrelated files.
7. **No temporary fixes.** Find root causes. Senior developer standards only.

---

## 📁 Project Structure

```
maya/
├── CLAUDE.md                        ← you are here
├── tasks/
│   ├── todo.md                      ← live task tracker (you update this)
│   └── lessons.md                   ← your learning log (you update this)
├── docs/
│   └── MAYA_Session*_CC_Directive.md ← session directives from Claude.ai
├── chat_loop.py
├── src/maya/
│   ├── config/settings.py
│   ├── models/state.py              ← MayaState TypedDict
│   ├── graph/hello_world_graph.py   ← all LangGraph nodes
│   ├── agents/
│   │   ├── memory_store.py
│   │   └── connectivity_checker.py
│   ├── stt/transcriber.py
│   ├── tts/speaker.py
│   └── web/
│       ├── app.py                   ← FastAPI
│       └── static/
│           ├── index.html
│           ├── style.css
│           └── app.js
└── tests/
    └── test_hello_world.py          ← 38+ tests, always green
```

---

## ⚙️ Workflow Orchestration

### 1. Session Start Ritual
Every session, before writing a single line of code:
- Read `tasks/lessons.md` — learn from past mistakes
- Read `tasks/todo.md` — know current state
- Read the session directive from `docs/`
- Summarise your understanding back to Srinivasan
- Wait for his "go ahead" before starting

### 2. Plan Before Building
- For ANY non-trivial task (3+ steps or architectural decisions): write the plan first
- If something goes sideways mid-implementation: STOP, re-plan, tell Srinivasan
- Write specs upfront — reduce ambiguity before touching code

### 3. Approval Gates — Sacred
```
Implement Step N
→ Run tests
→ Show Srinivasan the result
→ Wait for explicit approval
→ Only then move to Step N+1
```
Never skip gates. Never combine steps without permission.

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Run tests after every step
- Ask yourself: "Would a senior engineer approve this?"
- Show diffs when relevant — make changes visible

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: implement the elegant solution instead
- Skip this for simple, obvious fixes — don't over-engineer
- Simple code > clever code, always

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it — no hand-holding needed
- Point to logs, errors, failing tests — then resolve them
- Go fix failing tests without being told how
- Zero unnecessary context switching for Srinivasan

---

## 📋 Task Management

### todo.md — Update As You Work
```markdown
## Session 14 — Persona Settings Panel

### Step 1: SQLite persona_config table
- [x] create_persona_config_table() added
- [x] 6 seed rows inserted for 'srinika'
- [x] Tests passing
- [ ] ⏸️ WAITING FOR APPROVAL

### Step 2: LangGraph system prompt injection
- [ ] persona_system_prompt field in MayaState
- [ ] build_system_prompt() function
- [ ] All nodes use state.persona_system_prompt
- [ ] Tests: greeting has no session/mastery mention
```

### lessons.md — Capture Every Correction
After ANY correction from Srinivasan, immediately write:
```markdown
## Lesson [date]
**What happened:** I did X
**What should have happened:** Y
**Rule going forward:** Always Z
```
Review this file at the start of every session. These lessons are gold.

---

## 🧠 Technical Decisions — Already Made, Don't Revisit

| Decision | Choice | Reason |
|----------|--------|--------|
| Agent framework | LangGraph | Production-grade, BNP uses it |
| LLM unification | LiteLLM | One interface for Sarvam + Claude + Ollama |
| Local LLM | Ollama (llama3.2:3b) | Free, offline, RPi-ready |
| Memory | SQLite | No server, portable, offline |
| Web stack | Vanilla HTML/CSS/JS | No build step, RPi-friendly |
| Animation | p5.js (RoboEyes) | Session 13 — complete, don't touch |
| Language detection | Word-set matching | 100% testable, no ML needed |
| State | MayaState TypedDict | Injectable, testable |

---

## 🤖 LLM Tiered Fallback (Session 8)

```
Tier 1: Ollama (llama3.2:3b)   → always works, offline, free
Tier 2: Claude API              → online, best reasoning, STEM
Tier 3: Sarvam AI (sarvam-m)   → Hindi/Hinglish specialist
Unified via: LiteLLM
```
Do not change this architecture without a directive.

---

## 🧪 Testing Philosophy

- Run full test suite after every step: `pytest tests/ -v`
- 38+ tests must pass — always
- Add new tests for every new feature
- Test names must be descriptive: `test_greeting_does_not_mention_session_number`
- Never comment out a failing test — fix the root cause

---

## 💾 Memory Architecture (Cognitive Model)

```
Semantic Memory  → WHAT was learned (topics, mastery level)
                   Table: semantic_memory

Episodic Memory  → WHAT happened each session (summaries)
                   Table: episodes

Procedural Memory → HOW Srinika learns (patterns, preferences)
                    Table: procedures

Persona Config   → HOW MAYA behaves (tone, language, greeting style)
                   Table: persona_config  ← Session 14
```

Hot path (every turn): read last episode + top 3 semantic + top 2 procedural
Batch (on farewell): summarise session → write all tables

---

## 🌐 LangGraph Node Topology

```
START
↓
[check_connectivity]   ← online/offline routing
↓
[load_memory]          ← reads SQLite + builds system prompt
↓
[detect_language]      ← word-set matching (Hindi/English)
↓
[understand_intent]    ← farewell > greeting > math > question > general
↓
[greet | farewell | math_tutor | help]   ← 4-way routing
↓
[save_memory]          ← batch write to SQLite
↓
END
```

When adding nodes: add only, don't restructure existing flow.

---

## 🚫 What MAYA Must Never Do in Conversation

- Never mention session numbers (e.g., "session 93")
- Never mention mastery counts (e.g., "you're an expert 112x")
- Never summarise past learning history in greetings
- Never be formal or robotic — warm didi energy always
- Sidebar handles all metadata display — not conversation

---

## 🌍 The Bigger Picture (Keep This In Mind)

MAYA is not just Srinika's tutor. It is:
- Proof of architecture for Bhopal AI Builders programme
- A template other families can run with their own personas
- Built to run on solar power with zero marginal cost
- The first product from a solopreneur who chose mission over money

Every line of code you write should be clean enough for a Bhopal graduate to read and learn from.

---

## 📅 Key Dates

| Date | Event |
|------|-------|
| April 3, 2026 | Good Friday — Srinika's WOW test #2 |
| 12-18 months | Bhopal move — MAYA runs on Raspberry Pi + solar lab |

---

*"Don't interrupt the chef mid-cook. Cook well, plate beautifully, wait to be tasted."* 🍳
