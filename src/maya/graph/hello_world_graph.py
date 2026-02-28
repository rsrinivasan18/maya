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
# NODES
# =============================================================================


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

    Updated: Added farewell detection (bye/goodbye/alvida/phir milenge).
    Precedence: farewell > greeting > math > question > general
    """
    user_input = state["user_input"].lower()
    current_steps = state["steps"]

    farewell_words = {
        "bye", "goodbye", "good bye", "see you", "later", "cya",
        "alvida", "phir milenge", "tata", "good night", "goodnight",
        "band karo", "exit", "quit", "stop",
    }
    greeting_words = {
        "hello", "hi", "hey", "namaste", "namaskar",
        "good morning", "good evening", "sup",
    }
    math_words = {
        "calculate", "solve", "math", "add", "subtract", "multiply", "divide",
        "plus", "minus", "times", "equals", "+", "-", "*", "/", "sum", "total",
    }
    question_words = {
        "what", "why", "how", "when", "where", "who", "which", "explain",
        "tell me", "describe", "kya", "kyun", "kaise", "kab", "kahaan",
        "kaun", "batao", "samjhao",
    }

    # Farewell takes highest precedence - it exits the conversation
    if any(word in user_input for word in farewell_words):
        intent = "farewell"
    elif any(word in user_input for word in greeting_words):
        intent = "greeting"
    elif any(word in user_input for word in math_words):
        intent = "math"
    elif any(word in user_input for word in question_words):
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

    NEW: Returns message_history entry.
    Annotated[list, operator.add] means LangGraph APPENDS this to existing history.
    """
    language = state["language"]
    current_steps = state["steps"]

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


def help_response(state: MayaState) -> dict:
    """
    Node 3c: Helpful response via Ollama LLM (Session 3 upgrade).

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

        # Build messages: language-aware system prompt + full conversation history
        # chat_loop.py always appends the user message before invoking, so
        # message_history ends with {"role": "user", ...}. But if called directly
        # (e.g. in tests) with empty history, we add user_input explicitly.
        history = message_history
        if not history or history[-1].get("role") != "user":
            history = history + [{"role": "user", "content": state["user_input"]}]
        messages = [{"role": "system", "content": _build_system_prompt(language)}] + history

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
    Routing function: 3-way split on intent.

    Returns a string matching one of the conditional_edge keys below.
    This grows over time - Week 4 adds math_tutor, story, vocabulary routes.
    """
    intent = state.get("intent", "general")

    if intent == "greeting":
        return "greet_response"
    elif intent == "farewell":
        return "farewell_response"
    else:
        return "help_response"


# =============================================================================
# GRAPH ASSEMBLY
# =============================================================================


def build_conversation_graph():
    """
    Assembles MAYA's conversation graph (Session 2 version).

    Changes from Session 1:
    - Added farewell_response node
    - route_by_intent is now 3-way
    - Response nodes now write to message_history
    """
    graph = StateGraph(MayaState)

    # Register nodes
    graph.add_node("detect_language", detect_language)
    graph.add_node("understand_intent", understand_intent)
    graph.add_node("greet_response", greet_response)
    graph.add_node("farewell_response", farewell_response)   # NEW
    graph.add_node("help_response", help_response)

    # Fixed edges
    graph.add_edge(START, "detect_language")
    graph.add_edge("detect_language", "understand_intent")

    # Conditional edge - now 3-way
    graph.add_conditional_edges(
        "understand_intent",
        route_by_intent,
        {
            "greet_response":    "greet_response",
            "farewell_response": "farewell_response",   # NEW
            "help_response":     "help_response",
        },
    )

    # All response nodes lead to END
    graph.add_edge("greet_response", END)
    graph.add_edge("farewell_response", END)             # NEW
    graph.add_edge("help_response", END)

    return graph.compile()


# Module-level compiled graph
maya_graph = build_conversation_graph()
