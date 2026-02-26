"""
MAYA TTS Standalone Test
=========================
Run this to verify Piper TTS and your speakers are working
before using --speak mode in the full chat loop.

Usage:
    python test_tts.py

What this does:
  1. Loads the default voice (en_US-lessac-medium, ~55MB download first time)
  2. Speaks 3 test phrases: English, Hinglish, and the user prompt
  3. Confirms everything is working before the full voice loop
"""

from rich.console import Console
from rich.panel import Panel

console = Console()


def main() -> None:
    console.print(Panel.fit(
        "MAYA - TTS Speaker Test\n"
        "[dim]Piper TTS + sounddevice[/dim]",
        border_style="cyan",
    ))

    # ── Load TTS engine ────────────────────────────────────────────────────────
    console.print("\n[bold]Step 1:[/bold] Loading Piper TTS voice...")
    console.print("[dim]First run downloads ~55MB voice model. Subsequent runs use cache.[/dim]")

    from src.maya.tts.speaker import TTSEngine

    try:
        tts = TTSEngine(voice="en_US_female")
    except Exception as e:
        console.print(
            f"\n[bold red]Failed to load TTS:[/bold red] {e}\n\n"
            "Possible fixes:\n"
            "  1. pip install piper-tts\n"
            "  2. Check internet connection (needed for first-time model download)\n"
            "  3. Check that speakers are working and not muted"
        )
        return

    console.print(f"\n[bold]Available voices:[/bold]")
    for v in TTSEngine.list_voices():
        console.print(f"  {v}")

    # ── Test phrases ───────────────────────────────────────────────────────────
    console.print("\n[bold]Step 2:[/bold] Speaking 3 test phrases...\n")

    test_phrases = [
        (
            "English",
            "Hello! I am MAYA, your bilingual STEM companion. "
            "What would you like to learn today?"
        ),
        (
            "Hinglish",
            "Namaste! Main MAYA hoon. "
            "Aaj hum science, math, ya kuch aur seekhein?"
        ),
        (
            "User's phrase",
            "Namaste! Main MAYA hoon.",
        ),
    ]

    for label, text in test_phrases:
        console.print(f"[cyan]{label}:[/cyan] {text}")
        try:
            tts.speak(text)
            console.print("[dim]  ✓ Played[/dim]")
        except RuntimeError as e:
            console.print(f"[red]  ✗ Error: {e}[/red]")

        input("  Press ENTER for next phrase...")

    # ── Done ───────────────────────────────────────────────────────────────────
    console.print(
        "\n[bold green]TTS test complete![/bold green]\n\n"
        "If MAYA's voice sounded good, you're ready for full voice mode:\n"
        "  [bold]python chat_loop.py --speak[/bold]          (keyboard + voice output)\n"
        "  [bold]python chat_loop.py --voice --speak[/bold]  (full voice conversation)\n\n"
        "[dim]To try a different voice, edit TTSEngine(voice=...) in this file.\n"
        "Available: en_US_female, en_US_female2, en_GB_female[/dim]"
    )


if __name__ == "__main__":
    main()
