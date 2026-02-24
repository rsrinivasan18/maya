"""
MAYA Hello World - First LangGraph Agent
=========================================
Week 1 deliverable: a working LangGraph graph with 4 nodes and 1 conditional edge.
No LLM required - pure Python rule-based logic so you can focus on graph structure.

WHAT THIS FILE TEACHES (read before running):
----------------------------------------------

1. STATEGRAPH  - The container that holds nodes and edges (the "circuit board")
2. STATE       - TypedDict flowing through nodes like a baton in a relay race
3. NODE        - A plain Python function: receives full state, returns partial dict
4. EDGE        - A directed connection from one node to the next
5. CONDITIONAL EDGE - A routing function that picks which node to go to next
                      This is what makes LangGraph powerful!
6. COMPILE     - Validates the graph structure and locks it for execution
7. INVOKE      - Runs the graph from START to END with an initial state

GRAPH FLOW:
-----------
    START
      ↓
  [detect_language]       Node 1: Is it Hindi / English / Hinglish?
      ↓
  [understand_intent]     Node 2: Greeting? Question? Math?
      ↓
  [route_by_intent]  ──── CONDITIONAL EDGE (the key LangGraph concept!)
      ↓              ↓
 [greet_response]  [help_response]    Node 3a / 3b: Different paths!
      ↓              ↓
     END            END

WHY CONDITIONAL EDGES MATTER FOR MAYA:
---------------------------------------
This simple greeting/help split is the prototype for MAYA's Intent Router Agent,
which will eventually route to:
  - Offline local LLM  (fast, free, private) for simple questions
  - Sarvam API / Claude (richer, bilingual)   for complex STEM explanations
  - Math Tutor Agent                           for math problems
  - Story Agent                                for storytelling requests
"""

from langgraph.graph import StateGraph, END, START

from src.maya.models.state import MayaState


# =============================================================================
# NODES
# Each node is a plain Python function with this signature:
#   def node_name(state: MayaState) -> dict:
#
# Rules:
#   - Receive the FULL current state as input
#   - Return ONLY a dict of the keys you changed (LangGraph merges the rest)
#   - Never mutate the state dict directly - always return a new dict
# =============================================================================


def detect_language(state: MayaState) -> dict:
    """
    Node 1: Detect whether the user wrote in Hindi, English, or Hinglish.

    Method: Simple word-matching (no ML). Good enough for Week 1.
    Week 3 upgrade: Replace with Sarvam's language detection API.
    """
    user_input = state["user_input"].lower()
    current_steps = state["steps"]

    # Common Hindi words that appear even in Hinglish sentences
    hindi_markers = {
        "namaste", "namaskar", "kya", "hai", "hain", "nahi", "haan",
        "karo", "kuch", "mujhe", "tumhe", "aap", "tum", "main", "mera",
        "tera", "uska", "bahut", "accha", "theek", "kyun", "kaise",
        "kaun", "kab", "kahaan", "batao", "samjhao", "seekhna", "chahte",
    }

    words_in_input = set(user_input.split())
    hindi_count = len(words_in_input & hindi_markers)

    if hindi_count >= 2:
        language = "hindi"
    elif hindi_count == 1:
        language = "hinglish"
    else:
        language = "english"

    # Return ONLY the keys this node updates (LangGraph merges the rest)
    return {
        "language": language,
        "steps": current_steps + [
            f"[detect_language] → '{language}' (found {hindi_count} Hindi marker(s))"
        ],
    }


def understand_intent(state: MayaState) -> dict:
    """
    Node 2: Understand what the user wants.

    This is the prototype of MAYA's Intent Router Agent.
    Today: rule-based matching.
    Week 4 upgrade: Small local classifier or LLM-based routing.
    """
    user_input = state["user_input"].lower()
    current_steps = state["steps"]

    greeting_words = {
        "hello", "hi", "hey", "namaste", "namaskar",
        "good morning", "good evening", "good night", "sup",
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

    # Precedence: greeting > math > question > general
    if any(word in user_input for word in greeting_words):
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
    Node 3a: Generate a warm greeting in the detected language.

    MAYA's personality: enthusiastic, warm, bilingual, encouraging.
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
        "steps": current_steps + [
            f"[greet_response] → Greeting generated in '{language}'"
        ],
    }


