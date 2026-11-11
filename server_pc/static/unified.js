const workspaceButtons = document.querySelectorAll('[data-workspace]');
const assistantWorkspace = document.getElementById('assistantWorkspace');
const hardwareWorkspace = document.getElementById('hardwareWorkspace');
workspaceButtons.forEach(button => button.addEventListener('click', () => {
  const hardware = button.dataset.workspace === 'hardware';
  assistantWorkspace.hidden = hardware;
  hardwareWorkspace.hidden = !hardware;
  workspaceButtons.forEach(item => item.setAttribute('aria-selected', String(item === button)));
  if (hardware && !document.getElementById('hardwareFrame').src) {
    document.getElementById('hardwareFrame').src = '/hardware';
  }
}));

async function integrationHealth() {
  const label = document.getElementById('integrationStatus');
  try {
    const [speech, hardware, network] = await Promise.all([
      fetch('/api/speech/status').then(r => r.json()),
      fetch('/api/hardware/status').then(r => r.json()),
      fetch('/api/network').then(r => r.json())
    ]);
    label.textContent = (hardware.connected ? 'Arduino conectado' : 'Esperando Arduino') +
      ' · ' + (speech.ready ? 'Voz: ' + ({whisper: 'Whisper local', groq: 'Whisper (Groq)', google: 'Google', vosk: 'Vosk local'}[speech.engine] || speech.engine) : 'Reconocimiento de voz no disponible') +
      ' · ' + (window.isSecureContext ? 'Micrófono HTTPS' : 'Abre HTTPS para usar el micrófono') +
      ' · ' + (network.shared ? 'Internet por ESP32' : 'Funciones locales');
    document.getElementById('connectionHelp').hidden = window.isSecureContext;
  } catch (_) { label.textContent = 'Servidor no disponible. Revisa la computadora.'; }
}
integrationHealth();
setInterval(integrationHealth, 5000);
