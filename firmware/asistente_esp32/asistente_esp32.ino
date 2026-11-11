/*
  =============================================================================
  PROYECTO: Asistente de Escritorio Autónomo / Gran Hermano
  PLACA: ESP32 DevKit V1 (ESP32-WROOM-32)
  ROL: Pasarela Inalámbrica y Servidor Web Móvil de Diagnóstico
  HARDWARE:
    - UART2 Hardware Serial:
        * GPIO 16 (RX2) <- Recibe desde Divisor Resistivo (Arduino D3 TX)
        * GPIO 17 (TX2) -> Envía directo a Arduino D2 RX (3.3V compatible)
        * GND común unida a Arduino Uno y Fuente de Servos
    - Servidor Web HTTP (Puerto 80):
        * Punto de Acceso Wi-Fi: "Asistente-ESP32" (Clave: "arquitectura123")
        * IP por defecto: 192.168.4.1
  =============================================================================
*/

#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include "panel.h"

const char *AP_NAME = "Asistente-ESP32";
const char *AP_PASS = "arquitectura123";

HardwareSerial uartLink(2);
WebServer server(80);
Preferences settings;
String assistantUrl;
String internetSsid;
String internetPassword;
bool internetShared = false;
unsigned long lastNetworkCheck = 0;

void connectInternet() {
  WiFi.setAutoReconnect(true);
  if (internetSsid.length()) {
    WiFi.begin(internetSsid.c_str(), internetPassword.c_str());
    Serial.println(F("WIFI: conectando a la red de internet guardada"));
  }
}

String networkJson() {
  return String("{\"stationConnected\":") + (WiFi.status() == WL_CONNECTED ? "true" : "false") +
    ",\"shared\":" + (internetShared ? "true" : "false") +
    ",\"stationIP\":\"" + WiFi.localIP().toString() + "\",\"apIP\":\"" + WiFi.softAPIP().toString() +
    "\",\"dns\":\"" + WiFi.dnsIP().toString() + "\"}";
}

bool gotFrame = false;
unsigned long lastFrame = 0;
const unsigned long FRAME_TIMEOUT_MS = 6000;
bool commandReady = false;
unsigned long readyAt = 0;
unsigned long ackSequence = 0;
unsigned long frameSequence = 0;

int temp10 = -32768, hum10 = -1, flags = 0;
int servo0 = 90, servo1 = 90, autoMode = 0;
unsigned long unoUptime = 0;
int dhtErrors = 0, serialErrors = 0;
int lmAddr = 0, lcdAddr = 0, pcaAddr = 0;

char lastAck[48] = "";
char uartLine[128];
uint8_t uartLen = 0;

void parseLine(char *line) {
  if (strcmp(line, "R") == 0) {
    commandReady = true;
    readyAt = millis();
    return;
  }
  if (line[0] == 'A' && line[1] == ',') {
    strncpy(lastAck, line + 2, sizeof(lastAck) - 1);
    lastAck[sizeof(lastAck) - 1] = 0;
    ++ackSequence;
    Serial.print(F("ACK UNO: "));
    Serial.println(lastAck);
    return;
  }

  int t, h, f, s0, s1, aut, de, se, la, da, pa;
  unsigned long up;
  int n = sscanf(line, "S,%d,%d,%d,%d,%d,%d,%lu,%d,%d,%d,%d,%d",
                 &t, &h, &f, &s0, &s1, &aut, &up, &de, &se, &la, &da, &pa);
  if (n != 12) {
    Serial.print(F("Trama UART inválida: "));
    Serial.println(line);
    return;
  }

  temp10 = t;
  hum10 = h;
  flags = f;
  servo0 = s0;
  servo1 = s1;
  autoMode = aut;
  unoUptime = up;
  dhtErrors = de;
  serialErrors = se;
  lmAddr = la;
  lcdAddr = da;
  pcaAddr = pa;

  lastFrame = millis();
  ++frameSequence;
  gotFrame = true;
  Serial.print(F("TELEMETRIA UNO: "));
  Serial.println(line);
}

