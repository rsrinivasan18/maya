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

LANGUAGE DETECTION - BILINGUAL STRATEGY:
-----------------------------------------
  Known Whisper bug: Hindi speech is frequently misdetected as Arabic ("ar"),
  Farsi ("fa"), or Urdu ("ur") because their phonetics overlap significantly.

  Fix: Always try Hindi ("hi") first. If Hindi confidence < threshold (0.65),
  retry with English ("en") and return whichever scored higher.

  This means:
  - Pure Hindi  → Hindi pass succeeds (high confidence) → returned
  - Pure English → Hindi pass has low confidence → English retry wins
  - Hinglish    → Hindi pass usually wins (Hindi is the base language)

  language=None in __init__ activates this bilingual mode (recommended).
  language="hi" or "en" forces a single-pass with that language only.

LEARNING NOTE - What is VAD?
------------------------------
Voice Activity Detection = software that detects when someone is actually
speaking vs just silence/background noise.
  vad_filter=True → faster-whisper skips the silent parts automatically.
  Without this, silence gets transcribed as garbage text ("Thank you.", "..." etc.)
"""

import numpy as np

# If Hindi transcription confidence is below this, also try English.
# 0.65 is a good balance - confident Hindi stays Hindi, ambiguous gets retried.
_HINDI_CONFIDENCE_THRESHOLD = 0.65


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

        mode = "bilingual (Hindi→English fallback)" if language is None else f"forced '{language}'"
        print(f"  STT ready. Language mode: {mode}")

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

    def _transcribe_once(self, audio: np.ndarray, language: str | None) -> tuple[str, float]:
        """
        Single transcription pass with a specific language.

        Args:
            audio:    float32 numpy array at 16kHz
            language: "hi", "en", or None for auto-detect

        Returns:
            (text, language_probability)
            language_probability is how confident Whisper was (0.0 - 1.0)
        """
        segments, info = self._model.transcribe(
            audio,
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        # Consume the generator (faster-whisper is lazy)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text, info.language_probability

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Bilingual transcription: Hindi first, English fallback.

        Fixes Whisper's known bug where Hindi is misdetected as Arabic:
          - Always runs Hindi pass first (language="hi")
          - If Hindi confidence < _HINDI_CONFIDENCE_THRESHOLD (0.65):
              → also runs English pass (language="en")
              → returns whichever scored higher confidence

        If self._language is set (forced mode), does a single pass only.

        Args:
            audio: float32 numpy array at 16kHz (from record_audio)

        Returns:
            Transcribed text string. Empty string if nothing detected.
        """
        # Forced language mode - single pass, no fallback
        if self._language is not None:
            text, _ = self._transcribe_once(audio, self._language)
            return text

        # Bilingual mode: Hindi first (avoids Arabic misdetection)
        hi_text, hi_conf = self._transcribe_once(audio, "hi")

        if hi_conf >= _HINDI_CONFIDENCE_THRESHOLD:
            # Confident Hindi (or Hinglish) - return it
            return hi_text

        # Hindi confidence low - also try English
        en_text, en_conf = self._transcribe_once(audio, "en")

        # Return whichever the model is more confident about
        if en_conf > hi_conf:
            return en_text
        return hi_text

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
