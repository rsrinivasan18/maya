"""
MAYA Conversation Graph - Session 2 Update
===========================================
Session 1: Hello world - 4 nodes, 1 conditional edge, batch demo
Session 2: Added farewell intent + message history recording

NEW CONCEPTS THIS SESSION:
---------------------------
1. Annotated[list, operator.add] REDUCER
   Response nodes now append to message_history instead of replacing it.
   LangGraph merges {"message_history": [new_msg]} by ADDING to existing list.

2. FAREWELL INTENT
   A new branch in the conditional edge:
   - "farewell" → farewell_response node
   - The REPL uses this to know when to exit the loop

3. MULTI-TURN CONVERSATION PATTERN
   The REPL (chat_loop.py) carries message_history between turns:
     Turn 1: invoke({..., "message_history": [user_msg_1]})
             → history grows to [user_msg_1, assistant_msg_1]
     Turn 2: invoke({..., "message_history": [user_msg_1, assistant_msg_1, user_msg_2]})
             → history grows to [..., user_msg_2, assistant_msg_2]

UPDATED GRAPH FLOW:
-------------------
    START
      ↓
  [detect_language]       Node 1: Hindi / English / Hinglish?
      ↓
  [understand_intent]     Node 2: Greeting / Question / Math / Farewell / General?
      ↓
  [route_by_intent]  ──── CONDITIONAL EDGE (now 3-way!)
      ↓         ↓         ↓
 [greet]    [farewell]  [help]
      ↓         ↓         ↓
     END       END       END
"""

import threading
from pathlib import Path

from langgraph.graph import StateGraph, END, START

from src.maya.agents.connectivity_checker import ConnectivityChecker
from src.maya.agents.llm_router import call_llm_tiered
from src.maya.agents.memory_store import MemoryStore
from src.maya.models.state import MayaState


# =============================================================================
# PROMPT LOADER  (Session 13 - prompts as .md files)
# =============================================================================
# Each agent's personality lives in src/maya/prompts/<name>.md
# This makes prompts easy to read and tweak without touching Python code.

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    """Load a system prompt from src/maya/prompts/{name}.md"""
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


# Per-language instructions injected at call time (small models need explicit reminders).
# Kept in Python — they are short, parameterised, and not prompt engineering.
_LANGUAGE_INSTRUCTIONS = {
    "english":  "CRITICAL: You MUST respond in English only. Do not use any Hindi or Urdu words.",
    "hindi":    "CRITICAL: You MUST respond in Hinglish (Roman script Hindi mixed with English). Do not use Devanagari script.",
    "hinglish": "CRITICAL: You MUST respond in Hinglish - natural mix of Hindi (Roman script) and English, like: 'Waah, bahut accha question hai! Gravity is the force...'",
}

_MATH_LANGUAGE_INSTRUCTIONS = {
    "english":  "CRITICAL: Respond in English only.",
    "hindi":    "CRITICAL: Respond in Hinglish (Roman script Hindi + English). Show math steps in English numbers.",
    "hinglish": "CRITICAL: Respond in Hinglish - mix Hindi (Roman script) and English naturally. Math steps in English.",
}

# CBSE Grade 4 context — injected into every tutor/question system prompt.
# Srinika is 9 years old and types Indian historical names phonetically.
# This note tells the LLM to infer the correct name from CBSE context
# instead of asking for clarification.
_CBSE_CONTEXT = (
    "You are tutoring a 9 year old Indian girl on CBSE Grade 4 curriculum. "
    "She misspells Indian historical names phonetically. "
    "When you see garbled names like 'krishna verma raja', 'kishore raja' → infer Krishnadevaraya. "
    "'ashok raja' → Ashoka. "
    "Always infer from CBSE Grade 4 context and answer confidently without asking for spelling clarification."
)

# Hard no-markdown reminder appended to every system prompt.
# LLMs ignore this instruction in .md files — injecting it in Python ensures it sticks.
_NO_MARKDOWN = (
    "CRITICAL: Never use markdown formatting in your response. "
    "No **bold**, no *italic*, no bullet points (- or *), no numbered lists, "
    "no headers (# or ##), no backticks. "
    "Plain conversational sentences only. Write like you are speaking to a child."
)


def _strip_markdown(text: str) -> str:
    """
    Post-processing safety net: strip common markdown from LLM response.
    Removes bold/italic markers, headers, bullet points, and horizontal rules.
    """
    import re
    # Remove bold and italic: **text** → text, *text* → text, __text__ → text
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,2}(.*?)_{1,2}', r'\1', text)
    # Remove ATX headers: ## Header → Header
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bullet points: "- item" or "* item" at line start → "item"
    text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
    # Remove numbered lists: "1. item" → "item"
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove horizontal rules: --- or *** or ___
    text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Remove inline code: `code` → code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Collapse excess blank lines left by removals
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# Map agent_override values to prompt file names
_AGENT_PROMPT_MAP: dict[str, str] = {
    "science": "science_agent",
    "story":   "story_agent",
    "general": "base",
    "auto":    "base",
}


