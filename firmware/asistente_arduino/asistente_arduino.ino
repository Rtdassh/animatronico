/*
  =============================================================================
  PROYECTO: Asistente de Escritorio Autónomo / Gran Hermano
  PLACA: Arduino UNO R3 (Microcontrolador ATmega328P)
  HARDWARE:
    - Bus I2C compartido (A4 = SDA, A5 = SCL):
        * LM75A Sensor de Temperatura (0x48 - 0x4F)
        * LCD 1602 con adaptador PCF8574 (0x27 o 0x3F)
        * PCA9685 Controlador PWM 16 Canales (0x40 - 0x47)
    - Sensor DHT11 en Pin D4 (Humedad y Temperatura con lectura por ciclos)
    - Buzzer pasivo KY-006 en Pin D8 (Señal S)
    - Servos SG90 en Canales 0 y 1 del PCA9685 (Alimentación externa 5V en borne V+)
    - Comunicación Serie con ESP32 (SoftwareSerial):
        * Pin D2 (RX) <- Directo desde ESP32 TX2 / GPIO17 (3.3V)
        * Pin D3 (TX) -> Divisor Resistivo (1kΩ serie + 2kΩ a GND) -> ESP32 RX2 / GPIO16
        * Tasa: 38400 baudios (4x ancho de banda, baja latencia para servos)
    - Monitor Serie USB: 115200 baudios para diagnóstico y comandos manuales
  =============================================================================
*/

#include <Wire.h>
#include <SoftwareSerial.h>
#include <string.h>
#include <stdlib.h>

const uint8_t DHT_PIN = 4;
const uint8_t BUZZER_PIN = 8;
const uint8_t LIGHT_PIN = 7;
unsigned long blinkUntil = 0;
int blinkSaved[4];
const uint8_t RX_FROM_ESP = 2;
const uint8_t TX_TO_ESP = 3;

SoftwareSerial link(RX_FROM_ESP, TX_TO_ESP);

uint8_t lmAddr = 0, lcdAddr = 0, pcaAddr = 0;
bool lmOK = false, dhtOK = false, lcdOK = false, pcaOK = false;
bool automatico = false;

int temp10 = -32768, hum10 = -1;
int servo0 = 90, servo1 = 90;
int servoAngles[16] = {90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90};
uint16_t dhtErrors = 0, serialErrors = 0;
uint8_t dhtErrorCode = 0; // 1=inicio, 2/3=respuesta, 4/5=datos, 6=checksum, 7=rango

unsigned long lastSensor = 0, lastStatus = 0, lastScan = 0, lastLCD = 0, lastAuto = 0;
unsigned long lastReady = 0;
bool commandWindow = false;
char commandLine[32];
uint8_t commandLen = 0;
bool commandOverflow = false;
char usbLine[32];
uint8_t usbLen = 0;
bool usbOverflow = false;

bool i2cProbe(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

bool i2cRegWrite(uint8_t addr, uint8_t reg, uint8_t value) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

void scanModules() {
  lmAddr = 0; lcdAddr = 0; pcaAddr = 0;
  for (uint8_t a = 0x48; a <= 0x4F; ++a) {
    if (i2cProbe(a)) { lmAddr = a; break; }
  }
  for (uint8_t a = 0x40; a <= 0x47; ++a) {
    if (i2cProbe(a)) { pcaAddr = a; break; }
  }
  if (i2cProbe(0x27)) lcdAddr = 0x27;
  else if (i2cProbe(0x3F)) lcdAddr = 0x3F;

  lmOK = (lmAddr != 0);
  lcdOK = (lcdAddr != 0);
  pcaOK = (pcaAddr != 0);
}

bool readLM75(int &value10) {
  if (!lmAddr) return false;
  Wire.beginTransmission(lmAddr);
  Wire.write((uint8_t)0x00);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)lmAddr, 2) != 2) return false;
  int16_t raw = (int16_t)((Wire.read() << 8) | Wire.read());
  // LM75: temperatura signed de 9 a 11 bits justificada a la izquierda
  value10 = (int)((int32_t)raw * 10 / 256);
  return true;
}

