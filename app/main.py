"""TTRPG Ruleset Lookup — local server.

Pipeline: audio device -> local Whisper transcription -> fuzzy rule match ->
WebSocket push to the browser UI. Everything runs on this machine.
"""
from __future__ import annotations

import asyncio
import queue
import threading
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .matcher import RuleMatcher
from .rulesets import load_all

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="TTRPG Ruleset Lookup")


class Engine:
    def __init__(self):
        self.all_entries, self.ruleset_summaries = load_all()
        self.active_rulesets = {s["name"] for s in self.ruleset_summaries}
        self._rebuild_matcher()
        self.status = "idle"
        self.detail = ""
        self.loop: asyncio.AbstractEventLoop | None = None
        self.clients: set[WebSocket] = set()
        self.transcriber = None
        self.model_size = None
        self.capture = None
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None

    def _rebuild_matcher(self):
        entries = [e for e in self.all_entries if e.ruleset in self.active_rulesets]
        self.matcher = RuleMatcher(entries)
        self.entry_count = len(entries)

    def set_active_rulesets(self, names: list[str]):
        valid = {s["name"] for s in self.ruleset_summaries}
        self.active_rulesets = set(names) & valid
        self._rebuild_matcher()

    # ---- websocket plumbing ----
    async def broadcast(self, msg: dict):
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def broadcast_threadsafe(self, msg: dict):
        if self.loop is not None:
            asyncio.run_coroutine_threadsafe(self.broadcast(msg), self.loop)

    def set_status(self, status: str, detail: str = ""):
        self.status = status
        self.detail = detail
        self.broadcast_threadsafe({"type": "status", "status": status, "detail": detail})

    # ---- listening lifecycle ----
    def start(self, device_index: int, model_size: str) -> tuple[bool, str]:
        if self._worker and self._worker.is_alive():
            return False, "Already listening. Stop first."
        self._stop.clear()
        self._worker = threading.Thread(
            target=self._run, args=(device_index, model_size), daemon=True
        )
        self._worker.start()
        return True, "starting"

    def stop(self):
        self._stop.set()
        if self.capture is not None:
            try:
                self.capture.close()
            except Exception:
                pass
            self.capture = None

    def _run(self, device_index: int, model_size: str):
        from .audio import AudioCapture, SpeechChunker

        try:
            if self.transcriber is None or self.model_size != model_size:
                self.set_status("loading", f"Loading Whisper model '{model_size}' "
                                           "(first run downloads it — one time only)…")
                from .transcriber import Transcriber
                self.transcriber = Transcriber(model_size)
                self.model_size = model_size

            self.set_status("loading", "Opening audio device…")
            self.capture = AudioCapture(device_index)
            chunker = SpeechChunker()
            self.set_status("listening")

            while not self._stop.is_set():
                try:
                    block = self.capture.blocks.get(timeout=0.25)
                except queue.Empty:
                    continue
                chunk = chunker.push(block)
                if chunk is None:
                    continue
                text = self.transcriber.transcribe(chunk)
                if not text:
                    continue
                self.broadcast_threadsafe({"type": "transcript", "text": text})
                self._match_and_send(text)
        except Exception as e:
            self.broadcast_threadsafe({"type": "error", "message": str(e)})
        finally:
            if self.capture is not None:
                try:
                    self.capture.close()
                except Exception:
                    pass
                self.capture = None
            self.set_status("idle")

    def _match_and_send(self, text: str):
        for entry in self.matcher.match(text):
            self.broadcast_threadsafe({"type": "card", "card": entry.to_card()})


engine = Engine()


@app.on_event("startup")
async def _startup():
    engine.loop = asyncio.get_running_loop()


class StartRequest(BaseModel):
    device_index: int
    model: str = "base.en"


class SimulateRequest(BaseModel):
    text: str


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/devices")
async def devices():
    try:
        from .audio import list_devices
        return {"devices": list_devices()}
    except Exception as e:
        return JSONResponse({"devices": [], "error": str(e)}, status_code=500)


@app.get("/api/status")
async def status():
    return {
        "status": engine.status,
        "detail": engine.detail,
        "entries": engine.entry_count,
        "rulesets": [{**s, "active": s["name"] in engine.active_rulesets}
                     for s in engine.ruleset_summaries],
        "model": engine.model_size,
    }


class RulesetsRequest(BaseModel):
    active: list[str]


@app.post("/api/rulesets")
async def set_rulesets(req: RulesetsRequest):
    engine.set_active_rulesets(req.active)
    return {"ok": True, "active": sorted(engine.active_rulesets),
            "entries": engine.entry_count}


@app.post("/api/start")
async def start(req: StartRequest):
    ok, msg = engine.start(req.device_index, req.model)
    return {"ok": ok, "message": msg}


@app.post("/api/stop")
async def stop():
    engine.stop()
    return {"ok": True}


@app.post("/api/simulate")
async def simulate(req: SimulateRequest):
    """Test the matcher without audio: pretend this text was heard."""
    await engine.broadcast({"type": "transcript", "text": req.text, "simulated": True})
    cards = [e.to_card() for e in engine.matcher.match(req.text)]
    for card in cards:
        await engine.broadcast({"type": "card", "card": card})
    return {"ok": True, "matches": [c["name"] for c in cards]}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    engine.clients.add(ws)
    await ws.send_json({
        "type": "status", "status": engine.status, "detail": engine.detail,
    })
    try:
        while True:
            await ws.receive_text()  # keepalive; client doesn't send commands
    except WebSocketDisconnect:
        pass
    finally:
        engine.clients.discard(ws)
