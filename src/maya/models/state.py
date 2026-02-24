"""
MAYA State Definition
======================
The State is the "baton" passed between every node in a LangGraph graph.
Think of it as a shared notepad - each node reads from it and writes its results back.

LEARNING NOTES for Srinivasan:
--------------------------------
Q: Why TypedDict instead of a regular dict?
A: TypedDict gives IDE autocomplete and catches typos at development time,
   while still behaving exactly like a plain Python dict at runtime.
   LangGraph requires a dict-compatible type for state.

Q: How does LangGraph update state?
A: Each node returns a PARTIAL dict (only the keys it changed).
   LangGraph merges that partial dict into the full state automatically.
   Example: a node that only detects language returns {"language": "hindi"}
            LangGraph keeps all other state keys unchanged.

Q: What is Annotated[list, operator.add] for?
A: It's a special LangGraph pattern for lists you want to ACCUMULATE instead
   of REPLACE. Used for message history in chat apps. Not needed here yet,
   but you'll see it in LangGraph docs - now you know what it means!
"""

from typing import TypedDict


class MayaState(TypedDict):
    """
    Central state for MAYA's LangGraph.

    Every node in the graph receives this full state object and returns
    a dict containing only the keys it updated.

    Fields are ordered by the flow of data through the graph:
    Input → Processing → Output → Debug
    """

    # ── Input (set before graph starts) ──────────────────────────────────────
    user_input: str          # Raw text from user (voice → Whisper → text later)

    # ── Processing results (filled by nodes as graph runs) ────────────────────
    language: str            # Detected: "english" | "hindi" | "hinglish"
    intent: str              # Detected: "greeting" | "question" | "math" | "general"

    # ── Output (set by the final response node) ────────────────────────────────
    response: str            # MAYA's reply to the user

    # ── Debug / Learning visibility ────────────────────────────────────────────
    steps: list[str]         # Log entry from each node - shows graph execution flow
                             # Remove or make optional once you understand the flow
