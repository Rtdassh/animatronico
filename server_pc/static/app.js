/**
 * ============================================================================
 * CÍCLOPE AI · CONTROLADOR DE INTERFAZ MÓVIL (MICRÓFONO & ALTAVOZ)
 * ============================================================================
 * Implementa:
 *   1. Web Speech API: Captura de voz desde el micrófono del teléfono.
 *   2. Web Audio API: Sincronización labial (Lip-Sync) analizando la bocina.
 *   3. WebSocket: Enlace bidireccional de baja latencia con la PC y ESP32.
 *   4. Renderizado háptico y cinemático de la cara animatrónica virtual.
 * ============================================================================
 */

// Elementos del DOM
const esp32Dot = document.getElementById('esp32Dot');
const esp32StatusText = document.getElementById('esp32StatusText');
const tempValue = document.getElementById('tempValue');
const humValue = document.getElementById('humValue');
const btnToggleLight = document.getElementById('btnToggleLight');
const lightText = document.getElementById('lightText');

const statusCaption = document.getElementById('statusCaption');
const subCaption = document.getElementById('subCaption');
const btnMic = document.getElementById('btnMic');
const inputQuery = document.getElementById('inputQuery');
const btnSendText = document.getElementById('btnSendText');

const eyeball = document.getElementById('eyeball');
const pupil = document.getElementById('pupil');
const eyesSocket = document.querySelector('.eyes-socket');
const jawLower = document.getElementById('jawLower');
const audioPlayer = document.getElementById('audioPlayer');

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
let recognition = null;
let audioContext = null;
let analyser = null;
let audioSource = null;
let isAudioContextReady = false;
let lipSyncInterval = null;
let lightState = 0;

