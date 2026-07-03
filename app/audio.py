"""Audio capture on Windows via WASAPI (PyAudioWPatch).

Supports both regular input devices (microphones) and loopback capture of
output devices — so the app can listen to whatever is playing through your
speakers/headset (Discord, Zoom, etc.) with no virtual audio cable.
"""
from __future__ import annotations

import queue
import threading

import numpy as np

TARGET_RATE = 16000  # what Whisper expects
BLOCK_SECONDS = 0.1


def list_devices() -> list[dict]:
    import pyaudiowpatch as pyaudio

    p = pyaudio.PyAudio()
    devices = []
    try:
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) <= 0:
                continue
            is_loopback = bool(info.get("isLoopbackDevice", False))
            name = info["name"]
            devices.append({
                "index": info["index"],
                "name": name,
                "is_loopback": is_loopback,
                "label": (f"System audio: {name}" if is_loopback else f"Microphone: {name}"),
            })
    finally:
        p.terminate()
    # Loopback (system audio) devices first — most useful for Discord/Zoom.
    devices.sort(key=lambda d: (not d["is_loopback"], d["name"]))
    return devices


class AudioCapture:
    """Captures a device into a queue of 100ms float32 mono blocks @ 16kHz."""

    def __init__(self, device_index: int):
        import pyaudiowpatch as pyaudio

        self._pyaudio = pyaudio
        self.blocks: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
        self._p = pyaudio.PyAudio()
        info = self._p.get_device_info_by_index(device_index)
        self.src_rate = int(info["defaultSampleRate"])
        self.channels = max(1, min(2, int(info["maxInputChannels"])))
        self._frames_per_block = int(self.src_rate * BLOCK_SECONDS)
        self._stream = self._p.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.src_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=self._frames_per_block,
            stream_callback=self._on_audio,
        )
        self._closed = threading.Event()

    def _on_audio(self, in_data, frame_count, time_info, status):
        if self._closed.is_set():
            return (None, self._pyaudio.paComplete)
        samples = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        if self.channels > 1:
            samples = samples.reshape(-1, self.channels).mean(axis=1)
        if self.src_rate != TARGET_RATE:
            out_len = int(round(len(samples) * TARGET_RATE / self.src_rate))
            samples = np.interp(
                np.linspace(0.0, len(samples) - 1, out_len),
                np.arange(len(samples)),
                samples,
            ).astype(np.float32)
        try:
            self.blocks.put_nowait(samples)
        except queue.Full:
            pass  # consumer stalled; drop rather than lag further behind
        return (None, self._pyaudio.paContinue)

    def close(self):
        self._closed.set()
        try:
            self._stream.stop_stream()
            self._stream.close()
        finally:
            self._p.terminate()


class SpeechChunker:
    """Groups 100ms blocks into utterance-sized chunks using energy VAD."""

    def __init__(self, silence_end_s: float = 0.7, max_chunk_s: float = 9.0,
                 min_speech_s: float = 0.4, preroll_blocks: int = 3):
        self.silence_end_blocks = int(silence_end_s / BLOCK_SECONDS)
        self.max_chunk_blocks = int(max_chunk_s / BLOCK_SECONDS)
        self.min_speech_blocks = int(min_speech_s / BLOCK_SECONDS)
        self.preroll_blocks = preroll_blocks
        self._noise_floor = 0.003
        self._preroll: list[np.ndarray] = []
        self._buf: list[np.ndarray] = []
        self._speech_blocks = 0
        self._silence_run = 0
        self._speaking = False

    def push(self, block: np.ndarray) -> np.ndarray | None:
        """Feed one block; returns a finished utterance chunk or None."""
        rms = float(np.sqrt(np.mean(block ** 2)))
        threshold = max(0.006, self._noise_floor * 3.0)

        if not self._speaking:
            self._noise_floor = 0.9 * self._noise_floor + 0.1 * rms
            self._preroll.append(block)
            if len(self._preroll) > self.preroll_blocks:
                self._preroll.pop(0)
            if rms > threshold:
                self._speaking = True
                self._buf = list(self._preroll)
                self._preroll = []
                self._speech_blocks = 1
                self._silence_run = 0
            return None

        self._buf.append(block)
        if rms > threshold:
            self._speech_blocks += 1
            self._silence_run = 0
        else:
            self._silence_run += 1

        done = (self._silence_run >= self.silence_end_blocks
                or len(self._buf) >= self.max_chunk_blocks)
        if not done:
            return None

        chunk = np.concatenate(self._buf) if self._buf else None
        enough_speech = self._speech_blocks >= self.min_speech_blocks
        self._buf = []
        self._speech_blocks = 0
        self._silence_run = 0
        self._speaking = False
        return chunk if enough_speech else None
