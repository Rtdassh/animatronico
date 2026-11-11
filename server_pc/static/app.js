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
voiceSelect?.addEventListener('change', () => localStorage.setItem('asistente_voice', voiceSelect.value));

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
const sliderEyesV = document.getElementById('sliderEyesV');
const valMouth = document.getElementById('valMouth');
const valEyes = document.getElementById('valEyes');
const valEyesV = document.getElementById('valEyesV');
const btnTriggerBlink = document.getElementById('btnTriggerBlink');
const btnCenterAll = document.getElementById('btnCenterAll');

// Modo Visión Artificial (Seguimiento de Rostro)
const visionModeBar = document.getElementById('visionModeBar');
const visionDot = document.getElementById('visionDot');
const visionTitle = document.getElementById('visionTitle');
const visionBadge = document.getElementById('visionBadge');
const visionAngles = document.getElementById('visionAngles');
const btnToggleVision = document.getElementById('btnToggleVision');
const visionBtnLabel = document.getElementById('visionBtnLabel');
const btnTogglePreview = document.getElementById('btnTogglePreview');
const previewBtnLabel = document.getElementById('previewBtnLabel');
const visionPreviewCard = document.getElementById('visionPreviewCard');
const visionFeedImg = document.getElementById('visionFeedImg');
const feedFpsText = document.getElementById('feedFpsText');
const feedStatusText = document.getElementById('feedStatusText');
const chkInvertX = document.getElementById('chkInvertX');
const chkInvertY = document.getElementById('chkInvertY');
const sliderSmooth = document.getElementById('sliderSmooth');

let isVisionActive = false;
let isPreviewOpen = false;
let isFaceDetected = false;

// Modo Asistente Manos Libres (Tipo Alexa / WakeNet)
const alexaModeBar = document.getElementById('alexaModeBar');
const alexaDot = document.getElementById('alexaDot');
const alexaTitle = document.getElementById('alexaTitle');
const alexaDesc = document.getElementById('alexaDesc');
const btnToggleAlexa = document.getElementById('btnToggleAlexa');
const alexaBtnLabel = document.getElementById('alexaBtnLabel');

let alexaModeEnabled = false;
let wakeWordRecognizer = null;
let queryRecognizer = null;
let alexaState = 'IDLE'; // 'IDLE', 'LISTENING_WAKE', 'WAKE_TRIGGERED', 'LISTENING_QUERY', 'PROCESSING', 'SPEAKING', 'FOLLOW_UP'
let querySilenceTimer = null;
let followUpTimer = null;

const WAKE_WORDS = [
  'dom dom',
  'domdom',
  'don don',
  'dondon',
  'dom don',
  'don dom',
  'dum dum',
  'oye libni',
  'oye livni',
  'oye lipni',
  'oye libny',
  'hola libni',
  'libni',
  'livni',
  'oye hube', // Variante fonética que devuelve el modelo local español.
  'oye b',    // Google suele transcribir la letra V como "b", "be" o "ve".
  'oye be',
  'oye bebe',
  'oyeb',
  'oyeve',
  'hoy ve',
  'hoy v',
  'oye uve',
  'oye v',
  'oye ve',
  'oye la uve',
  'oye la v',
  'oye ube',
  'hola uve',
  'hola v',
  'hola ve',
  'v de venganza',
  'v de vendetta',
  'vendetta',
  'venganza',
  'uve',
  'oye robot',
  'hola robot',
  'robot',
  'oye google',
  'hola google',
  'google',
  'despierta',
  'oye ciclope',
  'oye cíclope',
  'asistente',
  'oye asistente'
];

// Reconocimiento de voz: el nativo del navegador (Chrome Android = Google en streaming)
// cuando hay internet; el local (clips al PC con Vosk/Google del servidor) como respaldo sin red o en Safari.
let nativeSpeechFailed = false;
function getSpeechRecognition() {
  const Native = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (Native && !nativeSpeechFailed && navigator.onLine !== false) return Native;
  return window.LocalSpeechRecognition || Native;
}

function markNativeSpeechFailed(recognizer, event) {
  const isLocal = window.LocalSpeechRecognition && recognizer instanceof window.LocalSpeechRecognition;
  if (isLocal || nativeSpeechFailed || !window.LocalSpeechRecognition) return false;
  if (['network', 'service-not-allowed', 'language-not-supported'].includes(event.error)) {
    console.warn('[Voz] Reconocimiento nativo sin servicio; usando el reconocimiento del PC.');
    nativeSpeechFailed = true;
    return true;
  }
  return false;
}

// Normaliza texto eliminando mayúsculas, tildes y puntuación ("¡Dom, dom!" -> "dom dom")
function normalizeSpeech(text) {
  return (text || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9ñ]+/g, ' ').trim().replace(/\s+/g, ' ');
}

