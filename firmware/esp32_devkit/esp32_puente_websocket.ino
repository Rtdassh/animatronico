/**
 * ============================================================================
 * PROYECTO: Cabeza Animatrónica con IA Local
 * NODO: ESP32 DevKit V1 (Pasarela Inalámbrica Wi-Fi WebSocket <-> UART2)
 * ÁREA: Sistemas Embebidos y Robótica
 * ============================================================================
 * 
 * DISTRIBUCIÓN DE PINES OFICIAL:
 *   - GPIO 17 (TX2) : Salida UART2 (3.3V) -> Directo a Arduino Pin D2 (RX)
 *   - GPIO 16 (RX2) : Entrada UART2 (3.3V) <- Desde divisor 1k/2k (Arduino D3 TX)
 *   - GPIO 2        : LED azul integrado (Indicador de conexión Wi-Fi/WebSocket)
 *   - GND           : Tierra Común (Unida a Arduino y Fuente Externa de Servos)
 * ============================================================================
 */

#include <WiFi.h>
#include <WebSocketsClient.h>

// ----------------------------------------------------------------------------
// CONFIGURACIÓN DE RED WI-FI Y SERVIDOR PC LOCAL
// ----------------------------------------------------------------------------
// Ingrese el nombre y contraseña de su red Wi-Fi doméstica o punto de acceso:
const char* WIFI_SSID     = "TU_RED_WIFI";
const char* WIFI_PASSWORD = "TU_PASSWORD";

// Dirección IP local de la computadora (donde corre el servidor en Python):
const char* PC_SERVER_IP  = "192.168.1.15";
const uint16_t PC_PORT    = 8000;
const char* WS_PATH       = "/ws/animatronic";

// ----------------------------------------------------------------------------
// PINES Y HARDWARE SERIAL
// ----------------------------------------------------------------------------
#define PIN_UART2_RX  16  // Recibe telemetría desde Arduino (acondicionada a 3.3V)
#define PIN_UART2_TX  17  // Envía comandos hacia Arduino D2 (3.3V nativo)
#define PIN_STATUS_LED 2  // LED azul integrado en placa

// Tasa de baudios optimizada con el Arduino Uno (38400 bps: 4x ancho de banda y 0.16% error)
#define UART2_BAUD_RATE 38400

// ----------------------------------------------------------------------------
// OBJETOS Y VARIABLES GLOBALES
// ----------------------------------------------------------------------------
WebSocketsClient webSocket;
HardwareSerial ArduinoSerial(2); // Usar hardware UART2 del ESP32

String uartBuffer = "";
bool isWebSocketConnected = false;

// Buffer Latest-Command-Wins no bloqueante para evitar desbordamiento del FIFO UART
String pendingCommand = "";
bool hasPendingCommand = false;

// ============================================================================
// MANEJADOR DE EVENTOS WEBSOCKET (CALLBACK)
// ============================================================================

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      isWebSocketConnected = false;
      digitalWrite(PIN_STATUS_LED, LOW);
      Serial.println(F("[WS] Desconectado del servidor PC local. Reintentando..."));
      break;

    case WStype_CONNECTED:
      isWebSocketConnected = true;
      digitalWrite(PIN_STATUS_LED, HIGH); // LED fijo = Enlace activo
      Serial.println(F("[WS] ¡CONECTADO CON ÉXITO AL SERVIDOR DE LA PC!"));
      
      // Enviar mensaje de saludo e identificación
      webSocket.sendTXT("HELLO:NODE=ESP32_ANIMATRONIC_V1");
      break;

    case WStype_TEXT:
      {
        String command = String((char*)payload);
        command.trim();

        // Política Latest-Command-Wins para comandos cinemáticos continuos
        if (command.startsWith("CMD:")) {
          pendingCommand = command;
          hasPendingCommand = true;
        } else {
          // Comandos discretos o no continuos: enviar directamente
          ArduinoSerial.println(command);
        }
      }
      break;

    case WStype_BIN:
    case WStype_ERROR:
    case WStype_FRAGMENT_TEXT_START:
    case WStype_FRAGMENT_BIN_START:
    case WStype_FRAGMENT:
    case WStype_FRAGMENT_FIN:
    case WStype_PING:
    case WStype_PONG:
      break;
  }
}

