// Captures mono audio frames from the graph and posts them to the main
// thread in ~100ms blocks. The AudioContext runs at 16kHz, so blocks are
// 1600 samples — exactly what Whisper expects.
class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buf = new Float32Array(1600);
    this.fill = 0;
  }
  process(inputs) {
    const ch = inputs[0];
    if (!ch || !ch.length) return true;
    // average channels to mono
    const n = ch[0].length;
    for (let i = 0; i < n; i++) {
      let s = 0;
      for (let c = 0; c < ch.length; c++) s += ch[c][i];
      this.buf[this.fill++] = s / ch.length;
      if (this.fill === this.buf.length) {
        this.port.postMessage(this.buf.slice(0));
        this.fill = 0;
      }
    }
    return true;
  }
}
registerProcessor('capture-processor', CaptureProcessor);