// Busca la palabra de activación como palabras completas o patrones fonéticos
function findWakeWord(transcript) {
  const norm = normalizeSpeech(transcript);
  if (!norm) return null;
  const padded = ` ${norm} `;

  // 1. Patrón DOM DOM: repetición ("dom dom", "don don", "tom tom", "domdom", "ding dong", etc.) o "dom" aislado
  const domMatch = padded.match(/(?:^|\s)(dom\s*dom|don\s*don|dum\s*dum|tom\s*tom|ton\s*ton|tan\s*tan|dan\s*dan|ding\s*dong|domdom|dondon|dumdum|tomtom|tonton|dom)(?:\s|$)/i);
  if (domMatch) {
    const wake = domMatch[1].trim();
    const idx = padded.indexOf(` ${wake} `);
    const query = idx !== -1 ? padded.slice(idx + wake.length + 2).trim() : '';
    return { wake: 'dom dom', detected: wake, query };
  }

  // 2. Patrón OYE LIBNI: variaciones fonéticas frecuentes en STT (livni, lipni, lidia, lily, living, limni, etc.)
  const libniMatch = padded.match(/(?:^|\s)(?:(?:oye|hola|hey|ok|ay)\s+)?(libni|livni|lipni|libny|livny|lidia|lily|lili|living|limni|lifni|libi|digni)(?:\s|$)/i);
  if (libniMatch) {
    const fullPhrase = libniMatch[0].trim();
    const idx = padded.indexOf(` ${fullPhrase} `);
    const query = idx !== -1 ? padded.slice(idx + fullPhrase.length + 2).trim() : '';
    return { wake: 'oye libni', detected: fullPhrase, query };
  }

  // 3. Patrón OYE V / V DE VENGANZA (fonéticas: oye ve, oye uve, oye ube, oye b, a ver v)
  const vMatch = padded.match(/(?:^|\s)(?:(?:oye|hola|hey)\s+(v|ve|uve|ube|b|be)|(?:v|uve)\s+de\s+(venganza|vendetta)|venganza|vendetta|a\s+ver\s+v)(?:\s|$)/i);
  if (vMatch) {
    const fullPhrase = vMatch[0].trim();
    const idx = padded.indexOf(` ${fullPhrase} `);
    const query = idx !== -1 ? padded.slice(idx + fullPhrase.length + 2).trim() : '';
    return { wake: 'oye v', detected: fullPhrase, query };
  }

  // 4. Patrón ROBOT / ASISTENTE / GOOGLE
  const robotMatch = padded.match(/(?:^|\s)(?:(?:oye|hola|hey)\s+)?(robot|google|asistente|ciclope|despierta)(?:\s|$)/i);
  if (robotMatch) {
    const fullPhrase = robotMatch[0].trim();
    const idx = padded.indexOf(` ${fullPhrase} `);
    const query = idx !== -1 ? padded.slice(idx + fullPhrase.length + 2).trim() : '';
    return { wake: robotMatch[1].trim(), detected: fullPhrase, query };
  }

  // 5. Búsqueda en la lista completa de palabras clave configuradas
  let best = null;
  for (const wake of WAKE_WORDS) {
    const index = padded.indexOf(` ${wake} `);
    if (index !== -1 && (!best || wake.length > best.wake.length)) best = { wake, index };
  }
  if (!best) return null;
  return { wake: best.wake, detected: best.wake, query: padded.slice(best.index + best.wake.length + 2).trim() };
}

// Música de fondo clásica de Loquendo
const loquendoBgm = document.getElementById('loquendoBgm');
const btnToggleBgm = document.getElementById('btnToggleBgm');
const bgmLabel = document.getElementById('bgmLabel');
const sliderBgmVol = document.getElementById('sliderBgmVol');
const valBgmVol = document.getElementById('valBgmVol');

let isBgmEnabled = localStorage.getItem('loquendo_bgm_enabled') !== 'false';
let bgmVolume = parseFloat(localStorage.getItem('loquendo_bgm_vol') || '0.15');
let bgmFadeTimer = null;

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
let currentGreetingAudio = null;

function stopGreetingAudio() {
  if (currentGreetingAudio) {
    try {
      currentGreetingAudio.pause();
      currentGreetingAudio.currentTime = 0;
    } catch (_) { }
    currentGreetingAudio = null;
  }
}

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
    }).catch(() => { });

    if (loquendoBgm) {
      loquendoBgm.volume = bgmVolume;
      loquendoBgm.load();
    }
  }
}

document.addEventListener('touchstart', unlockAudioSession, { passive: true });
document.addEventListener('touchend', unlockAudioSession, { passive: true });
document.addEventListener('click', unlockAudioSession, { passive: true });

// ============================================================================
// 1.1 GESTIÓN DE MÚSICA DE FONDO LOQUENDO
// ============================================================================
function startLoquendoBgm(restart = false) {
  if (!loquendoBgm || !isBgmEnabled) return;
  if (bgmFadeTimer) {
    clearInterval(bgmFadeTimer);
    bgmFadeTimer = null;
  }
  loquendoBgm.volume = bgmVolume;
  if (restart || loquendoBgm.ended) {
    loquendoBgm.currentTime = 0;
  }
  const playPromise = loquendoBgm.play();
  if (playPromise !== undefined) {
    playPromise.catch(err => {
      console.warn('[Loquendo BGM] Reproducción:', err);
    });
  }
}

