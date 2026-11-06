/**
 * ============================================================================
 * CÍCLOPE AI · CONTROLADOR DE INTERFAZ MÓVIL (MICRÓFONO & ALTAVOZ)
 * ============================================================================
 * Implementa:
 *   1. Captura de audio WAV 16kHz PCM directa vía Web Audio API (compatible con iOS/Android).
 *   2. Envío a FastAPI (/api/process-audio) con transcripción STT y Ollama Qwen 2.5 local.
 *   3. Síntesis de voz Loquendo (Jorge, Carlos, Carmen) con caché en disco.
 *   4. Desbloqueo de sesión de audio para navegadores móviles (iOS Safari).
 *   5. Analizador espectral Web Audio para modulación labial (Lip-Sync) y visualizador de onda.
 *   6. Enlace WebSocket bidireccional de baja latencia con el ESP32 y Arduino Uno.
 * ============================================================================
 */

// Elementos del DOM
const esp32Dot = document.getElementById('esp32Dot');
const esp32StatusText = document.getElementById('esp32StatusText');
const tempValue = document.getElementById('tempValue');
const humValue = document.getElementById('humValue');
const btnToggleLight = document.getElementById('btnToggleLight');
const lightText = document.getElementById('lightText');

const modelStatusPill = document.getElementById('modelStatusPill');
const ollamaDot = document.getElementById('ollamaDot');
const modelStatusText = document.getElementById('modelStatusText');
const voiceSelect = document.getElementById('voiceSelect');

const statusCaption = document.getElementById('statusCaption');
const subCaption = document.getElementById('subCaption');
const btnMic = document.getElementById('btnMic');
const inputQuery = document.getElementById('inputQuery');
const btnSendText = document.getElementById('btnSendText');
const replayAudioContainer = document.getElementById('replayAudioContainer');
const btnReplayAudio = document.getElementById('btnReplayAudio');

const eyeball = document.getElementById('eyeball');
const pupil = document.getElementById('pupil');
const eyesSocket = document.querySelector('.eyes-socket');
const jawLower = document.getElementById('jawLower');
const audioPlayer = document.getElementById('audioPlayer');

// Visualizador de onda
const waveformCanvas = document.getElementById('waveformCanvas');
const waveformCtx = waveformCanvas ? waveformCanvas.getContext('2d') : null;

// Panel Manual
const btnToggleManual = document.getElementById('btnToggleManual');
const btnCloseManual = document.getElementById('btnCloseManual');
const manualPanel = document.getElementById('manualPanel');
const sliderMouth = document.getElementById('sliderMouth');
const sliderEyes = document.getElementById('sliderEyes');
const valMouth = document.getElementById('valMouth');
const valEyes = document.getElementById('valEyes');
const btnTriggerBlink = document.getElementById('btnTriggerBlink');
const btnCenterAll = document.getElementById('btnCenterAll');

// Variables de Estado
let ws = null;
let isRecording = false;
let audioContext = null;
let micMediaStream = null;
let micInputNode = null;
let micProcessorNode = null;
let micAnalyserNode = null;
let recordedSamples = [];
let conversationHistory = [];
let waveformAnimId = null;
let audioUnlocked = false;
let currentWebAudioSource = null;
let isAudioContextReady = false;
let playbackAnalyser = null;
let playbackSource = null;
let lightState = 0;
let lastAudioUrl = null;
let lastAudioBase64 = null;

// ============================================================================
// 1. DESBLOQUEO DE SESIÓN DE AUDIO PARA MÓVILES (iOS SAFARI)
// ============================================================================
function unlockAudioSession() {
  if (!audioContext) {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (AudioCtx) audioContext = new AudioCtx();
  }
  if (audioContext && audioContext.state === 'suspended') {
    audioContext.resume();
  }

  if (!audioUnlocked && audioPlayer) {
    // Reproducir microbuffer silencioso de 0.05s para desbloquear audio en Safari
    audioPlayer.src = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA';
    audioPlayer.play().then(() => {
      audioPlayer.pause();
      audioUnlocked = true;
      console.log('[Audio] Sesión móvil desbloqueada.');
    }).catch(() => {});
  }
}