// Mide el nivel que YA está presente evitando pérdida de pulsos consecutivos
uint16_t dhtLevelCycles(volatile uint8_t *port, uint8_t mask, bool level) {
  uint16_t cycles = 0;
  while (((*port & mask) != 0) == level) {
    if (++cycles >= 2000) return 0;
  }
  return cycles;
}

bool readDHT11(int &temperature10, int &humidity10) {
  dhtErrorCode = 0;
  uint8_t data[5] = {0, 0, 0, 0, 0};
  volatile uint8_t *port = portInputRegister(digitalPinToPort(DHT_PIN));
  uint8_t mask = digitalPinToBitMask(DHT_PIN);

  // Pulso de inicio: LOW durante ~20ms, luego soltar DATA a entrada pull-up
  pinMode(DHT_PIN, OUTPUT);
  digitalWrite(DHT_PIN, LOW);
  delay(20);
  pinMode(DHT_PIN, INPUT_PULLUP);

  noInterrupts();
  uint16_t startHigh = dhtLevelCycles(port, mask, HIGH);
  uint16_t responseLow = startHigh ? dhtLevelCycles(port, mask, LOW) : 0;
  uint16_t responseHigh = responseLow ? dhtLevelCycles(port, mask, HIGH) : 0;
  bool ok = startHigh && responseLow && responseHigh;

  if (!startHigh) dhtErrorCode = 1;
  else if (!responseLow) dhtErrorCode = 2;
  else if (!responseHigh) dhtErrorCode = 3;

  for (uint8_t i = 0; i < 40; ++i) {
    if (!ok) break;
    uint16_t lowCycles = dhtLevelCycles(port, mask, LOW);
    uint16_t highCycles = dhtLevelCycles(port, mask, HIGH);
    if (!lowCycles || !highCycles) {
      dhtErrorCode = lowCycles ? 5 : 4;
      ok = false;
      break;
    }
    data[i / 8] <<= 1;
    if (highCycles > lowCycles) data[i / 8] |= 1;
  }
  interrupts();

  if (!ok) return false;
  if ((uint8_t)(data[0] + data[1] + data[2] + data[3]) != data[4]) {
    dhtErrorCode = 6;
    return false;
  }
  if (data[0] > 100) {
    dhtErrorCode = 7;
    return false;
  }

  humidity10 = data[0] * 10 + data[1];
  temperature10 = data[2] * 10 + data[3];
  if (data[3] & 0x80) temperature10 = -temperature10;
  return true;
}

bool pcaSetAngle(uint8_t channel, int angle) {
  if (!pcaAddr || channel > 15) return false;
  angle = constrain(angle, 30, 150);
  // SG90: rango conservador de 1000 a 2000 us a 50 Hz
  uint16_t pulse = 1000 + (uint32_t)(angle - 30) * 1000 / 120;
  uint16_t ticks = (uint32_t)pulse * 4096 / 20000;
  Wire.beginTransmission(pcaAddr);
  Wire.write((uint8_t)(0x06 + 4 * channel));
  Wire.write((uint8_t)0);
  Wire.write((uint8_t)0);
  Wire.write((uint8_t)(ticks & 0xFF));
  Wire.write((uint8_t)(ticks >> 8));
  return Wire.endTransmission() == 0;
}

bool pcaStart() {
  if (!pcaAddr) return false;
  // Prescale 121 produce ~50 Hz con oscilador nominal de 25 MHz
  if (!i2cRegWrite(pcaAddr, 0x00, 0x10)) return false;
  if (!i2cRegWrite(pcaAddr, 0xFE, 121)) return false;
  if (!i2cRegWrite(pcaAddr, 0x00, 0x20)) return false;
  delay(5);
  if (!i2cRegWrite(pcaAddr, 0x00, 0xA0)) return false;

  bool allOk = true;
  for (uint8_t ch = 0; ch < 16; ++ch) {
    if (!pcaSetAngle(ch, servoAngles[ch])) allOk = false;
  }
  return allOk;
}


bool lcdExpander(uint8_t value) {
  if (!lcdAddr) return false;
  Wire.beginTransmission(lcdAddr);
  Wire.write(value | 0x08); // Retroiluminación activa (bit 3)
  return Wire.endTransmission() == 0;
}