function stopLoquendoBgm(fade = true) {
  if (!loquendoBgm) return;
  if (bgmFadeTimer) {
    clearInterval(bgmFadeTimer);
    bgmFadeTimer = null;
  }
  if (!fade || loquendoBgm.paused) {
    loquendoBgm.pause();
    loquendoBgm.currentTime = 0;
    return;
  }
  const startVol = loquendoBgm.volume;
  const steps = 10;
  const intervalMs = 40; // 400ms fade-out suave
  let currentStep = 0;
  bgmFadeTimer = setInterval(() => {
    currentStep++;
    const ratio = (steps - currentStep) / steps;
    if (ratio <= 0) {
      clearInterval(bgmFadeTimer);
      bgmFadeTimer = null;
      loquendoBgm.pause();
      loquendoBgm.currentTime = 0;
      loquendoBgm.volume = bgmVolume;
    } else {
      loquendoBgm.volume = Math.max(0, startVol * ratio);
    }
  }, intervalMs);
}

function updateBgmUI() {
  if (btnToggleBgm) {
    btnToggleBgm.classList.toggle('active', isBgmEnabled);
    if (bgmLabel) {
      bgmLabel.textContent = isBgmEnabled ? 'Música ON' : 'Música OFF';
    }
  }
  if (sliderBgmVol) {
    sliderBgmVol.value = Math.round(bgmVolume * 100);
  }
  if (valBgmVol) {
    valBgmVol.textContent = `${Math.round(bgmVolume * 100)}%`;
  }
  if (loquendoBgm) {
    loquendoBgm.volume = bgmVolume;
  }
}

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
      let statusStr = `🟢 Ollama listo (${data.model})`;
      if (data.voicebox_ready) {
        statusStr += ` | 🎙️ Voicebox Activo`;
      }
      modelStatusText.textContent = statusStr;
    } else {
      ollamaDot.classList.remove('ready');
      modelStatusText.textContent = `🟡 Ollama esperando (${data.model})`;
    }

    if (data.voices && voiceSelect) {
      const currentVal = localStorage.getItem('asistente_voice') || voiceSelect.value || 'windows_local';
      voiceSelect.innerHTML = '';
      for (const [vKey, vName] of Object.entries(data.voices)) {
        const opt = document.createElement('option');
        opt.value = vKey;
        opt.textContent = vName;
        if (vKey === currentVal) opt.selected = true;
        voiceSelect.appendChild(opt);
      }
      voiceSelect.value = [...voiceSelect.options].some(o => o.value === currentVal) ? currentVal : 'windows_local';
    }

    if (data.temperature !== undefined) updateTelemetry(data.temperature, data.humidity);
    if (data.light_state !== undefined) updateLightState(data.light_state);
    if (data.esp32_connected !== undefined) updateESP32Status(data.esp32_connected);
    if (data.vision_active !== undefined) {
      updateVisionUI(data.vision_active, data.face_detected, data.eyes_angle, data.eyes_vertical_angle, data.vision_fps);
      updateAvatarEyePosition(data.eyes_angle || 90, data.eyes_vertical_angle || 90);
    }

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
          if (data.vision_active !== undefined) {
            updateVisionUI(data.vision_active, data.face_detected, data.eyes_angle, data.eyes_vertical_angle);
            updateAvatarEyePosition(data.eyes_angle || 90, data.eyes_vertical_angle || 90);
          }
        } else if (data.type === 'telemetry') {
          updateTelemetry(data.temperature, data.humidity);
          if (data.light_state !== undefined) updateLightState(data.light_state);
        } else if (data.type === 'esp32_status') {
          updateESP32Status(data.connected);
        } else if (data.type === 'servo_position') {
          updateVisionUI(isVisionActive, data.face_detected, data.eyes, data.eyes_v, data.fps);
          updateAvatarEyePosition(data.eyes, data.eyes_v);
          if (sliderEyes) {
            sliderEyes.value = data.eyes;
            valEyes.textContent = `${data.eyes}°`;
          }
          if (sliderEyesV) {
            sliderEyesV.value = data.eyes_v;
            valEyesV.textContent = `${data.eyes_v}°`;
          }
        } else if (data.type === 'vision_status') {
          updateVisionUI(data.active, data.face_detected, data.eyes || 90, data.eyes_v || 90);
          if (!data.active) updateAvatarEyePosition(90, 90);
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
  if (temp !== undefined && tempValue) tempValue.textContent = temp === null ? "--.- °C" : `${Number(temp).toFixed(1)} °C`;
  if (hum !== undefined && humValue) humValue.textContent = hum === null ? "-- %" : `${Number(hum).toFixed(0)} %`;
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
window.exportWAV = exportWAV;

// ============================================================================
// 6. GRABACIÓN DE MICRÓFONO DIRECTO POR WEB AUDIO API
// ============================================================================
async function startRecording() {
  try {
    if (!window.isSecureContext || !navigator.mediaDevices) throw new Error("Abre HTTPS y confía en el certificado del asistente.");
    if (alexaModeEnabled) toggleAlexaMode();
    unlockAudioSession();
    stopGreetingAudio();

    if (!audioPlayer.paused) {
      audioPlayer.pause();
      document.body.classList.remove('speaking');
    }
    stopLoquendoBgm(false);

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
  const selectedVoice = voiceSelect ? voiceSelect.value : 'windows_local';
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
  subCaption.textContent = '🎭 V meditando su réplica...';
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
    if (alexaModeEnabled) {
      setTimeout(() => {
        onPlaybackCompletedAlexa();
      }, 1500);
    }
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
let lastSentMouthAngle = 90;
function sendLipsyncFrame(mouthAngle) {
  const now = Date.now();
  if (now - lastSentTime < 60 && mouthAngle !== 90) return;
  if (Math.abs(mouthAngle - lastSentMouthAngle) < 3 && mouthAngle !== 90) return;
  lastSentTime = now;
  lastSentMouthAngle = mouthAngle;

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      event: 'lipsync_frame',
      mouth: mouthAngle
    }));
  }
}

