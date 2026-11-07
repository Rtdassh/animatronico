# Sistema Animatronico Inteligente con Procesamiento Local y Vision Ambiental

Sistema robotico interactivo de 4 niveles que desacopla el procesamiento de Inteligencia Artificial (LLM local y sintesis de voz Loquendo), la pasarela de red inalambrica, el control fisico determinista y la interfaz acustica manos libres.

---

## Arquitectura del Sistema

```text
 ┌──────────────────────┐    Wi-Fi / HTTPS   ┌───────────────────────────────┐
 │ 1. SMARTPHONE        │ <----------------> │ 2. PC LOCAL                   │
 │ • Modo Manos Libres  │                    │ • Ollama (Qwen 2.5:7b Local)  │
 │ • Microfono Continuo │                    │ • Loquendo TTS (Jorge/Carlos) │
 │ • WakeNet / Hotword  │                    │ • STT Motor SpeechRecognition │
 │ • Altavoz de Salida  │                    │ • Tunel Cloudflare HTTPS      │
 └──────────────────────┘                    │ • FastAPI / WebSockets        │
                                             └───────────────────────────────┘
                                                             │
                                                    WebSocket / Wi-Fi
                                                             │
                                                             v
 ┌──────────────────────┐    Hardware UART   ┌───────────────────────────────┐
 │ 4. ARDUINO UNO       │ <----------------- │ 3. ESP32 DEVKIT V1            │
 │ • PCA9685 (6x Servos)│ (9600 bps / 3.3V)  │ • Pasarela WebSocket          │
 │ • Bus I2C LM75A      │                    │ • Hardware UART2              │
 │ • Sensor DHT11       │                    │ • Cero latencia               │
 │ • Pines D10/D11 Libres│                   └───────────────────────────────┘
 └──────────────────────┘
```