def _build_agent_prompt(prompt_name: str, language: str) -> str:
    """Load a prompt file and append the language instruction."""
    base = _load_prompt(prompt_name)
    lang_instruction = _LANGUAGE_INSTRUCTIONS.get(language, _LANGUAGE_INSTRUCTIONS["english"])
    return f"{base}\n\n{lang_instruction}"


def _build_system_prompt(language: str) -> str:
    """Base MAYA prompt (general / auto mode)."""
    return _build_agent_prompt("base", language)


def _build_math_prompt(language: str) -> str:
    """Math tutor prompt with math-specific language instruction."""
    base = _load_prompt("math_tutor")
    lang_instruction = _MATH_LANGUAGE_INSTRUCTIONS.get(language, _MATH_LANGUAGE_INSTRUCTIONS["english"])
    return f"{base}\n\n{lang_instruction}"


def _build_persona_system_prompt(db_path: str | None = None) -> str:
    """
    Session 14: Build system prompt from persona_config in SQLite.
    Returns empty string on any error — nodes fall back to .md files.
    """
    try:
        store = MemoryStore(db_path=db_path)
        config = store.load_persona_config("srinika")
    except Exception:
        return ""
    if not config:
        return ""
    return (
        "You are MAYA, a bilingual Hindi-English STEM tutor.\n\n"
        f"TONE: {config.get('tone', '')}\n"
        f"LANGUAGE: {config.get('language', '')}\n"
        f"GRADE LEVEL: {config.get('grade_level', '')}\n"
        f"GREETING STYLE: {config.get('greeting_style', '')}\n"
        f"RESPONSE STYLE: {config.get('response_style', '')}\n"
        f"AVOID: {config.get('avoid', '')}\n"
    )


# =============================================================================
# NODES
# =============================================================================


def load_memory(state: MayaState) -> dict:
    """
    Node 0: Load persistent memory from SQLite before any other processing.

    Reads user profile (session_count) and recent conversation topics,
    injects them into state so downstream nodes (greet, help) can use them.
    Graceful fallback if DB is missing or corrupt — MAYA still works.
    """
    current_steps = state.get("steps", [])  # Studio sends minimal state (no steps key)
    db_path = state.get("memory_db_path") or None  # None → use default ~/.maya/memory.db

    try:
        store = MemoryStore(db_path=db_path)
        profile = store.get_profile()
        recent = store.get_recent_topics(limit=3)
        last_summary = store.get_last_session_summary()   # Session 9: episodic
        mastery = store.get_mastery_summary(limit=5)      # Session 10: procedural
        todos  = store.get_pending_todos()               # Session 17: reminders
    except Exception:
        profile = {"user_name": "Srinika", "session_count": 0, "total_turns": 0}
        recent = []
        last_summary = ""
        mastery = []
        todos  = []

    # Session 14: Build system prompt from editable persona config in SQLite
    persona_prompt = _build_persona_system_prompt(db_path=db_path)

    practiced = [m for m in mastery if m["count"] >= 3]

    return {
        "user_name":            profile["user_name"],
        "session_count":        profile["session_count"],
        "recent_topics":        recent,
        "last_session_summary": last_summary,             # Session 9
        "mastered_topics":      mastery,                  # Session 10
        "persona_system_prompt": persona_prompt,          # Session 14
        "pending_todos":        todos,                    # Session 17
        "steps": current_steps + [
            f"[load_memory] → session_count={profile['session_count']}, "
            f"{len(recent)} recent topic(s), "
            f"{len(practiced)} practiced topic(s)"
        ],
    }


def check_connectivity(state: MayaState) -> dict:
    """
    Node 0b (Session 8): Check internet access and inject result into state.

    Calls ConnectivityChecker.is_online() — a lightweight TCP probe to 8.8.8.8:53.
    Result flows downstream to LLM nodes so they can pick the right provider tier:
      is_online=True  → try Sarvam → Claude → OpenAI → Ollama
      is_online=False → go straight to Ollama (no wasted API calls)

    Runs AFTER load_memory so memory is already populated before we hit the network.
    """
    current_steps = state.get("steps", [])

    online = ConnectivityChecker().is_online()

    return {
        "is_online": online,
        "steps": current_steps + [
            f"[check_connectivity] → {'online' if online else 'offline'}"
        ],
    }