async function playVoiceResponse(audioUrl, audioBase64, responseText) {
  unlockAudioSession();
  stopGreetingAudio();
  setupPlaybackWebAudio();

  const selectedText = voiceSelect && voiceSelect.selectedOptions[0] ? voiceSelect.selectedOptions[0].textContent : 'Loquendo';
  const voiceName = selectedText.split(' ')[0] || 'Asistente';

  statusCaption.textContent = responseText;
  subCaption.textContent = `🔊 Reproduciendo con voz de ${voiceName}...`;

  if (replayAudioContainer) replayAudioContainer.style.display = 'block';
  if (btnReplayAudio) {
    btnReplayAudio.classList.add('speaking-active');
    btnReplayAudio.textContent = `🔊 Hablando con ${voiceName}...`;
  }

  if (alexaModeEnabled) {
    setAlexaUIState('SPEAKING');
    // Detener el micrófono mientras el asistente habla para evitar auto-interrupción y eco del altavoz
    stopAllAlexaRecognition();
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
      startLoquendoBgm();
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
        try { currentWebAudioSource.stop(); } catch (_) { }
      }

      currentWebAudioSource = audioContext.createBufferSource();
      currentWebAudioSource.buffer = decoded;
      currentWebAudioSource.connect(playbackAnalyser || audioContext.destination);
      currentWebAudioSource.start(0);
      played = true;
      startLoquendoBgm();

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
    stopLoquendoBgm(false);
  }

  audioPlayer.onended = () => {
    finishPlayback();
  };
}

