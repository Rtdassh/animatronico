# 🤖 Guía Técnica de Arquitectura: Asistente de Escritorio Autónomo ("Gran Hermano")

Este documento detalla la arquitectura completa, esquema eléctrico, diseño de software embebido y procedimiento de diagnóstico del **Asistente de Escritorio Inteligente**.

---

## 1. Visión General del Sistema

El proyecto implementa un sistema embebido distribuido en **dos microcontroladores desacoplados** que resuelven en conjunto los requerimientos de sensado ambiental, interacción cinemática y servidor web interactivo:

```text
 ┌────────────────────────────────────────────────────────┐
 │ 1. DISPOSITIVO MÓVIL (Smartphone / Tablet / PC)       │
 │ • Conexión Wi-Fi directa a red 'Asistente-ESP32'       │
 │ • Interfaz Web HMI responsiva en http://192.168.4.1    │
 │ • Telemetría en vivo, botones de prueba y alertas      │
 └───────────────────────────┬────────────────────────────┘
                             │
                      HTTP / Wi-Fi SoftAP
                             v
 ┌────────────────────────────────────────────────────────┐
 │ 2. NODO DE RED Y COMUNICACIÓN: ESP32 DevKit V1         │
 │ • Modo Access Point: SSID "Asistente-ESP32" (WPA2)     │
 │ • Servidor Web HTTP embebido en puerto 80 (panel.h)    │
 │ • Parser JSON de telemetría y generador de comandos    │
 │ • Hardware UART2 (GPIO 16 RX2 / GPIO 17 TX2 a 9600 bps)│
 └───────────────────────────┬────────────────────────────┘
                             │
                      UART Bidireccional
                 (Divisor Resistivo 1kΩ / 2kΩ)
                             v
 ┌────────────────────────────────────────────────────────┐
 │ 3. NODO DE TIEMPO REAL: Arduino Uno R3 (ATmega328P)    │
 │ • SoftwareSerial en D2 (RX) y D3 (TX) a 9600 bps       │
 │ • Bus I2C Compartido (A4/A5 a 100 kHz):                │
 │    - Sensor LM75A (0x48): Temperatura ambiente         │
 │    - Pantalla LCD 1602 (0x27 / 0x3F): Muestra T° y H%  │
 │    - PCA9685 (0x40): Control PWM de 16 canales         │
 │ • Sensor DHT11 en Pin D4: Humedad relativa             │
 │ • Buzzer Pasivo KY-006 en Pin D8: Avisos y alarmas     │
 │ • Servomotores SG90 en Canales 0 y 1 del PCA9685       │
 └───────────────────────────┬────────────────────────────┘
                             │
                  Alimentación de Servos
                             v
 ┌────────────────────────────────────────────────────────┐
 │ 4. SISTEMA DE ENERGÍA Y POTENCIA                       │
 │ • Fuente Externa: Transformador 12 V / 1 A DC          │
 │ • Convertidor Buck LM2596: Calibrado a 5.00 V          │
 │ • Borne verde V+ / GND del PCA9685: Fuerza para servos │
 │ • Tierras comunes (GND) unificadas                     │
 └────────────────────────────────────────────────────────┘
```

---

## 2. Lista de Materiales (BOM)

| Componente | Cantidad | Función Principal |
|---|---|---|
| **Arduino Uno R3** | 1 | Controlador de tiempo real, sensores y bus I2C |
| **ESP32 DevKit V1 (30 pines)** | 1 | Servidor web HTTP y pasarela Wi-Fi |
| **Controlador PWM PCA9685** | 1 | Generación de pulsos servo de 12 bits vía I2C |
| **Sensor de Temperatura LM75A** | 1 | Medición digital I2C de temperatura |
| **Sensor de Humedad DHT11** | 1 | Medición de humedad relativa por bus de 1 hilo (Pin D4) |
| **Pantalla LCD 1602 con PCF8574** | 1 | Interfaz visual local I2C (4 hilos) |
| **Buzzer Pasivo KY-006** | 1 | Señalización acústica de confirmación y alarma (Pin D8) |
| **Microservomotores SG90 (9g)** | 2 | Actuadores de brazo/cabeza (Canales 0 y 1) |
| **Módulo Convertidor LM2596** | 1 | Regulador reductor conmutado de 12 V a 5.0 V |
| **Fuente de Alimentación 12 V / 1 A**| 1 | Suministro de potencia para servomotores |
| **Resistencia 1 kΩ (1/4 W)** | 1 | Divisor de voltaje rama serie (D3 $\to$ RX2) |
| **Resistencia 2 kΩ (1/4 W)** | 1 | Divisor de voltaje rama a tierra (RX2 $\to$ GND) |
| **Protoboard y Cables Jumper** | 1 kit | Distribución de señales e interconexión |