def save_memory(state: MayaState) -> dict:
    """
    Node (final): Persist this turn to SQLite after the response is generated.

    Pure side-effect node — logs user_input + intent to the topics table.
    Returns only an updated steps list (no state data changes).
    """
    current_steps = state["steps"]
    db_path = state.get("memory_db_path") or None
    session_id = state.get("session_id", 0)
    user_input = state["user_input"]
    intent = state.get("intent", "general")

    # Don't save farewell turns — "bye" is not a topic to recall next session
    if intent == "farewell":
        return {
            "steps": current_steps + ["[save_memory] → skipped (farewell)"],
        }

    # ── Session 9: Extract a 2-4 word semantic topic via LLM ─────────────────
    # Example: "What is photosynthesis?" → "photosynthesis"
    # Stored in the topic column; get_recent_topics() returns this instead of
    # the raw user_input so greet_response sounds natural, not mechanical.
    is_online = state.get("is_online", False)
    topic = ""
    try:
        topic_messages = [
            {
                "role": "system",
                "content": (
                    "Extract the main topic from the user's question in 2-4 words. "
                    "Reply with ONLY those words — no punctuation, no explanation."
                ),
            },
            {"role": "user", "content": user_input},
        ]
        extracted, _ = call_llm_tiered(topic_messages, is_online)
        topic = extracted.strip()[:50]
    except Exception:
        topic = ""  # Graceful fallback — message is always stored too

    try:
        store = MemoryStore(db_path=db_path)
        store.log_turn(user_input, intent, session_id=session_id, topic=topic)
        if topic:
            store.update_mastery(topic)   # Session 10: increment procedural count
        log_status = f"ok (topic: {topic!r})" if topic else "ok (no topic)"
    except Exception as e:
        log_status = f"error: {e}"

    return {
        "steps": current_steps + [f"[save_memory] → {log_status}"],
    }


def detect_language(state: MayaState) -> dict:
    """
    Node 1: Detect whether the user wrote in Hindi, English, or Hinglish.

    Method: Simple word-matching (no ML). Good enough for Week 1.
    Week 3 upgrade: Replace with Sarvam's language detection API.
    """
    user_input = state["user_input"].lower()
    current_steps = state["steps"]

    hindi_markers = {
        "namaste", "namaskar", "kya", "hai", "hain", "nahi", "haan",
        "karo", "kuch", "mujhe", "tumhe", "aap", "tum", "main", "mera",
        "tera", "uska", "bahut", "accha", "theek", "kyun", "kaise",
        "kaun", "kab", "kahaan", "batao", "samjhao", "seekhna", "chahte",
        "alvida", "phir", "milenge", "shukriya", "dhanyavaad",
    }

    words_in_input = {w.strip(".,!?;:'\"") for w in user_input.split()}
    hindi_count = len(words_in_input & hindi_markers)

    if hindi_count >= 2:
        language = "hindi"
    elif hindi_count == 1:
        language = "hinglish"
    else:
        language = "english"

    return {
        "language": language,
        "steps": current_steps + [
            f"[detect_language] → '{language}' ({hindi_count} Hindi marker(s))"
        ],
    }