void readUART() {
  while (uartLink.available()) {
    char c = (char)uartLink.read();
    if (c == '\r') continue;
    if (c == '\n') {
      uartLine[uartLen] = 0;
      if (uartLen) parseLine(uartLine);
      uartLen = 0;
    } else if (uartLen < sizeof(uartLine) - 1) {
      uartLine[uartLen++] = c;
    } else {
      uartLen = 0;
    }
  }
}

bool ackSucceeded(const String &ack) {
  return ack == "PONG" || ack == "SCAN_OK" || ack == "BEEP_OK" ||
         ack == "AUTO_ON" || ack == "AUTO_OFF" || ack == "CMD_OK" ||
         ack == "ALL_PWM_OK" || ack == "PWM_ENVIADO" || ack == "LIGHT_OK" || ack == "BLINK_OK";
}

String sendUnoCommand(const String &command) {
  if (command.length() == 0 || command.length() > 31) return "COMANDO_INVALIDO";
  for (size_t i = 0; i < command.length(); ++i) {
    char c = command[i];
    if (!((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
          c == ':' || c == '_' || c == ',' || c == '=' || c == '-')) {
      return "COMANDO_INVALIDO";
    }
  }

  // Descartar permisos antiguos del buffer y esperar una nueva ventana del Uno.
  readUART();
  commandReady = false;
  unsigned long start = millis();
  while (millis() - start < 2500) {
    readUART();
    if (commandReady && millis() - readyAt < 40) break;
    delay(1);
  }
  if (!commandReady || millis() - readyAt >= 40) return "UNO_NO_DISPONIBLE";

  commandReady = false;
  unsigned long previousAck = ackSequence;
  unsigned long previousFrame = frameSequence;
  bool expectsStatus = command != "PING" && command != "BEEP" && command != "BLINK" && !command.startsWith("LIGHT:");
  uartLink.println(command);
  uartLink.flush();
  start = millis();
  while (millis() - start < 500) {
    readUART();
    if (ackSequence != previousAck) {
      String ack(lastAck);
      if (!expectsStatus || !ackSucceeded(ack) || frameSequence != previousFrame) return ack;
    }
    delay(1);
  }
  return ackSequence != previousAck ? "TELEMETRIA_NO_CONFIRMADA" : "SIN_CONFIRMACION";
}

String statusJson() {
  readUART();
  unsigned long frameAge = gotFrame ? millis() - lastFrame : 0;
  bool alive = gotFrame && frameAge < FRAME_TIMEOUT_MS;

  bool lm = alive && (flags & 0x01);
  bool dht = alive && (flags & 0x02);
  bool lcd = alive && (flags & 0x04);
  bool pca = alive && (flags & 0x08);

  char buf[512];
  int length = snprintf(buf, sizeof(buf),
    "{\"connected\":%s,\"received\":%s,\"lastFrame\":%lu,\"frameAgeMs\":%lu,\"temp10\":%d,\"hum10\":%d,"
    "\"lm\":%s,\"dht\":%s,\"lcd\":%s,\"pca\":%s,"
    "\"s0\":%d,\"s1\":%d,\"auto\":%s,\"uptime\":%lu,"
    "\"dhtErrors\":%d,\"serialErrors\":%d,"
    "\"lmAddr\":%d,\"lcdAddr\":%d,\"pcaAddr\":%d,\"ack\":\"%s\"}",
    alive ? "true" : "false",
    gotFrame ? "true" : "false",
    lastFrame,
    frameAge,
    alive ? temp10 : -32768,
    alive ? hum10 : -1,
    lm ? "true" : "false",
    dht ? "true" : "false",
    lcd ? "true" : "false",
    pca ? "true" : "false",
    servo0, servo1,
    autoMode ? "true" : "false",
    unoUptime,
    dhtErrors, serialErrors,
    lmAddr, lcdAddr, pcaAddr,
    lastAck
  );

  if (length < 0 || length >= (int)sizeof(buf)) {
    return "{\"error\":\"Estado demasiado largo\"}";
  }
  return String(buf);
}

void sendJson() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Cache-Control", "no-cache");
  server.send(200, "application/json", statusJson());
}