function finishPlayback() {
  document.body.classList.remove('speaking');
  stopLoquendoBgm(true);
  if (jawLower) jawLower.style.transform = 'translateY(0px)';
  sendLipsyncFrame(90);

  const selectedText = voiceSelect && voiceSelect.selectedOptions[0] ? voiceSelect.selectedOptions[0].textContent : 'Loquendo';
  const voiceName = selectedText.split(' ')[0] || 'Asistente';

  subCaption.textContent = 'Toca el micrófono para volver a hablar';
  if (btnReplayAudio) {
    btnReplayAudio.classList.remove('speaking-active');
    btnReplayAudio.textContent = `🔊 Volver a escuchar a ${voiceName}`;
  }

  if (alexaModeEnabled) {
    if (alexaState === 'SPEAKING') {
      onPlaybackCompletedAlexa();
    }
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

// Miradas aleatorias sólo cuando el seguimiento de visión no está activo
setInterval(() => {
  if (eyeball && !document.body.classList.contains('speaking') && !isVisionActive) {
    const offsetX = (Math.random() - 0.5) * 16;
    const offsetY = (Math.random() - 0.5) * 8;
    eyeball.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
  }
}, 3000);

// ============================================================================
// 10.1 FUNCIONES DE CONTROL DE VISIÓN COMPUTACIONAL (CÁMARA LOCAL)
// ============================================================================
function updateVisionUI(active, faceDetected, pan, tilt, fps) {
  isVisionActive = !!active;
  isFaceDetected = !!faceDetected;

  if (visionModeBar) {
    visionModeBar.classList.toggle('active', isVisionActive);
    visionModeBar.classList.toggle('tracking', isVisionActive && isFaceDetected);
  }

  if (visionDot) {
    visionDot.className = 'vision-pulse-dot';
    if (isVisionActive && isFaceDetected) {
      visionDot.classList.add('tracking');
    } else if (isVisionActive) {
      visionDot.classList.add('active');
    }
  }

  if (visionBadge) {
    visionBadge.className = 'vision-badge';
    if (!isVisionActive) {
      visionBadge.textContent = 'OFF';
    } else if (isFaceDetected) {
      visionBadge.textContent = 'SIGUIENDO';
      visionBadge.classList.add('tracking');
    } else {
      visionBadge.textContent = 'BUSCANDO';
      visionBadge.classList.add('active');
    }
  }

  if (visionBtnLabel) {
    visionBtnLabel.textContent = isVisionActive ? '⏹ Detener Visión' : '📷 Iniciar Visión';
    if (btnToggleVision) btnToggleVision.classList.toggle('running', isVisionActive);
  }

  if (visionAngles && pan !== undefined && tilt !== undefined) {
    visionAngles.textContent = `PAN: ${pan}° | TILT: ${tilt}°`;
  }

  if (feedStatusText) {
    feedStatusText.textContent = !isVisionActive ? 'INACTIVO' : (isFaceDetected ? 'SIGUIENDO ROSTRO' : 'BUSCANDO...');
    feedStatusText.style.color = isFaceDetected ? '#34d399' : (isVisionActive ? '#c084fc' : '#94a3b8');
  }

  if (feedFpsText && fps !== undefined) {
    feedFpsText.textContent = `FPS: ${fps}`;
  }
}

function updateAvatarEyePosition(pan, tilt) {
  if (!eyeball) return;
  // Pan EH: 60° (izq) a 120° (der), neutro 90° -> offset X [-16px, 16px]
  // Tilt EV: 70° (arriba) a 110° (abajo), neutro 90° -> offset Y [-10px, 10px]
  const p = Math.max(60, Math.min(120, pan || 90));
  const t = Math.max(70, Math.min(110, tilt || 90));

  const offsetX = ((p - 90) / 30) * 16;
  const offsetY = ((t - 90) / 20) * 10;
  eyeball.style.transform = `translate(${offsetX.toFixed(1)}px, ${offsetY.toFixed(1)}px)`;
}

async function toggleVisionTracking() {
  triggerHaptic(25);
  try {
    const resp = await fetch('/api/vision/toggle', { method: 'POST' });
    const data = await resp.json();
    updateVisionUI(data.active, false, 90, 90);
    if (data.active) {
      isPreviewOpen = true;
      if (visionPreviewCard) visionPreviewCard.style.display = 'flex';
      startVisionStream();
    } else {
      isPreviewOpen = false;
      if (visionPreviewCard) visionPreviewCard.style.display = 'none';
      stopVisionStream();
      updateAvatarEyePosition(90, 90);
    }
  } catch (err) {
    console.error('[Vision Toggle Error]', err);
  }
}

function toggleCameraPreview() {
  triggerHaptic(20);
  isPreviewOpen = !isPreviewOpen;
  if (visionPreviewCard) {
    visionPreviewCard.style.display = isPreviewOpen ? 'flex' : 'none';
  }
  if (btnTogglePreview) {
    btnTogglePreview.classList.toggle('active', isPreviewOpen);
  }
  if (isPreviewOpen) {
    startVisionStream();
  } else {
    stopVisionStream();
  }
}

function startVisionStream() {
  if (visionFeedImg) {
    visionFeedImg.src = `/api/vision/video_feed?t=${Date.now()}`;
  }
}

function stopVisionStream() {
  if (visionFeedImg) {
    visionFeedImg.src = '';
  }
}

async function sendVisionConfig() {
  try {
    await fetch('/api/vision/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        invert_x: chkInvertX ? chkInvertX.checked : true,
        invert_y: chkInvertY ? chkInvertY.checked : false,
        smooth_factor: sliderSmooth ? parseFloat(sliderSmooth.value) : 0.25
      })
    });
  } catch (err) {
    console.error('[Vision Config Error]', err);
  }
}

function triggerHaptic(pattern) {
  if (navigator.vibrate) {
    try { navigator.vibrate(pattern); } catch (e) { }
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

if (btnToggleLight) {
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
}

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
  if (jawLower) {
    const px = Math.max(0, Math.round(((val - 90) / 60) * 14));
    jawLower.style.transform = `translateY(${px}px)`;
  }
  sendManualMove(val, parseInt(sliderEyes.value), parseInt(sliderEyesV ? sliderEyesV.value : 90), 0);
});

sliderEyes.addEventListener('input', (e) => {
  const val = parseInt(e.target.value);
  valEyes.textContent = `${val}°`;
  sendManualMove(parseInt(sliderMouth.value), val, parseInt(sliderEyesV ? sliderEyesV.value : 90), 0);
  updateAvatarEyePosition(val, parseInt(sliderEyesV ? sliderEyesV.value : 90));
});

if (sliderEyesV) {
  sliderEyesV.addEventListener('input', (e) => {
    const val = parseInt(e.target.value);
    if (valEyesV) valEyesV.textContent = `${val}°`;
    sendManualMove(parseInt(sliderMouth.value), parseInt(sliderEyes.value), val, 0);
    updateAvatarEyePosition(parseInt(sliderEyes.value), val);
  });
}

btnTriggerBlink.addEventListener('click', () => {
  triggerBlinkAnimation();
  sendManualMove(
    parseInt(sliderMouth.value),
    parseInt(sliderEyes.value),
    parseInt(sliderEyesV ? sliderEyesV.value : 90),
    1
  );
});

btnCenterAll.addEventListener('click', () => {
  sliderMouth.value = 90;
  sliderEyes.value = 90;
  if (sliderEyesV) sliderEyesV.value = 90;
  valMouth.textContent = '90°';
  valEyes.textContent = '90°';
  if (valEyesV) valEyesV.textContent = '90°';
  if (jawLower) jawLower.style.transform = 'translateY(0px)';
  sendManualMove(90, 90, 90, 0);
  updateAvatarEyePosition(90, 90);
});

