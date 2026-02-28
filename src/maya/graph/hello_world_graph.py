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

from langgraph.graph import StateGraph, END, START

from src.maya.agents.memory_store import MemoryStore
from src.maya.models.state import MayaState


# =============================================================================
# MAYA SYSTEM PROMPT  (Session 3 - Ollama LLM integration)
# =============================================================================

_MAYA_BASE_PROMPT = """You are MAYA (Multi-Agent hYbrid Assistant) - a warm, encouraging bilingual \
STEM companion for Srinika, a curious 10-year-old girl in India.

YOUR PERSONALITY:
- Warm, enthusiastic, and encouraging - like a smart older sister
- You love Science, Technology, Engineering, and Math
- You use simple analogies from everyday life (food, cricket, nature, school)
- You celebrate curiosity: every question is a GREAT question
- You keep explanations simple - no jargon unless you explain it immediately

RESPONSE STYLE:
- Keep responses SHORT - 2 to 4 sentences maximum
- Responses are spoken aloud via TTS: write naturally, no bullet points or markdown
- End with a short follow-up question to keep Srinika curious
- Never be condescending - treat her as a smart, capable learner"""

# Per-language instructions injected at call time (small models need explicit reminders)
_LANGUAGE_INSTRUCTIONS = {
    "english":  "CRITICAL: You MUST respond in English only. Do not use any Hindi or Urdu words.",
    "hindi":    "CRITICAL: You MUST respond in Hinglish (Roman script Hindi mixed with English). Do not use Devanagari script.",
    "hinglish": "CRITICAL: You MUST respond in Hinglish - natural mix of Hindi (Roman script) and English, like: 'Waah, bahut accha question hai! Gravity is the force...'",
}


def _build_system_prompt(language: str) -> str:
    """Combine base prompt with a per-turn language instruction."""
    lang_instruction = _LANGUAGE_INSTRUCTIONS.get(language, _LANGUAGE_INSTRUCTIONS["english"])
    return f"{_MAYA_BASE_PROMPT}\n\n{lang_instruction}"


# =============================================================================
# MATH TUTOR SYSTEM PROMPT  (Session 6 - dedicated math agent)
# =============================================================================

_MATH_TUTOR_PROMPT = """You are MAYA's Math Tutor mode - a patient, step-by-step math teacher \
for Srinika, a curious 10-year-old girl in India.

YOUR TEACHING STYLE:
- Always solve the problem first, THEN explain each step clearly
- Use simple everyday analogies: apples, cricket scores, chai cups, rupees
- Celebrate effort: "Great question! Let me show you how..."
- If it's a calculation, show the working: "Step 1... Step 2... Answer!"
- Keep it SHORT - 3 to 5 sentences maximum (spoken aloud via TTS)
- End with a similar practice problem to reinforce learning

IMPORTANT: Never just give the answer without explaining WHY."""

_MATH_LANGUAGE_INSTRUCTIONS = {
    "english":  "CRITICAL: Respond in English only.",
    "hindi":    "CRITICAL: Respond in Hinglish (Roman script Hindi + English). Show math steps in English numbers.",
    "hinglish": "CRITICAL: Respond in Hinglish - mix Hindi (Roman script) and English naturally. Math steps in English.",
}


