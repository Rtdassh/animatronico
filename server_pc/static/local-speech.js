/* SpeechRecognition compatible con el modo manos libres; audio solo al PC local. */
class LocalSpeechRecognition {
  constructor() {
    this.continuous = true;
    this.running = false;
    this.generation = 0;
    this.busy = false;
  }

  async start() {
    if (this.running) return;
    const generation = ++this.generation;
    this.running = true;
    try {
      if (!window.isSecureContext || !navigator.mediaDevices) {
        throw new Error('Abre la web HTTPS y confía en el certificado del asistente.');
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: {
        channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true
      }});
      if (!this.running || generation !== this.generation) {
        stream.getTracks().forEach(track => track.stop()); return;
      }
      this.stream = stream;
      this.context = new (window.AudioContext || window.webkitAudioContext)();
      await this.context.resume();
      this.source = this.context.createMediaStreamSource(stream);
      this.processor = this.context.createScriptProcessor(4096, 1, 1);
      this.source.connect(this.processor);
      this.processor.connect(this.context.destination);
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
        const voice = Math.sqrt(sum / input.length) > 0.012;
        const now = performance.now();
        if (voice) {
          if (!this.speaking) {
            this.samples = this.preRoll.slice();
            this.startedVoice = now;
          }
          this.speaking = true;
          this.lastVoice = now;
        }
        if (this.speaking) this.samples.push(input);
        else { this.preRoll.push(input); if (this.preRoll.length > 3) this.preRoll.shift(); }
        if (this.speaking && (now - this.lastVoice > 650 || now - this.startedVoice > 8000)) {
          this.submit(generation);
        }
      };
    } catch (error) {
      if (generation !== this.generation) return;
      this.onerror?.({error: 'not-allowed', message: error.message});
      this.stop();
    }
  }

  async submit(generation) {
    this.busy = true;
    this.speaking = false;
    const length = this.samples.reduce((sum, sample) => sum + sample.length, 0);
    const merged = new Float32Array(length);
    let offset = 0;
    for (const sample of this.samples) { merged.set(sample, offset); offset += sample.length; }
    this.samples = [];
    this.preRoll = [];
    try {
      const form = new FormData();
      form.append('audio', exportWAV(merged, this.context.sampleRate), 'frase.wav');
      const response = await fetch('/api/transcribe', {method: 'POST', body: form});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Error de reconocimiento local');
      if (this.running && generation === this.generation && data.text) {
        const result = [{transcript: data.text, confidence: 1}];
        result.isFinal = true;
        this.onresult?.({resultIndex: 0, results: [result]});
      }
    } catch (error) {
      if (this.running && generation === this.generation) this.onerror?.({error: 'network', message: error.message});
    } finally { this.busy = false; }
  }

  stop() {
    if (!this.running) return;
    this.running = false;
    ++this.generation;
    this.processor?.disconnect();
    this.source?.disconnect();
    this.stream?.getTracks().forEach(track => track.stop());
    this.context?.close().catch(() => {});
    this.onend?.();
  }
  abort() { this.stop(); }
}
window.LocalSpeechRecognition = LocalSpeechRecognition;