document.addEventListener('touchstart', unlockAudioSession, { passive: true });
document.addEventListener('touchend', unlockAudioSession, { passive: true });
document.addEventListener('click', unlockAudioSession, { passive: true });

// ============================================================================
// 2. VERIFICACIÓN DE ESTADO DEL SERVIDOR Y OLLAMA
// ============================================================================
async function checkBackendStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) throw new Error('Status no disponible');
    const data = await res.json();

    if (data.ollama_ready) {
      ollamaDot.classList.add('ready');
      modelStatusText.textContent = `🟢 Ollama listo (${data.model})`;
    } else {
      ollamaDot.classList.remove('ready');
      modelStatusText.textContent = `🟡 Ollama esperando (${data.model})`;
    }

    if (data.temperature !== undefined) updateTelemetry(data.temperature, data.humidity);
    if (data.light_state !== undefined) updateLightState(data.light_state);
    if (data.esp32_connected !== undefined) updateESP32Status(data.esp32_connected);

  } catch (err) {
    ollamaDot.classList.remove('ready');
    modelStatusText.textContent = `🔴 Servidor desconectado`;
    console.warn('[Backend]', err);
  }
}

// ============================================================================
// 3. GESTIÓN DEL ENLACE WEBSOCKET CON LA PC Y ESP32
// ============================================================================
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/mobile`;

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('[WS] Conectado al servidor de la PC');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'init_state') {
          updateTelemetry(data.temperature, data.humidity);
          updateLightState(data.light_state);
          updateESP32Status(data.esp32_connected);
        } else if (data.type === 'telemetry') {
          updateTelemetry(data.temperature, data.humidity);
          if (data.light_state !== undefined) updateLightState(data.light_state);
        } else if (data.type === 'esp32_status') {
          updateESP32Status(data.connected);
        }
      } catch (e) {
        console.error('[WS Error]', e);
      }
    };

    ws.onclose = () => {
      updateESP32Status(false);
      setTimeout(initWebSocket, 2000);
    };
  } catch (e) {
    setTimeout(initWebSocket, 2000);
  }
}

function updateTelemetry(temp, hum) {
  if (temp !== undefined && tempValue) tempValue.textContent = `${Number(temp).toFixed(1)} °C`;
  if (hum !== undefined && humValue) humValue.textContent = `${Number(hum).toFixed(0)} %`;
}

function updateLightState(state) {
  lightState = state;
  if (!btnToggleLight || !lightText) return;
  if (lightState === 1) {
    btnToggleLight.classList.add('active');
    lightText.textContent = 'Luz: ON';
  } else {
    btnToggleLight.classList.remove('active');
    lightText.textContent = 'Luz: OFF';
  }
}

function updateESP32Status(connected) {
  if (!esp32Dot || !esp32StatusText) return;
  if (connected) {
    esp32Dot.classList.add('connected');
    esp32StatusText.textContent = 'ESP32 Conectado (En línea)';
    esp32StatusText.style.color = '#38bdf8';
  } else {
    esp32Dot.classList.remove('connected');
    esp32StatusText.textContent = 'ESP32 Esperando conexión...';
    esp32StatusText.style.color = '#94a3b8';
  }
}

// ============================================================================
// 4. VISUALIZADOR DE FORMA DE ONDA EN CANVAS
// ============================================================================
function resizeCanvas() {
  if (!waveformCanvas || !waveformCanvas.parentElement) return;
  waveformCanvas.width = waveformCanvas.parentElement.clientWidth;
  waveformCanvas.height = waveformCanvas.parentElement.clientHeight;
}
window.addEventListener('resize', resizeCanvas);

function drawWaveform() {
  const activeAnalyser = micAnalyserNode || playbackAnalyser;
  if (!activeAnalyser || !waveformCtx) return;

  const bufferLength = activeAnalyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  activeAnalyser.getByteTimeDomainData(dataArray);

  waveformCtx.clearRect(0, 0, waveformCanvas.width, waveformCanvas.height);
  waveformCtx.lineWidth = 2.5;
  waveformCtx.strokeStyle = isRecording ? '#f43f5e' : '#38bdf8';
  waveformCtx.beginPath();

  const sliceWidth = waveformCanvas.width / bufferLength;
  let x = 0;

  for (let i = 0; i < bufferLength; i++) {
    const v = dataArray[i] / 128.0;
    const y = (v * waveformCanvas.height) / 2;

    if (i === 0) {
      waveformCtx.moveTo(x, y);
    } else {
      waveformCtx.lineTo(x, y);
    }
    x += sliceWidth;
  }

  waveformCtx.lineTo(waveformCanvas.width, waveformCanvas.height / 2);
  waveformCtx.stroke();

  if (isRecording || document.body.classList.contains('speaking')) {
    waveformAnimId = requestAnimationFrame(drawWaveform);
  } else {
    waveformCtx.clearRect(0, 0, waveformCanvas.width, waveformCanvas.height);
  }
}

// ============================================================================
// 5. CONVERSIÓN DE AUDIO A WAV (16kHz 16-bit Mono PCM)
// ============================================================================
function exportWAV(samples, sampleRate) {
  const targetRate = 16000;
  let downsampledSamples = samples;

  if (sampleRate !== targetRate) {
    const ratio = sampleRate / targetRate;
    const newLength = Math.round(samples.length / ratio);
    downsampledSamples = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {
      const idx = Math.floor(i * ratio);
      downsampledSamples[i] = samples[idx];
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
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
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

// ============================================================================
// 6. GRABACIÓN DE MICRÓFONO DIRECTO POR WEB AUDIO API
// ============================================================================
async function startRecording() {
  try {
    unlockAudioSession();

    if (!audioPlayer.paused) {
      audioPlayer.pause();
      document.body.classList.remove('speaking');
    }

    micMediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });

    if (!audioContext) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      audioContext = new AudioCtx();
    }
    if (audioContext.state === 'suspended') {
      await audioContext.resume();
    }

    micInputNode = audioContext.createMediaStreamSource(micMediaStream);

    micAnalyserNode = audioContext.createAnalyser();
    micAnalyserNode.fftSize = 256;
    micInputNode.connect(micAnalyserNode);

    recordedSamples = [];
    micProcessorNode = audioContext.createScriptProcessor(4096, 1, 1);
    micProcessorNode.onaudioprocess = (e) => {
      if (!isRecording) return;
      const input = e.inputBuffer.getChannelData(0);
      recordedSamples.push(new Float32Array(input));
    };

    micInputNode.connect(micProcessorNode);
    micProcessorNode.connect(audioContext.destination);

    isRecording = true;
    btnMic.classList.add('recording');
    document.body.classList.add('listening');

    statusCaption.textContent = '🎙️ Escuchando tu voz...';
    subCaption.textContent = 'Toca de nuevo el botón para enviar a Ollama';
    triggerHaptic(50);

    resizeCanvas();
    drawWaveform();

  } catch (err) {
    console.error('[Mic Error]', err);
    alert('No se pudo acceder al micrófono: ' + err.message + '\nVerifica los permisos en tu navegador.');
    statusCaption.textContent = 'Permiso de micrófono requerido';
    subCaption.textContent = 'Concede permisos o utiliza la entrada de texto';
  }
}

async function stopRecording() {
  if (!isRecording) return;

  isRecording = false;
  btnMic.classList.remove('recording');
  document.body.classList.remove('listening');

  statusCaption.textContent = '🧠 Procesando con Qwen 2.5...';
  subCaption.textContent = 'Transcribiendo audio y sintetizando Loquendo...';
  triggerHaptic(40);

  if (micProcessorNode) micProcessorNode.disconnect();
  if (micInputNode) micInputNode.disconnect();
  if (micMediaStream) {
    micMediaStream.getTracks().forEach(track => track.stop());
  }

  let totalLength = 0;
  for (const arr of recordedSamples) {
    totalLength += arr.length;
  }
  const merged = new Float32Array(totalLength);
  let offset = 0;
  for (const arr of recordedSamples) {
    merged.set(arr, offset);
    offset += arr.length;
  }

  if (totalLength < 3500) {
    statusCaption.textContent = 'Audio demasiado corto';
    subCaption.textContent = 'Toca el micrófono e inténtalo de nuevo';
    return;
  }

  const wavBlob = exportWAV(merged, audioContext.sampleRate);
  await sendAudioToServer(wavBlob);
}

function toggleMicrophone() {
  triggerHaptic(30);
  if (!isRecording) {
    startRecording();
  } else {
    stopRecording();
  }
}

// ============================================================================
// 7. ENVÍO DE AUDIO WAV AL SERVIDOR FASTAPI
// ============================================================================
async function sendAudioToServer(wavBlob) {
  const selectedVoice = voiceSelect ? voiceSelect.value : 'jorge';
  const formData = new FormData();
  formData.append('audio', wavBlob, 'recording.wav');
  formData.append('voice', selectedVoice);
  formData.append('history_json', JSON.stringify(conversationHistory.slice(-6)));

  try {
    const response = await fetch('/api/process-audio', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Error en el servidor (${response.status})`);
    }

    const data = await response.json();

    conversationHistory.push({ role: 'user', content: data.transcription });
    conversationHistory.push({ role: 'assistant', content: data.speech_text });

    if (data.light_state !== undefined) {
      updateLightState(data.light_state);
    }

    lastAudioUrl = data.audio_url;
    lastAudioBase64 = data.audio_base64;

    playVoiceResponse(data.audio_url, data.audio_base64, data.speech_text);

  } catch (error) {
    console.error('[Error de Procesamiento]', error);
    statusCaption.textContent = 'Error al procesar tu consulta';
    subCaption.textContent = error.message;
  }
}