bool lcdNibble(uint8_t value, bool rs) {
  uint8_t out = (value & 0xF0) | (rs ? 1 : 0);
  if (!lcdExpander(out | 0x04)) return false;
  delayMicroseconds(1);
  if (!lcdExpander(out)) return false;
  delayMicroseconds(50);
  return true;
}

bool lcdByte(uint8_t value, bool rs) {
  return lcdNibble(value, rs) && lcdNibble(value << 4, rs);
}

bool lcdCommand(uint8_t value) {
  bool ok = lcdByte(value, false);
  if (value == 0x01 || value == 0x02) delay(2);
  return ok;
}

bool lcdStart() {
  if (!lcdAddr) return false;
  delay(50);
  lcdExpander(0x00);
  delay(15);
  lcdNibble(0x30, false); delay(5);
  lcdNibble(0x30, false); delayMicroseconds(150);
  lcdNibble(0x30, false); delay(1);
  lcdNibble(0x20, false); delay(1); // Modo 4 bits
  if (!lcdCommand(0x28)) return false; // 2 líneas, fuente 5x8
  if (!lcdCommand(0x08)) return false; // Display off
  if (!lcdCommand(0x01)) return false; // Clear
  if (!lcdCommand(0x06)) return false; // Entry mode
  if (!lcdCommand(0x0C)) return false; // Display on, cursor off
  return true;
}

void lcdLine(uint8_t line, const char *text) {
  if (!lcdAddr) return;
  lcdCommand(line == 0 ? 0x80 : 0xC0);
  uint8_t i = 0;
  while (text[i] && i < 16) {
    lcdByte((uint8_t)text[i], true);
    ++i;
  }
  while (i < 16) {
    lcdByte(' ', true);
    ++i;
  }
}

void updateLCD() {
  if (!lcdAddr) return;
  char l1[17], l2[17];
  if (temp10 > -3000) {
    int whole = temp10 / 10;
    int dec = abs(temp10 % 10);
    snprintf(l1, sizeof(l1), "%s %d.%d C", lmOK ? "LM75" : "DHT11", whole, dec);
  } else {
    strncpy(l1, "TEMP SIN DATOS", sizeof(l1));
  }

  if (dhtOK && hum10 >= 0) {
    int whole = hum10 / 10;
    snprintf(l2, sizeof(l2), "DHT11 %d%%", whole);
  } else {
    snprintf(l2, sizeof(l2), "DHT11 ERROR E%d", dhtErrorCode);
  }

  lcdLine(0, l1);
  lcdLine(1, l2);
}

void ack(const char *msg) {
  link.print("A,");
  link.println(msg);
  Serial.print("ACK: ");
  Serial.println(msg);
}

void sendStatus() {
  uint8_t flags = 0;
  if (lmOK)  flags |= 0x01;
  if (dhtOK) flags |= 0x02;
  if (lcdOK) flags |= 0x04;
  if (pcaOK) flags |= 0x08;

  char buf[96];
  snprintf(buf, sizeof(buf), "S,%d,%d,%u,%d,%d,%u,%lu,%u,%u,%u,%u,%u",
           temp10, hum10, (unsigned)flags, servo0, servo1,
           automatico ? 1 : 0, millis() / 1000UL,
           dhtErrors, serialErrors,
           (unsigned)lmAddr, (unsigned)lcdAddr, (unsigned)pcaAddr);
  link.println(buf);
  Serial.print("TX UART: ");
  Serial.println(buf);
}