---

## 3. Topología Eléctrica y Justificación de Diseño

### 3.1. Divisor de Voltaje para la Entrada Serial del ESP32
El microcontrolador ATmega328P del Arduino Uno trabaja con lógica TTL de **5.0 V**. Por el contrario, el microprocesador ESP32 opera con lógica CMOS de **3.3 V** máximo en sus pines GPIO.

Para proteger el pin `GPIO 16 (RX2)` del ESP32 cuando el Arduino transmite por su pin `D3 (TX)`, se implementa un divisor de tensión resistivo:

$$V_{\text{out}} = V_{\text{in}} \cdot \frac{R_2}{R_1 + R_2} = 5.0\,\text{V} \cdot \frac{2000\,\Omega}{1000\,\Omega + 2000\,\Omega} = 3.33\,\text{V}$$

La corriente que drena el pin D3 es despreciable:
$$I = \frac{5.0\,\text{V}}{3000\,\Omega} \approx 1.67\,\text{mA}$$

En sentido inverso, el pin `GPIO 17 (TX2)` del ESP32 entrega **3.3 V**, lo cual supera holgadamente el umbral de nivel alto de entrada ($V_{IH}$) del Arduino Uno (especificado en $0.6 \times V_{CC} = 3.0\,\text{V}$), por lo que la conexión hacia `D2 (RX)` es directa.

### 3.2. Aislamiento de Potencia de Servomotores (PCA9685 y LM2596)
Cada servomotor SG90 demanda una corriente típica de reposo de 10 a 20 mA, pero bajo movimiento o bloqueo mecánico puede consumir picos de corriente transitorios superiores a **500–800 mA**.

Intentar alimentar los servos desde la salida de 5 V del Arduino Uno o desde el ESP32 provoca caídas súbitas de tensión (*brownouts*), reseteando los microcontroladores y bloqueando el bus I2C. Por ello:
1. El pin `VCC` del PCA9685 alimenta únicamente su chip lógico y se conecta a los **5 V regulados del Arduino**.
2. Los servomotores reciben energía a través del **borne verde de tornillo (`V+` y `GND`)** proveniente de la salida ajustada a **5.00 V** del convertidor **LM2596**, alimentado por el adaptador externo de 12 V / 1 A.

### 3.3. Bus I2C Compartido
Los tres módulos esclavos (`LM75A`, `LCD 1602` y `PCA9685`) conviven en las mismas líneas analógicas `A4 (SDA)` y `A5 (SCL)` del Arduino Uno gracias a sus direcciones de hardware independientes:
- **PCA9685:** `0x40` (configurable con jumpers de dirección A0-A5).
- **LCD 1602:** `0x27` (o `0x3F` según el chip PCF8574 / PCF8574A).
- **LM75A:** `0x48` (pines A0, A1, A2 a GND).

El firmware del Arduino incluye un escáner I2C autónomo al inicio y cada 10 segundos, asegurando la auto-recuperación de módulos si alguno se desconecta temporalmente.

---

## 4. Arquitectura de Firmware Embebido

### 4.1. Arduino Uno (`asistente_arduino.ino`)
- **Lectura precisa de DHT11 sin dependencias:** En lugar de emplear `pulseIn()`, que bloquea la ejecución o pierde pulsos consecutivos, el firmware utiliza muestreo directo sobre el registro de puerto (`portInputRegister`) dentro de una sección crítica protegida con `noInterrupts()` y conteo de ciclos. Proporciona códigos de diagnóstico de error (`E1` a `E7`).
- **Controlador LCD liviano:** Inicialización directa del controlador HD44780 en modo de 4 bits sobre el expansor PCF8574 por comandos de nibble, evitando conflictos de librerías LiquidCrystal externas.
- **Trama de telemetría UART periódica (cada 1.5 s):**
  ```text
  S,temp10,hum10,flags,servo0,servo1,autoMode,uptime,dhtErrors,serialErrors,lmAddr,lcdAddr,pcaAddr
  ```