def understand_intent(state: MayaState) -> dict:
    """
    Node 2: Understand what the user wants.

    BUG FIX (Session 6): Use word-set membership for single-word triggers,
    substring match only for multi-word phrases.
    Old code: `"hi" in "...hindi"` → True (false greeting!)
    New code: `"hi" in {"hindi", ...}` → False (correct: word must match exactly)

    Precedence: farewell > greeting > math > question > general
    """
    user_input = state["user_input"].lower()
    current_steps = state["steps"]

    # Build a set of individual words (punctuation stripped) for exact-word checks
    words_in_input = {w.strip(".,!?;:'\"") for w in user_input.split()}

    # Single-word triggers — checked via set membership (no substring false positives)
    # Also check hyphen-split words so "bye-bye" → {"bye", "bye"} → matches "bye"
    words_also_hyphen = words_in_input | {
        part for w in words_in_input for part in w.split("-") if part
    }
    farewell_single  = {"bye", "goodbye", "goodnight", "cya", "alvida", "tata", "exit", "quit", "stop", "later"}
    greeting_single  = {"hello", "hi", "hey", "namaste", "namaskar", "sup"}
    math_single      = {"calculate", "solve", "math", "add", "subtract", "multiply", "divide",
                        "plus", "minus", "times", "equals", "+", "-", "*", "/", "sum", "total"}
    question_single  = {"what", "why", "how", "when", "where", "who", "which", "explain",
                        "describe", "kya", "kyun", "kaise", "kab", "kahaan", "kaun", "batao", "samjhao"}

    # Multi-word phrases — substring match is fine (they're specific enough)
    farewell_phrases  = {
        "good bye", "see you", "phir milenge", "good night", "band karo",
        "talk tomorrow", "talk to you later", "talk later", "chat later",
        "see you tomorrow", "see you later", "i'm going", "i am going",
        "going to sleep", "going to bed",
    }
    greeting_phrases  = {"good morning", "good evening"}
    question_phrases  = {"tell me"}
    # Single-word reminder triggers
    reminder_single = {"reminder", "reminders", "todo", "todos"}
    # Multi-word reminder phrases — tight enough to avoid "remind me how to..." false positives
    reminder_phrases = {
        "remind me to", "remind me about", "don't forget", "set a reminder",
        "add a reminder", "याद रखो", "याद दिलाओ", "mujhe yaad dilao",
        "add to my list", "add to my todo", "my todo", "my reminder",
        "show my todo", "show reminder", "what are my todo",
    }

    def _match(single_set, phrase_set=None):
        # Use hyphen-expanded word set so "bye-bye" splits into {"bye"} → matches
        if words_also_hyphen & single_set:
            return True
        if phrase_set and any(p in user_input for p in phrase_set):
            return True
        return False

    # Greeting fires only if the message is short (≤ 6 words) AND contains a greeting word.
    # Prevents "namaste, photosynthesis kya hai?" from being classified as a greeting.
    def _is_greeting():
        if len(words_in_input) > 6:
            return False
        return _match(greeting_single, greeting_phrases)

    if _match(farewell_single, farewell_phrases):
        intent = "farewell"
    elif _is_greeting():
        intent = "greeting"
    elif _match(reminder_single) or any(p in user_input for p in reminder_phrases):
        intent = "reminder"
    elif _match(math_single):
        intent = "math"
    elif _match(question_single, question_phrases):
        intent = "question"
    else:
        intent = "general"

    return {
        "intent": intent,
        "steps": current_steps + [f"[understand_intent] → '{intent}'"],
    }


def greet_response(state: MayaState) -> dict:
    """
    Node 3a: Warm greeting in the detected language.

    Session 5 upgrade: Uses session_count from load_memory.
    - session_count == 1 → first-ever visit, introduce MAYA
    - session_count > 1  → returning visit, "Welcome back!" + recall last topic
    """
    language = state["language"]
    current_steps = state["steps"]
    session_count = state.get("session_count", 0)
    recent_topics = state.get("recent_topics", [])
    last_summary = state.get("last_session_summary", "")   # Session 9: episodic
    mastered = state.get("mastered_topics", [])            # Session 10: procedural

    # Only show last_summary if it's a real learning recap (not a trivial session artifact)
    _show_summary = (
        last_summary
        and len(last_summary) > 20
        and last_summary.upper() != "SKIP"
        and not any(w in last_summary.lower() for w in ("saying hello", "saying bye", "said hello", "said bye", "greeting"))
    )

    if session_count > 1 and _show_summary:
        # ── Best case: episodic summary — warm, no metadata ───────────────────
        greetings = {
            "english": (
                f"Welcome back, Srinika!\n"
                f"{last_summary}\n"
                "What shall we explore today?"
            ),
            "hindi": (
                f"Wapas aa gayi Srinika! Kitna accha laga!\n"
                f"{last_summary}\n"
                "Aaj kya seekhna chahti ho?"
            ),
            "hinglish": (
                f"Welcome back Srinika! Bahut accha laga!\n"
                f"{last_summary}\n"
                "Aaj kya explore karna hai?"
            ),
        }
    elif session_count > 1 and not _show_summary and recent_topics:
        # ── Fallback: recent topics, no metadata ──────────────────────────────
        topic_list = ", ".join(t[:40] for t in recent_topics[:2])
        greetings = {
            "english": (
                f"Welcome back, Srinika!\n"
                f"Last time you explored: {topic_list}.\n"
                "What shall we explore today?"
            ),
            "hindi": (
                f"Wapas aa gayi Srinika! Kitna accha laga!\n"
                f"Pichhli baar tumne {topic_list} ke baare mein seekha tha.\n"
                "Aaj kya seekhna chahti ho?"
            ),
            "hinglish": (
                f"Welcome back Srinika! Bahut accha laga!\n"
                f"Last time tumne {topic_list} explore kiya tha.\n"
                "Aaj kya explore karna hai?"
            ),
        }
    else:
        # ── First visit ever (or load_memory not available) ───────────────────
        greetings = {
            "english": (
                "Hello! I'm MAYA - your bilingual STEM companion!\n"
                "I can help you explore Science, Technology, Engineering and Math.\n"
                "What would you like to learn today?"
            ),
            "hindi": (
                "Namaste! Main MAYA hun - aapka bilingual STEM saathi!\n"
                "Main aapko Science, Technology, Engineering aur Math mein help kar sakti hun.\n"
                "Aaj kya seekhna chahte hain?"
            ),
            "hinglish": (
                "Hello! Main MAYA hun - tumhara bilingual STEM companion!\n"
                "Science, Math, Technology - sab mein main help karungi!\n"
                "Kya seekhna chahte ho aaj?"
            ),
        }

    response = greetings.get(language, greetings["english"])

    return {
        "response": response,
        # Annotated reducer: LangGraph will ADD this single-item list
        # to the existing message_history (passed in from the REPL)
        "message_history": [{"role": "assistant", "content": response}],
        "steps": current_steps + [f"[greet_response] → greeting in '{language}'"],
    }


