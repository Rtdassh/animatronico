/**
 * ============================================================================
 * ANIMATRONICO · CONTROLADOR DE INTERFAZ
 * ============================================================================
 * Funcionalidad:
 *   1. Captura de audio WAV 16kHz PCM directa vía Web Audio API.
 *   2. Comunicación con FastAPI (/api/process-audio) para STT e inferencia Ollama.
 *   3. Reproducción de síntesis de voz y análisis espectral para modulación labial (Lip-Sync).
 *   4. Enlace WebSocket bidireccional con ESP32 y Arduino Uno.
 *   5. Telemetría y control manual de actuadores.
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
// 1. DESBLOQUEO DE SESIÓN DE AUDIO PARA NAVEGADORES MÓVILES
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
    audioPlayer.src = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA';
    audioPlayer.play().then(() => {
      audioPlayer.pause();
      audioUnlocked = true;
    }).catch(() => {});
  }
}

document.addEventListener('touchstart', unlockAudioSession, { passive: true });
document.addEventListener('touchend', unlockAudioSession, { passive: true });
document.addEventListener('click', unlockAudioSession, { passive: true });

// ============================================================================
// 2. VERIFICACIÓN DE ESTADO DEL SERVIDOR Y MODELOS
// ============================================================================
async function checkBackendStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) throw new Error('Estado no disponible');
    const data = await res.json();

    if (data.ollama_ready) {
      ollamaDot.classList.add('ready');
      let statusStr = `Ollama: ${data.model}`;
      if (data.voicebox_ready) {
        statusStr += ` | Voicebox`;
      }
      modelStatusText.textContent = statusStr;
    } else {
      ollamaDot.classList.remove('ready');
      modelStatusText.textContent = `Ollama: En espera (${data.model || 'sin modelo'})`;
    }

    if (data.voices && voiceSelect) {
      const currentVal = voiceSelect.value;
      voiceSelect.innerHTML = '';
      for (const [vKey, vName] of Object.entries(data.voices)) {
        const cleanName = vName.replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}]/gu, '').trim();
        const opt = document.createElement('option');
        opt.value = vKey;
        opt.textContent = cleanName;
        if (vKey === currentVal) opt.selected = true;
        voiceSelect.appendChild(opt);
      }
      if (!voiceSelect.value && voiceSelect.options.length > 0) {
        voiceSelect.selectedIndex = 0;
      }
    }

    if (data.temperature !== undefined) updateTelemetry(data.temperature, data.humidity);
    if (data.light_state !== undefined) updateLightState(data.light_state);
    if (data.esp32_connected !== undefined) updateESP32Status(data.esp32_connected);

  } catch (err) {
    ollamaDot.classList.remove('ready');
    modelStatusText.textContent = 'Servidor desconectado';
  }
}

// ============================================================================
// 3. ENLACE WEBSOCKET
// ============================================================================
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/mobile`;

  try {
    ws = new WebSocket(wsUrl);

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
    esp32StatusText.textContent = 'ESP32 conectado';
  } else {
    esp32Dot.classList.remove('connected');
    esp32StatusText.textContent = 'ESP32 desconectado';
  }
}

// ============================================================================
// 4. VISUALIZADOR DE ONDA DE AUDIO EN CANVAS
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
  waveformCtx.lineWidth = 1.5;
  waveformCtx.strokeStyle = isRecording ? '#ef4444' : '#38bdf8';
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
// 5. EXPORTACIÓN WAV (16kHz Mono PCM)
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
  const bytesPerSample = 2;
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
// 6. CONTROL DEL MICRÓFONO
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

    statusCaption.textContent = 'Escuchando voz...';
    subCaption.textContent = '';
    triggerHaptic(50);

    resizeCanvas();
    drawWaveform();

  } catch (err) {
    console.error('[Mic Error]', err);
    statusCaption.textContent = 'Permiso de micrófono no disponible';
    subCaption.textContent = 'Revisa los permisos del navegador';
  }
}

async function stopRecording() {
  if (!isRecording) return;

  isRecording = false;
  btnMic.classList.remove('recording');
  document.body.classList.remove('listening');

  statusCaption.textContent = 'Procesando...';
  subCaption.textContent = '';
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
// 7. ENVÍO DE AUDIO AL BACKEND
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
    statusCaption.textContent = 'Error al procesar consulta';
    subCaption.textContent = error.message;
  }
}

// ============================================================================
// 8. ENVÍO DE CONSULTA POR TEXTO
// ============================================================================
async function sendQueryToAI(text) {
  if (!text || text.trim() === '') return;
  unlockAudioSession();

  const selectedVoice = voiceSelect ? voiceSelect.value : 'jorge';
  statusCaption.textContent = `"${text}"`;
  subCaption.textContent = 'Consultando modelo...';
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

    if (!response.ok) throw new Error('Fallo en la respuesta del servidor');

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
    statusCaption.textContent = 'Error de conexión';
    subCaption.textContent = 'Revisa que el servidor esté activo';
  }
}

// ============================================================================
// 9. REPRODUCCIÓN DE AUDIO Y LIP-SYNC
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
      jawPixels = Math.round(normalized * 12);
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

  const selectedText = voiceSelect && voiceSelect.selectedOptions[0] ? voiceSelect.selectedOptions[0].textContent : 'Loquendo';
  const voiceName = selectedText.split(' ')[0] || 'Voz';

  statusCaption.textContent = responseText;
  subCaption.textContent = `Voz: ${voiceName}`;

  if (replayAudioContainer) replayAudioContainer.style.display = 'block';
  if (btnReplayAudio) {
    btnReplayAudio.classList.add('speaking-active');
    btnReplayAudio.textContent = 'Reproduciendo...';
  }

  if (alexaModeEnabled) {
    setAlexaUIState('SPEAKING');
  }

  const srcToUse = audioUrl || audioBase64;
  let played = false;

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
    subCaption.textContent = 'Toca el botón para reproducir.';
    if (btnReplayAudio) {
      btnReplayAudio.classList.remove('speaking-active');
      btnReplayAudio.textContent = 'Reproducir respuesta';
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

  subCaption.textContent = '';
  if (btnReplayAudio) {
    btnReplayAudio.classList.remove('speaking-active');
    btnReplayAudio.textContent = 'Reproducir respuesta';
  }

  if (alexaModeEnabled) {
    onPlaybackCompletedAlexa();
  }
}

// ============================================================================
// 10. ANIMACIONES VISUALES (PARPADEO Y MOVIMIENTO OCULAR)
// ============================================================================
function triggerBlinkAnimation() {
  if (eyesSocket) {
    eyesSocket.classList.add('blink');
    setTimeout(() => {
      eyesSocket.classList.remove('blink');
    }, 120);
  }
}

setInterval(() => {
  if (Math.random() > 0.35) {
    triggerBlinkAnimation();
  }
}, 4500);

setInterval(() => {
  if (eyeball && !document.body.classList.contains('speaking')) {
    const offsetX = (Math.random() - 0.5) * 12;
    const offsetY = (Math.random() - 0.5) * 6;
    eyeball.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
  }
}, 3200);

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

// ============================================================================
// 12. MÓDULO ASISTENTE MANOS LIBRES (TIPO ALEXA / WAKENET)
// ============================================================================
const alexaModeBar = document.getElementById('alexaModeBar');
const alexaDot = document.getElementById('alexaDot');
const alexaTitle = document.getElementById('alexaTitle');
const alexaDesc = document.getElementById('alexaDesc');
const btnToggleAlexa = document.getElementById('btnToggleAlexa');
const alexaBtnLabel = document.getElementById('alexaBtnLabel');

let alexaModeEnabled = false;
let wakeWordRecognizer = null;
let queryRecognizer = null;
let alexaState = 'IDLE'; // 'IDLE', 'LISTENING_WAKE', 'WAKE_TRIGGERED', 'LISTENING_QUERY', 'PROCESSING', 'SPEAKING'
let querySilenceTimer = null;

// Palabras clave de activación (Wake-Words en español)
const WAKE_WORDS = [
  'oye robot',
  'hola robot',
  'robot',
  'alexa',
  'jarvis',
  'animatrónico',
  'animatronico',
  'computadora',
  'despierta'
];

function initAlexaMode() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    if (alexaDesc) alexaDesc.textContent = 'Navegador sin soporte de voz WebSpeech';
    if (btnToggleAlexa) btnToggleAlexa.disabled = true;
    return;
  }

  if (btnToggleAlexa) {
    btnToggleAlexa.addEventListener('click', () => {
      unlockAudioSession();
      toggleAlexaMode();
    });
  }
}

function toggleAlexaMode() {
  alexaModeEnabled = !alexaModeEnabled;
  if (alexaModeEnabled) {
    btnToggleAlexa.classList.add('running');
    if (alexaBtnLabel) alexaBtnLabel.textContent = 'Detener';
    startWakeWordRecognition();
  } else {
    btnToggleAlexa.classList.remove('running');
    if (alexaBtnLabel) alexaBtnLabel.textContent = 'Iniciar Manos Libres';
    stopAllAlexaRecognition();
    setAlexaUIState('DISABLED');
  }
}

function setAlexaUIState(state) {
  alexaState = state;
  if (!alexaModeBar || !alexaDot || !alexaDesc) return;

  alexaModeBar.classList.remove('listening', 'wake-triggered');
  alexaDot.classList.remove('active', 'hearing');

  switch (state) {
    case 'LISTENING_WAKE':
      alexaModeBar.classList.add('listening');
      alexaDot.classList.add('active');
      if (alexaTitle) alexaTitle.textContent = 'Manos Libres Activo';
      alexaDesc.textContent = 'Esperando: "Oye Robot" / "Alexa"';
      statusCaption.textContent = 'Esperando palabra clave...';
      break;

    case 'WAKE_TRIGGERED':
      alexaModeBar.classList.add('wake-triggered');
      alexaDot.classList.add('hearing');
      if (alexaTitle) alexaTitle.textContent = 'Activado';
      alexaDesc.textContent = '¿En qué te ayudo?';
      statusCaption.textContent = '¡Palabra clave detectada!';
      break;

    case 'LISTENING_QUERY':
      alexaModeBar.classList.add('wake-triggered');
      alexaDot.classList.add('hearing');
      if (alexaTitle) alexaTitle.textContent = 'Escuchando tu pregunta';
      alexaDesc.textContent = 'Habla ahora (sin tocar pantalla)';
      statusCaption.textContent = 'Escuchando...';
      break;

    case 'PROCESSING':
      alexaDot.classList.add('active');
      if (alexaTitle) alexaTitle.textContent = 'Procesando consulta';
      alexaDesc.textContent = 'Consultando IA local...';
      statusCaption.textContent = 'Pensando respuesta...';
      break;

    case 'SPEAKING':
      alexaDot.classList.add('hearing');
      if (alexaTitle) alexaTitle.textContent = 'Respondiendo';
      alexaDesc.textContent = 'Reproduciendo por altavoz móvil';
      break;

    case 'DISABLED':
    default:
      if (alexaTitle) alexaTitle.textContent = 'Asistente Manos Libres';
      alexaDesc.textContent = 'Palabra clave: "Oye Robot" / "Alexa"';
      statusCaption.textContent = 'Listo';
      break;
  }
}

function startWakeWordRecognition() {
  if (!alexaModeEnabled) return;
  stopAllAlexaRecognition();

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return;

  try {
    wakeWordRecognizer = new SpeechRecognition();
    wakeWordRecognizer.continuous = true;
    wakeWordRecognizer.interimResults = true;
    wakeWordRecognizer.lang = 'es-ES';

    setAlexaUIState('LISTENING_WAKE');

    wakeWordRecognizer.onresult = (event) => {
      if (alexaState !== 'LISTENING_WAKE') return;

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript.trim().toLowerCase();

        const detected = WAKE_WORDS.some(w => transcript.includes(w));
        if (detected) {
          handleWakeWordDetected();
          break;
        }
      }
    };

    wakeWordRecognizer.onerror = (e) => {
      console.warn('[WakeWord Recognition Error]', e.error);
      if (alexaModeEnabled && alexaState === 'LISTENING_WAKE') {
        setTimeout(() => {
          if (alexaModeEnabled && alexaState === 'LISTENING_WAKE') {
            try { wakeWordRecognizer.start(); } catch (_) {}
          }
        }, 1000);
      }
    };

    wakeWordRecognizer.onend = () => {
      if (alexaModeEnabled && alexaState === 'LISTENING_WAKE') {
        try {
          wakeWordRecognizer.start();
        } catch (_) {}
      }
    };

    wakeWordRecognizer.start();
  } catch (err) {
    console.warn('[WakeWord start error]', err);
  }
}

function stopAllAlexaRecognition() {
  if (wakeWordRecognizer) {
    try {
      wakeWordRecognizer.onend = null;
      wakeWordRecognizer.onerror = null;
      wakeWordRecognizer.stop();
    } catch (_) {}
    wakeWordRecognizer = null;
  }
  if (queryRecognizer) {
    try {
      queryRecognizer.onend = null;
      queryRecognizer.onerror = null;
      queryRecognizer.stop();
    } catch (_) {}
    queryRecognizer = null;
  }
  if (querySilenceTimer) {
    clearTimeout(querySilenceTimer);
    querySilenceTimer = null;
  }
}

async function handleWakeWordDetected() {
  stopAllAlexaRecognition();
  setAlexaUIState('WAKE_TRIGGERED');
  triggerHaptic([60, 40, 60]);

  // 1. Notificar al ESP32 / Arduino para que la cabeza reaccione inmediatamente
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ event: 'wake_alert' }));
  }

  // 2. Reproducir inmediatamente el saludo: "¿En qué te ayudo?"
  await speakGreetingPrompt("¿En qué te ayudo?");

  // 3. Pasar a escuchar la consulta del usuario manos libres
  startQueryListening();
}

function speakGreetingPrompt(text) {
  return new Promise((resolve) => {
    // Si Web Speech Synthesis está disponible, usarlo para respuesta instantánea
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'es-ES';
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
      utterance.onend = () => resolve();
      utterance.onerror = () => resolve();
      window.speechSynthesis.speak(utterance);
    } else {
      // Fallback: reproducir mediante endpoint /api/tts
      const selectedVoice = voiceSelect ? voiceSelect.value : 'jorge';
      const audio = new Audio(`/api/tts?text=${encodeURIComponent(text)}&voice=${selectedVoice}`);
      audio.onended = () => resolve();
      audio.onerror = () => resolve();
      audio.play().catch(() => resolve());
    }
  });
}

function startQueryListening() {
  if (!alexaModeEnabled) return;
  setAlexaUIState('LISTENING_QUERY');

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return;

  queryRecognizer = new SpeechRecognition();
  queryRecognizer.continuous = false;
  queryRecognizer.interimResults = true;
  queryRecognizer.lang = 'es-ES';

  let finalTranscript = '';

  queryRecognizer.onresult = (event) => {
    let interim = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) {
        finalTranscript += event.results[i][0].transcript;
      } else {
        interim += event.results[i][0].transcript;
      }
    }

    const currentText = (finalTranscript || interim).trim();
    if (currentText) {
      statusCaption.textContent = `"${currentText}"`;
      // Reiniciar temporizador de silencio (1.4s después de la última palabra)
      if (querySilenceTimer) clearTimeout(querySilenceTimer);
      querySilenceTimer = setTimeout(() => {
        commitQuery(currentText);
      }, 1400);
    }
  };

  queryRecognizer.onerror = (e) => {
    console.warn('[Query Recognition Error]', e.error);
    if (finalTranscript.trim()) {
      commitQuery(finalTranscript.trim());
    } else {
      onPlaybackCompletedAlexa();
    }
  };

  queryRecognizer.onend = () => {
    if (finalTranscript.trim()) {
      commitQuery(finalTranscript.trim());
    } else if (alexaState === 'LISTENING_QUERY') {
      onPlaybackCompletedAlexa();
    }
  };

  try {
    queryRecognizer.start();
  } catch (err) {
    console.warn('[Query Start Error]', err);
    onPlaybackCompletedAlexa();
  }
}

async function commitQuery(text) {
  stopAllAlexaRecognition();
  if (!text || text.trim() === '') {
    onPlaybackCompletedAlexa();
    return;
  }

  setAlexaUIState('PROCESSING');
  await sendQueryToAI(text.trim());
}

function onPlaybackCompletedAlexa() {
  if (!alexaModeEnabled) return;
  // Breve retardo para evitar feedback acústico del altavoz del móvil
  setTimeout(() => {
    if (alexaModeEnabled) {
      startWakeWordRecognition();
    }
  }, 500);
}

// INICIAR AL CARGAR
window.addEventListener('DOMContentLoaded', () => {
  initWebSocket();
  checkBackendStatus();
  initAlexaMode();
  resizeCanvas();
});
