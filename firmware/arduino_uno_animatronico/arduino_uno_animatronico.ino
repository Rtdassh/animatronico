// Arduino Uno R3: seis servos EyeMech ε3.2, PCA9685 y DHT11.
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <DHT.h>
#include <SoftwareSerial.h>

constexpr uint8_t PIN_SW_RX = 2;
constexpr uint8_t PIN_SW_TX = 3;
constexpr uint8_t PIN_DHT = 4;
constexpr uint8_t PIN_LED = 7;
constexpr uint8_t PIN_RUN = 8;  // Abierto = Hold, cerrado a GND = Move.
constexpr uint8_t PCA9685_ADDR = 0x40;
constexpr unsigned long UART_BAUD = 38400;
constexpr unsigned long TELEMETRY_MS = 3500;
constexpr unsigned long BLINK_MS = 140;
constexpr unsigned long IDLE_MS = 6500;
constexpr unsigned long RUN_DEBOUNCE_MS = 50;

enum Channel : uint8_t { LR, UD, TL, BL, TR, BR, SERVO_COUNT };

struct ServoCalibration {
  uint8_t minAngle;
  uint8_t maxAngle;
  uint8_t holdAngle;
  uint8_t openAngle;  // Solo se usa para los párpados.
  uint16_t minPulseUs;  // Pulso equivalente a 0° antes de limitar el ángulo.
  uint16_t maxPulseUs;  // Pulso equivalente a 180° antes de limitar el ángulo.
};

// Orden del manual (L/R, U/D, TL, BL, TR, BR). Hold a 90°.
// TL y BR abren al aumentar el ángulo, BL y TR al disminuirlo.
// Los recorridos de puesta en marcha son deliberadamente reducidos.
const ServoCalibration SERVOS[SERVO_COUNT] = {
  // mín, máx, Hold, abierto, pulso 0°, pulso 180°
  {   60, 120,   90,     90,     1000,       2000 },  // CH0 L/R
  {   70, 110,   90,     90,     1000,       2000 },  // CH1 U/D
  {   90, 110,   90,    110,     1000,       2000 },  // CH2 TL
  {   70,  90,   90,     70,     1000,       2000 },  // CH3 BL
  {   70,  90,   90,     70,     1000,       2000 },  // CH4 TR
  {   90, 110,   90,    110,     1000,       2000 },  // CH5 BR
};

SoftwareSerial espSerial(PIN_SW_RX, PIN_SW_TX);
DHT dht(PIN_DHT, DHT11);  // Cambiar a DHT22 únicamente si se monta ese modelo.
Adafruit_PWMServoDriver pca(PCA9685_ADDR);

struct CommandBuffer {
  char text[64];
  uint8_t length = 0;
  bool overflow = false;
};

CommandBuffer espInput, usbInput;
bool pcaReady = false;
bool moving = false;
bool blinking = false;
int eyeH = SERVOS[LR].holdAngle;
int eyeV = SERVOS[UD].holdAngle;
int lidOpening = 100;
unsigned long lastHoldTime = 0;
unsigned long lastTelemetryTime = 0;
unsigned long lastCommandTime = 0;
unsigned long blinkStarted = 0;
unsigned long nextBlink = 0;
unsigned long nextSaccade = 0;

void setServoAngle(uint8_t channel, long angle) {
  const ServoCalibration &servo = SERVOS[channel];
  angle = constrain(angle, servo.minAngle, servo.maxAngle);
  pca.writeMicroseconds(channel, map(angle, 0, 180, servo.minPulseUs, servo.maxPulseUs));
}

void setEyes(long horizontal, long vertical) {
  int newH = constrain(horizontal, SERVOS[LR].minAngle, SERVOS[LR].maxAngle);
  int newV = constrain(vertical, SERVOS[UD].minAngle, SERVOS[UD].maxAngle);
  if (newH != eyeH) setServoAngle(LR, newH);
  if (newV != eyeV) setServoAngle(UD, newV);
  eyeH = newH;
  eyeV = newV;
}

void setLids(int opening) {
  for (uint8_t channel = TL; channel < SERVO_COUNT; ++channel) {
    const ServoCalibration &servo = SERVOS[channel];
    setServoAngle(channel, map(opening, 0, 100, servo.holdAngle, servo.openAngle));
  }
}

void startBlink(unsigned long now) {
  blinking = true;
  blinkStarted = now;
  setLids(0);
}