def _summarize_session_background(
    message_history: list[dict],
    is_online: bool,
    session_id: int,
    db_path: str | None,
) -> None:
    """
    Background thread: generate a 1-sentence episodic summary and save to SQLite.

    Called (daemon=True) when Srinika says goodbye — fires after farewell_response
    returns so it never delays the UX. MAYA's farewell message appears instantly;
    the summary is written to the DB while she's reading it.

    Session 9: Episodic memory — next time Srinika opens MAYA, greet_response
    shows "Srinika explored gravity and the water cycle." instead of nothing.
    """
    if not message_history:
        return

    # ── Gate 1: Skip summary if session had no real learning content ──────────
    # A "substantive" user turn is longer than 20 chars and not a trivial greeting.
    _TRIVIAL = {"hi", "hello", "bye", "goodbye", "namaste", "ok", "okay", "yes",
                "no", "thanks", "thank you", "alvida", "phir milenge", "bye bye"}

    def _is_substantive(msg: dict) -> bool:
        if msg.get("role") != "user":
            return False
        content = msg.get("content", "").strip().lower()
        if len(content) < 20:
            return False
        if content in _TRIVIAL or any(content.startswith(t + " ") for t in _TRIVIAL):
            return False
        return True

    substantive_turns = [m for m in message_history if _is_substantive(m)]
    if not substantive_turns:
        return  # Only greetings/farewells — no summary worth saving

    # ── Build compact digest of substantive turns only ────────────────────────
    lines = []
    for m in message_history:
        role = "Srinika" if m["role"] == "user" else "MAYA"
        text = m["content"][:120].replace("\n", " ")
        lines.append(f"{role}: {text}")
    conversation_digest = "\n".join(lines)[:800]

    summary_messages = [
        {
            "role": "system",
            "content": (
                "You summarize children's learning sessions. "
                "Write ONE sentence (max 25 words) about what STEM topic was explored. "
                "Start with 'Srinika explored' or 'Srinika learned about' — only if there was real science, math, or story content. "
                "If the session only had greetings, small talk, or no educational content, respond with exactly: SKIP"
            ),
        },
        {"role": "user", "content": conversation_digest},
    ]

    try:
        summary, _ = call_llm_tiered(summary_messages, is_online)
        summary = summary.strip()
        # ── Gate 2: Discard if LLM signals nothing worth remembering ──────────
        if summary and summary.upper() != "SKIP" and len(summary) > 15:
            store = MemoryStore(db_path=db_path)
            store.save_session_summary(session_id, summary)
    except Exception:
        pass  # Background — silent failure is OK; next session just won't have a summary


def farewell_response(state: MayaState) -> dict:
    """
    Node 3b: Warm goodbye in the detected language.

    Session 9 upgrade: fires a background thread (daemon=True) that generates
    a 1-sentence episodic session summary after the farewell message is sent.
    The summary is saved to SQLite and shown in greet_response next session.
    This never delays the UX — MAYA's goodbye appears instantly.
    """
    language = state["language"]
    current_steps = state["steps"]
    message_history = state["message_history"]
    is_online = state.get("is_online", False)
    session_id = state.get("session_id", 0)
    db_path = state.get("memory_db_path") or None

    farewells = {
        "english": (
            "Goodbye! It was wonderful talking with you today.\n"
            "Come back whenever you want to learn something new! See you soon!"
        ),
        "hindi": (
            "Alvida! Aaj aapse baat karke bahut accha laga.\n"
            "Jab bhi kuch seekhna ho, wapas aana! Phir milenge!"
        ),
        "hinglish": (
            "Goodbye! Aaj bahut maza aaya tumse baat karke.\n"
            "Kuch bhi seekhna ho toh wapas aana! Phir milenge!"
        ),
    }

    response = farewells.get(language, farewells["english"])

    # ── Session 9: Episodic summary in background (non-blocking) ─────────────
    # Daemon thread: auto-killed if the process exits before it finishes.
    threading.Thread(
        target=_summarize_session_background,
        args=(message_history, is_online, session_id, db_path),
        daemon=True,
    ).start()

    return {
        "response": response,
        "message_history": [{"role": "assistant", "content": response}],
        "steps": current_steps + [f"[farewell_response] → goodbye in '{language}'"],
    }