// ============================================================================
// CONEXIÓN A LA RED WI-FI
// ============================================================================

void connectWiFi() {
  Serial.print(F("\n[WIFI] Conectando a red: "));
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED)); // Parpadeo rápido
    Serial.print(F("."));
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(PIN_STATUS_LED, LOW);
    Serial.println(F("\n[WIFI] ¡Conexión establecida con éxito!"));
    Serial.print(F("[WIFI] IP asignada al ESP32: "));
    Serial.println(WiFi.localIP());
  } else {
    Serial.println(F("\n[ERROR] No se pudo conectar a la red Wi-Fi. Revise credenciales."));
  }
}

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  // Puerto serie USB para depuración con la computadora
  Serial.begin(115200);
  delay(100);

  // Configuración de LED de estado
  pinMode(PIN_STATUS_LED, OUTPUT);
  digitalWrite(PIN_STATUS_LED, LOW);

  // Inicializar Hardware UART2 para comunicación de alta velocidad con Arduino Uno
  // 38400 baudios: 4x ancho de banda frente a 9600 bps originales
  ArduinoSerial.begin(UART2_BAUD_RATE, SERIAL_8N1, PIN_UART2_RX, PIN_UART2_TX);

  Serial.println(F("=================================================="));
  Serial.println(F(" ESP32 DevKit V1: Pasarela Wi-Fi WebSocket <-> UART2 "));
  Serial.println(F(" Hardware UART2: GPIO 16 (RX2), GPIO 17 (TX2)     "));
  Serial.println(F(" Baudrate: 38400 bps (Optimizado Latest-Frame)    "));
  Serial.println(F("=================================================="));

  // Conectar a la red inalámbrica
  connectWiFi();

  // Configuración del cliente WebSocket hacia la PC
  Serial.print(F("[WS] Configurando cliente hacia: ws://"));
  Serial.print(PC_SERVER_IP);
  Serial.print(F(":"));
  Serial.print(PC_PORT);
  Serial.println(WS_PATH);

  webSocket.begin(PC_SERVER_IP, PC_PORT, WS_PATH);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(2000); // Reintentar reconexión cada 2 segundos
  webSocket.enableHeartbeat(5000, 3000, 2); // Mantener enlace activo
}

// ============================================================================
// LOOP PRINCIPAL (No bloqueante, alta prioridad)
// ============================================================================

void loop() {
  // 1. Mantener la pila de red y el protocolo WebSocket activos con máxima prioridad
  webSocket.loop();

  // 2. Transmisión no bloqueante hacia Arduino Uno con buffer Latest-Command-Wins
  if (hasPendingCommand) {
    if (ArduinoSerial.availableForWrite() >= (int)(pendingCommand.length() + 2)) {
      ArduinoSerial.println(pendingCommand);
      hasPendingCommand = false;
    }
  }

  // 3. Verificar si hay datos que provienen del Arduino (Telemetría de sensores)
  while (ArduinoSerial.available() > 0) {
    char c = ArduinoSerial.read();
    if (c == '\n' || c == '\r') {
      if (uartBuffer.length() > 0) {
        // Si estamos conectados por WebSocket a la PC, enviar de inmediato
        if (isWebSocketConnected) {
          webSocket.sendTXT(uartBuffer);
        }
        uartBuffer = "";
      }
    } else {
      if (uartBuffer.length() < 128) {
        uartBuffer += c;
      }
    }
  }

  // 4. Reconexión Wi-Fi automática si se pierde la señal
  if (WiFi.status() != WL_CONNECTED) {
    static unsigned long lastWiFiCheck = 0;
    if (millis() - lastWiFiCheck > 10000) {
      lastWiFiCheck = millis();
      Serial.println(F("[WIFI] Señal perdida. Intentando reconectar..."));
      WiFi.reconnect();
    }
  }
}