function sendManualMove(m, e, ev, b) {
  const payload = {
    event: 'manual_move',
    mouth: m,
    eyes: e,
    eyes_v: ev || 90,
    blink: b,
    light: lightState,
    channel: 0,
    angle: m
  };
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  }
  // Enviar también por HTTP para garantizar despacho instantáneo al servo PCA9685
  fetch('/api/control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).catch(() => { });
}

// Controles del Módulo de Visión Artificial
if (btnToggleVision) btnToggleVision.addEventListener('click', toggleVisionTracking);
if (btnTogglePreview) btnTogglePreview.addEventListener('click', toggleCameraPreview);
if (chkInvertX) chkInvertX.addEventListener('change', sendVisionConfig);
if (chkInvertY) chkInvertY.addEventListener('change', sendVisionConfig);
if (sliderSmooth) sliderSmooth.addEventListener('input', sendVisionConfig);

// Controles de Música de Fondo Loquendo
if (btnToggleBgm) {
  btnToggleBgm.addEventListener('click', () => {
    triggerHaptic(20);
    isBgmEnabled = !isBgmEnabled;
    localStorage.setItem('loquendo_bgm_enabled', isBgmEnabled);
    updateBgmUI();
    if (!isBgmEnabled) {
      stopLoquendoBgm(false);
    } else if (document.body.classList.contains('speaking')) {
      startLoquendoBgm();
    }
  });
}

if (sliderBgmVol) {
  sliderBgmVol.addEventListener('input', (e) => {
    const percent = parseInt(e.target.value);
    bgmVolume = percent / 100;
    localStorage.setItem('loquendo_bgm_vol', bgmVolume);
    if (valBgmVol) valBgmVol.textContent = `${percent}%`;
    if (loquendoBgm && !loquendoBgm.paused) {
      loquendoBgm.volume = bgmVolume;
    }
  });
}

// ============================================================================
// 12. MÓDULO ASISTENTE MANOS LIBRES (TIPO ALEXA / WAKENET)
// ============================================================================
function initAlexaMode() {
  if (!window.isSecureContext) {
    if (alexaDesc) alexaDesc.textContent = "Requiere HTTPS y certificado de confianza en el celular";
    if (btnToggleAlexa) btnToggleAlexa.disabled = true;
    return;
  }
  // Pre-cargar en segundo plano el saludo ultracorto con Loquendo Jorge para que la respuesta sea instantánea
  try {
    const prefetchUrl = `/api/tts?text=${encodeURIComponent("¡Dime!")}&voice=windows_local`;
    const prefetchAudio = new Audio();
    prefetchAudio.src = prefetchUrl;
    prefetchAudio.preload = 'auto';
  } catch (_) { }

  const SpeechRecognition = getSpeechRecognition();
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
    if (window.LocalSpeechRecognition && window.LocalSpeechRecognition.releaseMic) {
      window.LocalSpeechRecognition.releaseMic();
    }
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
      alexaDesc.textContent = 'Comandos: "Dom Dom" · "Oye Libni" · "Oye V"';
      statusCaption.textContent = 'Esperando "Dom Dom", "Oye Libni" u "Oye V"...';
      break;

    case 'WAKE_TRIGGERED':
      alexaModeBar.classList.add('wake-triggered');
      alexaDot.classList.add('hearing');
      if (alexaTitle) alexaTitle.textContent = '¡Oye V!';
      alexaDesc.textContent = '¡Dime!';
      statusCaption.textContent = '¡Comando "Oye V" detectado!';
      break;

    case 'LISTENING_QUERY':
      alexaModeBar.classList.add('wake-triggered');
      alexaDot.classList.add('hearing');
      if (alexaTitle) alexaTitle.textContent = 'Escuchando a vuestra merced';
      alexaDesc.textContent = 'Hablad ahora sin acortadores... XD';
      statusCaption.textContent = 'Escuchando...';
      break;

    case 'PROCESSING':
      alexaDot.classList.add('active');
      if (alexaTitle) alexaTitle.textContent = 'Consultando a la mente maestra';
      alexaDesc.textContent = 'Extrayendo conocimiento aquí... XD';
      statusCaption.textContent = 'Pensando réplica loquendera...';
      break;

    case 'SPEAKING':
      alexaModeBar.classList.add('wake-triggered');
      alexaDot.classList.add('hearing');
      if (alexaTitle) alexaTitle.textContent = 'V respondiendo';
      alexaDesc.textContent = 'Reproduciendo respuesta...';
      break;

    case 'FOLLOW_UP':
      alexaModeBar.classList.add('wake-triggered');
      alexaDot.classList.add('hearing');
      if (alexaTitle) alexaTitle.textContent = 'Conversación abierta';
      alexaDesc.textContent = 'Esperando réplica (7s)...';
      statusCaption.textContent = 'Escuchando réplica (7s)...';
      break;

    case 'DISABLED':
    default:
      if (alexaTitle) alexaTitle.textContent = 'Invocación Manos Libres';
      alexaDesc.textContent = 'Comandos: "Dom Dom" · "Oye Libni" · "Oye V"';
      statusCaption.textContent = 'Listo';
      break;
  }
}