def math_tutor_response(state: MayaState) -> dict:
    """
    Node 3c: Dedicated Math Tutor with tiered LLM fallback (Session 8 upgrade).

    Separate from help_response so it has its own:
    - System prompt focused on step-by-step math teaching
    - Analogies using everyday Indian context (rupees, cricket scores, chai)
    - Practice problem at the end of each response

    Session 8: now uses call_llm_tiered — tries Sarvam/Claude/OpenAI when online,
    falls back to Ollama when offline. The step log shows which tier was used.
    """
    language = state["language"]
    current_steps = state["steps"]
    message_history = state["message_history"]
    is_online = state.get("is_online", False)

    history = message_history
    if not history or history[-1].get("role") != "user":
        history = history + [{"role": "user", "content": state["user_input"]}]

    persona_prompt = state.get("persona_system_prompt", "")
    if persona_prompt:
        lang_instruction = _MATH_LANGUAGE_INSTRUCTIONS.get(language, _MATH_LANGUAGE_INSTRUCTIONS["english"])
        system_content = persona_prompt + "\n\n" + _load_prompt("math_tutor") + "\n\n" + lang_instruction
    else:
        system_content = _build_math_prompt(language)

    # Session 10: mastery context for math too
    mastered = state.get("mastered_topics", [])
    practiced_math = [m for m in mastered if m["count"] >= 2]
    if practiced_math:
        mastery_ctx = ", ".join(
            f"{m['topic']} ({m['count']}x)" for m in practiced_math[:3]
        )
        system_content += (
            f"\n\nMastery context: Srinika has explored these before: {mastery_ctx}. "
            "Build on what she knows — skip basics she's already seen, go deeper."
        )

    system_content += f"\n\n{_CBSE_CONTEXT}"
    system_content += f"\n\n{_NO_MARKDOWN}"

    messages = [{"role": "system", "content": system_content}] + history

    preferred_model = state.get("preferred_model") or None  # None → auto tiered
    response, provider = call_llm_tiered(
        messages, is_online,
        fallback_error_prefix="MAYA Math Tutor",
        force_provider=preferred_model,
    )
    response = _strip_markdown(response)

    # Don't store error responses in history — they corrupt context for next turn
    history_update = [] if provider == "error" else [{"role": "assistant", "content": response}]

    return {
        "response": response,
        "message_history": history_update,
        "steps": current_steps + [
            f"[math_tutor_response/{provider}] → language='{language}'"
        ],
    }


def help_response(state: MayaState) -> dict:
    """
    Node 3d: General helpful response with tiered LLM fallback (Session 8 upgrade).

    Session 8: now uses call_llm_tiered — tries Sarvam/Claude/OpenAI when online,
    falls back to Ollama when offline. is_online comes from check_connectivity node.
    The step log shows which tier actually answered: [help_response/claude], etc.
    """
    intent = state["intent"]
    language = state["language"]
    current_steps = state["steps"]
    message_history = state["message_history"]
    is_online = state.get("is_online", False)

    # Build messages: language-aware system prompt + full conversation history.
    # chat_loop.py always appends the user message before invoking, so
    # message_history ends with {"role": "user", ...}. But if called directly
    # (e.g. in tests) with empty history, we add user_input explicitly.
    history = message_history
    if not history or history[-1].get("role") != "user":
        history = history + [{"role": "user", "content": state["user_input"]}]

    # Session 13+14: pick system prompt based on agent_override + persona config
    agent = state.get("agent_override") or "auto"
    prompt_name = _AGENT_PROMPT_MAP.get(agent, "base")
    persona_prompt = state.get("persona_system_prompt", "")
    lang_instruction = _LANGUAGE_INSTRUCTIONS.get(language, _LANGUAGE_INSTRUCTIONS["english"])

    if persona_prompt and agent in ("science", "story"):
        # Specialist agent: persona tone + specialist .md knowledge
        system_content = persona_prompt + "\n\n" + _load_prompt(prompt_name) + "\n\n" + lang_instruction
    elif persona_prompt:
        # General/auto: persona prompt replaces the base .md
        system_content = persona_prompt + "\n\n" + lang_instruction
    else:
        system_content = _build_agent_prompt(prompt_name, language)
    recent_topics = state.get("recent_topics", [])
    if recent_topics:
        topic_list = ", ".join(f'"{t[:40]}"' for t in recent_topics[:2])
        system_content += f"\n\nContext: Srinika has previously asked about {topic_list}. You can refer back to these if relevant."

    # Session 10: inject mastery context so MAYA builds on what Srinika knows
    mastered = state.get("mastered_topics", [])
    practiced = [m for m in mastered if m["count"] >= 2]
    if practiced:
        mastery_ctx = ", ".join(
            f"{m['topic']} ({m['count']}x, {m['level']})" for m in practiced[:3]
        )
        system_content += (
            f"\n\nMastery context: Srinika has explored these topics before: {mastery_ctx}. "
            "She already knows the basics of these — go deeper, challenge her thinking, "
            "connect to new concepts she hasn't seen yet."
        )

    system_content += f"\n\n{_CBSE_CONTEXT}"
    system_content += f"\n\n{_NO_MARKDOWN}"

    messages = [{"role": "system", "content": system_content}] + history

    preferred_model = state.get("preferred_model") or None  # None → auto tiered
    response, provider = call_llm_tiered(messages, is_online, force_provider=preferred_model)
    response = _strip_markdown(response)

    # Don't store error responses in history — they corrupt context for next turn
    history_update = [] if provider == "error" else [{"role": "assistant", "content": response}]

    return {
        "response": response,
        "message_history": history_update,
        "steps": current_steps + [
            f"[help_response/{provider}] → agent='{agent}', intent='{intent}', language='{language}'"
        ],
    }


