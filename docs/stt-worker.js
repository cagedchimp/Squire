// Speech-to-text worker — runs Whisper locally in the browser via
// transformers.js. Model downloads once from the HuggingFace CDN, then is
// cached by the browser. No API keys, no per-use cost.
import { pipeline, env } from 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.3.3';

env.allowLocalModels = false;

let asr = null;
let device = 'wasm';
const queue = [];
let busy = false;

async function load(modelSize) {
  const model = `onnx-community/whisper-${modelSize}`;
  const hasWebGPU = typeof navigator !== 'undefined' && !!navigator.gpu;
  const attempts = hasWebGPU
    ? [{ device: 'webgpu', dtype: 'fp32' }, { device: 'wasm', dtype: 'q8' }]
    : [{ device: 'wasm', dtype: 'q8' }];
  let lastErr = null;
  for (const opts of attempts) {
    try {
      asr = await pipeline('automatic-speech-recognition', model, {
        ...opts,
        progress_callback: (p) => {
          if (p.status === 'progress' && p.total) {
            postMessage({
              type: 'progress', file: p.file,
              pct: Math.round((p.loaded / p.total) * 100),
            });
          }
        },
      });
      device = opts.device;
      return;
    } catch (e) {
      lastErr = e;
      asr = null;
    }
  }
  throw lastErr;
}

async function drain() {
  if (busy) return;
  busy = true;
  while (queue.length) {
    const audio = queue.shift();
    try {
      const out = await asr(audio);
      const text = (out.text || '').trim();
      if (text) postMessage({ type: 'transcript', text });
    } catch (e) {
      postMessage({ type: 'error', message: 'transcribe failed: ' + e.message });
    }
  }
  busy = false;
}

onmessage = async (ev) => {
  const msg = ev.data;
  if (msg.type === 'load') {
    try {
      postMessage({ type: 'status', status: 'loading' });
      await load(msg.model);
      postMessage({ type: 'ready', device });
    } catch (e) {
      postMessage({ type: 'error', message: 'model load failed: ' + e.message });
    }
  } else if (msg.type === 'transcribe') {
    if (!asr) return;
    queue.push(msg.audio);
    if (queue.length > 4) queue.shift(); // transcriber fell behind; drop oldest
    drain();
  }
};
