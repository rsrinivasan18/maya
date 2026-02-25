"""
MAYA Interactive Chat Loop - Session 2
========================================
Run this to have a real multi-turn conversation with MAYA.

Usage:
    python chat_loop.py
    python chat_loop.py --debug      # Show graph execution trace each turn

HOW MULTI-TURN CONVERSATION WORKS:
------------------------------------
Each time you type something, this REPL:
  1. Adds your message to history
  2. Calls maya_graph.invoke() with the full history in state
  3. The graph runs (detect_language → understand_intent → response node)
  4. The response node APPENDS the assistant reply to message_history
     (using Annotated[list, operator.add] reducer in MayaState)
  5. We save the updated history for the next turn
  6. If intent == "farewell" → break the loop

SPECIAL COMMANDS:
  !history    - Show the full conversation so far
  !debug      - Toggle graph execution trace on/off
  !clear      - Clear conversation history and start fresh
  bye / quit / exit / alvida  → Ends the conversation

WHAT'S NEXT (Week 3 upgrade):
  Replace rule-based responses with Ollama LLM call inside help_response node.
  The chat loop stays exactly the same - only the node's internals change.
"""

import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.maya.graph.hello_world_graph import maya_graph
from src.maya.config.settings import settings

console = Console()


# =============================================================================
# DISPLAY HELPERS
# =============================================================================

def print_header() -> None:
    console.print(
        Panel.fit(
            Text.assemble(
                ("MAYA\n", "bold magenta"),
                ("Multi-Agent hYbrid Assistant\n", "magenta"),
                ("Session 2 - Interactive Chat Loop\n", "dim"),
                ("Type 'bye' or 'alvida' to exit  |  '!history' to review  |  '!debug' to toggle trace", "dim"),
            ),
            border_style="magenta",
        )
    )
    console.print(f"[dim]{settings.summary()}[/dim]\n")


def print_maya_response(response: str, intent: str, language: str) -> None:
    console.print(
        Panel(
            response,
            title=f"[bold green]MAYA[/bold green]  [dim]({language} | {intent})[/dim]",
            border_style="green",
            padding=(0, 1),
        )
    )


def print_trace(steps: list[str]) -> None:
    console.print("[dim]  Trace:[/dim]")
    for step in steps:
        console.print(f"[dim]    {step}[/dim]")


def print_history(history: list[dict]) -> None:
    if not history:
        console.print("[dim]No conversation history yet.[/dim]")
        return

    table = Table(title="Conversation History", border_style="blue", show_lines=True)
    table.add_column("Turn", style="dim", justify="center", width=6)
    table.add_column("Role", style="yellow", width=10)
    table.add_column("Message", style="white")

    turn = 1
    for i, msg in enumerate(history):
        role = msg["role"]
        content = msg["content"]
        # Truncate long messages for display
        display = content[:120] + "..." if len(content) > 120 else content
        display = display.replace("\n", " ")
        row_turn = str(turn) if role == "user" else ""
        if role == "user":
            turn += 1
        table.add_row(row_turn, role, display)

    console.print(table)


def print_summary(history: list[dict], turn_count: int) -> None:
    user_turns = [m for m in history if m["role"] == "user"]
    console.print(
        Panel(
            f"[bold]Conversation complete![/bold]\n\n"
            f"Total turns: {turn_count}\n"
            f"Messages exchanged: {len(history)}\n\n"
            f"[dim]Type '!history' before exiting next time to review the full conversation.[/dim]",
            border_style="magenta",
            title="[magenta]Session Summary[/magenta]",
        )
    )


# =============================================================================
# MAIN CHAT LOOP
# =============================================================================

def run_chat(debug: bool = False) -> None:
    """
    The main REPL loop.

    State carried between turns:
      - message_history: list of {"role": "user"|"assistant", "content": str}
      - debug: bool (toggleable with !debug command)
    """
    print_header()

    message_history: list[dict] = []
    turn_count = 0
    show_debug = debug

    while True:
        # ── Get user input ────────────────────────────────────────────────────
        try:
            user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Interrupted. Goodbye![/dim]")
            break

        if not user_input:
            continue

        # ── Handle special REPL commands ──────────────────────────────────────
        if user_input.lower() == "!history":
            print_history(message_history)
            continue

        if user_input.lower() == "!debug":
            show_debug = not show_debug
            status = "ON" if show_debug else "OFF"
            console.print(f"[dim]Graph trace: {status}[/dim]")
            continue

        if user_input.lower() == "!clear":
            message_history = []
            turn_count = 0
            console.print("[dim]History cleared. Fresh start![/dim]")
            continue

        # ── Build state for this turn ─────────────────────────────────────────
        turn_count += 1

        # Add user message to history BEFORE invoking
        # The graph's response node will APPEND the assistant reply via Annotated reducer
        history_with_user = message_history + [
            {"role": "user", "content": user_input}
        ]

        # ── Run the graph ─────────────────────────────────────────────────────
        result = maya_graph.invoke(
            {
                "user_input": user_input,
                "language": "",
                "intent": "",
                "response": "",
                "steps": [],
                "message_history": history_with_user,
                # Annotated[list, operator.add]:
                # If any node returns {"message_history": [new_msg]},
                # LangGraph APPENDS it to history_with_user automatically
            }
        )

        # ── Display ───────────────────────────────────────────────────────────
        if show_debug:
            print_trace(result["steps"])

        print_maya_response(result["response"], result["intent"], result["language"])

        # ── Save history for next turn ────────────────────────────────────────
        # result["message_history"] = history_with_user + [assistant_msg]
        # (the response node appended the assistant message via Annotated reducer)
        message_history = result["message_history"]

        # ── Exit on farewell ──────────────────────────────────────────────────
        if result["intent"] == "farewell":
            print_summary(message_history, turn_count)
            break

    console.print("\n[dim]Chat session ended.[/dim]")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MAYA Interactive Chat Loop")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show graph execution trace for every turn",
    )
    args = parser.parse_args()

    run_chat(debug=args.debug)
