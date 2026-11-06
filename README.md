# 🤖 Sistema Animatrónico Inteligente con Procesamiento Local y Visión Ambiental

Sistema robótico interactivo de 4 niveles que desacopla el procesamiento de Inteligencia Artificial (LLM local y síntesis de voz), la pasarela de red inalámbrica y el control físico en tiempo real determinista.

---

## 🏛️ Arquitectura del Sistema

```text
 ┌─────────────────┐       Wi-Fi       ┌────────────────────────┐
 │ 1. SMARTPHONE   │ <---------------> │ 2. PC LOCAL            │
 │ • Micrófono web │                   │ • Ollama (Qwen 2.5 1B) │
 │ • Altavoz audio │                   │ • edge-tts             │
 │ • Web Audio API │                   │ • FastAPI / WebSockets │
 └─────────────────┘                   └────────────────────────┘
                                                    │
                                           WebSocket / Wi-Fi
                                                    │
                                                    v
 ┌─────────────────┐    Hardware UART  ┌────────────────────────┐
 │ 4. ARDUINO UNO  │ <---------------- │ 3. ESP32 DEVKIT V1     │
 │ • 3x SG90 PWM   │ (9600 bps / 3.3V) │ • Pasarela WebSocket   │
 │ • Bus I2C LM75A │                   │ • Hardware UART2       │
 │ • Sensor DHT11  │                   │ • Cero latencia        │
 └─────────────────┘                   └────────────────────────┘
```

1. **Smartphone (Micrófono & Altavoz Inalámbrico):** Interfaz web táctil con reconocimiento de voz nativo (Web Speech API) y reproducción de audio por el altavoz del teléfono. Su analizador espectral (Web Audio API) calcula la envolvente fonética para una modulación labial (*Lip-Sync*) con cero desfase.
2. **PC Local (Cerebro Central):** Servidor asíncrono en Python con FastAPI. Conecta con el modelo local **Qwen 2.5 (1.5B)** vía Ollama, sintetiza la voz en español con **edge-tts** y administra la telemetría ambiental.
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
│   ├── app.py                            # Servidor FastAPI + WebSockets + Ollama + TTS
│   ├── run_server.py                     # Lanzador con código QR en consola para teléfonos
│   ├── requirements.txt                  # Dependencias de Python
│   └── static/                           # Aplicación Web Móvil (HTML5 / CSS / JS)
│       ├── index.html                    # Interfaz táctil con simulador facial en vivo
│       ├── style.css                     # Estilos oscuros responsivos
│       └── app.js                        # Control de audio, micrófono y Lip-Sync
│
├── tools/                                 # Scripts de utilidad
│   └── render_plano_circuito.py          # Generador programático del plano esquemático
│
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

### 1. Carga de Firmwares
1. **Arduino Uno:** Abre `firmware/arduino_uno/arduino_uno_animatronico.ino` en el Arduino IDE e instálalo en la placa.
2. **ESP32 DevKit:** Abre `firmware/esp32_devkit/esp32_puente_websocket.ino`, configura las credenciales de tu red Wi-Fi y la dirección IP de tu computadora, y súbelo a la placa.

### 2. Iniciar el Servidor y la Aplicación Móvil
1. Instala las dependencias de Python en tu PC:
   ```bash
   cd server_pc
   pip install -r requirements.txt
   ```
2. Ejecuta el servidor:
   ```bash
   python run_server.py
   ```
3. En la consola verás la URL local y un **código QR**:
   * Abre la cámara de tu celular y escanea el código QR (o entra a `http://<IP_PC>:8000`).
4. Toca el botón del micrófono en el celular para hablar con el animatrónico. La respuesta se escuchará por la bocina del teléfono mientras la mandíbula física se mueve al compás de la voz.