// ============================================================================
// 1. GESTIÓN DEL ENLACE WEBSOCKET CON LA PC
// ============================================================================
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/mobile`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log('[WS] Conectado al servidor de la PC');
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);

      // Estado inicial
      if (data.type === 'init_state') {
        updateTelemetry(data.temperature, data.humidity);
        updateLightState(data.light_state);
        updateESP32Status(data.esp32_connected);
      }
      // Telemetría en tiempo real desde el Arduino Uno
      else if (data.type === 'telemetry') {
        updateTelemetry(data.temperature, data.humidity);
        if (data.light_state !== undefined) updateLightState(data.light_state);
      }
      // Estado de conexión del ESP32
      else if (data.type === 'esp32_status') {
        updateESP32Status(data.connected);
      }
    } catch (e) {
      console.error('[WS Error] Error procesando mensaje:', e);
    }
  };

  ws.onclose = () => {
    console.warn('[WS] Desconectado. Reconectando en 2 segundos...');
    updateESP32Status(false);
    setTimeout(initWebSocket, 2000);
  };
}

function updateTelemetry(temp, hum) {
  if (temp !== undefined) tempValue.textContent = `${Number(temp).toFixed(1)} °C`;
  if (hum !== undefined) humValue.textContent = `${Number(hum).toFixed(0)} %`;
}

function updateLightState(state) {
  lightState = state;
  if (lightState === 1) {
    btnToggleLight.classList.add('active');
    lightText.textContent = 'Luz: ON';
  } else {
    btnToggleLight.classList.remove('active');
    lightText.textContent = 'Luz: OFF';
  }
}

function updateESP32Status(connected) {
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
// 2. WEB AUDIO API & SINCRONIZACIÓN LABIAL (LIP-SYNC POR BOCINA)
// ============================================================================
function setupWebAudio() {
  if (isAudioContextReady) return;

  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    audioContext = new AudioContextClass();

    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.4;

    audioSource = audioContext.createMediaElementSource(audioPlayer);
    audioSource.connect(analyser);
    analyser.connect(audioContext.destination);

    isAudioContextReady = true;
    console.log('[Audio] Web Audio API inicializada para análisis de energía.');
  } catch (err) {
    console.warn('[Audio] No se pudo inicializar Web Audio:', err);
  }
}

// Desbloquear audio en móviles con el primer toque del usuario
document.addEventListener('click', () => {
  if (audioContext && audioContext.state === 'suspended') {
    audioContext.resume();
  }
}, { once: true });

function startLipSyncAnalysis() {
  if (!analyser) return;

  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  let lastMouthAngle = 90;

  document.body.classList.add('speaking');

  function analyzeLoop() {
    if (audioPlayer.paused || audioPlayer.ended) {
      document.body.classList.remove('speaking');
      jawLower.style.transform = 'translateY(0px)';
      sendLipsyncFrame(90);
      return;
    }

    analyser.getByteFrequencyData(dataArray);

    // Calcular energía en frecuencias vocales (rango medio 100 - 3000 Hz)
    let sum = 0;
    const voiceBins = Math.min(bufferLength, 32);
    for (let i = 2; i < voiceBins; i++) {
      sum += dataArray[i];
    }
    const avgEnergy = sum / (voiceBins - 2);

    // Mapeo no lineal: 0-255 de energía a ángulo de 90° (cerrado) a 128° (abierto)
    let mouthAngle = 90;
    let jawPixels = 0;

    if (avgEnergy > 15) {
      const normalized = Math.min(1.0, (avgEnergy - 15) / 110);
      mouthAngle = Math.round(90 + normalized * 38);
      jawPixels = Math.round(normalized * 14);
    }

    // Suavizado para evitar brincos
    mouthAngle = Math.round(lastMouthAngle * 0.3 + mouthAngle * 0.7);
    lastMouthAngle = mouthAngle;

    // 1. Mover mandíbula en la pantalla del celular
    jawLower.style.transform = `translateY(${jawPixels}px)`;

    // 2. Enviar ángulo al ESP32 a través del servidor
    sendLipsyncFrame(mouthAngle);

    requestAnimationFrame(analyzeLoop);
  }

  requestAnimationFrame(analyzeLoop);
}

let lastSentTime = 0;
function sendLipsyncFrame(mouthAngle) {
  const now = Date.now();
  if (now - lastSentTime < 45 && mouthAngle !== 90) return; // Muestreo cada 45 ms
  lastSentTime = now;

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      event: 'lipsync_frame',
      mouth: mouthAngle
    }));
  }
}

// Reproducir audio recibido de la IA por la bocina del celular
function playVoiceResponse(audioUrl, responseText) {
  setupWebAudio();
  if (audioContext && audioContext.state === 'suspended') {
    audioContext.resume();
  }

  statusCaption.textContent = responseText;
  subCaption.textContent = "🔊 Reproduciendo por la bocina del celular...";

  audioPlayer.src = audioUrl;
  audioPlayer.play().then(() => {
    startLipSyncAnalysis();
  }).catch((err) => {
    console.error("[Audio] Error al reproducir audio:", err);
    subCaption.textContent = "Toca la pantalla para activar el audio de la bocina.";
  });

  audioPlayer.onended = () => {
    statusCaption.textContent = "Listo. Puedes volver a hablar.";
    subCaption.textContent = "Presiona el botón de micrófono";
    document.body.classList.remove('speaking');
    jawLower.style.transform = 'translateY(0px)';
    sendLipsyncFrame(90);
  };
}

// ============================================================================
// 3. WEB SPEECH API (MICRÓFONO DEL CELULAR)
// ============================================================================
function initSpeechRecognition() {
  const SpeechRecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognitionClass) {
    console.warn('[Speech] Web Speech API no disponible en este navegador.');
    return null;
  }

  const rec = new SpeechRecognitionClass();
  rec.lang = 'es-MX'; // Español latinoamericano natural
  rec.continuous = false;
  rec.interimResults = false;

  rec.onstart = () => {
    isRecording = true;
    btnMic.classList.add('recording');
    statusCaption.textContent = "🎙️ Escuchando tu voz...";
    subCaption.textContent = "Habla con claridad cerca del micrófono";
    triggerHaptic(50);
  };

  rec.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    console.log('[Speech] Transcripción:', transcript);
    sendQueryToAI(transcript);
  };

  rec.onerror = (event) => {
    console.error('[Speech Error]', event.error);
    isRecording = false;
    btnMic.classList.remove('recording');
    statusCaption.textContent = "No alcancé a escucharte bien.";
    subCaption.textContent = "Toca el micrófono e inténtalo de nuevo";
    triggerHaptic([30, 50, 30]);
  };

  rec.onend = () => {
    isRecording = false;
    btnMic.classList.remove('recording');
  };

  return rec;
}

recognition = initSpeechRecognition();

function toggleMicrophone() {
  triggerHaptic(30);

  // Si ya se está reproduciendo audio, detenerlo
  if (!audioPlayer.paused) {
    audioPlayer.pause();
    document.body.classList.remove('speaking');
  }

  if (!recognition) {
    // Si el navegador no soporta Web Speech, enfocar caja de texto
    inputQuery.focus();
    statusCaption.textContent = "Escribe tu pregunta:";
    return;
  }

  if (isRecording) {
    recognition.stop();
  } else {
    try {
      recognition.start();
    } catch (e) {
      console.warn("Reinicio de reconocimiento forzado:", e);
      recognition.stop();
    }
  }
}

// ============================================================================
// 4. CONSULTA A LA IA (FASTAPI SERVER)
// ============================================================================
async function sendQueryToAI(text) {
  if (!text || text.trim() === '') return;

  statusCaption.textContent = `"${text}"`;
  subCaption.textContent = "🧠 Procesando con inteligencia artificial...";
  triggerHaptic(30);

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text.trim() })
    });

    if (!response.ok) throw new Error("Falla en el servidor de IA");

    const data = await response.json();
    console.log('[AI Response]', data);

    if (data.light_state !== undefined) {
      updateLightState(data.light_state);
    }

    // Reproducir la voz resultante por el altavoz del celular
    playVoiceResponse(data.audio_url, data.ai_response);

  } catch (err) {
    console.error('[Fetch Error]', err);
    statusCaption.textContent = "Error al conectar con la PC.";
    subCaption.textContent = "Verifica que el servidor en Python esté en ejecución.";
  }
}

// ============================================================================
// 5. ANIMACIONES VISUALES (OJOS Y PARPADEO VIRTUAL)
// ============================================================================
function triggerBlinkAnimation() {
  eyesSocket.classList.add('blink');
  setTimeout(() => {
    eyesSocket.classList.remove('blink');
  }, 140);
}

// Parpadeo virtual cada 4 a 6 segundos
setInterval(() => {
  if (Math.random() > 0.3) {
    triggerBlinkAnimation();
  }
}, 4500);

// Miradas sutiles en la pantalla del celular
setInterval(() => {
  if (!document.body.classList.contains('speaking')) {
    const offsetX = (Math.random() - 0.5) * 16;
    const offsetY = (Math.random() - 0.5) * 8;
    eyeball.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
  }
}, 3000);

// Háptica táctil para teléfonos móviles
function triggerHaptic(pattern) {
  if (navigator.vibrate) {
    try { navigator.vibrate(pattern); } catch (e) {}
  }
}

// ============================================================================
// 6. EVENT LISTENERS DE LA INTERFAZ
// ============================================================================
btnMic.addEventListener('click', toggleMicrophone);

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

// Chips de sugerencia rápida
document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const prompt = chip.getAttribute('data-prompt');
    sendQueryToAI(prompt);
  });
});

// Control de luz desde el botón superior
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

// Panel Manual de Servos
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
});