def reminder_agent(state: MayaState) -> dict:
    """
    Node 3e (Session 17): Handles todo/reminder intents.

    Parses the user's request via LLM to determine the action:
      - "add"  → extract task text (+ optional due_date/recurrence) → add_todo()
      - "list" → format pending_todos into a friendly message
      - "done" → mark_todo_done() for the referenced item
      - "delete" → delete_todo() for the referenced item

    LLM is used only for intent parsing and text extraction — all DB writes
    go through MemoryStore to keep state clean and testable.
    """
    language = state["language"]
    current_steps = state["steps"]
    user_input = state["user_input"]
    pending = state.get("pending_todos", [])
    is_online = state.get("is_online", False)
    db_path = state.get("memory_db_path") or None

    # Ask LLM to parse the action and extract structured data
    parse_messages = [
        {
            "role": "system",
            "content": (
                "You are a reminder parser for a children's app. "
                "Given the user's message, reply with a JSON object (no markdown, no explanation) with:\n"
                '  "action": "add" | "list" | "done" | "delete"\n'
                '  "task": the task text if action is add (else null)\n'
                '  "due_date": optional due date string if mentioned (else null)\n'
                '  "recurrence": "daily" | "weekly" | null\n'
                '  "item_number": 1-based index if action is done/delete (else null)\n'
                "Current pending todos:\n"
                + (
                    "\n".join(f"{i+1}. {t['text']}" for i, t in enumerate(pending))
                    if pending else "(none)"
                )
            ),
        },
        {"role": "user", "content": user_input},
    ]

    action = "list"
    task_text = ""
    due_date = None
    recurrence = None
    item_number = None

    try:
        import json as _json
        raw, _ = call_llm_tiered(parse_messages, is_online)
        # Strip any markdown code fences if the model adds them
        raw = raw.strip().strip("```json").strip("```").strip()
        parsed = _json.loads(raw)
        action = parsed.get("action", "list")
        task_text = parsed.get("task") or ""
        due_date = parsed.get("due_date")
        recurrence = parsed.get("recurrence")
        item_number = parsed.get("item_number")
    except Exception:
        pass  # Fallback: treat as "list" if parsing fails

    store = MemoryStore(db_path=db_path)

    if action == "add" and task_text:
        new_id = store.add_todo(task_text, due_date=due_date, recurrence=recurrence)
        due_str = f" by {due_date}" if due_date else ""
        rec_str = f" (repeats {recurrence})" if recurrence else ""
        response_map = {
            "english": f"Got it! I've added '{task_text}'{due_str}{rec_str} to your list.",
            "hindi":   f"Ho gaya! Maine '{task_text}'{due_str}{rec_str} tumhari list mein add kar diya.",
            "hinglish": f"Done! '{task_text}'{due_str}{rec_str} tumhari list mein add kar diya.",
        }
        # Refresh pending list after add
        pending = store.get_pending_todos()

    elif action == "done" and item_number and 1 <= item_number <= len(pending):
        todo = pending[item_number - 1]
        store.mark_todo_done(todo["id"])
        response_map = {
            "english":  f"Great job! I've marked '{todo['text']}' as done.",
            "hindi":    f"Wah! '{todo['text']}' complete kar diya — bahut accha!",
            "hinglish": f"Awesome! '{todo['text']}' done mark kar diya!",
        }
        pending = store.get_pending_todos()

    elif action == "delete" and item_number and 1 <= item_number <= len(pending):
        todo = pending[item_number - 1]
        store.delete_todo(todo["id"])
        response_map = {
            "english":  f"Removed '{todo['text']}' from your list.",
            "hindi":    f"'{todo['text']}' list se hata diya.",
            "hinglish": f"'{todo['text']}' list se remove kar diya.",
        }
        pending = store.get_pending_todos()

    else:
        # action == "list" or fallback
        if not pending:
            response_map = {
                "english":  "Your todo list is empty! Want to add something?",
                "hindi":    "Tumhari todo list khali hai! Kuch add karna hai?",
                "hinglish": "Todo list abhi empty hai! Kuch add karein?",
            }
        else:
            items = "\n".join(f"{i+1}. {t['text']}" for i, t in enumerate(pending))
            response_map = {
                "english":  f"Here are your todos:\n{items}",
                "hindi":    f"Yeh hain tumhare todos:\n{items}",
                "hinglish": f"Tumhare todos:\n{items}",
            }

    response = response_map.get(language, response_map["english"])

    return {
        "response": response,
        "pending_todos": pending,
        "message_history": [{"role": "assistant", "content": response}],
        "steps": current_steps + [f"[reminder_agent] → action='{action}', language='{language}'"],
    }


