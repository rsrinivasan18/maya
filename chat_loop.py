"""
MAYA Interactive Chat Loop - Session 3 Update
==============================================
Run this to have a real multi-turn conversation with MAYA.

Usage:
    python chat_loop.py                          # Keyboard input
    python chat_loop.py --voice                  # Microphone input (Srinika speaks!)
    python chat_loop.py --voice --record-time 7  # Longer recording window
    python chat_loop.py --debug                  # Show graph trace each turn
    python chat_loop.py --voice --debug          # Both

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

SPECIAL COMMANDS (keyboard mode only):
  !history    - Show the full conversation so far
  !debug      - Toggle graph execution trace on/off
  !clear      - Clear conversation history and start fresh
  bye / quit / exit / alvida  → Ends the conversation

VOICE MODE NOTES:
  - Srinika speaks for the duration set by --record-time (default 5 seconds)
  - The transcribed text is shown so she can see what MAYA heard
  - If nothing is heard, she gets another chance automatically
  - Hindi, English, and Hinglish all work (Whisper auto-detects)

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

def print_header(voice_mode: bool = False) -> None:
    mode_line = "Voice mode ON  |  Speak when prompted" if voice_mode else \
                "Type 'bye' or 'alvida' to exit  |  '!history' to review  |  '!debug' to toggle trace"
    console.print(
        Panel.fit(
            Text.assemble(
                ("MAYA\n", "bold magenta"),
                ("Multi-Agent hYbrid Assistant\n", "magenta"),
                ("Session 3 - Voice + Chat Loop\n", "dim"),
                (mode_line, "dim"),
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

def run_chat(debug: bool = False, voice: bool = False, record_time: int = 5) -> None:
    """
    The main REPL loop.

    Args:
        debug:       Show graph execution trace each turn
        voice:       Use microphone instead of keyboard
        record_time: Recording duration in seconds (voice mode only)

    State carried between turns:
      - message_history: list of {"role": "user"|"assistant", "content": str}
      - debug: bool (toggleable with !debug command in keyboard mode)
    """
    print_header(voice_mode=voice)

    # ── Set up STT if voice mode ───────────────────────────────────────────────
    stt = None
    if voice:
        from src.maya.stt.transcriber import STTEngine

        if not STTEngine.is_available():
            console.print(
                "[bold red]No microphone detected![/bold red]\n"
                "Check your mic is plugged in, then try again.\n"
                "Running in keyboard mode instead."
            )
            voice = False
        else:
            stt = STTEngine(model_size="base")
            console.print(
                f"[green]Microphone ready.[/green] "
                f"[dim]Recording {record_time}s per turn. "
                f"Say 'alvida' or 'bye' to exit.[/dim]\n"
            )

    message_history: list[dict] = []
    turn_count = 0
    show_debug = debug

    while True:
        # ── Get user input: voice OR keyboard ─────────────────────────────────
        if voice and stt:
            try:
                console.print(
                    f"[bold yellow]Srinika, speak now "
                    f"({record_time} seconds)...[/bold yellow]"
                )
                user_input = stt.listen(duration=record_time)

                if not user_input:
                    console.print("[dim]Nothing heard. Please try again.[/dim]")
                    continue

                # Show what was heard so Srinika can confirm
                console.print(f"[bold cyan]You (heard):[/bold cyan] {user_input}")

            except RuntimeError as e:
                console.print(f"[red]Mic error: {e}[/red]")
                continue
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Interrupted. Goodbye![/dim]")
                break
        else:
            # Keyboard mode
            try:
                user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Interrupted. Goodbye![/dim]")
                break

            if not user_input:
                continue

            # Special commands only available in keyboard mode
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
    parser.add_argument(
        "--voice",
        action="store_true",
        help="Use microphone input instead of keyboard (Srinika speaks!)",
    )
    parser.add_argument(
        "--record-time",
        type=int,
        default=5,
        dest="record_time",
        help="Recording duration in seconds for voice mode (default: 5)",
    )
    args = parser.parse_args()

    run_chat(debug=args.debug, voice=args.voice, record_time=args.record_time)
