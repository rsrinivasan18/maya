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

Q: What is Annotated[list, operator.add]?  ← NEW CONCEPT (Session 2)
A: It's a LangGraph REDUCER - it tells LangGraph HOW to merge a key
   when a node returns it.

   Without Annotated (normal):
     existing: ["item1", "item2"]
     node returns: ["item3"]
     result: ["item3"]         ← REPLACES the whole list!

   With Annotated[list, operator.add]:
     existing: ["item1", "item2"]
     node returns: ["item3"]
     result: ["item1", "item2", "item3"]  ← APPENDS! (operator.add on lists = concatenate)

   This is how LangGraph chat apps accumulate message history across nodes.
   We pass the accumulated history into each new graph invocation (each conversation turn).
"""

import operator
from typing import Annotated, TypedDict


class MayaState(TypedDict):
    """
    Central state for MAYA's LangGraph.

    Every node in the graph receives this full state object and returns
    a dict containing only the keys it updated.

    Fields ordered by flow: Input → Processing → Output → Memory → Debug
    """

    # ── Input (set fresh each conversation turn) ──────────────────────────────
    user_input: str          # Raw text from user (voice → Whisper → text, Week 2)

    # ── Processing results (filled by nodes as graph runs) ────────────────────
    language: str            # Detected: "english" | "hindi" | "hinglish"
    intent: str              # Detected: "greeting" | "question" | "math" |
                             #           "general"  | "farewell"  ← NEW

    # ── Output (set by the final response node) ────────────────────────────────
    response: str            # MAYA's reply to the user

    # ── Conversation Memory ────────────────────────────────────────────────────
    # Annotated[list[dict], operator.add] = REDUCER
    # When a node returns {"message_history": [new_msg]}, LangGraph
    # APPENDS new_msg to the existing list instead of replacing it.
    # The REPL passes the accumulated history into each new turn.
    message_history: Annotated[list[dict], operator.add]

    # ── Debug / Learning visibility ────────────────────────────────────────────
    steps: list[str]         # Log entry from each node - shows graph execution flow
