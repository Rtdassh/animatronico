# Asistente de Escritorio Autónomo: Arduino Uno + ESP32

Esta guía contiene las instrucciones esenciales de seguridad eléctrica, asignación de pines, carga de firmware y verificación para el **Asistente de Escritorio ("Gran Hermano")**.

---

## 1. Revisión Crítica de Alimentación Eléctrica

> [!CAUTION]
> **No energizar el sistema sin verificar estos 5 puntos de seguridad:**
> 1. **Arduino Uno R3:** Alimentado por su cable USB estándar (5 V desde la computadora o cargador).
> 2. **ESP32 DevKit V1:** Alimentado independientemente por su propio cable USB. **Nunca conectes 3.3 V al pin VIN del ESP32** (el pin VIN requiere mínimo 4.5 V para su regulador AMS1117 interno; alimentarlo con 3.3 V congelará el procesador y bloqueará el bus I2C).
> 3. **Servomotores SG90 y PCA9685:**
>    - `VCC` del PCA9685 (lógica): Alimentado exclusivamente desde el pin `5V` del Arduino.
>    - `V+` del borne verde (fuerza de servos): Alimentado **únicamente desde fuente externa de 5.0 V regulada**.
>    - Si usas una fuente de 12 V (1 A) con el módulo reductor **LM2596**, desconecta los servos y mide con un multímetro entre `OUT+` y `OUT-` girando el potenciómetro hasta obtener exactamente **5.00 V**. Solo después conecta la salida al borne verde.
> 4. **Tierras comunes (GND):** Deben estar unidas entre sí en un solo punto o riel negativo:
>    - `GND` Arduino Uno $\leftrightarrow$ `GND` ESP32 $\leftrightarrow$ `GND` LM2596 $\leftrightarrow$ `GND` PCA9685.
> 5. **Pin AREF del Arduino Uno:** **Debe quedar libre**. No lo uses como tierra; AREF es la referencia de voltaje del conversor analógico-digital y no es GND.

---

## 2. Tabla Maestra de Conexiones

### Bus I2C Compartido (4 hilos)
Todos los módulos esclavos comparten los mismos pines analógicos del Arduino Uno:

| Componente | Pin del Módulo | Arduino Uno R3 | Notas |
|---|---|---|---|
| LM75A (Temperatura) | VCC / GND | 5V / GND | Dirección típica `0x48` |
| LM75A | SDA / SCL | A4 / A5 | Bus I2C a 100 kHz |
| LCD 1602 con backpack | VCC / GND | 5V / GND | Módulo PCF8574 (`0x27` o `0x3F`) |
| LCD 1602 | SDA / SCL | A4 / A5 | Ajustar potenciómetro de contraste azul |
| PCA9685 (16 Canales PWM) | VCC / GND | 5V / GND | Alimentación exclusiva de lógica (`0x40`) |
| PCA9685 | SDA / SCL | A4 / A5 | OE a nivel bajo / pull-down |
| PCA9685 Borne Verde | V+ / GND | LM2596 OUT (5.0V) | **Alimentación externa de fuerza para servos** |

### Sensores y Actuadores en Pines Digitales

| Componente | Pin del Módulo | Arduino Uno | Notas |
|---|---|---|---|
| DHT11 (Humedad) | VCC / GND | 5V / GND | Riel común de la protoboard |
| DHT11 | DATA / S | **Pin D4** | Módulo de 3 pines (incluye pull-up) |
| Buzzer Pasivo KY-006 | Señal S / GND | **Pin D8** / GND | Tono acústico y confirmación de comandos |
| Servo SG90 Canal 0 | Señal (Naranja) / Rojo / Marrón | PCA9685 Canal 0 | Movimiento Brazo / Giro Horizontal |
| Servo SG90 Canal 1 | Señal (Naranja) / Rojo / Marrón | PCA9685 Canal 1 | Movimiento Cabeza / Tilt |

### Enlace de Comunicación Serie Bidireccional (UART)

```text
Arduino Uno D3 (TX) ──[ 1 kΩ ]──●──── ESP32 RX2 / GPIO 16 (3.3V)
                               │
                            [ 2 kΩ ]
                               │
                              GND

Arduino Uno D2 (RX) ────────────────── ESP32 TX2 / GPIO 17 (3.3V nativo)

Arduino Uno GND     ────────────────── ESP32 GND
```

> [!IMPORTANT]
> El divisor de voltaje formado por la resistencia de 1 kΩ (en serie) y la de 2 kΩ (a tierra) reduce los 5 V emitidos por el pin D3 del Arduino a aproximadamente **3.33 V**, protegiendo la compuerta de entrada del ESP32 contra sobretensiones permanentes.

---

## 3. Carga de Firmwares

### Con Arduino IDE
1. **Arduino Uno:**
   - Abre `firmware/asistente_arduino/asistente_arduino.ino`.
   - Selecciona la placa **Arduino Uno** y el puerto serial correspondiente (ej. `/dev/ttyACM0` en Linux o `COM3` en Windows).
   - Haz clic en **Subir**.
2. **ESP32 DevKit V1:**
   - Abre `firmware/asistente_esp32/asistente_esp32.ino` (asegúrate de que `panel.h` esté en la misma carpeta).
   - Selecciona la placa **ESP32 Dev Module** o **DOIT ESP32 DEVKIT V1** y su puerto (`/dev/ttyUSB0` o `COM4`).
   - Haz clic en **Subir**.

### Con Arduino CLI (desde consola)
```bash
# Compilar y grabar Arduino Uno
arduino-cli compile --upload -p /dev/ttyACM0 --fqbn arduino:avr:uno firmware/asistente_arduino

# Compilar y grabar ESP32 DevKit
arduino-cli compile --upload -p /dev/ttyUSB0 --fqbn esp32:esp32:esp32 firmware/asistente_esp32
```

---

## 4. Secuencia de Verificación y Puesta en Marcha

1. **Prueba Inmediata sin ESP32 (Monitor Serie USB):**
   - Con el Uno conectado, abre el Monitor Serie a **115200 baudios** con **Nueva línea (`\n`)**.
   - Envía `S0:45` y luego `S0:135`. Debe responder `ACK: PWM_ENVIADO` y el servo debe moverse.
   - Envía `BEEP`. El buzzer debe sonar brevemente.
   - Observa las lecturas del DHT11: debe imprimir `DHT11 humedad x10: XXX`. Si imprime `DHT11 error E#`:
     * `E1`: Sin pulso inicial de respuesta (revisar cable DATA en D4 o alimentación).
     * `E2-E3`: Respuesta incompleta del sensor.
     * `E4-E5`: Pérdida de bits en la trama de 40 pulsos.
     * `E6`: Error de suma de comprobación (*checksum*).
     * `E7`: Humedad fuera de rango normal.
2. **Conexión al Panel Web Móvil:**
   - Conecta el celular o iPad a la red Wi-Fi: **`Asistente-ESP32`**.
   - Contraseña: **`arquitectura123`**.
   - Abre en el navegador: **`http://192.168.4.1`**.
3. **Comprobación en el Panel Web:**
   - **Indicador UART:** Debe mostrarse en color verde: `CONECTADO`.
   - **Tarjetas de Sensores:** `LM75A` reporta temperatura en °C; `DHT11` reporta humedad en % HR; `LCD` y `PCA9685` muestran sus direcciones I2C detectadas.
   - **Controles de Actuadores:** Pulsa los botones para girar el Servo 1 (45°, 90°, 135°), Servo 2 y probar el buzzer.