// ============================================================================
// 8. ENVÍO DE TEXTO DIRECTO (CHIPS O TECLADO)
// ============================================================================
async function sendQueryToAI(text) {
  if (!text || text.trim() === '') return;
  unlockAudioSession();

  const selectedVoice = voiceSelect ? voiceSelect.value : 'jorge';
  statusCaption.textContent = `"${text}"`;
  subCaption.textContent = '🧠 Consultando a Qwen 2.5 en Ollama...';
  triggerHaptic(30);

  conversationHistory.push({ role: 'user', content: text.trim() });

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: text.trim(),
        voice: selectedVoice,
        history: conversationHistory.slice(-6)
      })
    });

    if (!response.ok) throw new Error('Falla en la respuesta de la PC');

    const data = await response.json();
    conversationHistory.push({ role: 'assistant', content: data.speech_text });

    if (data.light_state !== undefined) {
      updateLightState(data.light_state);
    }

    lastAudioUrl = data.audio_url;
    lastAudioBase64 = data.audio_base64;

    playVoiceResponse(data.audio_url, data.audio_base64, data.speech_text);

  } catch (err) {
    console.error('[Fetch Error]', err);
    statusCaption.textContent = 'Error al conectar con la PC.';
    subCaption.textContent = 'Verifica que Ollama y el servidor estén activos.';
  }
}