void processCommand(char *cmd) {
  Serial.print("CMD recibido: ");
  Serial.println(cmd);

  if (strcmp(cmd, "PING") == 0) {
    ack("PONG");
    return;
  }
  if (strcmp(cmd, "LIGHT:0") == 0 || strcmp(cmd, "LIGHT:1") == 0) {
    digitalWrite(LIGHT_PIN, cmd[6] == '1' ? HIGH : LOW);
    ack("LIGHT_OK");
    return;
  }
  if (strcmp(cmd, "BLINK") == 0) {
    if (!pcaAddr) { ack("PCA_NO_DETECTADO"); return; }
    for (uint8_t i = 0; i < 4; ++i) {
      if (!blinkUntil) blinkSaved[i] = servoAngles[i + 2];
      pcaSetAngle(i + 2, (i % 2 == 0) ? 45 : 105);
    }
    blinkUntil = millis() + 140;
    ack("BLINK_OK");
    return;
  }
  if (strncmp(cmd, "CMD:", 4) == 0) {
    char *p = cmd + 4;
    char *token = strtok(p, ",");
    while (token != NULL) {
      char *eq = strchr(token, '=');
      if (eq != NULL) {
        *eq = '\0';
        char *key = token;
        int val = atoi(eq + 1);
        if (strcmp(key, "EH") == 0) {
          int a = constrain(val, 30, 150);
          pcaSetAngle(0, a);
          servo0 = a;
          servoAngles[0] = a;
        } else if (strcmp(key, "EV") == 0) {
          int a = constrain(val, 30, 150);
          pcaSetAngle(1, a);
          servo1 = a;
          servoAngles[1] = a;
        } else if (strcmp(key, "B") == 0 && val == 1) {
          tone(BUZZER_PIN, 2200, 100);
        }
      }
      token = strtok(NULL, ",");
    }
    ack("CMD_OK");
    sendStatus();
    return;
  }
  if (strcmp(cmd, "SCAN") == 0) {
    scanModules();
    pcaOK = pcaStart();
    lcdOK = lcdStart();
    ack("SCAN_OK");
    sendStatus();
    return;
  }
  if (strcmp(cmd, "BEEP") == 0) {
    tone(BUZZER_PIN, 2200, 150);
    ack("BEEP_OK");
    return;
  }
  if (strcmp(cmd, "AUTO:1") == 0) {
    automatico = true;
    ack("AUTO_ON");
    sendStatus();
    return;
  }
  if (strcmp(cmd, "AUTO:0") == 0) {
    automatico = false;
    ack("AUTO_OFF");
    sendStatus();
    return;
  }
  if (strncmp(cmd, "S_ALL:", 6) == 0) {
    char *end;
    long angle = strtol(cmd + 6, &end, 10);
    if (*end || angle < 30 || angle > 150) {
      ack("ANGULO_INVALIDO");
      return;
    }
    if (!pcaAddr) {
      ack("PCA_NO_DETECTADO");
      return;
    }
    for (uint8_t ch = 0; ch < 16; ++ch) {
      pcaSetAngle(ch, (int)angle);
      servoAngles[ch] = (int)angle;
    }
    servo0 = (int)angle;
    servo1 = (int)angle;
    ack("ALL_PWM_OK");
    sendStatus();
    return;
  }

  if (cmd[0] == 'S') {
    char *colon = strchr(cmd, ':');
    if (colon != NULL) {
      char *endCh;
      long channel = strtol(cmd + 1, &endCh, 10);
      if (endCh == colon && channel >= 0 && channel <= 15) {
        char *endAng;
        long angle = strtol(colon + 1, &endAng, 10);
        if (*endAng || angle < 30 || angle > 150) {
          ack("ANGULO_INVALIDO");
          return;
        }
        if (!pcaAddr) {
          ack("PCA_NO_DETECTADO");
          return;
        }
        bool ok = pcaSetAngle((uint8_t)channel, (int)angle);
        if (ok) {
          servoAngles[channel] = (int)angle;
          if (channel == 0) servo0 = (int)angle;
          else if (channel == 1) servo1 = (int)angle;
        }
        pcaOK = ok;
        ack(ok ? "PWM_ENVIADO" : "PCA_ERROR");
        sendStatus();
        return;
      }
    }
  }

  ++serialErrors;
  ack("COMANDO_INVALIDO");
}

void readCommands() {
  while (link.available()) {
    char c = (char)link.read();
    if (c == '\r') continue;
    if (c == '\n') {
      commandLine[commandLen] = 0;
      if (!commandOverflow && commandLen) processCommand(commandLine);
      commandLen = 0;
      commandOverflow = false;
    } else if (commandOverflow) {
      continue;
    } else if (commandLen < sizeof(commandLine) - 1) {
      commandLine[commandLen++] = c;
    } else {
      commandLen = 0;
      commandOverflow = true;
      ++serialErrors;
    }
  }
}

