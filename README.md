# 🤖 Sistema Animatrónico Inteligente con Procesamiento Local y Visión Ambiental

Sistema robótico interactivo de 4 niveles que desacopla el procesamiento de Inteligencia Artificial (LLM local y síntesis de voz Loquendo), la pasarela de red inalámbrica y el control físico en tiempo real determinista.

---

## 🏛️ Arquitectura del Sistema

```text
 ┌──────────────────────┐    Wi-Fi / HTTPS   ┌───────────────────────────────┐
 │ 1. SMARTPHONE        │ <----------------> │ 2. PC LOCAL                   │
 │ • Micrófono Web Audio│                    │ • Ollama (Qwen 2.5:7b Local)  │
 │ • Altavoz de voz     │                    │ • Loquendo TTS (Jorge/Carlos) │
 │ • Web Audio Lip-Sync │                    │ • STT Motor SpeechRecognition │
 └──────────────────────┘                    │ • Túnel Cloudflare HTTPS      │
                                             │ • FastAPI / WebSockets        │
                                             └───────────────────────────────┘
                                                             │
                                                    WebSocket / Wi-Fi
                                                             │
                                                             v
 ┌──────────────────────┐    Hardware UART   ┌───────────────────────────────┐
 │ 4. ARDUINO UNO       │ <----------------- │ 3. ESP32 DEVKIT V1            │
 │ • 3x SG90 PWM        │ (9600 bps / 3.3V)  │ • Pasarela WebSocket          │
 │ • Bus I2C LM75A      │                    │ • Hardware UART2              │
 │ • Sensor DHT11       │                    │ • Cero latencia               │
 └──────────────────────┘                    └───────────────────────────────┘
```

1. **Smartphone (Micrófono & Altavoz Inalámbrico):** Interfaz web táctil con grabación directa en PCM WAV (16kHz), analizador espectral (Web Audio API) y reproducción de audio por el altavoz del teléfono. Calcula la envolvente fonética para una modulación labial (*Lip-Sync*) con cero desfase y control de servos físico en tiempo real.
2. **PC Local (Cerebro Central):** Servidor asíncrono en Python con FastAPI. Conecta con el modelo local **Qwen 2.5 (7B)** vía Ollama, sintetiza la legendaria voz de **Loquendo** (Jorge, Carlos, Carmen) con caché en disco y administra la telemetría ambiental.
3. **ESP32 DevKit V1 (Pasarela Inalámbrica):** Cliente WebSocket de alta velocidad conectado a la PC. Reenvía instrucciones de movimiento por `Serial2` al Arduino Uno en menos de $2\text{ ms}$.
4. **Arduino Uno R3 (Controlador de Tiempo Real):** Módulo esclavo libre de interrupciones Wi-Fi que ejecuta un bucle determinista con `millis()`. Acciona los 3 servos SG90 (ojos, párpados, mandíbula) sin temblores (*jitter*), genera parpadeo autónomo y reporta telemetría periódica del sensor I2C **LM75A** y sensor de humedad **DHT11**.

---

## 📁 Estructura del Repositorio

```text
animatronico/
├── docs/                                  # Documentación técnica y planos eléctricos
│   ├── DOC_01_Arduino_Uno_Firmware.md    # Especificación de puertos y firmware Arduino
│   ├── DOC_02_ESP32_DevKit_Firmware.md   # Especificación de red y pasarela ESP32
│   ├── DOC_03_App_Movil_y_Servidor_PC.md # Guía del servidor y aplicación móvil
│   ├── plano_circuito_animatronico.png   # Plano unifilar esquemático en alta resolución
│   └── plano_interactivo_circuito.html   # Visor interactivo web del circuito con tablas
│
├── firmware/                              # Código fuente embebido
│   ├── arduino_uno/
│   │   └── arduino_uno_animatronico.ino  # Firmware Arduino Uno (LM75A + DHT11 + 3x Servos)
│   └── esp32_devkit/
│       └── esp32_puente_websocket.ino    # Firmware ESP32 (Cliente WebSocket <-> UART2)
│
├── server_pc/                             # Servidor local y aplicación móvil táctil
│   ├── app.py                            # Servidor FastAPI + WebSockets + Ollama + Loquendo TTS
│   ├── run_server.py                     # Lanzador con túnel Cloudflare HTTPS y QR en consola
│   ├── start.py                          # Alias de conveniencia para run_server.py
│   ├── start.bat                         # Lanzador por lotes para Windows
│   ├── ollama_client.py                  # Cliente de inferencia Qwen 2.5 local con telemetría
│   ├── tts_loquendo.py                   # Motor Loquendo (Jorge, Carlos, Carmen) con caché MD5
│   ├── stt_engine.py                     # Reconocimiento de voz a texto (WAV 16kHz)
│   ├── requirements.txt                  # Dependencias de Python
│   ├── bin/                              # Binarios de soporte (cloudflared.exe para HTTPS móvil)
│   ├── audio/                            # Almacén en caché de audios sintetizados
│   └── static/                           # Aplicación Web Móvil (HTML5 / CSS / JS)
│       ├── index.html                    # Interfaz táctil con simulador facial en vivo y visualizador
│       ├── style.css                     # Estilos oscuros responsivos
│       └── app.js                        # Control de audio, micrófono y Lip-Sync
│
├── tools/                                 # Scripts de utilidad
│   └── render_plano_circuito.py          # Generador programático del plano esquemático
│
├── start.bat                              # Lanzador de un clic para Windows
├── .gitignore                             # Reglas de exclusión de archivos
└── README.md                              # Documentación principal del proyecto
```

