# 🤖 MAYA - Multi-Agent hYbrid Assistant
## Master Project Context Document
### Version: 2.5 | Updated: 2026-02-28 | Status: Active Development - Week 4

---

## 🎯 PROJECT IDENTITY

**Name:** MAYA  
**Full Form:** Multi-Agent hYbrid Assistant  
**Named by:** Srinivasan's 10-year-old daughter ❤️  
**Sanskrit meaning:** माया (Magic/Illusion) - perfect for an AI companion  
**Tagline:** Bilingual STEM companion for curious kids  

---

## 👨‍💻 BUILDER CONTEXT

**Who:** Srinivasan - AI Architect at BNP Paribas Singapore  
**Experience:** 15+ years (Data Engineering, ML, MLOps, GenAI)  
**Current stack at work:** LangGraph, LangChain, TigerGraph, LangSmith  
**Development time:** 2-4 hrs/day (office GenAI time + evenings after gym)  
**Philosophy:** coding with AI assistance - build fast, understand, iterate  
**GitHub:** Push every session, even messy code  

---

## 🌟 VISION & PURPOSE

### Primary Purpose
Bilingual Hindi/English AI companion that helps Srinivasan's daughter learn STEM concepts through natural voice conversation - running on edge hardware (Raspberry Pi 5).

### Why This Project
1. **Family:** Meaningful father-daughter project - daughter will watch Maya being born
2. **Learning:** Real hands-on LangGraph + edge AI experience
3. **Portfolio:** Demonstrates edge AI, bilingual NLP, multi-agent systems for Lead AI Architect interviews
4. **Future:** Foundation for agentic Sarasai (stock analysis platform)

### What MAYA Does
- Hears daughter's voice (Hindi or English or Hinglish)
- Thinks locally on RPi5 + Hailo chip, initial prototype in windows laptop
- Responds in natural Hindi/English
- Shows animated face/emotions on display
- Teaches STEM concepts adaptively
- Remembers past conversations (evolving personality)
- Works fully offline when needed

---

## 🏗️ ARCHITECTURE

### Core Design Principle
**Hybrid Online/Offline** - Smart routing between local and cloud models

```
Voice Input (Whisper STT)
        ↓
Wake Word Agent (ALWAYS offline)
        ↓
Intent Router Agent
    /           \
Offline         Online
(Local LLM)     (Sarvam API / Claude)
    \           /
    Response Generation
        ↓
Voice Output (Piper TTS)
        +
Display (Animated face + text)
```

### Agent Architecture (LangGraph)

| Agent | Role | Model | Always Online? |
|-------|------|-------|---------------|
| Wake Word Agent | Detect "Hey Maya" | Local only | No (offline) |
| Intent Router | Classify query complexity | Local | No (offline) |
| Conversation Agent | General chat, STEM Q&A | Sarvam/Claude | Preferred online |
| Math Tutor Agent | Solve + explain math | Local capable | Optional |
| Story Agent | Hindi/English stories | Online preferred | Optional |
| Vocabulary Agent | Word of the day | Local | No (offline) |
| Memory Agent | Load/save personality | Local SQLite | No (offline) |
| Session Manager | Load daughter's profile | Local | No (offline) |

### Online/Offline Switching Logic
- **Simple questions** → Offline (fast, no cost, private)
- **Complex STEM explanations** → Online (better quality)
- **No internet / Bhopal connectivity issues** → Fallback to offline always
- **Night time** → Offline preferred
- **Router decides** based on: complexity, connectivity, latency needs

---

## 💻 TECH STACK

### Core
- **Agent Orchestration:** LangGraph
- **LLM Framework:** LangChain
- **Backend:** FastAPI (Python 3.12+)
- **Local LLM:** Ollama + Sarvam-2B quantized (4-bit)
- **Bilingual Model:** Sarvam AI (built for Hindi/English Hinglish)
- **STT:** Whisper tiny/base (local)
- **TTS:** Piper TTS (offline) or Sarvam TTS (online)
- **Memory:** SQLite (persistent personality, learning history)
- **Observability:** LangSmith (free Developer tier)

