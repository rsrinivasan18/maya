"""
MAYA Hello World - Entry Point
================================
Run this script to see MAYA's first LangGraph agent in action.

Usage:
    # 1. Activate your virtual environment first:
    #    Windows: .venv\\Scripts\\activate
    #    Mac/Linux: source .venv/bin/activate

    # 2. Install dependencies (first time only):
    #    pip install -r requirements.txt

    # 3. Run:
    python run_hello_world.py

What you will see:
    - MAYA processing several test inputs
    - The graph execution trace (which nodes ran, in order)
    - MAYA's response for each input
    - A summary table of all test results

This is Week 1 - no LLMs, no voice, no APIs needed.
Just pure LangGraph graph structure in action.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.maya.graph.hello_world_graph import maya_graph
from src.maya.models.state import MayaState
from src.maya.config.settings import settings

console = Console()


def run_single_conversation(user_input: str) -> dict:
    """
    Run one conversation through MAYA's graph.

    Args:
        user_input: What the user said (text)

    Returns:
        The final state dict after the graph completes
    """

    # Build the initial state - ALL fields must be provided for TypedDict
    initial_state: MayaState = {
        "user_input": user_input,
        "language": "",      # Will be filled by detect_language node
        "intent": "",        # Will be filled by understand_intent node
        "response": "",      # Will be filled by greet_response or help_response node
        "steps": [],         # Each node appends to this - shows graph execution
    }

    # invoke() runs the graph synchronously from START to END
    # It returns the final state after all nodes have run
    result = maya_graph.invoke(initial_state)
    return result


def display_conversation(user_input: str, result: dict) -> None:
    """Display one conversation exchange in the terminal."""

    console.print(f"\n[bold cyan]You:[/bold cyan] {user_input}")

    # Show the execution trace so you can see the graph in action
    console.print("[dim]  Graph trace:[/dim]")
    for step in result["steps"]:
        console.print(f"[dim]    {step}[/dim]")

    # Show MAYA's response in a panel
    console.print(
        Panel(
            result["response"],
            title=f"[bold green]MAYA[/bold green]  "
                  f"[dim](lang: {result['language']} | intent: {result['intent']})[/dim]",
            border_style="green",
            padding=(0, 1),
        )
    )


def run_demo() -> None:
    """Run MAYA through a set of test conversations."""

    # Header
    console.print(
        Panel.fit(
            Text.assemble(
                ("MAYA\n", "bold magenta"),
                ("Multi-Agent hYbrid Assistant\n", "magenta"),
                ("Week 1 - Hello World LangGraph Agent", "dim"),
            ),
            border_style="magenta",
        )
    )

    console.print(f"\n[dim]{settings.summary()}[/dim]")
    console.rule("[dim]Test Conversations[/dim]")

    # Test inputs covering all language + intent combinations
    test_inputs = [
        "Hello MAYA!",                              # English greeting
        "Namaste! Kya hal hai?",                    # Hindi greeting
        "Hi! Main tumse milke bahut khush hun!",    # Hinglish greeting
        "What is photosynthesis?",                  # English question
        "Gravity kya hoti hai?",                    # Hindi question
        "How does the sun work?",                   # English question
        "Calculate 25 multiplied by 4",             # Math
        "5 + 3 kya hoga?",                          # Hindi math
        "Tell me something cool",                   # General
    ]

    results_summary = []

    for user_input in test_inputs:
        result = run_single_conversation(user_input)
        display_conversation(user_input, result)
        results_summary.append({
            "input": user_input,
            "language": result["language"],
            "intent": result["intent"],
        })
        console.rule(style="dim")

    # Summary table
    console.print("\n")
    table = Table(title="Test Results Summary", border_style="blue")
    table.add_column("Input", style="cyan", max_width=40)
    table.add_column("Language", style="yellow", justify="center")
    table.add_column("Intent", style="green", justify="center")

    for r in results_summary:
        table.add_row(r["input"], r["language"], r["intent"])

    console.print(table)

    console.print(
        Panel(
            "[bold green]All conversations processed successfully![/bold green]\n\n"
            "[dim]Next steps:\n"
            "  1. Read through src/maya/graph/hello_world_graph.py\n"
            "  2. Run the tests: pytest tests/\n"
            "  3. Modify a node and see how state changes\n"
            "  4. Push to GitHub when you understand the code[/dim]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    run_demo()