void readUsbCommands() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      usbLine[usbLen] = 0;
      if (!usbOverflow && usbLen) processCommand(usbLine);
      usbLen = 0;
      usbOverflow = false;
    } else if (usbOverflow) {
      continue;
    } else if (usbLen < sizeof(usbLine) - 1) {
      usbLine[usbLen++] = c;
    } else {
      usbLen = 0;
      usbOverflow = true;
      ++serialErrors;
    }
  }
}

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LIGHT_PIN, OUTPUT);
  pinMode(DHT_PIN, INPUT_PULLUP);
  Serial.begin(115200);
  link.begin(38400);
  Wire.begin();
  Wire.setClock(100000);
  Wire.setWireTimeout(25000, true);
  delay(300);

  scanModules();
  pcaOK = pcaStart();
  lcdOK = lcdStart();

  Serial.println(F("UNO listo: LM75 / DHT11 / LCD / PCA9685 / UART"));
  Serial.println(F("Comandos USB a 115200 (Nueva linea): S0:45 / S0:90 / S0:135 / BEEP / SCAN"));
  sendStatus();
}

void loop() {
  readCommands();
  unsigned long now = millis();
  // SoftwareSerial no recibe mientras transmite o el DHT bloquea interrupciones.
  // R concede una ventana de escucha: el ESP32 inicia una sola orden durante
  // sus primeros 40 ms y la trama completa (máximo 33 bytes) cabe en 90 ms.
  if (commandWindow && now - lastReady < 90) {
    delay(1);
    return;
  }
  commandWindow = false;
  readUsbCommands();
  if (blinkUntil && (long)(now - blinkUntil) >= 0) {
    for (uint8_t i = 0; i < 4; ++i) pcaSetAngle(i + 2, blinkSaved[i]);
    blinkUntil = 0;
  }

  // Muestreo periódico de sensores cada 2.5 segundos
  if (now - lastSensor >= 2500) {
    lastSensor = now;
    int t, h;
    lmOK = readLM75(t);
    temp10 = lmOK ? t : -32768;

    dhtOK = readDHT11(t, h);
    if (dhtOK) {
      hum10 = h;
      if (!lmOK) {
        temp10 = t;
      }
      Serial.print(F("DHT11 humedad x10: ")); Serial.println(hum10);
      Serial.print(F("DHT11 temp x10: ")); Serial.println(temp10);
    } else {
      hum10 = -1;
      ++dhtErrors;
      Serial.print(F("DHT11 error E")); Serial.println(dhtErrorCode);
    }

    pcaOK = pcaAddr && i2cProbe(pcaAddr);

    // Alerta automática: temperatura >= 30.0 C o humedad >= 75.0 %
    if (automatico && now - lastAuto >= 15000 &&
        ((lmOK && temp10 >= 300) || (dhtOK && hum10 >= 750))) {
      lastAuto = now;
      tone(BUZZER_PIN, 1800, 250);
      if (pcaOK && pcaSetAngle(0, 130)) servo0 = 130;
    }
  }

  // Refresco de pantalla LCD cada 3 segundos
  if (now - lastLCD >= 3000) {
    lastLCD = now;
    updateLCD();
  }

  // Auto-recuperación de bus I2C cada 10 segundos si un módulo se desconecta
  if (now - lastScan >= 10000) {
    lastScan = now;
    if (!lmAddr || !lcdAddr || !pcaAddr || !lmOK || !lcdOK || !pcaOK) {
      scanModules();
      if (pcaAddr) pcaOK = pcaStart();
      if (lcdAddr) lcdOK = lcdStart();
    }
  }

  // Envío periódico de telemetría UART al ESP32 cada 1.5 segundos
  if (now - lastStatus >= 1500) {
    lastStatus = now;
    sendStatus();
  }

  if (millis() - lastReady >= 120) {
    link.println(F("R"));
    lastReady = millis();
    commandWindow = true;
  }
}

