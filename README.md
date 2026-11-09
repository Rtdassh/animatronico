# 🤖 Sistema Animatrónico Inteligente con Procesamiento Local, Visión Computacional y Modo Manos Libres

Sistema robótico interactivo de 4 niveles que desacopla el procesamiento de Inteligencia Artificial (LLM local Qwen 2.5, síntesis de voz neuronal / Loquendo y visión computacional en tiempo real con OpenCV), la pasarela de red inalámbrica Wi-Fi / WebSockets y el control físico en tiempo real determinista.

---

## 🏛️ Arquitectura del Sistema

```text
 ┌──────────────────────┐    Wi-Fi / HTTPS   ┌───────────────────────────────┐
 │ 1. SMARTPHONE        │ <----------------> │ 2. PC LOCAL                   │
 │ • Modo Manos Libres  │                    │ • Ollama (Qwen 2.5:7b Local)  │
 │ • Micrófono Continuo │                    │ • Loquendo TTS / Voicebox     │
 │ • WakeNet / Hotword  │                    │ • Visión Facial OpenCV 30 FPS │
 │ • Altavoz de Salida  │                    │ • Túnel Cloudflare HTTPS      │
 │ • Virtual Lip-Sync   │                    │ • FastAPI / WebSockets        │
 └──────────────────────┘                    └───────────────────────────────┘
                                                             │
                                                    WebSocket / Wi-Fi
                                                   (Latencia <15 ms)
                                                             v
 ┌──────────────────────┐    Hardware UART   ┌───────────────────────────────┐
 │ 4. ARDUINO UNO R3    │ <----------------- │ 3. ESP32 DEVKIT V1            │
 │ • PCA9685 (6x Servos)│(38400 bps / 3.3V)  │ • Pasarela Wi-Fi WebSocket    │
 │ • Mecanismo Ocular   │ Latest-Cmd-Wins    │ • Hardware UART2 (GPIO 16/17) │
 │ • Bus I2C LM75A      │                    │ • Buffer no bloqueante        │
 │ • Sensor DHT11       │                    └───────────────────────────────┘
 │ • Luz Pin D7         │
 └──────────────────────┘
```

1. **Smartphone (Nodo de Audio Manos Libres Tipo Alexa):** El celular funciona como micrófono continuo y altavoz inalámbrico. El usuario puede operar sin tocar la pantalla: detecta la palabra clave ("Oye Robot" o "Alexa"), responde de inmediato con "¿En qué te ayudo?", captura la pregunta por voz y reproduce la respuesta de la IA por su altavoz.
2. **PC Local (Cerebro Central):** Servidor asíncrono en Python con FastAPI. Conecta con el modelo local **Qwen 2.5 (7B)** vía Ollama en hilos no bloqueantes, sintetiza voz neuronal con el esqueleto de **Voicebox** o las voces de **Loquendo** (Jorge, Carlos, Carmen) con caché en disco, gestiona el pipeline de visión artificial a 30+ FPS y administra la telemetría ambiental.
3. **ESP32 DevKit V1 (Pasarela Inalámbrica):** Cliente WebSocket de alta velocidad conectado a la PC. Reenvía instrucciones de movimiento por `UART2` al Arduino Uno a 38400 baudios con política *Latest-Command-Wins* para evitar saturación de colas.
4. **Arduino Uno R3 (Controlador de Tiempo Real):** Módulo esclavo libre de interrupciones Wi-Fi que ejecuta un bucle determinista con `millis()`. Gobierna por bus I2C al chip **PCA9685** para 6 servomotores del mecanismo ocular ε3.2 (Will Cogley #1184807) sin temblores (*jitter*), genera parpadeo autónomo, micro-sacadas oculares y reporta telemetría del sensor **LM75A** y **DHT11**.

---

## 🚀 Guía de Puesta en Marcha

### 1. Iniciar el Modelo Local con Ollama
Asegúrate de tener **Ollama** ejecutándose en tu PC con el modelo **`qwen2.5:7b`**:
```bash
ollama run qwen2.5:7b
```

### 2. Iniciar el Servidor Central
Ejecuta el archivo **`start.bat`** en la raíz del proyecto (o desde la consola):
```bash
.\start.bat
```
El servidor automáticamente:
- Verificará la conexión con Ollama.
- Iniciará el servidor FastAPI en el puerto 8000.
- Creará un túnel seguro **Cloudflare HTTPS** (`https://*.trycloudflare.com`).
- Generará un **código QR en la terminal**.

### 3. Conectar el Celular en Modo Manos Libres ("Oye V")
1. Abre la cámara de tu celular y **escanea el código QR**.
2. Al ingresar en Chrome o Safari móvil, pulsa una vez sobre **"Iniciar Manos Libres"** para habilitar el micrófono y altavoz del dispositivo.
3. Coloca el teléfono sobre la mesa. A partir de este momento **no necesitas tocar la pantalla**.
4. Di en voz alta: **"Oye V"** (u **"Oye Uve"**).
5. El teléfono responderá de inmediato: **"¡Dime!"** con la voz de Loquendo seleccionada y la cabeza animatrónica mirará al frente encendiendo su luz.
6. Formula tu pregunta directamente. La IA con personalidad de **V de Venganza** responderá con estilo elocuente y humor clásico de Loquendo (*"Yo no lo descargo porque ya lo tengo"*, *"El link está en la descripción por Mediafire"*, `JAJAJAJA`, `XD XD XD`).
7. **Modo Conversacional Continuo y Barge-in:**
   - Durante la respuesta de la IA puedes interrumpir en cualquier momento hablando.
   - Tras terminar de hablar, la sesión permanece abierta durante **3 segundos** esperando tu réplica sin requerir volver a decir la palabra clave. Si transcurren 3 segundos en silencio, la sesión se cierra automáticamente hasta la próxima invocación.
8. Opcionalmente, puedes activar la **🎵 Música Loquendo** de fondo con volumen graduable.

### 4. 👁️ Seguimiento Facial (Visión Artificial a 30+ FPS)
El sistema incluye seguimiento facial en tiempo real usando la cámara web integrada o USB de la computadora:
* **Desde la Interfaz Web / Celular:**
  1. En la aplicación web verás la tarjeta **Visión Artificial**.
  2. Haz clic en **"Iniciar Visión"** para activar la cámara de la PC.
  3. Haz clic en **"📷 Cámara"** para desplegar el video en vivo con bounding box, vector de seguimiento y telemetría de FPS.
  4. La cabeza animatrónica moverá sus servos (Pan EH: $60^\circ\text{--}120^\circ$, Tilt EV: $70^\circ\text{--}110^\circ$) siguiendo tu rostro mediante filtrado exponencial (EMA) y zona muerta anti-vibración (*anti-jitter*).
* **Herramienta de Prueba y Calibración Rápida:**
  ```bash
  python server_pc/test_vision.py
  ```
