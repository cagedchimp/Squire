"""Local speech-to-text via faster-whisper. No API calls, no ongoing cost."""
from __future__ import annotations

import numpy as np


class Transcriber:
    def __init__(self, model_size: str = "base.en"):
        from faster_whisper import WhisperModel  # heavy import, defer

        self.model_size = model_size
        # int8 on CPU is the best speed/quality tradeoff for real-time use.
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio_16k_mono: np.ndarray) -> str:
        segments, _ = self.model.transcribe(
            audio_16k_mono,
            language="en",
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