- **Recepción coordinada:** El Uno envía `R` cuando abre una ventana de escucha de 90 ms. El ESP32 espera una nueva ventana y comienza una sola orden durante los primeros 40 ms. Durante la ventana, el Uno aplaza las lecturas de sensores y la telemetría para evitar pérdidas de caracteres en `SoftwareSerial`. Se deben actualizar los dos firmwares juntos.
- **Contador serie:** `serialErrors` acumula comandos inválidos o buffers desbordados desde el arranque del Uno; no representa errores nuevos en cada consulta. El LCD puede permanecer desconectado y se muestra como opcional en el panel.
- **Lógica de Alerta Automática:** Si la temperatura es $\ge 30.0^\circ\text{C}$ o la humedad es $\ge 75\%$, activa un tono en el buzzer y posiciona el servo en 130° como señal de advertencia.

### 4.2. ESP32 DevKit V1 (`asistente_esp32.ino`)
- **Punto de Acceso Wi-Fi:** Genera la red inalámbrica `Asistente-ESP32` con cifrado WPA2.
- **Servidor Web Embebido:** Sirve `panel.h` directamente en la raíz `/` con compresión en memoria flash (`PROGMEM`) y cero dependencias de almacenamiento SPIFFS/LittleFS.
- **API REST Local:**
  - `GET /api/status`: Devuelve el JSON de telemetría completa. `frameAgeMs` indica los milisegundos desde la última trama, calculados por el ESP32. `received` distingue el arranque sin datos de una pérdida posterior; `connected` pasa a falso tras 6 segundos sin telemetría. El panel no compara `millis()` con el reloj del celular. El comando USB `STATUS` devuelve el mismo JSON.
  - `GET /api/cmd?c=<comando>`: Envía comandos (`PING`, `SCAN`, `BEEP`, `S0:45`, `S0:90`, `S0:135`, `AUTO:1`) por UART2 y retorna su propio `ACK`. `ok` solo es verdadero para confirmaciones de éxito. Las órdenes que cambian el estado esperan además su trama actualizada; si no llega confirmación, se informa `SIN_CONFIRMACION`, `UNO_NO_DISPONIBLE` o `TELEMETRIA_NO_CONFIRMADA`. El panel envía las órdenes en secuencia y sustituye posiciones pendientes del mismo servo.

---

## 5. Análisis de Problemas Resueltos en Laboratorio (Post-Mortem)

Durante las pruebas iniciales de integración se identificaron y solucionaron los siguientes fallos críticos:

1. **Pantalla LCD en blanco / congelada con luz azul:**
   - *Causa:* El ESP32 estaba siendo alimentado introduciendo 3.29 V regulados al pin `VIN`. El regulador interno AMS1117-3.3 del DevKit tiene una caída de voltaje (*dropout*) de ~1.1 V, por lo que el núcleo del ESP32 operaba a ~2.2 V, generando fallos aleatorios y sobrecargando el riel de 5 V del Arduino.
   - *Solución:* Desconectar el LM2596 del pin VIN y alimentar cada placa por su propio conector USB independiente con GND común.
2. **Servomotores sin movimiento con PCA9685 detectado por I2C:**
   - *Causa:* El borne verde de alimentación de servos (`V+`) estaba desconectado. El chip PCA9685 respondía por I2C porque su lógica estaba alimentada por `VCC`, pero los servos no recibían los 5 V de fuerza.
   - *Solución:* Conectar la salida regulada a 5.0 V del LM2596 al borne verde.
3. **Error permanente `DHT11 ERROR`:**
   - *Causa:* La función estándar `pulseIn()` del núcleo AVR espera a que ocurra una transición completa antes de empezar a medir, perdiendo la ventana temporal de los 40 pulsos consecutivos de 50 µs del DHT11.
   - *Solución:* Reescritura del driver mediante inspección de ciclos de reloj con `noInterrupts()` y suelta anticipada del pin como `INPUT_PULLUP`.

