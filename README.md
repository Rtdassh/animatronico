# 🤖 Sistema Robótico Dual: Asistente de Escritorio Autónomo ("Gran Hermano") & Cabeza Animatrónica con IA

Sistema robótico y de sensado ambiental desacoplado en 4 niveles de cómputo y control. Esta rama (`feature/asistente-escritorio`) adapta y unifica la arquitectura del **Asistente de Escritorio Autónomo con Diagnóstico Web Móvil** y el sistema de **Inteligencia Artificial Local (Qwen 2.5 + Loquendo + Visión OpenCV)**.

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
                                                     UART (9600 bps)
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

### Modo 2: Modo Inteligente con PC Local (Loquendo, Qwen 2.5 y Visión Facial)
Conecta el ESP32 por WebSockets al servidor FastAPI en la computadora, añadiendo procesamiento de lenguaje natural local con Ollama (Qwen 2.5), síntesis de voz Loquendo y visión facial a 30 FPS mediante OpenCV.

---

## 🔌 Diagrama Eléctrico y Distribución de Pines

> [!CAUTION]
> **Seguridad Eléctrica y Reglas Críticas:**
> 1. **Alimentación USB Independiente:** Arduino Uno y ESP32 deben alimentarse cada uno por su conector USB estándar. **Nunca introduzcas 3.3 V al pin VIN del ESP32** (su regulador interno requiere mínimo 4.5 V).
> 2. **Alimentación de Servos:** Los servomotores SG90 deben alimentarse exclusivamente desde el **borne verde (`V+` y `GND`) del PCA9685** mediante un convertidor LM2596 calibrado con multímetro a **5.00 V** (desde fuente externa 12 V / 1 A).
> 3. **Tierras comunes:** Une `GND` de Arduino, `GND` de ESP32 y `GND` del LM2596 / PCA9685.
> 4. **Pin AREF:** Debe permanecer desconectado.

### Tabla Maestra de Interconexión

| Señal | Arduino Uno R3 | Destino / Componente | Notas |
|---|---|---|---|
| **SDA** | Pin A4 | LM75A, LCD 1602 y PCA9685 | Bus I2C Compartido (100 kHz) |
| **SCL** | Pin A5 | LM75A, LCD 1602 y PCA9685 | Bus I2C Compartido (100 kHz) |
| **5V Lógica** | Pin 5V | VCC de LM75A, LCD, DHT11 y PCA9685 | Riel de 5V para sensores |
| **GND** | Pin GND | Tierra común de todo el circuito | Referencia eléctrica unificada |
| **DHT11 DATA** | Pin D4 | DATA sensor DHT11 | Driver ciclo a ciclo sin bloqueos |
| **Buzzer** | Pin D8 | Señal S del buzzer pasivo KY-006 | Pata central libre |
| **UART RX** | Pin D2 | GPIO 17 (TX2) del ESP32 | Conexión directa a 3.3V |
| **UART TX** | Pin D3 | Entrada Divisor 1kΩ / 2kΩ | Salida 3.33V hacia GPIO 16 (RX2) del ESP32 |
| **Borne V+** | — | Salida OUT+ LM2596 (5.0V) | Borne verde del PCA9685 para servos |

---

## 📁 Estructura del Firmware en esta Rama

- **`firmware/asistente_arduino/`**: Sketch completo del Arduino Uno (`asistente_arduino.ino`) con lectura de DHT11 por conteo de ciclos con `noInterrupts()`, escáner I2C autónomo, inicialización por nibbles de la LCD 1602 (PCF8574), control de 2 servos con PCA9685, buzzer en D8 y protocolo serie bidireccional.
- **`firmware/asistente_esp32/`**: Sketch del ESP32 DevKit V1 (`asistente_esp32.ino`) con servidor web HTTP autónomo en memoria (`panel.h`), punto de acceso `Asistente-ESP32` y pasarela UART2.
- **`docs/LEEME-ANTES-DE-CARGAR.md`**: Instrucciones directas de cableado, orden de armado y resolución de problemas.
- **`docs/GUIA_ASISTENTE_ESCRITORIO.md`**: Documentación técnica exhaustiva, análisis post-mortem de fallas de laboratorio y arquitectura.
- **`docs/plano_circuito_asistente.svg`**: Esquema gráfico vectorial de alta definición de las conexiones.

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
