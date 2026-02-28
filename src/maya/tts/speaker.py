"""
MAYA Text-to-Speech Engine
============================
Converts MAYA's text responses to spoken audio using Piper TTS (local, offline).

WHY Piper TTS?
--------------
- Fully offline - no API key, no data sent anywhere
- Neural quality voices (sounds natural, not robotic)
- Fast on CPU - speech starts in ~1 second
- ONNX models - same runtime used by many edge AI projects
- Voice models auto-downloaded from HuggingFace on first use

HOW IT WORKS:
-------------
  text
    ↓
  PiperVoice.synthesize()   → WAV bytes (in memory, no temp files)
    ↓
  numpy float32 array       → parsed from WAV
    ↓
  sounddevice.play()        → played through speakers

VOICE CATALOG:
--------------
  "en_US_female"  - US English, female (Lessac) ← DEFAULT
                    Clear, warm, natural. Good for MAYA's personality.

  "en_US_female2" - US English, female (Amy)
                    Alternative if Lessac doesn't suit.

  "en_GB_female"  - British English, female (Alba)
                    Slightly different accent.

NOTE ON INDIAN ENGLISH / HINDI VOICES:
---------------------------------------
  Piper does not currently have a stable Hindi (hi_IN) or Indian English
  (en_IN) voice in its public catalog. The US English female voice (Lessac)
  works well for MAYA and sounds warm and friendly.

  When Piper adds Hindi voices, update _VOICE_CATALOG with the correct path.
  The rest of the code stays unchanged.

VOICE MODEL FILES:
------------------
  Downloaded automatically from HuggingFace (rhasspy/piper-voices dataset).
  Cached in ~/.cache/huggingface/hub/ - shared, outside the git repo.
  Size: ~50-60MB per voice (medium quality).
"""

import numpy as np


# ─── Voice Catalog ───────────────────────────────────────────────────────────
# Format: "key": (display_name, hf_folder_path, filename_stem)
# HuggingFace path: rhasspy/piper-voices/{hf_folder_path}/{filename_stem}.onnx
# Browse all voices: https://huggingface.co/rhasspy/piper-voices/tree/main

_VOICE_CATALOG: dict[str, tuple[str, str, str]] = {
    "en_US_female": (
        "US English - female (Lessac)",
        "en/en_US/lessac/medium",
        "en_US-lessac-medium",
    ),
    "en_US_female2": (
        "US English - female (Amy)",
        "en/en_US/amy/medium",
        "en_US-amy-medium",
    ),
    "en_GB_female": (
        "British English - female (Alba)",
        "en/en_GB/alba/medium",
        "en_GB-alba-medium",
    ),
}

_DEFAULT_VOICE = "en_US_female"


class TTSEngine:
    """
    Text-to-Speech using Piper TTS neural voice models.

    Usage:
        tts = TTSEngine()                     # loads default US English female
        tts.speak("Namaste! Main MAYA hoon.") # speaks through speakers

    Voice models are auto-downloaded on first use (~55MB each) and
    cached in ~/.cache/huggingface/hub/ for subsequent runs.
    """

    def __init__(self, voice: str = _DEFAULT_VOICE):
        """
        Load Piper voice model.

        Args:
            voice: Key from _VOICE_CATALOG.
                   Default: "en_US_female" (Lessac - clear, warm female voice)
        """
        if voice not in _VOICE_CATALOG:
            raise ValueError(
                f"Unknown voice '{voice}'. "
                f"Available: {list(_VOICE_CATALOG.keys())}"
            )

        from piper.voice import PiperVoice

        display_name, hf_folder, filename_stem = _VOICE_CATALOG[voice]

        print(f"  Loading Piper voice: {display_name}")
        print("  (First run downloads ~55MB voice model to HuggingFace cache)")

        model_path, config_path = self._download_voice(hf_folder, filename_stem)
        self._voice = PiperVoice.load(model_path, config_path=config_path)
        self._voice_name = display_name

        print(f"  TTS ready: {display_name}")

    # ──────────────────────────────────────────────────────────────────────────
    # CORE METHODS
    # ──────────────────────────────────────────────────────────────────────────

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        """
        Convert text to audio samples (does NOT play - just generates).

        Uses piper v1.4+ API: synthesize() returns Iterable[AudioChunk].
        Each AudioChunk has audio_float_array (float32 in [-1,1]) and sample_rate.

        Args:
            text: Text to synthesize. Romanized Hindi works fine.
                  e.g. "Namaste! Main MAYA hoon. Kya seekhna chahte ho?"

        Returns:
            (audio_data, sample_rate)
            audio_data:  float32 numpy array shape (N, 1), values in [-1.0, 1.0]
            sample_rate: Hz (typically 22050 for medium quality models)
        """
        chunks = list(self._voice.synthesize(text))
        if not chunks:
            return np.zeros((0, 1), dtype=np.float32), 22050

        sample_rate = chunks[0].sample_rate
        # Concatenate float arrays from all sentence chunks, reshape to (N, 1)
        audio_float = np.concatenate(
            [c.audio_float_array for c in chunks]
        ).reshape(-1, 1)
        return audio_float, sample_rate

    def speak(self, text: str) -> None:
        """
        Synthesize text and play through the default speakers.
        Blocks until playback is fully complete.

        Args:
            text: Text to speak (English or Romanized Hindi/Hinglish)

        Raises:
            RuntimeError: If audio playback fails
        """
        import sounddevice as sd

        try:
            audio_data, sample_rate = self.synthesize(text)
            # audio_data is (N, 1) float32 - sounddevice plays directly
            sd.play(audio_data, samplerate=sample_rate)
            sd.wait()  # Block until playback complete
        except Exception as e:
            raise RuntimeError(f"TTS playback error: {e}") from e

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _download_voice(hf_folder: str, filename_stem: str) -> tuple[str, str]:
        """
        Download voice model files from HuggingFace if not already cached.

        Uses direct URL download (same approach as piper's own downloader).
        Files cached in ~/.cache/piper-voices/ to avoid HF hub auth issues.
        Returns local file paths to the .onnx and .onnx.json files.
        """
        import shutil
        from pathlib import Path
        from urllib.request import urlopen

        # Cache dir: ~/.cache/piper-voices/<filename_stem>/
        cache_dir = Path.home() / ".cache" / "piper-voices" / filename_stem
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Base URL (no /datasets/ prefix - that causes 401 with newer HF hub)
        _HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

        model_path  = cache_dir / f"{filename_stem}.onnx"
        config_path = cache_dir / f"{filename_stem}.onnx.json"

        for local_path, ext in [(model_path, ".onnx"), (config_path, ".onnx.json")]:
            if local_path.exists() and local_path.stat().st_size > 0:
                continue  # Already cached
            url = f"{_HF_BASE}/{hf_folder}/{filename_stem}{ext}?download=true"
            with urlopen(url) as response, open(local_path, "wb") as out_file:
                shutil.copyfileobj(response, out_file)

        return str(model_path), str(config_path)

    # ──────────────────────────────────────────────────────────────────────────
    # UTILITY
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def list_voices() -> list[str]:
        """Return the list of available voice keys."""
        return [
            f"{key}: {display}"
            for key, (display, _, _) in _VOICE_CATALOG.items()
        ]