def help_response(state: MayaState) -> dict:
    """
    Node 3b: Generate a helpful response for questions, math, or general chat.

    Week 1: Placeholder responses that hint at what's coming.
    Week 3 upgrade: Replace with actual Sarvam/Ollama LLM calls.
    Week 4 upgrade: Route math intent to dedicated Math Tutor Agent.
    """
    intent = state["intent"]
    language = state["language"]
    current_steps = state["steps"]

    # Response templates per intent and language
    templates = {
        "math": {
            "english": (
                "Ooh, a math problem! Numbers are my superpower!\n"
                "Full math solving with step-by-step explanations is coming in Week 4.\n"
                "For now, try me on: 'What is algebra?' or 'Explain fractions'!"
            ),
            "hindi": (
                "Arre waah, math ka sawaal! Numbers meri favourite hain!\n"
                "Week 4 mein main step-by-step solve karungi.\n"
                "Abhi try karo: 'Algebra kya hai?' ya 'Fractions samjhao'!"
            ),
            "hinglish": (
                "Oh, math question! Numbers mujhe bahut pasand hain!\n"
                "Week 4 mein full solving aayega.\n"
                "Abhi try karo: 'Algebra kya hai?' or 'Explain fractions'!"
            ),
        },
        "question": {
            "english": (
                "Great question! I'm thinking...\n"
                "Full AI-powered answers with Sarvam/Ollama are coming in Week 3.\n"
                "Right now I'm just a baby graph learning to walk!"
            ),
            "hindi": (
                "Bahut accha sawaal! Soch rahi hun...\n"
                "Week 3 mein Sarvam/Ollama se full AI answer aayega.\n"
                "Abhi main graph sikhna seekh rahi hun!"
            ),
            "hinglish": (
                "Accha question! Let me think...\n"
                "Week 3 mein full AI answer aayega Sarvam/Ollama se.\n"
                "Right now main ek baby graph hun, seekh rahi hun!"
            ),
        },
        "general": {
            "english": (
                "Got it! I'm MAYA, your STEM learning companion.\n"
                "Try asking me: 'Hello', 'What is gravity?', or 'Calculate 5 + 3'!"
            ),
            "hindi": (
                "Samjha! Main MAYA hun, aapka STEM saathi.\n"
                "Try karo: 'Namaste', 'Gravity kya hai?', ya '5 + 3 calculate karo'!"
            ),
            "hinglish": (
                "Okay! Main MAYA hun - tumhara STEM companion.\n"
                "Try karo: 'Hello', 'What is gravity?', ya 'Calculate 5 + 3'!"
            ),
        },
    }

    intent_templates = templates.get(intent, templates["general"])
    response = intent_templates.get(language, intent_templates["english"])

    return {
        "response": response,
        "steps": current_steps + [
            f"[help_response] → Response for intent='{intent}', language='{language}'"
        ],
    }


# =============================================================================
# ROUTING FUNCTION (Conditional Edge)
# This function is called by LangGraph after understand_intent.
# It returns the NAME of the next node as a string.
#
# This is the heart of MAYA's future Intent Router Agent!
# Today: greeting vs everything else.
# Week 4: will route to Math Tutor, Story Agent, Vocabulary Agent, etc.
# =============================================================================


def route_by_intent(state: MayaState) -> str:
    """
    Routing function: decides which response node to call.

    Returns a string that must match one of the keys in the
    conditional_edge mapping defined below.
    """
    intent = state.get("intent", "general")

    if intent == "greeting":
        return "greet_response"   # → Node 3a
    else:
        return "help_response"    # → Node 3b (math, question, general)


# =============================================================================
# GRAPH ASSEMBLY
# Wire the nodes and edges together, then compile.
# Think of this like building a flowchart:
#   - Nodes are the boxes
#   - Edges are the arrows
# =============================================================================


def build_hello_world_graph():
    """
    Assembles and compiles MAYA's hello world LangGraph.

    Returns a compiled graph ready to call .invoke() on.
    """

    # Step 1: Create the graph container
    # StateGraph takes our state type so it knows what data flows through
    graph = StateGraph(MayaState)

    # Step 2: Register nodes
    # Each node is a (name, function) pair
    graph.add_node("detect_language", detect_language)
    graph.add_node("understand_intent", understand_intent)
    graph.add_node("greet_response", greet_response)
    graph.add_node("help_response", help_response)

    # Step 3: Add edges (fixed - always go to the next node)
    graph.add_edge(START, "detect_language")
    graph.add_edge("detect_language", "understand_intent")

    # Step 4: Add conditional edge
    # After understand_intent runs, call route_by_intent() to decide where to go.
    # The dict maps return values → node names.
    graph.add_conditional_edges(
        "understand_intent",          # Source node
        route_by_intent,              # Routing function
        {
            "greet_response": "greet_response",   # If routing fn returns this → go here
            "help_response": "help_response",     # If routing fn returns this → go here
        },
    )

    # Step 5: Both response nodes lead to END
    graph.add_edge("greet_response", END)
    graph.add_edge("help_response", END)

    # Step 6: Compile - validates structure, prepares for execution
    # If you have errors (disconnected nodes, missing edges), compile() will tell you.
    return graph.compile()


# Module-level compiled graph - import this to use MAYA
maya_graph = build_hello_world_graph()