// ============================================================================
// 9. REPRODUCCIÓN DE AUDIO & MODULACIÓN LABIAL (LIP-SYNC)
// ============================================================================
function setupPlaybackWebAudio() {
  if (isAudioContextReady) return;
  try {
    if (!audioContext) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      audioContext = new AudioCtx();
    }
    playbackAnalyser = audioContext.createAnalyser();
    playbackAnalyser.fftSize = 256;
    playbackAnalyser.smoothingTimeConstant = 0.4;

    playbackSource = audioContext.createMediaElementSource(audioPlayer);
    playbackSource.connect(playbackAnalyser);
    playbackAnalyser.connect(audioContext.destination);

    isAudioContextReady = true;
  } catch (err) {
    console.warn('[Web Audio Playback]', err);
  }
}

function startLipSyncAnalysis() {
  if (!playbackAnalyser) return;

  const bufferLength = playbackAnalyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  let lastMouthAngle = 90;

  document.body.classList.add('speaking');
  resizeCanvas();
  drawWaveform();

  function analyzeLoop() {
    if (audioPlayer.paused || audioPlayer.ended) {
      document.body.classList.remove('speaking');
      if (jawLower) jawLower.style.transform = 'translateY(0px)';
      sendLipsyncFrame(90);
      return;
    }

    playbackAnalyser.getByteFrequencyData(dataArray);

    let sum = 0;
    const voiceBins = Math.min(bufferLength, 32);
    for (let i = 2; i < voiceBins; i++) {
      sum += dataArray[i];
    }
    const avgEnergy = sum / (voiceBins - 2);

    let mouthAngle = 90;
    let jawPixels = 0;

    if (avgEnergy > 15) {
      const normalized = Math.min(1.0, (avgEnergy - 15) / 110);
      mouthAngle = Math.round(90 + normalized * 38);
      jawPixels = Math.round(normalized * 14);
    }

    mouthAngle = Math.round(lastMouthAngle * 0.3 + mouthAngle * 0.7);
    lastMouthAngle = mouthAngle;

    if (jawLower) jawLower.style.transform = `translateY(${jawPixels}px)`;
    sendLipsyncFrame(mouthAngle);

    requestAnimationFrame(analyzeLoop);
  }

  requestAnimationFrame(analyzeLoop);
}