void handleCommand() {
  if (!server.hasArg("c")) {
    server.send(400, "application/json", "{\"ok\":false,\"error\":\"Falta argumento c\"}");
    return;
  }
  String c = server.arg("c");
  c.trim();

  Serial.print(F("CMD enviado a Uno: "));
  Serial.println(c);
  String ack = sendUnoCommand(c);

  char resp[128];
  snprintf(resp, sizeof(resp), "{\"ok\":%s,\"ack\":\"%s\"}",
           ackSucceeded(ack) ? "true" : "false", ack.c_str());
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", resp);
}

void setup() {
  Serial.begin(115200);
  delay(500);
  settings.begin("asistente", false);
  assistantUrl = settings.getString("pcUrl", "");
  internetSsid = settings.getString("wifiSsid", "");
  internetPassword = settings.getString("wifiPass", "");

  // Inicializar UART2 en GPIO 16 (RX) y GPIO 17 (TX) a 9600 baudios
  uartLink.begin(9600, SERIAL_8N1, 16, 17);

  // Iniciar Punto de Acceso Wi-Fi
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAPConfig(IPAddress(192,168,4,1), IPAddress(192,168,4,1), IPAddress(255,255,255,0),
                    IPAddress(192,168,4,2), IPAddress(1,1,1,1));
  if (!WiFi.softAP(AP_NAME, AP_PASS, 1, 0, 8)) {
    Serial.println(F("[ERROR] No se pudo iniciar el Punto de Acceso Wi-Fi"));
  } else {
    Serial.println(F("=================================================="));
    Serial.println(F("  ASISTENTE DE ESCRITORIO · ESP32 ACTIVO"));
    Serial.println(F("=================================================="));
    Serial.print(F("Red Wi-Fi AP: ")); Serial.println(AP_NAME);
    Serial.print(F("Clave:        ")); Serial.println(AP_PASS);
    Serial.print(F("Dirección IP: ")); Serial.println(WiFi.softAPIP());
    Serial.println(F("Abre en tu navegador: http://192.168.4.1"));
    Serial.println(F("=================================================="));
  }
  connectInternet();

  // Rutas del Servidor Web
  server.on("/", HTTP_GET, []() {
    server.sendHeader("Cache-Control", "no-store");
    String page(FPSTR(PANEL_HTML));
    String link = assistantUrl.length() ? assistantUrl : "https://192.168.4.2:8443";
    String setup = link;
    setup.replace("https://", "http://");
    setup.replace(":8443", ":8001");
    String nav = "<section style='padding:20px;background:#0e1219;color:#f1f5f9;font:16px system-ui'><h2>Asistente integrado</h2><p>Chat local, micrófono del celular, visión y hardware en una sola web.</p><p><a style='color:#38bdf8' href='" + link + "'>Abrir web unificada HTTPS</a> · <a style='color:#38bdf8' href='" + setup + "/setup'>Configurar certificado del celular</a></p><p>La computadora debe estar conectada a Asistente-ESP32 y ejecutar iniciar_web_unificada.bat. Si está apagada, los controles de abajo siguen disponibles.</p></section>";
    page.replace("<body>", "<body>" + nav);
    page.replace("<h2>Asistente integrado</h2>", String("<h2>Asistente integrado</h2><p>Internet: ") +
      (internetShared ? "conectado y compartido con esta red" : "esperando conexión del router") + "</p>");
    server.send(200, "text/html; charset=utf-8", page);
  });
  server.on("/api/assistant", HTTP_POST, []() {
    String url = server.arg("url");
    String host = url;
    host.replace("https://192.168.4.", "");
    int colon = host.indexOf(':');
    String octet = colon >= 0 ? host.substring(0, colon) : host;
    int number = octet.toInt();
    if (!url.startsWith("https://192.168.4.") || number < 2 || number > 254 ||
        octet != String(number) || (colon >= 0 && host.substring(colon) != ":8443")) {
      server.send(400, "application/json", "{\"ok\":false}"); return;
    }
    assistantUrl = url;
    settings.putString("pcUrl", url);
    server.send(200, "application/json", "{\"ok\":true}");
  });
  server.on("/api/status", HTTP_GET, sendJson);
  server.on("/api/network", HTTP_GET, []() {
    server.send(200, "application/json", networkJson());
  });
  server.on("/api/cmd", HTTP_GET, handleCommand);
  server.onNotFound([]() {
    server.send(404, "text/plain", "Ruta no encontrada");
  });

  server.begin();
  Serial.println(F("[OK] Servidor Web HTTP activo en puerto 80"));
}