function startWakeWordRecognition() {
  if (!alexaModeEnabled) return;
  stopAllAlexaRecognition();

  const SpeechRecognition = getSpeechRecognition();
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
        const transcript = event.results[i][0].transcript;
        const match = findWakeWord(transcript);
        console.log('[WakeWord] Oído:', JSON.stringify(transcript), match ? `→ activación "${match.wake}" (detectado: "${match.detected}")` : '→ sin activación');
        if (match) {
          const query = match.query;
          if (query) {
            stopAllAlexaRecognition();
            commitQuery(query);
          } else {
            handleWakeWordDetected();
          }
          break;
        }
      }
    };

    wakeWordRecognizer.onerror = (e) => {
      console.warn('[WakeWord Recognition Error]', e.error);
      if (markNativeSpeechFailed(wakeWordRecognizer, e)) {
        setTimeout(startWakeWordRecognition, 300);
        return;
      }
      if (e.error === 'not-allowed') {
        if (alexaModeEnabled) toggleAlexaMode();
        alexaDesc.textContent = e.message || 'Permiso de micrófono denegado. Revisa HTTPS y los permisos.';
        return;
      }
      // Los errores transitorios como 'no-speech' son seguidos de onend automáticamente
    };

    wakeWordRecognizer.onend = () => {
      if (alexaModeEnabled && alexaState === 'LISTENING_WAKE') {
        setTimeout(() => {
          if (alexaModeEnabled && alexaState === 'LISTENING_WAKE') {
            try {
              wakeWordRecognizer.start();
            } catch (err) {
              console.warn('[WakeWord reiniciando nueva sesión]', err);
              startWakeWordRecognition();
            }
          }
        }, 150);
      }
    };

    wakeWordRecognizer.start();
  } catch (err) {
    console.warn('[WakeWord start error]', err);
    setTimeout(() => {
      if (alexaModeEnabled && alexaState === 'LISTENING_WAKE') {
        startWakeWordRecognition();
      }
    }, 400);
  }
}

function stopAllAlexaRecognition() {
  if (followUpTimer) {
    clearTimeout(followUpTimer);
    followUpTimer = null;
  }
  if (wakeWordRecognizer) {
    try {
      wakeWordRecognizer.onend = null;
      wakeWordRecognizer.onerror = null;
      wakeWordRecognizer.stop();
    } catch (_) { }
    wakeWordRecognizer = null;
  }
  if (queryRecognizer) {
    try {
      queryRecognizer.onend = null;
      queryRecognizer.onerror = null;
      queryRecognizer.stop();
    } catch (_) { }
    queryRecognizer = null;
  }
  if (querySilenceTimer) {
    clearTimeout(querySilenceTimer);
    querySilenceTimer = null;
  }
}

async function handleWakeWordDetected() {
  stopAllAlexaRecognition();
  stopLoquendoBgm(true); // Pausar BGM para capturar voz limpia
  stopGreetingAudio();
  setAlexaUIState('WAKE_TRIGGERED');
  triggerHaptic([60, 40, 60]);

  // 1. Notificar al ESP32 / Arduino para que la cabeza reaccione inmediatamente
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ event: 'wake_alert' }));
  }

  // 2. Reproducir inmediatamente el saludo ultracorto (¡Dime!) con la misma voz de Loquendo
  await speakGreetingPrompt("¡Dime!");

  // 3. Pasar a escuchar la consulta del usuario manos libres
  startQueryListening(false, false);
}

function speakGreetingPrompt(text = "¡Dime!") {
  return new Promise((resolve) => {
    stopGreetingAudio();
    if (audioPlayer && !audioPlayer.paused) {
      try { audioPlayer.pause(); } catch (_) { }
    }

    try {
      const selectedVoice = (voiceSelect && voiceSelect.value) ? voiceSelect.value : 'windows_local';
      const audioUrl = `/api/tts?text=${encodeURIComponent(text)}&voice=${selectedVoice}`;
      const audio = new Audio(audioUrl);
      currentGreetingAudio = audio;

      let finished = false;
      const finish = () => {
        if (!finished) {
          finished = true;
          stopGreetingAudio();
          resolve();
        }
      };

      audio.onended = finish;
      audio.onerror = (err) => {
        console.warn('[Loquendo Greeting Error]', err);
        finish();
      };

      // Tiempo límite de seguridad generoso para permitir carga y reproducción completa
      setTimeout(finish, 3000);

      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          console.warn('[Loquendo Greeting Play Blocked]', err);
          finish();
        });
      }
    } catch (err) {
      console.warn('[Loquendo Greeting Exception]', err);
      stopGreetingAudio();
      resolve();
    }
  });
}

