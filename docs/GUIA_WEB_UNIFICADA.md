# Web unificada sobre la red del ESP32

El ESP32 mantiene la red **Asistente-ESP32** (clave `arquitectura123`) y el control autónomo del Arduino. La computadora, conectada a esa misma red y por USB al ESP32, sirve una sola web con dos espacios: **Asistente y visión** y **Hardware y servos**.

## Arranque

1. Enciende las placas y mantén el ESP32 conectado por USB a la computadora. Cierra los monitores serie que ocupen su puerto.
2. Ejecuta `iniciar_web_unificada.bat`. En Windows conecta la computadora al Wi-Fi del ESP32, detecta su IP y levanta HTTPS en el puerto 8443. Ollama debe estar ejecutándose con un modelo instalado; actualmente se verificó `qwen2.5:7b`.
3. Conecta el celular a **Asistente-ESP32**. Abre `http://192.168.4.1` y elige **Configurar certificado del celular** la primera vez.
4. Instala y confía en el certificado local. Después elige **Abrir web unificada HTTPS**. Con la dirección usada en las pruebas: `https://192.168.4.2:8443`.

La computadora debe seguir conectada al Wi-Fi del ESP32 durante el uso. El firmware con Arduino-ESP32 3.3.0 conecta simultáneamente el ESP32 al router y comparte internet mediante NAPT. Cuando el router no está disponible, las funciones locales siguen operativas. El lanzador registra la URL cada 10 segundos y actualiza el certificado y los enlaces cuando cambia la IP. Usa los enlaces de `http://192.168.4.1`, ya que la IP de la computadora puede ser `.2`, `.4` u otra asignada por DHCP.

El servidor puede ejecutarse como tarea manual de Windows **Animatronico-Web-Unificada**, usando Python sin consola. `iniciar_web_unificada.bat` la inicia y `detener_web_unificada.bat` la detiene. No tiene un desencadenador de inicio automático al encender la computadora. El registro está en `build/unified-service.log`; la instalación de la tarea está en `tools/instalar_servidor_local.ps1`.

Para abrir la misma web desde la computadora se ofrece `http://127.0.0.1:8002`, accesible solo desde la propia computadora. El servidor anterior del proyecto no es necesario; no ejecutes dos servidores intentando usar el mismo puerto serie.

## Certificado y micrófono del celular

El navegador exige un contexto seguro para acceder al micrófono. La configuración inicial está en `http://192.168.4.2:8001/setup`; esta página solo entrega el certificado público y las instrucciones. La aplicación, el audio, el video y WebSocket funcionan bajo el mismo origen HTTPS.

- **Android:** Ajustes → Seguridad → Cifrado y credenciales → Instalar certificado → Certificado de CA. Los nombres cambian según el fabricante.
- **iPhone:** instala el perfil descargado desde Ajustes → General → VPN y gestión de dispositivos. Luego activa su confianza en General → Información → Ajustes de confianza de certificados.

Compara la huella SHA256 que muestra la página con la consola del lanzador o con `server_pc/certs/metadata.json`. No saltes advertencias del navegador: si aparecen, revisa la instalación de confianza y la IP. La CA permanece igual cuando cambia la IP del servidor; no hace falta instalarla de nuevo por cada actualización del certificado de servidor.

Esta CA permite a quien tenga su clave emitir certificados que el teléfono confiará. La clave permanece en `server_pc/certs/ca-key.pem`; no se sirve por HTTP ni se incluye en Git. Elimina la CA de los ajustes del teléfono cuando ya no uses el proyecto. La instalación y confianza en el celular requieren intervención del usuario y no se han verificado automáticamente.

La regla **Animatronico Web ESP32** permite TCP 8443 y 8001 solo desde `192.168.4.0/24`. Para crearla en otra computadora, ejecuta `tools/habilitar_red_web.ps1` como administrador.

## Funcionalidades

| Función | Dónde se ejecuta | Acceso en la web |
|---|---|---|
| Chat y consultas del modelo | Ollama en la computadora | Entrada de texto, accesos rápidos y voz |
| Voz del celular | Captura en el navegador HTTPS; transcripción Vosk en el PC | Micrófono y modo manos libres |
| Activación sin tocar | Detección de voz y frases locales | Activa una vez y di «Oye V» u «Oye Uve» |
| Respuesta hablada | Windows local, Voicebox o Loquendo | Selector de voz y altavoz del celular |
| Visión y seguimiento | Cámara y OpenCV de la computadora | Iniciar visión, vista previa, inversión y suavizado |
| Sensores y 16 canales PWM | Uno y PCA9685, a través del ESP32 | Hardware y servos |
| Agenda y acciones del asistente | Servidor local | Consultas y API existentes |
| Control sin computadora | ESP32 y Arduino | Controles autónomos de `http://192.168.4.1` |