def _build_math_prompt(language: str) -> str:
    """Math tutor system prompt with language instruction."""
    lang_instruction = _MATH_LANGUAGE_INSTRUCTIONS.get(language, _MATH_LANGUAGE_INSTRUCTIONS["english"])
    return f"{_MATH_TUTOR_PROMPT}\n\n{lang_instruction}"


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
    except Exception:
        profile = {"user_name": "Srinika", "session_count": 0, "total_turns": 0}
        recent = []

    return {
        "user_name":     profile["user_name"],
        "session_count": profile["session_count"],
        "recent_topics": recent,
        "steps": current_steps + [
            f"[load_memory] → session_count={profile['session_count']}, "
            f"{len(recent)} recent topic(s)"
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

    try:
        store = MemoryStore(db_path=db_path)
        store.log_turn(user_input, intent, session_id=session_id)
        log_status = "ok"
    except Exception as e:
        log_status = f"error: {e}"

    return {
        "steps": current_steps + [f"[save_memory] → logged turn ({log_status})"],
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
    farewell_single  = {"bye", "goodbye", "goodnight", "cya", "alvida", "tata", "exit", "quit", "stop", "later"}
    greeting_single  = {"hello", "hi", "hey", "namaste", "namaskar", "sup"}
    math_single      = {"calculate", "solve", "math", "add", "subtract", "multiply", "divide",
                        "plus", "minus", "times", "equals", "+", "-", "*", "/", "sum", "total"}
    question_single  = {"what", "why", "how", "when", "where", "who", "which", "explain",
                        "describe", "kya", "kyun", "kaise", "kab", "kahaan", "kaun", "batao", "samjhao"}

    # Multi-word phrases — substring match is fine (they're specific enough)
    farewell_phrases  = {"good bye", "see you", "phir milenge", "good night", "band karo"}
    greeting_phrases  = {"good morning", "good evening"}
    question_phrases  = {"tell me"}

    def _match(single_set, phrase_set=None):
        if words_in_input & single_set:
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

    if session_count > 1 and recent_topics:
        # Returning visitor — personalised welcome
        last_topic = recent_topics[0][:60]  # cap length for TTS
        greetings = {
            "english": (
                f"Welcome back, Srinika! Great to see you again (session {session_count})!\n"
                f"Last time you asked about: \"{last_topic}\".\n"
                "What shall we explore today?"
            ),
            "hindi": (
                f"Wapas aa gayi Srinika! Kitna accha laga (session {session_count})!\n"
                f"Pichhli baar tumne poochha tha: \"{last_topic}\".\n"
                "Aaj kya seekhna chahti ho?"
            ),
            "hinglish": (
                f"Welcome back Srinika! Bahut accha laga (session {session_count})!\n"
                f"Last time tumne pucha tha: \"{last_topic}\".\n"
                "Aaj kya explore karna hai?"
            ),
        }
    else:
        # First visit ever (or load_memory not available)
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


def farewell_response(state: MayaState) -> dict:
    """
    Node 3b: Warm goodbye in the detected language. NEW in Session 2.

    The REPL checks intent == "farewell" to break the conversation loop.
    """
    language = state["language"]
    current_steps = state["steps"]
    turn_count = len([m for m in state["message_history"] if m["role"] == "user"])

    farewells = {
        "english": (
            f"Goodbye! It was wonderful talking with you today ({turn_count} turns).\n"
            "Come back whenever you want to learn something new! See you soon!"
        ),
        "hindi": (
            f"Alvida! Aaj aapse baat karke bahut accha laga ({turn_count} turns).\n"
            "Jab bhi kuch seekhna ho, wapas aana! Phir milenge!"
        ),
        "hinglish": (
            f"Goodbye! Aaj bahut maza aaya tumse baat karke ({turn_count} turns).\n"
            "Kuch bhi seekhna ho toh wapas aana! Phir milenge!"
        ),
    }

    response = farewells.get(language, farewells["english"])

    return {
        "response": response,
        "message_history": [{"role": "assistant", "content": response}],
        "steps": current_steps + [f"[farewell_response] → goodbye in '{language}'"],
    }


def math_tutor_response(state: MayaState) -> dict:
    """
    Node 3c: Dedicated Math Tutor via Ollama (Session 6 - new agent!).

    Separate from help_response so it has its own:
    - System prompt focused on step-by-step math teaching
    - Analogies using everyday Indian context (rupees, cricket scores, chai)
    - Practice problem at the end of each response

    Same Ollama call pattern as help_response — only the system prompt differs.
    This is the multi-agent principle: same model, different instructions = different agent.
    """
    language = state["language"]
    current_steps = state["steps"]
    message_history = state["message_history"]

    try:
        import ollama

        history = message_history
        if not history or history[-1].get("role") != "user":
            history = history + [{"role": "user", "content": state["user_input"]}]

        messages = [{"role": "system", "content": _build_math_prompt(language)}] + history

        result = ollama.chat(
            model="llama3.2:3b",
            messages=messages,
        )
        response = result.message.content.strip()

    except Exception as e:
        response = (
            "Hmm, my math brain isn't working right now! "
            "Make sure Ollama is running with: ollama serve. "
            f"Error: {e}"
        )

    return {
        "response": response,
        "message_history": [{"role": "assistant", "content": response}],
        "steps": current_steps + [
            f"[math_tutor_response/ollama] → language='{language}'"
        ],
    }


def help_response(state: MayaState) -> dict:
    """
    Node 3d: General helpful response via Ollama LLM (Session 3 upgrade).

    Calls llama3.2:3b with:
    - MAYA_SYSTEM_PROMPT: personality + language rules
    - Full message_history: gives Ollama multi-turn context
    The graph structure and return dict are unchanged from Session 2.

    Falls back to a friendly error message if Ollama is not reachable.
    """
    intent = state["intent"]
    language = state["language"]
    current_steps = state["steps"]
    message_history = state["message_history"]

    try:
        import ollama

        # Build messages: language-aware system prompt + full conversation history.
        # chat_loop.py always appends the user message before invoking, so
        # message_history ends with {"role": "user", ...}. But if called directly
        # (e.g. in tests) with empty history, we add user_input explicitly.
        history = message_history
        if not history or history[-1].get("role") != "user":
            history = history + [{"role": "user", "content": state["user_input"]}]

        # Enrich system prompt with memory context if available
        system_content = _build_system_prompt(language)
        recent_topics = state.get("recent_topics", [])
        if recent_topics:
            topic_list = ", ".join(f'"{t[:40]}"' for t in recent_topics[:2])
            system_content += f"\n\nContext: Srinika has previously asked about {topic_list}. You can refer back to these if relevant."

        messages = [{"role": "system", "content": system_content}] + history

        result = ollama.chat(
            model="llama3.2:3b",
            messages=messages,
        )
        response = result.message.content.strip()

    except Exception as e:
        # Graceful fallback - MAYA stays in character even if Ollama is down
        response = (
            "Hmm, I'm having a little trouble thinking right now! "
            "Make sure Ollama is running with: ollama serve. "
            f"Error: {e}"
        )

    return {
        "response": response,
        "message_history": [{"role": "assistant", "content": response}],
        "steps": current_steps + [
            f"[help_response/ollama] → intent='{intent}', language='{language}'"
        ],
    }


# =============================================================================
# ROUTING FUNCTION
# Now 3-way: greeting | farewell | everything else
# =============================================================================


def route_by_intent(state: MayaState) -> str:
    """
    Routing function: 4-way split on intent (Session 6: math added).

    Returns a string matching one of the conditional_edge keys below.
    - greeting  → greet_response      (warm hello)
    - farewell  → farewell_response   (goodbye)
    - math      → math_tutor_response (NEW: step-by-step math teaching)
    - everything else → help_response (general STEM Q&A via Ollama)
    """
    intent = state.get("intent", "general")

    if intent == "greeting":
        return "greet_response"
    elif intent == "farewell":
        return "farewell_response"
    elif intent == "math":
        return "math_tutor_response"
    else:
        return "help_response"


# =============================================================================
# GRAPH ASSEMBLY
# =============================================================================


def build_conversation_graph():
    """
    Assembles MAYA's conversation graph (Session 5 version).

    Changes from Session 4:
    - load_memory node added as the FIRST node (before detect_language)
    - save_memory node added as the LAST node (all response nodes → save_memory → END)
    - greet_response now says "Welcome back!" on return sessions
    - help_response includes recent topic context in system prompt

    Graph topology:
        START → load_memory → detect_language → understand_intent
             → [greet | farewell | help] → save_memory → END
    """
    graph = StateGraph(MayaState)

    # Register nodes
    graph.add_node("load_memory",          load_memory)          # Session 5
    graph.add_node("detect_language",      detect_language)
    graph.add_node("understand_intent",    understand_intent)
    graph.add_node("greet_response",       greet_response)
    graph.add_node("farewell_response",    farewell_response)
    graph.add_node("math_tutor_response",  math_tutor_response)  # NEW Session 6
    graph.add_node("help_response",        help_response)
    graph.add_node("save_memory",          save_memory)          # Session 5

    # Fixed edges
    graph.add_edge(START,           "load_memory")        # was: START → detect_language
    graph.add_edge("load_memory",   "detect_language")
    graph.add_edge("detect_language", "understand_intent")

    # Conditional edge - 4-way split on intent (Session 6: math added)
    graph.add_conditional_edges(
        "understand_intent",
        route_by_intent,
        {
            "greet_response":       "greet_response",
            "farewell_response":    "farewell_response",
            "math_tutor_response":  "math_tutor_response",   # NEW
            "help_response":        "help_response",
        },
    )

    # All response nodes lead to save_memory, then END
    graph.add_edge("greet_response",      "save_memory")
    graph.add_edge("farewell_response",   "save_memory")
    graph.add_edge("math_tutor_response", "save_memory")    # NEW
    graph.add_edge("help_response",       "save_memory")
    graph.add_edge("save_memory",       END)

    return graph.compile()


# Module-level compiled graph
maya_graph = build_conversation_graph()