function startQueryListening(isBargeIn = false, isFollowUp = false) {
  stopGreetingAudio(); // Garantizar silencio antes de activar el micrófono
  if (!alexaModeEnabled) return;

  if (!isFollowUp) {
    setAlexaUIState('LISTENING_QUERY');
  }

  const SpeechRecognition = getSpeechRecognition();
  if (!SpeechRecognition) return;

  // Si ya hay un queryRecognizer activo, detenerlo limpiamente antes de reiniciar
  if (queryRecognizer) {
    try {
      queryRecognizer.onend = null;
      queryRecognizer.onerror = null;
      queryRecognizer.stop();
    } catch (_) { }
    queryRecognizer = null;
  }

  try {
    queryRecognizer = new SpeechRecognition();
    queryRecognizer.continuous = true;
    queryRecognizer.interimResults = true;
    queryRecognizer.lang = 'es-ES';

    let finalTranscript = '';
    let speechDetected = false;

    // Timeout de seguridad si el usuario no dice nada (7 segundos)
    let queryTimeout = setTimeout(() => {
      if (alexaModeEnabled && !speechDetected && (alexaState === 'LISTENING_QUERY' || alexaState === 'FOLLOW_UP')) {
        console.log('[Alexa] Tiempo de espera de consulta agotado sin voz.');
        stopAllAlexaRecognition();
        startWakeWordRecognition();
      }
    }, 7000);

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
      if (currentText && currentText.length > 1) {
        speechDetected = true;
        if (queryTimeout) {
          clearTimeout(queryTimeout);
          queryTimeout = null;
        }
        if (followUpTimer) {
          clearTimeout(followUpTimer);
          followUpTimer = null;
        }

        // Pasar a estado de escucha activa
        if (alexaState !== 'LISTENING_QUERY') {
          setAlexaUIState('LISTENING_QUERY');
        }

        statusCaption.textContent = `"${currentText}"`;

        // Temporizador de silencio: 1.2 segundos sin hablar para despachar consulta
        if (querySilenceTimer) clearTimeout(querySilenceTimer);
        querySilenceTimer = setTimeout(() => {
          commitQuery(currentText);
        }, 1200);
      }
    };

    queryRecognizer.onerror = (e) => {
      console.warn('[Query Recognition Error]', e.error);
      if (finalTranscript.trim()) {
        commitQuery(finalTranscript.trim());
      }
    };

    queryRecognizer.onend = () => {
      if (queryTimeout) {
        clearTimeout(queryTimeout);
        queryTimeout = null;
      }
      if (finalTranscript.trim()) {
        commitQuery(finalTranscript.trim());
      } else if (alexaModeEnabled) {
        if (alexaState === 'FOLLOW_UP' && followUpTimer !== null) {
          setTimeout(() => {
            if (alexaModeEnabled && alexaState === 'FOLLOW_UP') {
              try { queryRecognizer.start(); } catch (_) { startQueryListening(false, true); }
            }
          }, 150);
        } else if (alexaState === 'LISTENING_QUERY') {
          // Si no se escuchó ninguna voz durante la consulta, volver a esperar "Oye V"
          stopAllAlexaRecognition();
          startWakeWordRecognition();
        }
      }
    };

    queryRecognizer.start();
  } catch (err) {
    console.warn('[Query Start Error]', err);
    if (alexaModeEnabled) {
      stopAllAlexaRecognition();
      startWakeWordRecognition();
    }
  }
}

async function commitQuery(text) {
  if (followUpTimer) {
    clearTimeout(followUpTimer);
    followUpTimer = null;
  }
  stopAllAlexaRecognition();

  if (!text || text.trim() === '') {
    onPlaybackCompletedAlexa();
    return;
  }

  // Filtrar posibles invocaciones al inicio de la frase (ej: "oye libni dime la hora", "dom dom enciende la luz")
  let cleanText = text.trim();
  cleanText = cleanText.replace(/^(dom\s*dom|don\s*don|dum\s*dum|tom\s*tom|ton\s*ton|domdom|dondon|dom|oye\s+libni|hola\s+libni|libni|livni|lipni|libny|livny|lidia|lily|lili|living|oye\s+lidia|oye\s+lily|oye\s+living|oye\s+v|oye\s+uve|oye\s+ve|oye\s+b|oye\s+be|hola\s+v|hola\s+uve|v\s+de\s+venganza|venganza|uve|oye\s+robot|hola\s+robot|robot|oye\s+google|hola\s+google|google|despierta|oye\s+ciclope|oye\s+asistente|asistente)\s*[,:]?\s*/i, '').trim();
  if (!cleanText) cleanText = text.trim();

  setAlexaUIState('PROCESSING');
  await sendQueryToAI(cleanText);
}

function onPlaybackCompletedAlexa() {
  if (!alexaModeEnabled) return;

  if (followUpTimer) {
    clearTimeout(followUpTimer);
    followUpTimer = null;
  }

  // Cambiar estado a FOLLOW_UP (conversación abierta tras terminar la respuesta)
  setAlexaUIState('FOLLOW_UP');

  // Activar la escucha limpia para la réplica del usuario
  startQueryListening(false, true);

  // Ventana de seguimiento: 7 segundos sin hablar para volver a esperar "Oye V"
  followUpTimer = setTimeout(() => {
    if (alexaModeEnabled && alexaState === 'FOLLOW_UP') {
      console.log('[Alexa] Ventana de 7 segundos expirada. Volviendo a esperar activación.');
      stopAllAlexaRecognition();
      startWakeWordRecognition();
    }
  }, 7000);
}

// INICIAR AL CARGAR
window.addEventListener('DOMContentLoaded', () => {
  initWebSocket();
  checkBackendStatus();
  initAlexaMode();
  resizeCanvas();
  updateBgmUI();
});
