"""
MAYA STT Standalone Test
=========================
Run this FIRST to verify your microphone and faster-whisper are working
before using voice mode in the full chat loop.

Usage:
    python test_stt.py

What this does:
  1. Checks microphone is available
  2. Loads the Whisper base model (downloads ~145MB first time)
  3. Records 3 test utterances (5 seconds each)
  4. Shows transcription after each one

Try saying:
  - "Hello MAYA, how are you?" (English)
  - "Namaste MAYA, kya hal hai?" (Hinglish)
  - Something in Hindi
"""

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

console = Console()


def main() -> None:
    console.print(Panel.fit(
        "MAYA - STT Microphone Test\n"
        "[dim]faster-whisper + sounddevice[/dim]",
        border_style="cyan",
    ))

    # ── Step 1: Check mic ──────────────────────────────────────────────────────
    console.print("\n[bold]Step 1:[/bold] Checking microphone...")

    from src.maya.stt.transcriber import STTEngine

    if not STTEngine.is_available():
        console.print(
            "[bold red]No microphone found![/bold red]\n"
            "Please check:\n"
            "  - Mic is plugged in\n"
            "  - Windows mic permissions are enabled\n"
            "  - Default recording device is set in Sound settings"
        )
        return

    mics = STTEngine.list_microphones()
    console.print(f"[green]Found {len(mics)} microphone(s):[/green]")
    for mic in mics:
        console.print(f"  [{mic['index']}] {mic['name']}")

    # ── Step 2: Load model ─────────────────────────────────────────────────────
    console.print("\n[bold]Step 2:[/bold] Loading Whisper base model...")
    console.print("[dim]First run downloads ~145MB. Subsequent runs load from cache.[/dim]")

    stt = STTEngine(model_size="base")

    # ── Step 3: Test recordings ────────────────────────────────────────────────
    console.print("\n[bold]Step 3:[/bold] 3 test recordings (5 seconds each)\n")

    prompts = [
        "Say something in English  (e.g. 'Hello MAYA!')",
        "Say something in Hinglish (e.g. 'Namaste MAYA, kya hal hai?')",
        "Say whatever you want     (Hindi / English / mix)",
    ]

    for i, prompt in enumerate(prompts, 1):
        console.rule(f"[cyan]Test {i}/3[/cyan]")
        console.print(f"[dim]{prompt}[/dim]")
        input("  Press ENTER when ready, then speak...")

        console.print("[bold yellow]Recording...[/bold yellow] (5 seconds)")

        try:
            text = stt.listen(duration=5)
        except RuntimeError as e:
            console.print(f"[red]Error: {e}[/red]")
            continue

        if text:
            console.print(Panel(
                f'"{text}"',
                title="[green]Transcribed[/green]",
                border_style="green",
            ))
        else:
            console.print(
                "[yellow]Nothing detected.[/yellow] "
                "Try speaking louder or closer to the mic."
            )

    # ── Done ───────────────────────────────────────────────────────────────────
    console.rule()
    console.print(
        "\n[bold green]STT test complete![/bold green]\n\n"
        "If transcription looked correct, you're ready for voice mode:\n"
        "  [bold]python chat_loop.py --voice[/bold]\n\n"
        "[dim]Tip: If Hindi/Hinglish was not transcribed well, "
        "try the 'small' model:\n"
        "  Edit transcriber.py → change model_size default to 'small'[/dim]"
    )


if __name__ == "__main__":
    main()
