"""
MAYA Speech-to-Text Engine
============================
Converts spoken audio to text using faster-whisper (local, offline).

WHY faster-whisper instead of openai-whisper?
----------------------------------------------
- 4x faster on CPU (uses CTranslate2 with int8 quantization)
- Same accuracy as original Whisper
- Works fully offline - no API key, no data sent anywhere
- Built-in VAD (Voice Activity Detection) - filters out silence automatically
- Same model weights, just a faster runtime

MODELS (downloaded automatically on first use from HuggingFace):
-----------------------------------------------------------------
  "tiny"   ~75MB   - Very fast, lower accuracy
  "base"   ~145MB  - Good balance  ← recommended for Srinika
  "small"  ~465MB  - Better Hindi accuracy, slower
  "medium" ~1.5GB  - Best accuracy, needs 4GB+ RAM

LANGUAGE DETECTION:
-------------------
  language=None → Whisper auto-detects the language each turn
  This handles Hinglish naturally - Srinika can switch mid-conversation.

LEARNING NOTE - What is VAD?
------------------------------
Voice Activity Detection = software that detects when someone is actually
speaking vs just silence/background noise.
  vad_filter=True → faster-whisper skips the silent parts automatically.
  Without this, silence gets transcribed as garbage text ("Thank you.", "..." etc.)
"""

import numpy as np


class STTEngine:
    """
    Records audio from microphone and transcribes it to text.

    Usage:
        stt = STTEngine()                    # loads base model
        text = stt.listen(duration=5)        # record 5s + transcribe
        print(text)                          # "Namaste MAYA!"

    The model is loaded once at init time. After that, each listen() call
    is fast (recording time + ~1-2 seconds for transcription on CPU).
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str | None = None,
    ):
        """
        Load the Whisper model. Downloads on first run (~145MB for base).

        Args:
            model_size:   "tiny" | "base" | "small" | "medium"
            device:       "cpu" (laptop) | "cuda" (GPU, if available)
            compute_type: "int8" for CPU (fastest), "float16" for GPU
            language:     None = auto-detect per turn (best for Hinglish)
                          "hi" = force Hindi, "en" = force English
        """
        from faster_whisper import WhisperModel

        print(f"  Loading Whisper '{model_size}' model on {device}...")
        print("  (First run downloads ~145MB - subsequent runs load from cache)")

        self._model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )
        self._language = language
        self._sample_rate = 16000   # Whisper requires exactly 16kHz input

        print(f"  STT ready. Auto-detect language: {language is None}")

    # ──────────────────────────────────────────────────────────────────────────
    # CORE METHODS
    # ──────────────────────────────────────────────────────────────────────────

    def record_audio(self, duration: int = 5) -> np.ndarray:
        """
        Record audio from the default microphone.

        Uses sounddevice which bundles PortAudio - no extra install needed on Windows.
        Blocks until recording is complete (synchronous).

        Args:
            duration: How many seconds to record

        Returns:
            1D float32 numpy array at 16kHz sample rate
            Shape: (duration * 16000,)
        """
        import sounddevice as sd

        audio = sd.rec(
            frames=int(duration * self._sample_rate),
            samplerate=self._sample_rate,
            channels=1,           # Mono - whisper doesn't need stereo
            dtype="float32",
        )
        sd.wait()                 # Block here until recording finishes

        return audio.flatten()    # (N, 1) → (N,) - whisper expects 1D

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe a numpy audio array to text.

        Args:
            audio: float32 numpy array at 16kHz (from record_audio)

        Returns:
            Transcribed text. Empty string if nothing was detected.
        """
        segments, info = self._model.transcribe(
            audio,
            language=self._language,        # None = auto-detect each call
            beam_size=5,                    # Higher = more accurate, slower
            vad_filter=True,                # Skip silence automatically
            vad_parameters={
                "min_silence_duration_ms": 500,   # 0.5s silence = end of speech
            },
        )

        # segments is a generator - iterate to collect all text
        # (faster-whisper returns segments lazily for memory efficiency)
        text_parts = [segment.text.strip() for segment in segments]
        return " ".join(text_parts).strip()

    def listen(self, duration: int = 5) -> str:
        """
        Record from microphone and return transcribed text.
        This is the main method called by chat_loop.py.

        Args:
            duration: Recording duration in seconds

        Returns:
            Transcribed text string. Empty string if nothing detected.

        Raises:
            RuntimeError: If microphone is not accessible
        """
        try:
            audio = self.record_audio(duration)
            return self.transcribe(audio)
        except Exception as e:
            raise RuntimeError(f"STT error: {e}") from e

    # ──────────────────────────────────────────────────────────────────────────
    # UTILITY
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def is_available() -> bool:
        """
        Check if a microphone is accessible.
        Safe to call before creating STTEngine - no model loaded.

        Returns:
            True if a working input device is found, False otherwise.
        """
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            # Check if any input device exists
            input_devices = [d for d in devices if d["max_input_channels"] > 0]
            return len(input_devices) > 0
        except Exception:
            return False

    @staticmethod
    def list_microphones() -> list[dict]:
        """
        List all available microphone devices.
        Useful for debugging if wrong mic is selected.

        Returns:
            List of device dicts with 'name' and 'index' keys.
        """
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            return [
                {"index": i, "name": d["name"]}
                for i, d in enumerate(devices)
                if d["max_input_channels"] > 0
            ]
        except Exception:
            return []