### Why Sarvam AI?
- Built specifically for Indian languages
- Handles Hinglish naturally (what 10yr old actually speaks)
- Better than Gemma 2B for mixed Hindi/English
- Sarvam-2B fits on RPi5 when quantized

### Frontend (Display)
- Python + Pygame OR simple React/HTML
- Animated Maya face showing emotions
- Text display for responses
- STEM diagrams when needed

---

## 🔧 HARDWARE PLAN

### Target Hardware (Raspberry Pi Setup)
| Component | Spec | Price (SGD est.) |
|-----------|------|-----------------|
| Raspberry Pi 5 | 8GB RAM | ~125 |
| AI HAT+ 2 | Hailo-10H, 40 TOPS, 8GB dedicated RAM | ~175 |
| SunFounder 7" Display | IPS 1024x600, built-in speaker | ~70 |
| USB Microphone | Quality mic for kids voice | ~20 |
| Active Cooler | RPi5 official cooler | ~15 |
| 64GB SD Card | Fast microSD | ~20 |
| 27W USB-C PSU | Official RPi PSU | ~20 |
| **TOTAL** | | **~SGD 445** |

### Why AI HAT+ 2 (Hailo-10H)?
- 40 TOPS with 8GB dedicated RAM (NEW - Jan 2026)
- Designed specifically for GenAI/LLMs (original HAT+ couldn't run LLMs)
- LLM inference won't compete with RPi5's main RAM
- Hindi/English conversation needs GenAI capability

### Phase 2 Hardware (Later)
- SunFounder PiDog V2 kit (~SGD 120-150)
- Port working Maya code to robot dog body
- Same software, new physical form

---

## 📅 DEVELOPMENT STRATEGY

### Key Principle: LAPTOP FIRST, RPi LATER
**Validate entire software stack on laptop before touching hardware**
###One step at a time. Dont rush. Human (I Srinivasan) should understand the code and learn it before commit.

Reasons:
- Separate software learning from hardware debugging
- Faster iteration without RPi quirks
- LangGraph agents work on laptop first
- Hardware becomes reward when brain is ready
- GitHub commits start immediately

### Phase 1: Laptop Development (Weeks 1-6)
**Goal: Working MAYA voice assistant on laptop**

| Week | Focus | Deliverable |
|------|-------|-------------|
| 1 | LangGraph basics + hello world | First agent commit |
| 2 | Add STT (Whisper) + TTS (Piper) | Voice I/O working |
| 3 | Sarvam/Ollama integration | Hindi/English responses |
| 4 | Multi-agent (3 agents) | Router + Tutor + Memory |
| 5 | Online/offline switching | Hybrid model routing |
| 6 | Display + personality | Animated face, memory |

### Phase 2: Hardware Deployment (Weeks 7-8)
- Buy RPi5 + Hailo-10H + Display (Sim Lim Square)
- Port working laptop code to RPi
- Just deployment, not re-debugging everything
- PiDog kit purchase after voice assistant working

### Phase 3: PiDog Integration (Month 3+)
- Add robot dog body
- Maya gets physical form
- Same brain, new body

---

## 🎯 IMMEDIATE NEXT STEPS

### Session 1 - 2026-02-25 (COMPLETED)
- ✅ Project structure set up (`src/maya/`, `tests/`, `dev_log/`)
- ✅ Hello world LangGraph agent built (4 nodes, 1 conditional edge)
- ✅ MayaState TypedDict, config/settings, 15 unit tests
- ✅ GitHub repo created: github.com/rsrinivasan18/maya
- ✅ 2 commits pushed under Srinivasan's name

### Session 2 - 2026-02-26 (COMPLETED)
- ✅ `Annotated[list, operator.add]` reducer added to MayaState for message_history
- ✅ Farewell intent + node (bye/quit/exit/alvida/phir milenge) - 3-way routing
- ✅ `chat_loop.py` REPL - real multi-turn conversation with !history/!debug/!clear
- ✅ Tests updated - farewell + message history accumulation tests added
- ✅ Committed and pushed to GitHub

### Session 3 - 2026-02-27 (COMPLETED)
- ✅ STT: `src/maya/stt/transcriber.py` - STTEngine with faster-whisper
  - Bilingual strategy: Hindi-first transcription, English fallback if confidence < 0.65
  - Fixes faster-whisper's known bug: Hindi misdetected as Arabic
  - `listen(duration)` → records mic + transcribes in one call
- ✅ `--voice` and `--record-time` flags added to `chat_loop.py`
- ✅ `test_stt.py` - standalone mic + transcription test (3 utterances)
- ✅ TTS: `src/maya/tts/speaker.py` - TTSEngine with Piper TTS
  - Auto-downloads ONNX voice models from rhasspy/piper-voices (HuggingFace)
  - Voice catalog: en_US-lessac-medium (default female), amy, en_GB-alba
  - In-memory WAV synthesis (no temp files), sounddevice playback
- ✅ `--speak` flag added to `chat_loop.py` - MAYA speaks every response
- ✅ `test_tts.py` - standalone 3-phrase speaker test
- ✅ Committed and pushed to GitHub

### Session 4 - 2026-02-28 (COMPLETED)
- ✅ Ollama installed (`llama3.2:3b`, Q4_K_M, ~2GB, fully offline)
- ✅ `help_response` node replaced with `ollama.chat()` call
- ✅ Bilingual system prompt: `_MAYA_BASE_PROMPT` + per-turn `_LANGUAGE_INSTRUCTIONS`
  - English / Hindi / Hinglish each get a separate explicit language reminder
  - Rationale: 3B model needs per-turn language reminder to stay consistent
- ✅ Full `message_history` passed to Ollama → multi-turn context awareness
- ✅ Fallback: friendly error message if Ollama not running (no crash)
- ✅ Bug fix: empty `message_history` guard (tests / direct invocations)
- ✅ 30/30 tests passing, committed and pushed

### Session 5 - 2026-02-28 (COMPLETED)
- ✅ `src/maya/agents/memory_store.py` — MemoryStore class (SQLite at `~/.maya/memory.db`)
  - Tables: `profile` (user_name, session_count, total_turns), `topics` (turn log)
  - Methods: `start_session()`, `get_profile()`, `get_recent_topics()`, `log_turn()`
- ✅ `src/maya/models/state.py` — Added 5 NotRequired fields (user_name, session_count, recent_topics, session_id, memory_db_path)
- ✅ `load_memory` node (first node) — loads profile + recent topics from SQLite into state
- ✅ `save_memory` node (last node) — persists each user turn to topics table
- ✅ `greet_response` updated — "Welcome back, Srinika! Last time you asked about..." on return sessions
- ✅ `help_response` updated — prepends recent topic context to Ollama system prompt
- ✅ Graph topology: START → load_memory → detect_language → ... → response → save_memory → END
- ✅ `chat_loop.py` — `start_session()` called once at startup, `session_id` passed into graph
- ✅ 33/33 tests passing (1 fixed + 3 new TestMemoryNodes)
- ✅ Committed and pushed to GitHub

### Next Session (Week 4 continued)
Options (choose one):
1. **Math Tutor agent** - add `math_tutor` node, route math intent there
2. **LangSmith Observability** - trace every Ollama call (free Developer tier)
3. **Animated face display** - Pygame or HTML face showing emotions (Week 6 preview)

### This Week
- [ ] LangGraph Academy modules (office GenAI time)
- [ ] Run `python chat_loop.py --voice --speak` for full voice conversation

### Next Weekend
- [ ] Buy RPi5 + AI HAT+ 2 from Sim Lim Square
- [ ] Order SunFounder display online

---

## 🔄 SESSION SYNC PROTOCOL

### How to use this file across AI sessions

**Starting Claude.ai session:**
```
"Here is my MAYA project context: [paste MAYA_CONTEXT.md]
Today I want to work on: [specific task]"
```

**Starting Claude Code session:**
```
"Read MAYA_CONTEXT.md first.
Today's task: [specific task]
Build it following the architecture defined."
```

**After each session - update:**
- Current Status section
- Completed items
- New decisions made
- Next steps

---

## 📊 CURRENT STATUS TRACKER

### Completed
- ✅ Project vision defined
- ✅ Architecture designed
- ✅ Tech stack selected
- ✅ Hardware researched (AI HAT+ 2 chosen)
- ✅ Development strategy (laptop first)
- ✅ Agent design (8 agents planned)
- ✅ Project named by daughter
- ✅ Context document created
- ✅ GitHub repo created: github.com/rsrinivasan18/maya
- ✅ Development environment set up (.venv, requirements.txt)
- ✅ Project structure scaffolded (src/maya/, tests/, dev_log/)
- ✅ Hello world LangGraph agent (4 nodes, 1 conditional edge, 15 tests)
- ✅ MayaState TypedDict, settings/config, bilingual responses
- ✅ First 2 commits pushed (Week 1 Day 1 done)

### In Progress
- 🔄 LangGraph learning (Academy modules - office time)

### Pending
- ⏳ Math Tutor agent node (Week 4)
- ⏳ LangSmith Observability (Week 4)
- ⏳ Hardware purchase (RPi5 + AI HAT+ 2)

### Week 4 Done (Session 5)
- ✅ SQLite memory (MemoryStore, load_memory + save_memory nodes)
- ✅ MAYA now remembers Srinika across sessions ("Welcome back!")

### Week 2 Done
- ✅ Whisper STT (faster-whisper, bilingual Hindi/English)
- ✅ Piper TTS (neural voice, en_US-lessac-medium)
- ✅ Full voice I/O: `python chat_loop.py --voice --speak`

### Week 3 Done
- ✅ Ollama LLM (llama3.2:3b, offline, bilingual system prompt)
- ✅ MAYA answers real STEM questions in English and Hinglish
- ✅ Multi-turn context: full message_history passed to Ollama

---

## 🏆 PORTFOLIO VALUE

**For Lead AI Architect interviews, MAYA demonstrates:**
- Edge AI deployment on constrained hardware
- Bilingual NLP (Hindi/English) - rare skill
- LangGraph multi-agent orchestration
- Hybrid online/offline architecture
- Persistent memory + evolving personality
- Multimodal I/O (voice + vision + display)
- Fully offline capable system
- Real-world use case (not just a demo)


---

## ⚠️ DECISIONS LOG

| Decision | Choice | Reason |
|----------|--------|--------|
| Hardware acceleration | Hailo-10H (AI HAT+ 2) | Only one supporting GenAI/LLMs |
| Bilingual model | Sarvam AI | Built for Hindi/English Hinglish |
| Agent framework | LangGraph | Used at BNP, learning investment |
| Development order | Laptop first | Validate before hardware complexity |
| Product first | Voice assistant | Faster to build, daughter uses sooner |
| Robot body | PiDog V2 later | Phase 2, after voice works |
| Memory | SQLite | Simple, offline, persistent |
| Coding approach | Vibe coding + AI | Build fast, understand, iterate |
| Observability | LangSmith free tier | Sufficient for personal project |
| STT language fix | Hindi-first + English fallback (conf 0.65) | faster-whisper misdetects Hindi as Arabic |
| TTS voice | en_US-lessac-medium (US female) | No stable hi_IN voice in Piper catalog yet |
| LLM model | llama3.2:3b (Ollama, offline) | Good enough for STEM Q&A; fast on CPU |
| Language prompt | Per-turn instruction in system prompt | 3B model needs explicit reminder each turn |
| Memory storage | SQLite (~/.maya/memory.db) | Offline, no server, single file, Python built-in |
| Memory test isolation | memory_db_path state field + tmp_path fixture | Tests use temp DB, never touch real DB |
| MemoryStore instantiation | Fresh per node call | No global state, clean and testable |

---

*This document is the single source of truth for MAYA project.*  
*Update after every meaningful session.*  
*Commit to GitHub after every update.*