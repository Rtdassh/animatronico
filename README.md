# 🤖 Sistema Robótico Dual: Asistente de Escritorio Autónomo ("Gran Hermano") & Cabeza Animatrónica con IA

Sistema robótico y de sensado ambiental desacoplado en 4 niveles de cómputo y control. Esta rama (`feature/asistente-escritorio`) adapta y unifica la arquitectura del **Asistente de Escritorio Autónomo con Diagnóstico Web Móvil** y el sistema de **Inteligencia Artificial Local (Qwen 2.5 + Loquendo + Visión OpenCV)**.

La aplicación integrada se inicia con **`iniciar_web_unificada.bat`**: usa el Wi-Fi del ESP32 y reúne asistente, visión, micrófono del celular por HTTPS, sensores y los 16 canales de servo. Consulta [la guía de la web unificada](docs/GUIA_WEB_UNIFICADA.md) para instalar el certificado del celular y usar el modo sin tocar sin depender de internet.

## Armado del EyeMech ε3.2

Consulta la [guía de armado y puesta en marcha](docs/GUIA_ARMADO_EYEMECH.md) para cablear el Uno, ESP32, PCA9685 y DHT11, calibrar los seis servos en Hold y probar el conjunto. Los planos anteriores con LM75A o módulo de audio quedan como referencia histórica.

---

## 🏛️ Modos de Funcionamiento

El proyecto soporta dos modos de operación según la infraestructura disponible:

### Modo 1: Asistente de Escritorio Autónomo ("Gran Hermano" - Sin PC)
No requiere computadora ejecutándose. El ESP32 crea su propio Punto de Acceso Wi-Fi y sirve una aplicación web móvil responsiva para diagnóstico y control en tiempo real:

```text
 ┌──────────────────────┐    Wi-Fi SoftAP    ┌───────────────────────────────┐
 │ 1. SMARTPHONE/TABLET │ <----------------> │ 2. ESP32 DEVKIT V1            │
 │ • Acceso a 192.168.4.1                    │ • Red AP: "Asistente-ESP32"   │
 │ • Diagnóstico I2C / UART                  │ • Servidor Web HTTP (panel.h) │
 │ • Movimiento de Servos                    │ • Hardware UART2 (GPIO 16/17) │
 │ • Alerta acústica Buzzer                  │ • Sin dependencias de router  │
 └──────────────────────┘                    └──────────────┬────────────────┘
                                                            │
                                                     UART (38400 bps)
                                                  (Divisor 1kΩ / 2kΩ)
                                                            v
                                             ┌───────────────────────────────┐
                                             │ 3. ARDUINO UNO R3             │
                                             │ • Pantalla LCD 1602 I2C       │
                                             │ • Sensor LM75A (Temperatura)  │
                                             │ • Sensor DHT11 (Humedad D4)   │
                                             │ • PCA9685 (Servos Brazo/Base) │
                                             │ • Buzzer KY-006 (Pin D8)      │
                                             │ • Fuente 5V LM2596 en V+      │
                                             └───────────────────────────────┘
```

### Modo 2: Sistema Animatrónico Inteligente con PC Local (EyeMech ε3.2)
La laptop comparte su conexión de internet vía Hotspot hacia el ESP32, o conecta mediante WebSocket de alta velocidad. Sirve la interfaz web integrada con pestañas de Asistente, Visión Facial OpenCV, IA Local Qwen 2.5 y panel de hardware y calibración de servos:

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
                                                     /ws/animatronic
                                                             v
 ┌──────────────────────┐    Hardware UART   ┌───────────────────────────────┐
 │ 4. ARDUINO UNO R3    │ <----------------- │ 3. ESP32 DEVKIT V1            │
 │ • PCA9685 (6x Servos)│(38400 bps / 3.3V)  │ • Pasarela Wi-Fi WebSocket    │
 │ • Mecanismo Ocular   │ Latest-Cmd-Wins    │ • Hardware UART2 (GPIO 16/17) │
 │ • Hold/Move en D8    │                    │ • Buffer de movimiento        │
 │ • Sensor DHT11       │                    └───────────────────────────────┘
 │ • Luz Pin D7         │
 └──────────────────────┘
```

1. **Smartphone (Nodo de Audio Manos Libres Tipo Alexa):** El celular funciona como micrófono continuo y altavoz inalámbrico. El usuario puede operar sin tocar la pantalla: detecta la palabra clave ("Oye Robot" o "Alexa"), responde de inmediato con "¿En qué te ayudo?", captura la pregunta por voz y reproduce la respuesta de la IA por su altavoz.
2. **PC Local (Cerebro Central):** Servidor asíncrono en Python con FastAPI. Conecta con el modelo local **Qwen 2.5 (7B)** vía Ollama en hilos no bloqueantes, sintetiza voz neuronal con el esqueleto de **Voicebox** o las voces de **Loquendo** (Jorge, Carlos, Carmen) con caché en disco, gestiona el pipeline de visión artificial a 30+ FPS y administra la telemetría ambiental.
3. **ESP32 DevKit V1 (Pasarela Inalámbrica):** Cliente WebSocket de alta velocidad conectado a la PC. Reenvía instrucciones de movimiento por `UART2` al Arduino Uno a 38400 baudios. Conserva el último comando de seguimiento y reenvía por separado las órdenes de luz y parpadeo.
4. **Arduino Uno R3 (Controlador de movimiento):** Maneja por I²C el **PCA9685** para los seis servos del EyeMech ε3.2. En Hold centra los ojos y cierra los párpados para calibrar. En Move recibe consignas de mirada y genera parpadeos y movimientos autónomos. El **DHT11** entrega temperatura y humedad.

---

## 🚀 Guía de Puesta en Marcha

### 1. Compilación y Grabación de Microcontroladores

#### Desde Consola con Arduino CLI:
```bash
# Grabar Arduino Uno
./grabar_arduino.sh /dev/ttyACM0

# Grabar ESP32 DevKit V1
./grabar_esp32.sh /dev/ttyUSB0

# O utilizar el asistente de grabación interactivo:
python3 tools/grabar_firmware.py
```

#### Desde Arduino IDE:
1. Abre `firmware/asistente_arduino/asistente_arduino.ino` -> Placa: **Arduino Uno** -> Subir.
2. Abre `firmware/asistente_esp32/asistente_esp32.ino` -> Placa: **ESP32 Dev Module** -> Subir.

### 2. Prueba Inmediata del Arduino (Monitor Serie USB)
Sin conectar el ESP32, abre el Monitor Serie a **115200 baudios** con **Nueva línea (`\n`)**:
- Envía `S0:45` y `S0:135` para mover el Servo 1.
- Envía `BEEP` para verificar el zumbador.
- Observa la telemetría del DHT11 y LM75A. La LCD debe mostrar:
  ```text
  LM75 21.2 C
  DHT11 61%
  ```

### 3. Conexión al Panel Web Móvil del ESP32
1. Enciende el ESP32 conectado por su cable USB.
2. Desde tu teléfono celular o tablet, conéctate a la red Wi-Fi:
   - **SSID:** `Asistente-ESP32`
   - **Contraseña:** `arquitectura123`
3. Abre el navegador web e ingresa a: **`http://192.168.4.1`**.
4. Podrás visualizar en tiempo real el estado de todos los módulos I2C, temperatura, humedad y operar los servomotores y buzzer desde la interfaz táctil.

### 4. Modo Servidor Central con IA Local (Opcional)
Para habilitar el modo inteligente con Loquendo y visión artificial:
```bash
./start.sh
```
El servidor levantará en `http://localhost:8000` con túnel seguro HTTPS para acceso móvil.