# =============================================================================
# ROUTING FUNCTION
# Now 3-way: greeting | farewell | everything else
# =============================================================================


def route_by_intent(state: MayaState) -> str:
    """
    Routing function (Session 13: agent_override added).

    Priority order:
    1. Greeting/farewell always win — social turns work in any agent mode
    2. agent_override == "math" → force math_tutor_response regardless of intent
    3. intent == "math" (auto mode) → math_tutor_response
    4. Everything else → help_response (uses agent-specific prompt inside)

    agent_override values: "auto"|"math"|"science"|"story"|"general"|None
    science/story/general are handled inside help_response via prompt selection.
    """
    intent = state.get("intent", "general")
    agent  = state.get("agent_override") or "auto"

    # Social turns always route to their dedicated nodes
    if intent == "greeting":
        return "greet_response"
    if intent == "farewell":
        return "farewell_response"
    if intent == "reminder":
        return "reminder_agent"

    # Agent override: "math" forces math tutor regardless of what the user typed
    if agent == "math" or intent == "math":
        return "math_tutor_response"

    # science / story / general / auto all go to help_response
    # (help_response picks the right system prompt from agent_override)
    return "help_response"


# =============================================================================
# GRAPH ASSEMBLY
# =============================================================================


def build_conversation_graph():
    """
    Assembles MAYA's conversation graph (Session 8 version).

    Changes from Session 6:
    - check_connectivity node added after load_memory (Session 8)
    - is_online injected into state so LLM nodes can pick the right provider tier

    Graph topology:
        START → load_memory → check_connectivity → detect_language → understand_intent
             → [greet | farewell | math | help] → save_memory → END
    """
    graph = StateGraph(MayaState)

    # Register nodes
    graph.add_node("load_memory",          load_memory)          # Session 5
    graph.add_node("check_connectivity",   check_connectivity)   # Session 8
    graph.add_node("detect_language",      detect_language)
    graph.add_node("understand_intent",    understand_intent)
    graph.add_node("greet_response",       greet_response)
    graph.add_node("farewell_response",    farewell_response)
    graph.add_node("math_tutor_response",  math_tutor_response)  # Session 6
    graph.add_node("help_response",        help_response)
    graph.add_node("reminder_agent",       reminder_agent)       # Session 17
    graph.add_node("save_memory",          save_memory)          # Session 5

    # Fixed edges
    graph.add_edge(START,                  "load_memory")
    graph.add_edge("load_memory",          "check_connectivity")   # Session 8
    graph.add_edge("check_connectivity",   "detect_language")      # Session 8
    graph.add_edge("detect_language",      "understand_intent")

    # Conditional edge - 4-way split on intent (Session 6: math added)
    graph.add_conditional_edges(
        "understand_intent",
        route_by_intent,
        {
            "greet_response":       "greet_response",
            "farewell_response":    "farewell_response",
            "reminder_agent":       "reminder_agent",         # Session 17
            "math_tutor_response":  "math_tutor_response",
            "help_response":        "help_response",
        },
    )

    # All response nodes lead to save_memory, then END
    graph.add_edge("greet_response",      "save_memory")
    graph.add_edge("farewell_response",   "save_memory")
    graph.add_edge("math_tutor_response", "save_memory")    # NEW
    graph.add_edge("reminder_agent",      "save_memory")    # Session 17
    graph.add_edge("help_response",       "save_memory")
    graph.add_edge("save_memory",       END)

    return graph.compile()


# Module-level compiled graph
maya_graph = build_conversation_graph()