char usbLine[128];
uint8_t usbLen = 0;
unsigned long lastSerialHeartbeat = 0;

void readUSBSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      usbLine[usbLen] = 0;
      if (usbLen > 0) {
        String cmd = String(usbLine);
        cmd.trim();
        if (cmd.startsWith("WIFI_CONFIG:")) {
          int separator = cmd.indexOf('\t', 12);
          if (separator > 12) {
            internetSsid = cmd.substring(12, separator);
            internetPassword = cmd.substring(separator + 1);
            settings.putString("wifiSsid", internetSsid);
            settings.putString("wifiPass", internetPassword);
            connectInternet();
            Serial.println(F("WIFI_CONFIG_OK"));
          } else Serial.println(F("WIFI_CONFIG_ERROR"));
        } else if (cmd == "NET_STATUS") {
          Serial.println(networkJson());
        } else if (cmd == "PING") {
          Serial.println(F("PONG"));
          String ack = sendUnoCommand(cmd);
          Serial.print(F("RESULT UNO: ")); Serial.println(ack);
        } else if (cmd == "STATUS") {
          // La misma respuesta JSON que recibe el panel, verificable por USB.
          Serial.println(statusJson());
        } else {
          Serial.print(F("FWD UNO: "));
          Serial.println(cmd);
          String ack = sendUnoCommand(cmd);
          Serial.print(F("RESULT UNO: ")); Serial.println(ack);
        }
      }
      usbLen = 0;
    } else if (usbLen < sizeof(usbLine) - 1) {
      usbLine[usbLen++] = c;
    } else {
      usbLen = 0;
    }
  }
}

void loop() {
  readUART();
  readUSBSerial();
  server.handleClient();
  if (millis() - lastNetworkCheck > 1000) {
    lastNetworkCheck = millis();
    if (WiFi.status() == WL_CONNECTED && !internetShared) {
      WiFi.STA.setDefault();
      internetShared = WiFi.AP.enableNAPT(true);
      Serial.print(F("INTERNET: ")); Serial.println(networkJson());
    } else if (WiFi.status() != WL_CONNECTED && internetShared) {
      WiFi.AP.enableNAPT(false);
      internetShared = false;
    }
  }

  if (millis() - lastSerialHeartbeat > 2000) {
    lastSerialHeartbeat = millis();
    if (gotFrame && (millis() - lastFrame < FRAME_TIMEOUT_MS)) {
      Serial.print(F("HEARTBEAT:OK,T="));
      Serial.print(temp10 / 10.0, 1);
      Serial.print(F(",H="));
      Serial.println(hum10 / 10.0, 1);
    } else {
      Serial.println(F("HEARTBEAT:ESP32_ALIVE"));
    }
  }
}