1. **Smartphone (Nodo de Audio Manos Libres Tipo Alexa):** El celular funciona unicamente como microfono continuo y altavoz inalambrico. El usuario no interactua con la pantalla. Detecta la palabra clave ("Oye Robot" o "Alexa"), responde de inmediato con "¿En que te ayudo?", captura la pregunta por voz y reproduce la respuesta de la IA por su altavoz.
2. **PC Local (Cerebro Central):** Servidor asincrono en Python con FastAPI. Conecta con el modelo local **Qwen 2.5 (7B)** via Ollama, sintetiza voz neuronal con el esqueleto de **Voicebox** o las voces de **Loquendo** (Jorge, Carlos, Carmen) con cache en disco y administra la telemetria ambiental.
3. **ESP32 DevKit V1 (Pasarela Inalambrica):** Cliente WebSocket de alta velocidad conectado a la PC. Reenvia instrucciones de movimiento por `Serial2` al Arduino Uno en menos de 2 ms.
4. **Arduino Uno R3 (Controlador de Tiempo Real):** Modulo esclavo libre de interrupciones Wi-Fi que ejecuta un bucle determinista con `millis()`. Gobierna por bus I2C al chip **PCA9685** para 6 servomotores del mecanismo ocular ε3.2 (Will Cogley #1184807) sin temblores (*jitter*), genera parpadeo autonomo, micro-sacadas oculares y reporta telemetria del sensor I2C **LM75A** y sensor de humedad **DHT11**. Los pines **D10** y **D11** quedan 100% libres.

---

## Estructura del Repositorio

```text
animatronico/
├── docs/                                  # Documentacion tecnica y planos electricos
│   ├── DOC_01_Arduino_Uno_Firmware.md    # Especificacion de puertos y firmware Arduino
│   ├── DOC_02_ESP32_DevKit_Firmware.md   # Especificacion de red y pasarela ESP32
│   ├── DOC_03_App_Movil_y_Servidor_PC.md # Guia del servidor y modo manos libres
│   ├── plano_circuito_animatronico.png   # Plano unifilar esquematico en alta resolucion
│   └── plano_interactivo_circuito.html   # Visor interactivo web del circuito con tablas
│
├── firmware/                              # Codigo fuente embebido
│   ├── arduino_uno/
│   │   └── arduino_uno_animatronico.ino  # Firmware Arduino Uno (PCA9685 + LM75A + DHT11)
│   └── esp32_devkit/
│       └── esp32_puente_websocket.ino    # Firmware ESP32 (Cliente WebSocket <-> UART2)
│
├── server_pc/                             # Servidor local y aplicacion web movil
│   ├── app.py                            # Servidor FastAPI + WebSockets + Ollama + Loquendo / Voicebox TTS
│   ├── run_server.py                     # Lanzador con tunel Cloudflare HTTPS y QR en consola
│   ├── start.py                          # Alias de conveniencia para run_server.py
│   ├── start.bat                         # Lanzador por lotes para Windows
│   ├── ollama_client.py                  # Cliente de inferencia Qwen 2.5 local con telemetria
│   ├── tts_loquendo.py                   # Motor Loquendo (Jorge, Carlos, Carmen) con cache MD5
│   ├── voicebox_client.py                # Integracion con servidor local Voicebox
│   ├── stt_engine.py                     # Reconocimiento de voz a texto (WAV 16kHz)
│   ├── requirements.txt                  # Dependencias de Python
│   ├── bin/                              # Binarios de soporte (cloudflared para HTTPS movil)
│   ├── audio/                            # Almacen en cache de audios sintetizados
│   └── static/                           # Aplicacion Web Movil Manos Libres (HTML5 / CSS / JS)
│       ├── index.html                    # Interfaz con barra de asistente Alexa y avatar animatronico
│       ├── style.css                     # Estilos oscuros responsivos
│       └── app.js                        # Detector de Wake-Word continuo y controlador WebSocket
│
├── tools/                                 # Scripts de utilidad
│   └── render_plano_circuito.py          # Generador programatico del plano esquematico
│
├── start.bat                              # Lanzador de un clic para Windows
├── .gitignore                             # Reglas de exclusion de archivos
└── README.md                              # Documentacion principal del proyecto
```

---

## Conexiones y Mapa de Pines (Mecanismo Ocular ε3.2 + PCA9685)

> [!NOTE]
> Mecanismo ocular basado en el diseno open-source de **Will Cogley**: [Animatronic Eye Mechanism ε3.2 (MakerWorld #1184807)](https://makerworld.com/es/models/1184807-animatronic-eye-mechanism-e3-2#profileId-1195681). El control de servomotores se delega al controlador I2C **PCA9685** (0x40) y el subsistema de sonido se ejecuta de forma inalambrica a traves del smartphone.

### Arduino Uno R3
| Pin | Funcion | Destino | Nivel Logico |
| :--- | :--- | :--- | :--- |
| **`D2`** | SoftwareSerial RX | ESP32 `GPIO 17` (`TX2`) | 3.3V (Entrada directa segura) |
| **`D3`** | SoftwareSerial TX | Divisor resistivo ($1\text{ k}\Omega / 2\text{ k}\Omega$) $\to$ ESP32 `GPIO 16` | 5.0V (Atenuado a 3.33V) |
| **`D4`** | DAT / OUT | Pin de datos sensor de humedad **DHT11** | 5.0V Logico |
| **`D7`** | Control Luz | Resistencia $220\,\Omega$ $\to$ Anodo LED (o modulo rele) | 5.0V Salida |
| **`D10`** | Pin Libre / NC | Sin conexion (Audio delegado al smartphone) | NC |
| **`D11`** | Pin Libre / NC | Sin conexion (Audio delegado al smartphone) | NC |
| **`A4`** | I2C SDA | Pin `SDA` de **LM75A** (`0x48`) y **PCA9685** (`0x40`) | Bidireccional I2C |
| **`A5`** | I2C SCL | Pin `SCL` de **LM75A** (`0x48`) y **PCA9685** (`0x40`) | Reloj I2C (100-400 kHz) |
| **`5V`** | VCC Logica | Alimentacion logica de LM75A, DHT11 y VCC PCA9685 | 5.0V Logico |
| **`GND`** | Tierra | Riel comun de tierra (unido a ESP32 y polo negativo de fuente externa) | 0.0V Comun |

### Controlador PCA9685 (I2C: 0x40) - Servomotores ε3.2
| Canal | Articulacion ε3.2 | Cable Senal | Rango Angular Seguro | Funcion |
| :--- | :--- | :--- | :--- | :--- |
| **`CH0`** | Servo M1 (Pan / Yaw) | Naranja / Amarillo | **$60^\circ$ a $120^\circ$** ($90^\circ$ neutro) | Giro lateral conjunto de ambos ojos |
| **`CH1`** | Servo M2 (Tilt / Pitch) | Naranja / Amarillo | **$70^\circ$ a $110^\circ$** ($90^\circ$ neutro) | Elevacion y descenso vertical de la mirada |
| **`CH2`** | Servo M3 (Parpado Sup. Izq.) | Naranja / Amarillo | **$45^\circ$ (Cerrado) a $100^\circ$ (Abierto)** | Apertura y parpadeo ojo izquierdo |
| **`CH3`** | Servo M4 (Parpado Inf. Izq.) | Naranja / Amarillo | **$80^\circ$ (Reposo) a $110^\circ$ (Elevado)** | Expresion y contraccion ojo izquierdo |
| **`CH4`** | Servo M5 (Parpado Sup. Der.) | Naranja / Amarillo | **$45^\circ$ (Cerrado) a $100^\circ$ (Abierto)** | Apertura y parpadeo ojo derecho |
| **`CH5`** | Servo M6 (Parpado Inf. Der.) | Naranja / Amarillo | **$80^\circ$ (Reposo) a $110^\circ$ (Elevado)** | Expresion y contraccion ojo derecho |
| **`V+ / GND`** | Bornera de Potencia | Rojo (+) / Negro (-) | 5.0V Regulados (4A) | Banco con condensador $2200\,\mu\text{F} + 100\text{ nF}$ |

### ESP32 DevKit V1
| Pin | Funcion | Destino | Nivel Logico |
| :--- | :--- | :--- | :--- |
| **`GPIO 17`** | UART2 TX | Arduino `Pin D2` (SoftwareSerial RX) | 3.3V Salida |
| **`GPIO 16`** | UART2 RX | Nodo central del divisor resistivo ($1\text{ k}\Omega / 2\text{ k}\Omega$) | 3.33V Entrada |
| **`GPIO 2`**  | LED Builtin | Indicador de estado de enlace de red | Salida |
| **`GND`**      | Tierra | Riel comun de tierra del sistema | 0.0V Comun |

> [!CAUTION]
> **ALIMENTACION DE LOS SERVOS:** Los 6 microservos del mecanismo ε3.2 se alimentan **exclusivamente** desde una fuente externa regulada de 5V (4A continuos) a traves de la bornera `V+` y `GND` del modulo PCA9685, respaldada por un condensador electrolitico de $2200\,\mu\text{F}$ y ceramico de $100\text{ nF}$ en paralelo. Nunca alimentes los servos desde los 5V del Arduino ni del ESP32.

---

## Grabacion de Firmware (Arduino Uno y ESP32)

Se incluyen scripts ejecutables automatizados para grabar los microcontroladores con deteccion automatica de puertos serie:

### En Linux:
```bash
# Grabar solo Arduino Uno
./grabar_arduino.sh
# o especificando el puerto directamente:
./grabar_arduino.sh /dev/ttyACM0

# Grabar solo ESP32 DevKit V1
./grabar_esp32.sh
# o especificando el puerto directamente:
./grabar_esp32.sh /dev/ttyUSB0

# Menu interactivo general:
./grabar_todo.sh
```

### En Windows:
* Haz doble clic sobre **`grabar_arduino.bat`** para flashear el Arduino Uno.
* Haz doble clic sobre **`grabar_esp32.bat`** para flashear el ESP32 DevKit V1.
* Haz doble clic sobre **`grabar_todo.bat`** para abrir el menu de seleccion.

Los binarios precompilados se encuentran en:
- `firmware/binarios/arduino_uno/arduino_uno_animatronico.ino.hex`
- `firmware/binarios/esp32/esp32_puente_websocket.ino.bin` (y `esp32_puente_websocket.ino.merged.bin`)

---

## Guia de Puesta en Marcha (Modo Alexa Manos Libres)

### 1. Iniciar el Modelo Local con Ollama
Asegurate de tener **Ollama** ejecutandose en tu PC con el modelo **`qwen2.5:7b`**:
```bash
ollama run qwen2.5:7b
```

### 2. Iniciar el Servidor Central
Ejecuta el archivo **`start.bat`** en la raiz del proyecto (o desde la consola):
```bash
python server_pc/run_server.py
```
El servidor automaticamente:
- Verificara la conexion con Ollama.
- Iniciara el servidor FastAPI en el puerto 8000.
- Creara un tunel seguro **Cloudflare HTTPS** (`https://*.trycloudflare.com`).
- Generara un **codigo QR en la terminal**.

### 3. Conectar el Celular en Modo Manos Libres
1. Abre la camara de tu celular y **escanea el codigo QR**.
2. Al ingresar en Chrome o Safari movil, pulsa una vez sobre **"Iniciar Manos Libres"** para habilitar el microfono y altavoz del dispositivo.
3. Coloca el telefono sobre la mesa. A partir de este momento **no necesitas tocar la pantalla**.
4. Di en voz alta: **"Oye Robot"** o **"Alexa"**.
5. El telefono respondera de inmediato con voz clara: **"¿En que te ayudo?"** y la cabeza animatronica mirara al frente encendiendo su luz.
6. Formula tu pregunta directamente. Al terminar de hablar, la IA local respondera por el altavoz del telefono y reactivara la escucha pasiva para la siguiente orden de forma autonoma.