let lastSentTime = 0;
function sendLipsyncFrame(mouthAngle) {
  const now = Date.now();
  if (now - lastSentTime < 45 && mouthAngle !== 90) return;
  lastSentTime = now;

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      event: 'lipsync_frame',
      mouth: mouthAngle
    }));
  }
}

async function playVoiceResponse(audioUrl, audioBase64, responseText) {
  unlockAudioSession();
  setupPlaybackWebAudio();

  statusCaption.textContent = responseText;
  subCaption.textContent = '🔊 Reproduciendo con voz de Loquendo...';

  if (replayAudioContainer) replayAudioContainer.style.display = 'block';
  if (btnReplayAudio) {
    btnReplayAudio.classList.add('speaking-active');
    btnReplayAudio.textContent = '🔊 Hablando con Loquendo...';
  }

  const srcToUse = audioUrl || audioBase64;
  let played = false;

  // Intento 1: Reproducción con etiqueta de audio HTML5
  if (audioPlayer && srcToUse) {
    try {
      if (audioPlayer.src !== srcToUse && !audioPlayer.src.endsWith(audioUrl)) {
        audioPlayer.src = srcToUse;
      }
      audioPlayer.load();
      await audioPlayer.play();
      played = true;
      startLipSyncAnalysis();
    } catch (e) {
      console.warn('[Audio Tag] Fallback a Web Audio API:', e);
    }
  }

  // Intento 2: Fallback por Web Audio API Buffer
  if (!played && audioUrl) {
    try {
      if (audioContext && audioContext.state === 'suspended') {
        await audioContext.resume();
      }
      const resp = await fetch(audioUrl);
      const ab = await resp.arrayBuffer();
      const decoded = await audioContext.decodeAudioData(ab);

      if (currentWebAudioSource) {
        try { currentWebAudioSource.stop(); } catch (_) {}
      }

      currentWebAudioSource = audioContext.createBufferSource();
      currentWebAudioSource.buffer = decoded;
      currentWebAudioSource.connect(playbackAnalyser || audioContext.destination);
      currentWebAudioSource.start(0);
      played = true;

      document.body.classList.add('speaking');
      currentWebAudioSource.onended = () => {
        finishPlayback();
      };
    } catch (webaudioErr) {
      console.warn('[Web Audio Error]', webaudioErr);
    }
  }

  if (!played) {
    subCaption.textContent = 'Toca el botón azul para escuchar la respuesta.';
    if (btnReplayAudio) {
      btnReplayAudio.classList.remove('speaking-active');
      btnReplayAudio.textContent = '▶️ Toca para escuchar a Loquendo';
    }
  }

  audioPlayer.onended = () => {
    finishPlayback();
  };
}

