# Guía de armado y puesta en marcha · EyeMech ε3.2

Esta adaptación usa el **Arduino Uno R3** para leer temperatura y humedad y controlar los seis servos mediante el **PCA9685**. El **ESP32 DevKit V1 con módulo ESP32-WROOM** conecta el Uno al servidor de la PC por UART y Wi-Fi. El teléfono abre el panel del servidor. [Modelo original de MakerWorld](https://makerworld.com/es/models/1184807-animatronic-eye-mechanism-e3-2)

## 1. Preparar las piezas

- Imprime el bloque de prueba de ajuste y usa la letra que corresponda a tus servos. El manual recomienda seis MG90S y la variante ε3.2-PIP. Los SG90 también aparecen como opción. Usa PLA, capas de 0,2 mm y orienta los ejes de los pivotes paralelos a la cama.
- Ten a mano dos ojos, los retenes y tornillos de los servos, el Uno, el ESP32, un PCA9685, un módulo DHT11, un interruptor de dos posiciones y dos cables USB de datos.
- Prepara una fuente regulada de **5 V para los servos** y cable adecuado para su corriente. Dimensiona la fuente y la distribución con la corriente de arranque o de bloqueo de los seis servos de tu lote. Para el divisor UART usa resistencias de **1 kΩ y 2 kΩ** de 1 %. Para el sentido inverso usa un búfer 74AHCT125 alimentado a 5 V o un adaptador UART con niveles de 3,3 V y 5 V. Para un DHT11 suelto, prepara una resistencia de 10 kΩ. El LED de D7 es opcional y lleva 220–330 Ω en serie. [Manual de montaje, pp. 1–2](https://makerworld.bblmw.com/makerworld/model/US83b6b7dde2b2f/design/2025-03-13_58f972adf6a6b.pdf)

## 2. Armar la mecánica

1. Retira los soportes y libera las articulaciones impresas. Verifica que giren a mano antes de instalar las varillas y que los ojos y párpados recorran su rango sin roce.
2. Inserta el primer servo en el subconjunto **X-A**, con el cable por la ranura. Encaja el subconjunto Y encima y monta los dos soportes del pivote central. Presenta **X-B** sin fijarlo al estriado para poder indexarlo al calibrar.
3. Encaja los pivotes centrales en la base desde abajo y coloca los ojos. Monta los párpados de palanca corta arriba y los de palanca larga abajo. Alinea las piezas en los pivotes centrales y termina de encajar los pivotes exteriores por debajo de la base.
4. Instala los cinco servos restantes con la orientación de la página 6 y fija los cuerpos con sus retenes. Deja los brazos y acoples desacoplados del eje hasta la calibración. Marca cada cable antes de cerrar el conjunto. Usa las etiquetas izquierda/derecha de la figura de la página 9, con las pupilas hacia el observador.
5. Fija la electrónica en separadores o en una base aislante. Sujeta el cableado al chasis y deja holgura en las articulaciones y acceso al interruptor y al corte de alimentación. [Manual de montaje, pp. 3–10](https://makerworld.bblmw.com/makerworld/model/US83b6b7dde2b2f/design/2025-03-13_58f972adf6a6b.pdf) · [Video del autor](https://youtu.be/MeHLouL9ltw)

## 3. Cablear con las fuentes desconectadas

| Origen | Destino | Para qué sirve |
| --- | --- | --- |
| Uno **A4** | PCA9685 **SDA** | Datos I²C |
| Uno **A5** | PCA9685 **SCL** | Reloj I²C |
| Uno **5V** | PCA9685 **VCC** y DHT **VCC** | Alimentación de lógica |
| Fuente externa **+5 V** | Bornera del PCA9685 **V+** | Alimentación de los servos |
| Fuente externa **−**, Uno **GND**, ESP32 **GND**, PCA9685 **GND**, DHT **GND** | Tierra común | Referencia de señales. Lleva el retorno de los servos directo a la fuente por la bornera |
| DHT **DATA** o **S** | Uno **D4** | Datos de temperatura y humedad |
| Uno **D3** (TX) | **1 kΩ** → nodo → ESP32 **GPIO16** (RX2) | Coloca **2 kΩ** desde ese mismo nodo hasta GND. El nodo queda cerca de 3,3 V con TX alto |
| ESP32 **GPIO17** (TX2) | Adaptador 3,3 → 5 V → Uno **D2** (RX) | En el 74AHCT125 conecta GPIO17 a 1A, 1Y a D2, 1OE a GND, VCC a 5 V del Uno y GND a tierra común |
| Uno **D8** | Interruptor → **GND** | Abierto = **Hold**. Cerrado = **Move** |
| Uno **D7** | Resistencia → ánodo LED. Cátodo → **GND** | Indicador de luz opcional |
| Puerto USB de cada placa | PC, mediante su cable de datos | Alimentación de las placas y grabación |

- En el PCA9685 deja los puentes de dirección abiertos para **0x40**. Si el módulo tiene **OE**, verifica que quede en nivel bajo para habilitar las salidas. Comprueba la serigrafía de cada módulo antes de conectar.
- **Mantén separados VCC y V+.** El positivo de la fuente de servos termina en **V+**. Evita llevar la corriente de los servos por el pin 5V del Uno, el USB o una protoboard. Antes de conectar los servos mide polaridad y tensión entre V+ y GND. Mantén accesible el corte de V+.
- **Protege GPIO16.** Lleva al ESP32 solamente el nodo del divisor, nunca D3 directo. Con el UART en reposo comprueba el nivel del nodo antes de unirlo al ESP32. La asignación GPIO16/17 es para ESP32-WROOM. Verifica el módulo impreso en la placa.
- Con la UART cableada, alimenta ambas placas por USB. Para el 74AHCT125 coloca 100 nF entre VCC y GND junto al integrado. En canales sin uso conecta las entradas A a GND y sus OE a 5 V, con Y libre.
- En un DHT11 de cuatro patas sin módulo, con la rejilla hacia ti y las patas hacia abajo, el orden habitual es **VCC, DATA, NC, GND**. Deja NC libre y conecta 10 kΩ entre DATA y VCC. En módulos de tres pines sigue la serigrafía y verifica si ya incluyen la resistencia. Ubica el sensor donde circule aire, lejos de fuentes de calor del equipo. [PCA9685 y alimentación](https://learn.adafruit.com/16-channel-pwm-servo-driver/pinouts) · [ESP32 DevKitC y GPIO16/17](https://docs.espressif.com/projects/esp-idf/en/v5.3.1/esp32/hw-reference/esp32/get-started-devkitc.html) · [74AHCT125](https://www.ti.com/lit/ds/symlink/sn74ahct125.pdf) · [DHT11/DHT22](https://learn.adafruit.com/dht)

### Canales del PCA9685

En cada canal, alinea **GND** con marrón/negro, **V+** con rojo y **PWM** con naranja/amarillo/blanco, previa verificación de los cables de tu servo. Usa las marcas del módulo para orientar el conector.

| Canal | Servo según el manual | Posición en Hold | Ajuste inicial en Move |
| --- | --- | ---: | --- |
| CH0 | L/R · eje horizontal, al frente entre los ojos | 90° | 60–120° |
| CH1 | U/D · eje vertical, en el centro del conjunto | 90° | 70–110° |
| CH2 | TL · párpado superior izquierdo | 90° cerrado | 110° abierto |
| CH3 | BL · párpado inferior izquierdo | 90° cerrado | 70° abierto |
| CH4 | TR · párpado superior derecho | 90° cerrado | 70° abierto |
| CH5 | BR · párpado inferior derecho | 90° cerrado | 110° abierto |
| CH6–15 | Libres | — | — |

El manual define la **pose de armado**. El código de referencia confirma que **TL y BR** abren en sentido ascendente y **BL y TR** en descendente. Los grados del cuadro son consignas del servo. El repositorio usa 50 Hz y centra cada canal en unos **1500 µs** con el perfil inicial. El recorrido de apertura se limitó a 20° por párpado para la puesta en marcha. Los límites de trabajo se ajustan en `SERVOS` en el sketch del Uno según el juego y los topes del equipo. [Manual, pp. 9–10](https://makerworld.bblmw.com/makerworld/model/US83b6b7dde2b2f/design/2025-03-13_58f972adf6a6b.pdf) · [Código EyeMech de referencia](https://github.com/will-cogley/EyeMech_Epsilon/blob/main/Code/NewFaceFollower.py)

## 4. Compilar y cargar

1. Instala Arduino IDE 2 o Arduino CLI. En el gestor de placas instala **Arduino AVR Boards** y **esp32 by Espressif Systems**. La URL adicional del gestor de placas para ESP32 es `https://espressif.github.io/arduino-esp32/package_esp32_index.json`.
2. En el gestor de bibliotecas instala **Adafruit PWM Servo Driver Library**, **DHT sensor library** de Adafruit y **WebSockets** de Markus Sattler (Links2004). Acepta las dependencias **Adafruit BusIO** y **Adafruit Unified Sensor**.
3. En la [carpeta del sketch ESP32](../firmware/esp32_puente_websocket) copia `wifi_config.example.h` a `wifi_config.h`. Ajusta SSID y clave de la red de 2,4 GHz y pon la IPv4 LAN de la PC en `PC_SERVER_IP` (en Windows se ve con `ipconfig`). Mantén ese archivo local.
4. Con **V+ apagado** y D8 en **Hold**, abre el [sketch Uno](../firmware/arduino_uno_animatronico/arduino_uno_animatronico.ino) como **Arduino Uno** y el [sketch ESP32](../firmware/esp32_puente_websocket/esp32_puente_websocket.ino) como **ESP32 Dev Module**. Verifica y carga cada uno por su puerto USB. Cierra el monitor serie durante la carga. [Instalación de Arduino CLI](https://arduino.github.io/arduino-cli/latest/installation/) · [Instalación del core ESP32](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html)

Con Arduino CLI y los cores en el sistema, desde la raíz puedes usar estos comandos. Sustituye los puertos de ejemplo por los que devuelve `--list`. El grabador compila desde los sketches y guarda los archivos en `build/firmware/`. Los archivos versionados en `firmware/binarios/` corresponden a una compilación anterior.

```powershell
python tools/grabar_firmware.py --compile-only all
python tools/grabar_firmware.py --list
python tools/grabar_firmware.py --arduino COM3
python tools/grabar_firmware.py --esp32 COM4
```

Para un módulo **DHT22** confirma su pinout y cambia `DHT11` por `DHT22` en el constructor `DHT dht(...)` antes de compilar el Uno. El firmware de esta adaptación toma ambas mediciones del DHT.

## 5. Calibrar antes de habilitar Move

1. Con el interruptor abierto, enciende primero la lógica por USB. Abre el monitor serie del **Uno a 115200 bps** con terminación de línea. Comprueba `PCA9685 0x40 OK. HOLD`. Cada 3,5 s debe llegar `SENS:T=...,H=...`. `NA` indica ausencia de lectura. Mantén el monitor abierto durante el ajuste, ya que abrirlo puede reiniciar el Uno.
2. En **Hold**, con los acoples todavía sueltos, da alimentación a **V+** para que los servos tomen sus referencias. Marca la posición del estriado. Corta **V+** antes de conectar, desconectar o atornillar. Presenta los ojos mirando al frente y las cuatro tapas cerradas, con los bordes encontrándose sin presión. Asienta los brazos en el diente más cercano. Si U/D queda inaccesible, marca la referencia y retira su cuerpo del soporte para indexarlo por fuera.
3. Vuelve a energizar en Hold. Si aparece zumbido continuo, tirones, calor o los párpados se presionan, corta **V+** de inmediato. Revisa el indexado, la alineación y las holguras antes de repetir. Hold sigue aplicando par. Para trabajar con las manos en el mecanismo, corta V+.
4. Con la UART hacia el ESP32 desconectada desde antes de encender, envía `CMD:O=0` en el monitor del Uno mientras estás en Hold. Pasa a Move y envía `CMD:O=25`, luego `CMD:O=50` y `CMD:O=100` si hay holgura. Estos valores son porcentajes de la apertura configurada. `CMD:EH=95,EV=90` prueba el eje horizontal y `CMD:EH=90,EV=95` el vertical. Prueba también 85° en cada eje, luego incrementa por pasos hacia cada extremo. `CMD:B=1` debe cerrar ambos lados y reabrirlos. En Move hay parpadeos y movimientos autónomos. Mantén las manos fuera.
5. Si una articulación se acerca al tope, reduce el recorrido de ese canal en `SERVOS` antes de continuar. Comprueba los extremos combinados de los dos ejes con los párpados abiertos y durante el parpadeo. Si el sentido de un párpado es incorrecto, revisa primero canal, montaje y orientación. Registra la configuración final por canal y vuelve a grabar el Uno con V+ apagado. [Calibración mecánica del autor, p. 10](https://makerworld.bblmw.com/makerworld/model/US83b6b7dde2b2f/design/2025-03-13_58f972adf6a6b.pdf)

## 6. Probar el conjunto

Para la primera prueba usa una LAN de confianza. El panel y la API de control aceptan órdenes sin autenticación, así que mantén el puerto 8000 dentro de esa red durante la puesta en marcha. Desde la raíz, instala las dependencias en un entorno Python 3.12 y arranca FastAPI directamente. Así el servidor queda accesible para el ESP32 en el puerto 8000 de la PC.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server_pc/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --app-dir server_pc --host 0.0.0.0 --port 8000
```

| Prueba | Resultado esperado |
| --- | --- |
| Arranque con D8 abierto | Ojos al frente y párpados cerrados. Sin parpadeos autónomos. Los comandos de movimiento se ignoran |
| Monitor Uno, sensor conectado | Ambas lecturas son plausibles y se actualizan cada 3,5 s |
| Monitor ESP32 a 115200 bps | Conexión Wi-Fi y luego WebSocket a `ws://IP_DE_LA_PC:8000/ws/animatronic`. Si falla, revisa IP, puerto, red de 2,4 GHz y firewall de la PC |
| Panel en `http://IP_DE_LA_PC:8000` | ESP32 conectado y temperatura/humedad coinciden con el monitor del Uno. Ante lectura fallida, el campo correspondiente aparece vacío |
| D8 cerrado, visión apagada | En el panel de calibración mueve Pan y Tilt y pulsa **Parpadear**. Prueba la luz D7 por separado. La boca es parte del avatar web |
| D8 abierto desde Move | Regresa a la pose de calibración y permanece quieto |
| Visión con cámara disponible | Mira en la dirección del rostro. Si un eje va al revés, usa la inversión de ese eje en el panel |
| Prueba sostenida | Sin roces, temblores persistentes, calentamiento ni reinicios. Si se reinicia al mover varios servos, mide caída de V+ y revisa fuente y retorno de tierra |

La prueba de hardware se puede hacer con el servidor y el panel solos. Para audio y asistente usa la [guía del servidor](DOC_03_App_Movil_y_Servidor_PC.md). El micrófono del teléfono requiere HTTPS en el navegador. La ruta de transcripción de audio del servidor usa el servicio de reconocimiento de Google. Realiza la verificación de voz aparte de la calibración mecánica.

## 7. Verificación de esta revisión

- Compilaron ambos sketches con Arduino AVR Boards 1.8.8 y ESP32 2.0.17. El Uno ocupó 44 % de flash y 39 % de RAM estática. El ESP32 ocupó 67 % de la partición de aplicación y 14 % de RAM estática.
                                                                                                                                                                                                                                                                                                                    - En un servidor local con clientes WebSocket simulados se probaron telemetría válida, lectura ausente, reconexión y envío de los comandos de mirada, parpadeo y luz. También se verificaron los límites de la API y el estado sin lectura en el panel.
- En el banco queda verificar la alimentación bajo carga, los sentidos y topes del mecanismo, el enlace UART/Wi-Fi entre las placas y la cámara y el audio con los dispositivos del equipo.