---

## ⚡ Conexiones y Mapa de Pines

### Arduino Uno R3
| Pin | Función | Destino | Nivel Lógico |
| :--- | :--- | :--- | :--- |
| **`D2`** | SoftwareSerial RX | ESP32 `GPIO 17` (`TX2`) | 3.3V (Entrada directa segura) |
| **`D3`** | SoftwareSerial TX | Divisor resistivo ($1\text{ k}\Omega / 2\text{ k}\Omega$) $\to$ ESP32 `GPIO 16` | 5.0V (Atenuado a 3.33V) |
| **`D4`** | DAT / OUT | Pin de datos sensor de humedad **DHT11** | 5.0V Lógico |
| **`D7`** | Control Luz | Resistencia $220\,\Omega$ $\to$ Ánodo LED (o módulo relé) | 5.0V Salida |
| **`D9`** | PWM Servo Ojos | Cable naranja Servo 1 (Giro horizontal: $60^\circ$ a $120^\circ$) | 5.0V PWM |
| **`D10`** | PWM Servo Párpados| Cable naranja Servo 2 (Apertura: $50^\circ$ a $100^\circ$) | 5.0V PWM |
| **`D11`** | PWM Servo Boca | Cable naranja Servo 3 (Mandíbula: $90^\circ$ a $130^\circ$) | 5.0V PWM |
| **`A4`** | I2C SDA | Pin `SDA` sensor de temperatura digital **LM75A** | Bidireccional I2C (`0x48`) |
| **`A5`** | I2C SCL | Pin `SCL` sensor de temperatura digital **LM75A** | Reloj I2C |
| **`5V`** | VCC Lógica | Alimentación exclusiva de sensores LM75A y DHT11 | 5.0V Lógico |
| **`GND`** | Tierra | Riel negativo protoboard (unido a ESP32 y fuente externa) | 0.0V Común |

### ESP32 DevKit V1
| Pin | Función | Destino | Nivel Lógico |
| :--- | :--- | :--- | :--- |
| **`GPIO 17`** | UART2 TX | Arduino `Pin D2` (SoftwareSerial RX) | 3.3V Salida |
| **`GPIO 16`** | UART2 RX | Nodo central del divisor resistivo ($1\text{ k}\Omega / 2\text{ k}\Omega$) | 3.33V Entrada |
| **`GPIO 2`**  | LED Builtin | Indicador de estado de enlace de red | Salida |
| **`GND`**      | Tierra | Riel común de tierra del sistema | 0.0V Común |

> [!CAUTION]
> **ALIMENTACIÓN DE LOS SERVOS:** Los 3 servomotores SG90 se alimentan **exclusivamente** desde una fuente externa regulada de 5V (2A a 3A) con un capacitor electrolítico de $1000\,\mu\text{F}$ en paralelo. Nunca alimentes los servos desde los 5V del Arduino ni del ESP32.

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

### 3. Conectar el Celular
1. Abre la cámara de tu celular y **escanea el código QR**.
2. Al ingresar en Chrome o Safari móvil, concede permisos de micrófono.
3. Elige la voz que prefieras: **Jorge (Loquendo 🇪🇸)**, **Carlos (Loquendo 🇲🇽)** o **Carmen (Loquendo 🇪🇸)**.
4. Toca el botón del micrófono para hablar. La respuesta será generada por **Qwen 2.5 local**, leída por **Loquendo** y tu animatrónico moverá su mandíbula en tiempo real con cero retraso.
