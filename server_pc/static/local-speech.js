/* SpeechRecognition compatible con el modo manos libres; el audio va al PC, que elige el motor (Whisper, Google o Vosk). */

let _sharedLocalStream = null;
let _sharedLocalContext = null;

function localExportWAV(samples, sampleRate) {
  if (typeof window.exportWAV === 'function') {
    return window.exportWAV(samples, sampleRate);
  }
  const targetRate = 16000;
  let downsampledSamples = samples;
  if (sampleRate !== targetRate) {
    const ratio = sampleRate / targetRate;
    const newLength = Math.round(samples.length / ratio);
    downsampledSamples = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {
      const start = Math.floor(i * ratio);
      const end = Math.min(samples.length, Math.floor((i + 1) * ratio));
      let acc = 0;
      for (let j = start; j < end; j++) acc += samples[j];
      downsampledSamples[i] = end > start ? acc / (end - start) : (samples[start] || 0);
    }
  }

  const numChannels = 1;
  const bytesPerSample = 2; // 16-bit
  const blockAlign = numChannels * bytesPerSample;
  const byteRate = targetRate * blockAlign;
  const dataLength = downsampledSamples.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataLength);
  const view = new DataView(buffer);

  function writeString(offset, string) {
    for (let i = 0; i < string.length; i++) view.setUint8(offset + i, string.charCodeAt(i));
  }

  writeString(0, 'RIFF');
  view.setUint32(4, 36 + dataLength, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, numChannels, true);
  view.setUint32(24, targetRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true);
  writeString(36, 'data');
  view.setUint32(40, dataLength, true);

  let offset = 44;
  for (let i = 0; i < downsampledSamples.length; i++, offset += 2) {
    let s = Math.max(-1, Math.min(1, downsampledSamples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }

  return new Blob([view], { type: 'audio/wav' });
}

class LocalSpeechRecognition {
  constructor() {
    this.continuous = true;
    this.running = false;
    this.generation = 0;
    this.busy = false;
  }

  static releaseMic() {
    if (_sharedLocalStream) {
      try {
        _sharedLocalStream.getTracks().forEach(track => track.stop());
      } catch (_) { }
      _sharedLocalStream = null;
    }
    if (_sharedLocalContext) {
      try {
        _sharedLocalContext.close().catch(() => {});
      } catch (_) { }
      _sharedLocalContext = null;
    }
  }

  async start() {
    if (this.running) return;
    const generation = ++this.generation;
    this.running = true;
    try {
      if (!window.isSecureContext || !navigator.mediaDevices) {
        throw new Error('Abre la web HTTPS y confía en el certificado del asistente.');
      }

      // Reutilizar stream de micrófono existente si sigue activo (evita diálogo de permisos repetido en móviles/iOS)
      let stream = _sharedLocalStream;
      const isStreamActive = stream && stream.active && stream.getAudioTracks().some(t => t.readyState === 'live');
      if (!isStreamActive) {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
          }
        });
        _sharedLocalStream = stream;
      }

      if (!this.running || generation !== this.generation) {
        return;
      }

      this.stream = stream;

      // Reutilizar o crear AudioContext
      if (!_sharedLocalContext || _sharedLocalContext.state === 'closed') {
        _sharedLocalContext = new (window.AudioContext || window.webkitAudioContext)();
      }
      this.context = _sharedLocalContext;
      if (this.context.state === 'suspended') {
        await this.context.resume();
      }

      this.source = this.context.createMediaStreamSource(stream);
      this.processor = this.context.createScriptProcessor(4096, 1, 1);

      // Conectar a través de nodo con ganancia 0 para alimentar el procesador sin reproducir la voz en los altavoces
      const muteGain = this.context.createGain();
      muteGain.gain.value = 0;
      this.source.connect(this.processor);
      this.processor.connect(muteGain);
      muteGain.connect(this.context.destination);

      this.samples = [];
      this.preRoll = [];
      this.speaking = false;
      this.lastVoice = 0;
      this.startedVoice = 0;

      this.processor.onaudioprocess = event => {
        if (!this.running || this.busy) return;
        const input = new Float32Array(event.inputBuffer.getChannelData(0));
        let sum = 0;
        for (const value of input) sum += value * value;
        const voice = Math.sqrt(sum / input.length) > 0.010;
        const now = performance.now();
        if (voice) {
          if (!this.speaking) {
            this.samples = this.preRoll.slice();
            this.startedVoice = now;
          }
          this.speaking = true;
          this.lastVoice = now;
        }
        if (this.speaking) {
          this.samples.push(input);
        } else {
          this.preRoll.push(input);
          if (this.preRoll.length > 3) this.preRoll.shift();
        }

        if (this.speaking && (now - this.lastVoice > 650 || now - this.startedVoice > 8000)) {
          // Descartar solo ruidos minúsculos (< 120ms), pero conservar palabras cortas como "ve", "v", "oye"
          if (this.lastVoice - this.startedVoice < 120) {
            this.speaking = false;
            this.samples = [];
          } else {
            this.submit(generation);
          }
        }
      };
    } catch (error) {
      if (generation !== this.generation) return;
      this.onerror?.({ error: 'not-allowed', message: error.message });
      this.stop();
    }
  }

  async submit(generation) {
    this.busy = true;
    this.speaking = false;
    const length = this.samples.reduce((sum, sample) => sum + sample.length, 0);
    const merged = new Float32Array(length);
    let offset = 0;
    for (const sample of this.samples) {
      merged.set(sample, offset);
      offset += sample.length;
    }
    this.samples = [];
    this.preRoll = [];

    try {
      const form = new FormData();
      form.append('audio', localExportWAV(merged, this.context.sampleRate), 'frase.wav');
      const response = await fetch('/api/transcribe', { method: 'POST', body: form });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Error de reconocimiento de voz');
      if (this.running && generation === this.generation && data.text) {
        const result = [{ transcript: data.text, confidence: 1 }];
        result.isFinal = true;
        this.onresult?.({ resultIndex: 0, results: [result] });
      }
    } catch (error) {
      if (this.running && generation === this.generation) {
        this.onerror?.({ error: 'network', message: error.message });
      }
    } finally {
      this.busy = false;
    }
  }

  stop() {
    if (!this.running) return;
    this.running = false;
    ++this.generation;
    try {
      this.processor?.disconnect();
      this.source?.disconnect();
    } catch (_) { }
    this.onend?.();
  }

  abort() {
    this.stop();
  }
}

window.LocalSpeechRecognition = LocalSpeechRecognition;