function finishPlayback() {
  document.body.classList.remove('speaking');
  if (jawLower) jawLower.style.transform = 'translateY(0px)';
  sendLipsyncFrame(90);

  subCaption.textContent = 'Toca el micrófono para volver a hablar';
  if (btnReplayAudio) {
    btnReplayAudio.classList.remove('speaking-active');
    btnReplayAudio.textContent = '🔊 Volver a escuchar a Loquendo';
  }
}

// ============================================================================
// 10. ANIMACIONES VISUALES (OJOS Y PARPADEO VIRTUAL)
// ============================================================================
function triggerBlinkAnimation() {
  if (eyesSocket) {
    eyesSocket.classList.add('blink');
    setTimeout(() => {
      eyesSocket.classList.remove('blink');
    }, 140);
  }
}

setInterval(() => {
  if (Math.random() > 0.3) {
    triggerBlinkAnimation();
  }
}, 4500);

setInterval(() => {
  if (eyeball && !document.body.classList.contains('speaking')) {
    const offsetX = (Math.random() - 0.5) * 16;
    const offsetY = (Math.random() - 0.5) * 8;
    eyeball.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
  }
}, 3000);

function triggerHaptic(pattern) {
  if (navigator.vibrate) {
    try { navigator.vibrate(pattern); } catch (e) {}
  }
}

// ============================================================================
// 11. EVENT LISTENERS
// ============================================================================
btnMic.addEventListener('click', toggleMicrophone);

if (btnReplayAudio) {
  btnReplayAudio.addEventListener('click', () => {
    if (lastAudioUrl || lastAudioBase64) {
      playVoiceResponse(lastAudioUrl, lastAudioBase64, statusCaption.textContent);
    }
  });
}

btnSendText.addEventListener('click', () => {
  const query = inputQuery.value.trim();
  if (query) {
    sendQueryToAI(query);
    inputQuery.value = '';
    inputQuery.blur();
  }
});

inputQuery.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    btnSendText.click();
  }
});

document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const prompt = chip.getAttribute('data-prompt');
    sendQueryToAI(prompt);
  });
});

btnToggleLight.addEventListener('click', () => {
  triggerHaptic(30);
  const newLight = lightState === 1 ? 0 : 1;
  updateLightState(newLight);

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      event: 'manual_move',
      light: newLight
    }));
  }
});

btnToggleManual.addEventListener('click', () => {
  manualPanel.classList.toggle('open');
  triggerHaptic(20);
});

btnCloseManual.addEventListener('click', () => {
  manualPanel.classList.remove('open');
});

sliderMouth.addEventListener('input', (e) => {
  const val = parseInt(e.target.value);
  valMouth.textContent = `${val}°`;
  sendManualMove(val, parseInt(sliderEyes.value), 0);
});

sliderEyes.addEventListener('input', (e) => {
  const val = parseInt(e.target.value);
  valEyes.textContent = `${val}°`;
  sendManualMove(parseInt(sliderMouth.value), val, 0);
});

btnTriggerBlink.addEventListener('click', () => {
  triggerBlinkAnimation();
  sendManualMove(parseInt(sliderMouth.value), parseInt(sliderEyes.value), 1);
});

btnCenterAll.addEventListener('click', () => {
  sliderMouth.value = 90;
  sliderEyes.value = 90;
  valMouth.textContent = '90°';
  valEyes.textContent = '90°';
  sendManualMove(90, 90, 0);
});

function sendManualMove(m, e, b) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      event: 'manual_move',
      mouth: m,
      eyes: e,
      blink: b,
      light: lightState
    }));
  }
}

// INICIAR AL CARGAR
window.addEventListener('DOMContentLoaded', () => {
  initWebSocket();
  checkBackendStatus();
  resizeCanvas();
});