void updateMode(unsigned long now) {
  if (digitalRead(PIN_RUN) == HIGH) lastHoldTime = now;
  bool run = now - lastHoldTime >= RUN_DEBOUNCE_MS;
  if (run == moving) return;

  moving = run;
  blinking = false;
  if (moving) {
    setLids(lidOpening);
    lastCommandTime = now;
    nextBlink = now + 3000;
    nextSaccade = now + IDLE_MS;
    Serial.println(F("MOVE"));
  } else {
    setEyes(SERVOS[LR].holdAngle, SERVOS[UD].holdAngle);
    setLids(0);
    Serial.println(F("HOLD"));
  }
}

void processCommand(char *command, bool fromUsb) {
  if (strncmp(command, "CMD:", 4) != 0) return;

  long horizontal = eyeH;
  long vertical = eyeV;
  int opening = lidOpening;
  bool hasEyeCommand = false;
  bool blink = false;
  for (char *pair = strtok(command + 4, ","); pair; pair = strtok(nullptr, ",")) {
    char *equals = strchr(pair, '=');
    if (!equals) continue;
    *equals = '\0';

    char *end;
    long value = strtol(equals + 1, &end, 10);
    if (end == equals + 1 || *end != '\0') continue;

    if (strcmp(pair, "L") == 0 && (value == 0 || value == 1)) {
      digitalWrite(PIN_LED, value == 1 ? HIGH : LOW);
    } else if (strcmp(pair, "EH") == 0 || strcmp(pair, "E") == 0) {
      horizontal = value;
      hasEyeCommand = true;
    } else if (strcmp(pair, "EV") == 0) {
      vertical = value;
      hasEyeCommand = true;
    } else if (strcmp(pair, "B") == 0) {
      blink = value == 1;
    } else if (fromUsb && strcmp(pair, "O") == 0) {
      opening = constrain(value, 0, 100);
    }
  }

  if (opening != lidOpening) {
    lidOpening = opening;
    if (moving && !blinking) setLids(lidOpening);
  }
  if (!moving) return;
  if (hasEyeCommand) {
    lastCommandTime = millis();
    setEyes(horizontal, vertical);
  }
  if (blink && !blinking) startBlink(millis());
}

void readCommands(Stream &port, CommandBuffer &buffer, bool fromUsb) {
  while (port.available() > 0) {
    char byte = port.read();
    if (byte == '\r' || byte == '\n') {
      if (buffer.length && !buffer.overflow) {
        buffer.text[buffer.length] = '\0';
        processCommand(buffer.text, fromUsb);
      }
      buffer.length = 0;
      buffer.overflow = false;
    } else if (buffer.length < sizeof(buffer.text) - 1 && byte != '\0') {
      buffer.text[buffer.length++] = byte;
    } else {
      buffer.overflow = true;
    }
  }
}

void updateAutonomy(unsigned long now) {
  if (!blinking && static_cast<int32_t>(now - nextBlink) >= 0) startBlink(now);
  if (blinking && now - blinkStarted >= BLINK_MS) {
    setLids(lidOpening);
    blinking = false;
    nextBlink = now + random(3500, 6500);
  }
  if (now - lastCommandTime > IDLE_MS && static_cast<int32_t>(now - nextSaccade) >= 0) {
    setEyes(random(82, 99), random(85, 96));
    nextSaccade = now + random(2500, 5500);
  }
}

void printTelemetry(Print &port, float temperature, float humidity) {
  port.print(F("SENS:T="));
  if (isnan(temperature)) port.print(F("NA"));
  else port.print(temperature, 1);
  port.print(F(",H="));
  if (isnan(humidity)) port.println(F("NA"));
  else port.println(humidity, 1);
}

void setup() {
  Serial.begin(115200);
  espSerial.begin(UART_BAUD);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_RUN, INPUT_PULLUP);
  Wire.begin();
  dht.begin();

  pcaReady = pca.begin();
  if (pcaReady) {
    pca.setPWMFreq(50);
    setServoAngle(LR, eyeH);
    setServoAngle(UD, eyeV);
    setLids(0);
    Serial.println(F("PCA9685 0x40 OK. HOLD"));
  } else {
    Serial.println(F("ERROR: PCA9685 0x40 no responde. Revisar I2C y reiniciar."));
  }

  randomSeed(analogRead(A0));
  lastHoldTime = lastTelemetryTime = millis();
}

void loop() {
  unsigned long now = millis();
  if (pcaReady) updateMode(now);
  readCommands(espSerial, espInput, false);
  readCommands(Serial, usbInput, true);
  // Los comandos pueden actualizar sus marcas con millis() después de leer now.
  now = millis();
  if (moving) updateAutonomy(now);

  if (now - lastTelemetryTime >= TELEMETRY_MS) {
    lastTelemetryTime = now;
    float humidity = dht.readHumidity();
    float temperature = dht.readTemperature();
    printTelemetry(espSerial, temperature, humidity);
    printTelemetry(Serial, temperature, humidity);
  }
}
