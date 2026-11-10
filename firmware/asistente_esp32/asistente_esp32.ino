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
#include "panel.h"

const char *AP_NAME = "Asistente-ESP32";
const char *AP_PASS = "arquitectura123";

HardwareSerial uartLink(2);
WebServer server(80);

bool gotFrame = false;
unsigned long lastFrame = 0;

int temp10 = -32768, hum10 = -1, flags = 0;
int servo0 = 90, servo1 = 90, autoMode = 0;
unsigned long unoUptime = 0;
int dhtErrors = 0, serialErrors = 0;
int lmAddr = 0, lcdAddr = 0, pcaAddr = 0;

char lastAck[48] = "";
char uartLine[128];
uint8_t uartLen = 0;

void parseLine(char *line) {
  if (line[0] == 'A' && line[1] == ',') {
    strncpy(lastAck, line + 2, sizeof(lastAck) - 1);
    lastAck[sizeof(lastAck) - 1] = 0;
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

void sendJson() {
  readUART();
  bool alive = gotFrame && (millis() - lastFrame < 6000);

  bool lm = alive && (flags & 0x01);
  bool dht = alive && (flags & 0x02);
  bool lcd = alive && (flags & 0x04);
  bool pca = alive && (flags & 0x08);

  char buf[256];
  snprintf(buf, sizeof(buf),
    "{\"connected\":%s,\"lastFrame\":%lu,\"temp10\":%d,\"hum10\":%d,"
    "\"lm\":%s,\"dht\":%s,\"lcd\":%s,\"pca\":%s,"
    "\"s0\":%d,\"s1\":%d,\"auto\":%s,\"uptime\":%lu,"
    "\"dhtErrors\":%d,\"serialErrors\":%d,"
    "\"lmAddr\":%d,\"lcdAddr\":%d,\"pcaAddr\":%d,\"ack\":\"%s\"}",
    alive ? "true" : "false",
    lastFrame,
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

  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Cache-Control", "no-cache");
  server.send(200, "application/json", buf);
}

void handleCommand() {
  if (!server.hasArg("c")) {
    server.send(400, "application/json", "{\"ok\":false,\"error\":\"Falta argumento c\"}");
    return;
  }
  String c = server.arg("c");
  c.trim();

  // Enviar comando a través de UART2 hacia Arduino Uno
  uartLink.println(c);
  Serial.print(F("CMD enviado a Uno: "));
  Serial.println(c);

  // Esperar brevemente un posible ACK
  unsigned long t0 = millis();
  while (millis() - t0 < 80) {
    readUART();
  }

  char resp[128];
  snprintf(resp, sizeof(resp), "{\"ok\":true,\"cmd\":\"%s\",\"ack\":\"%s\"}", c.c_str(), lastAck);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", resp);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  // Inicializar UART2 en GPIO 16 (RX) y GPIO 17 (TX) a 9600 baudios
  uartLink.begin(9600, SERIAL_8N1, 16, 17);

  // Iniciar Punto de Acceso Wi-Fi
  WiFi.mode(WIFI_AP);
  if (!WiFi.softAP(AP_NAME, AP_PASS)) {
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

  // Rutas del Servidor Web
  server.on("/", HTTP_GET, []() {
    server.sendHeader("Cache-Control", "no-store");
    server.send_P(200, "text/html; charset=utf-8", PANEL_HTML);
  });
  server.on("/api/status", HTTP_GET, sendJson);
  server.on("/api/cmd", HTTP_GET, handleCommand);
  server.onNotFound([]() {
    server.send(404, "text/plain", "Ruta no encontrada");
  });

  server.begin();
  Serial.println(F("[OK] Servidor Web HTTP activo en puerto 80"));
}

void loop() {
  readUART();
  server.handleClient();
}