El modo manos libres solicita permiso al micrófono en el celular y necesita que la página permanezca abierta y activa. Los sistemas móviles pueden suspenderlo al bloquear la pantalla o pasar a segundo plano. Reconoce una frase, la envía al PC local y vuelve a escuchar; no depende de Web Speech ni de Google. La frase completa «Oye Uve dime la hora» se puede enviar en una sola intervención. Tras una respuesta hay una ventana de 7 segundos para continuar la conversación.

**Voz local Windows** es la opción inicial y funciona sin internet. Voicebox mantiene sus perfiles locales existentes. Loquendo necesita internet para sintetizar frases nuevas; su caché sigue disponible. Si una voz no está disponible, el servidor usa la voz local para conservar la respuesta del modelo. La selección de voz se guarda en el navegador. La música existente se conserva si el archivo correspondiente está instalado.

## Internet a través del ESP32

El firmware usa `WIFI_AP_STA` y `WiFi.AP.enableNAPT(true)` de la plataforma oficial Arduino-ESP32 3.3.0. Conserva el SSID **Asistente-ESP32**, admite hasta 8 clientes y anuncia DNS por DHCP. `GET http://192.168.4.1/api/network` informa si está conectado al router, su IP de salida y si la compartición está activada.

La contraseña del router se envía por USB y se guarda en Preferences del ESP32; no se incluye en el código ni en los binarios del repositorio. Para configurar otra red, con el servidor detenido:

```powershell
.venv\Scripts\python.exe tools\configurar_internet_esp32.py --port COM8 --ssid NOMBRE_DE_RED
```

La herramienta pide la contraseña sin mostrarla. La opción `--windows-profile` permite usar una clave guardada solo cuando el usuario lo ha autorizado explícitamente. Después de actualizar desde el firmware autónomo, desconecta y vuelve a conectar el Wi-Fi del celular para renovar el DNS.

## Canales de hardware

| Función | Canal/pin |
|---|---|
| Ojos horizontales | PCA9685 CH0 |
| Ojos verticales | PCA9685 CH1 |
| Párpados | PCA9685 CH2–CH5 |
| Boca y sincronización de voz | PCA9685 CH6 |
| Luz | Arduino D7 |
| Buzzer | Arduino D8 |

La boca usa **CH6**, separado de CH0, para que la voz no mueva los ojos ni compita con el seguimiento facial. Si se conecta un servo de boca, su señal debe ir a CH6. Los canales que no tengan actuador conectado siguen disponibles en el panel. El LCD continúa siendo opcional.

El servidor abre solo el ESP32 CP210x (actualmente COM8); el Uno permanece comunicado por UART. No se envían órdenes duplicadas por ambos USB. Hay una cola acotada que conserva la última posición pendiente por canal y el ESP32 espera las ventanas de recepción del Uno. Las órdenes combinadas del asistente se dividen en comandos cortos compatibles con su buffer.

## Preparar otra instalación

```powershell
py -3.13 -m venv --system-site-packages .venv
.venv\Scripts\python.exe -m pip install -r server_pc\requirements.txt
.venv\Scripts\python.exe tools\preparar_web_unificada.py --download-model --ip 192.168.4.2
```

El modelo español se descarga una vez desde Alpha Cephei y se guarda en `server_pc/models`. Los modelos y claves locales están excluidos de Git. Los dos firmwares de `firmware/asistente_arduino` y `firmware/asistente_esp32` deben actualizarse juntos.

## Verificación realizada

- Compilación y grabación de ambas placas con verificación de escritura.
- HTTPS con validación de la CA y del nombre/IP del certificado, sin desactivar TLS.
- Doce órdenes PING desde la API integrada, con cero errores serie.
- Consulta real a Qwen con lectura de temperatura y voz Windows; archivo WAV servido correctamente.
- Transcripción local de una frase de prueba: «hola cómo estás»; activación sintética «Oye Uve» admitiendo la variante «oye hube» del reconocedor.
- Video JPEG real y captura de cámara alrededor de 30 FPS. No hubo un rostro delante de la cámara en esta prueba, por lo que el seguimiento de una cara en movimiento queda pendiente de comprobación física.
- Pruebas de rutas, telemetría, expiración y normalización de comandos en `server_pc/tests/test_unified.py`.

El informe de ejecución queda en `build/verificacion-web-unificada.json`. Para repetir las pruebas con el servidor activo:

```powershell
.venv\Scripts\python.exe tools\verificar_web_unificada.py --vision --chat
```

El navegador de control de esta sesión no estuvo disponible. Faltan la revisión visual en el teléfono, la instalación de confianza de la CA y la prueba del micrófono real del celular. No se presentan esas comprobaciones como realizadas.
