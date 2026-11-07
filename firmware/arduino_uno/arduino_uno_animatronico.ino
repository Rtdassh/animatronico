/**
 * ============================================================================
 * PROYECTO: Cabeza Animatrónica con IA Local
 * NODO: Arduino Uno R3 (Maestro I2C y Telemetría)
 * CONTROLADOR DE SERVOS: PCA9685 16 Canales PWM (I2C: 0x40)
 * MECANISMO OCULAR: Epsilon 3.2 (Will Cogley - MakerWorld #1184807)
 * AUDIO I/O: Teléfono Móvil Manos Libres (Micrófono + Altavoz vía Wi-Fi / WebSockets)
 * ÁREA: Sistemas Embebidos y Robótica
 * ============================================================================
 * 
 * DISTRIBUCIÓN OFICIAL DE PINES:
 *   - Pin D2   : SoftwareSerial RX (desde ESP32 TX2 / GPIO 17 - 3.3V)
 *   - Pin D3   : SoftwareSerial TX (hacia Divisor Resistivo 1k/2k -> ESP32 RX2)
 *   - Pin D4   : DATA Sensor de Humedad DHT11
 *   - Pin D7   : Control LED Indicador de Luz (con resistencia 220 Ohm)
 *   - Pin D10  : LIBRE (Audio procesado de forma inalámbrica por Smartphone)
 *   - Pin D11  : LIBRE (Audio procesado de forma inalámbrica por Smartphone)
 *   - Pin A4   : SDA Bus I2C Compartido (PCA9685: 0x40 y LM75A: 0x48)
 *   - Pin A5   : SCL Bus I2C Compartido (Reloj I2C a 400 kHz)
 *   - Pin 5V   : VCC exclusivo para lógica de sensores LM75A, DHT11 y lógica PCA9685
 *   - Pin GND  : Tierra común (unida a ESP32 y Fuente 5V 4A)
 * 
 * MAPEO DE CANALES EN CONTROLADOR PCA9685 (I2C: 0x40):
 *   - Canal 0  : M1 · Ojos Eje Horizontal (Pan / Yaw: 60° a 120°, neutro 90°)
 *   - Canal 1  : M2 · Ojos Eje Vertical (Tilt / Pitch: 70° a 110°, neutro 90°)
 *   - Canal 2  : M3 · Párpado Superior Izquierdo (45° cerrado a 100° abierto)
 *   - Canal 3  : M4 · Párpado Inferior Izquierdo (80° reposo a 110° elevado)
 *   - Canal 4  : M5 · Párpado Superior Derecho (45° cerrado a 100° abierto)
 *   - Canal 5  : M6 · Párpado Inferior Derecho (80° reposo a 110° elevado)
 *   - Canales 6-15 : Libres para expansión futura
 *   * NOTA: Audio e interactividad estilo Alexa gestionados por Smartphone manos libres.
 * ============================================================================
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <DHT.h>
#include <SoftwareSerial.h>

// ----------------------------------------------------------------------------
// CONFIGURACIÓN DE PINES Y CONSTANTES
// ----------------------------------------------------------------------------
#define PIN_SW_RX          2
#define PIN_SW_TX          3
#define PIN_DHT            4
#define PIN_LED            7
// Pines D10 y D11 quedan libres (audio y altavoz transferidos al Smartphone)

#define DHTTYPE DHT11
#define LM75_ADDR 0x48
#define PCA9685_ADDR 0x40

// Asignación de canales en PCA9685
#define PCA_CH_EYE_H       0   // M1: Horizontal (Pan)
#define PCA_CH_EYE_V       1   // M2: Vertical (Tilt)
#define PCA_CH_LID_TL      2   // M3: Párpado Sup. Izquierdo
#define PCA_CH_LID_BL      3   // M4: Párpado Inf. Izquierdo
#define PCA_CH_LID_TR      4   // M5: Párpado Sup. Derecho
#define PCA_CH_LID_BR      5   // M6: Párpado Inf. Derecho

// Configuración de pulsos PWM para PCA9685 (12 bits: 0 a 4095 a 50Hz)
#define SERVOMIN  120 // Longitud de pulso min (~550 us, 0 deg)
#define SERVOMAX  500 // Longitud de pulso max (~2400 us, 180 deg)

// Límites físicos de seguridad de los servomotores ε3.2
const int EYE_H_MIN       = 60;
const int EYE_H_MAX       = 120;
const int EYE_H_NEUTRAL   = 90;

const int EYE_V_MIN       = 70;
const int EYE_V_MAX       = 110;
const int EYE_V_NEUTRAL   = 90;

const int LID_TOP_CLOSED  = 45;
const int LID_TOP_OPEN    = 90;
const int LID_TOP_WIDE    = 100;

const int LID_BOT_REST    = 80;
const int LID_BOT_SQUINT  = 105;

// Temporizaciones asíncronas (millis)
const unsigned long TELEMETRY_INTERVAL_MS = 3000; // Enviar clima cada 3 seg
const unsigned long BLINK_DURATION_MS     = 140;  // Duración párpado cerrado
const unsigned long IDLE_SACCADE_TIMEOUT  = 6500; // Miradas aleatorias si no hay comandos

// ----------------------------------------------------------------------------
// INSTANCIAS DE OBJETOS
// ----------------------------------------------------------------------------
SoftwareSerial espSerial(PIN_SW_RX, PIN_SW_TX);
DHT dht(PIN_DHT, DHTTYPE);
Adafruit_PWMServoDriver pca = Adafruit_PWMServoDriver(PCA9685_ADDR);

// ----------------------------------------------------------------------------
// VARIABLES GLOBALES DE ESTADO
// ----------------------------------------------------------------------------
String inputBuffer = "";
unsigned long lastTelemetryTime = 0;
unsigned long lastCommandTime = 0;

// Variables para parpadeo autónomo
unsigned long nextBlinkTime = 0;
bool isBlinking = false;
unsigned long blinkStartTime = 0;

// Variables para micro-sacadas oculares (vida autónoma)
unsigned long nextSaccadeTime = 0;
int currentEyeHPos = EYE_H_NEUTRAL;
int currentEyeVPos = EYE_V_NEUTRAL;

// ============================================================================
// FUNCIONES AUXILIARES DE CONVERSIÓN DE ÁNGULO A PULSO PCA9685
// ============================================================================

/**
 * Convierte un ángulo en grados (0° a 180°) en cuentas de 12 bits para el PCA9685.
 */
int angleToPulse(int angle) {
  angle = constrain(angle, 0, 180);
  return map(angle, 0, 180, SERVOMIN, SERVOMAX);
}

void setServoAngle(uint8_t channel, int angle) {
  pca.setPWM(channel, 0, angleToPulse(angle));
}

void setEyelids(int topAngle, int botAngle) {
  setServoAngle(PCA_CH_LID_TL, topAngle);
  setServoAngle(PCA_CH_LID_TR, topAngle);
  setServoAngle(PCA_CH_LID_BL, botAngle);
  setServoAngle(PCA_CH_LID_BR, botAngle);
}

// ============================================================================
// FUNCIONES AUXILIARES DE SENSORES
// ============================================================================

float readLM75A() {
  Wire.beginTransmission(LM75_ADDR);
  Wire.write(0x00);
  if (Wire.endTransmission() != 0) {
    return -999.0;
  }

  Wire.requestFrom(LM75_ADDR, 2);
  if (Wire.available() >= 2) {
    uint8_t msb = Wire.read();
    uint8_t lsb = Wire.read();
    int16_t raw = (msb << 8) | lsb;
    return (raw >> 7) * 0.5;
  }
  return -999.0;
}

void sendTelemetry() {
  float temp = readLM75A();
  float hum = dht.readHumidity();

  if (isnan(hum)) hum = 0.0;
  if (temp < -100.0) temp = 0.0;

  String packet = "SENS:T=" + String(temp, 1) + ",H=" + String(hum, 1);
  espSerial.println(packet);

  Serial.print(F("[ARDUINO TX -> ESP32] "));
  Serial.println(packet);
}

// ============================================================================
// PARSER DE COMANDOS DESDE EL ESP32 / PC
// ============================================================================

/**
 * Procesa la trama recibida en formato: CMD:E=90,EV=90,B=0,L=1,A=1
 * Parámetros:
 *   E  o EH : Ojos Horizontal (60 - 120)
 *   EV      : Ojos Vertical (70 - 110)
 *   B       : Forzar Parpadeo (1 = sí, 0 = no)
 *   L       : Luz / LED (1 = encendido, 0 = apagado)
 *   A       : Pista de Audio (ID opcional para DFPlayer Mini)
 */
void processCommand(String cmd) {
  cmd.trim();
  if (!cmd.startsWith("CMD:")) return;

  lastCommandTime = millis();
  String params = cmd.substring(4);

  int eyeHVal  = currentEyeHPos;
  int eyeVVal  = currentEyeVPos;
  int blinkVal = 0;
  int lightVal = -1;

  int startIdx = 0;
  while (startIdx < params.length()) {
    int commaIdx = params.indexOf(',', startIdx);
    if (commaIdx == -1) commaIdx = params.length();

    String pair = params.substring(startIdx, commaIdx);
    int eqIdx = pair.indexOf('=');
    if (eqIdx != -1) {
      String key = pair.substring(0, eqIdx);
      int val = pair.substring(eqIdx + 1).toInt();

      key.toUpperCase();
      if (key == "E" || key == "EH") eyeHVal = val;
      else if (key == "EV") eyeVVal = val;
      else if (key == "B") blinkVal = val;
      else if (key == "L") lightVal = val;
    }
    startIdx = commaIdx + 1;
  }

  // 1. Aplicar posición de Ojos Horizontal (CH0) y Vertical (CH1) en PCA9685
  currentEyeHPos = constrain(eyeHVal, EYE_H_MIN, EYE_H_MAX);
  currentEyeVPos = constrain(eyeVVal, EYE_V_MIN, EYE_V_MAX);
  setServoAngle(PCA_CH_EYE_H, currentEyeHPos);
  setServoAngle(PCA_CH_EYE_V, currentEyeVPos);

  // 2. Forzar parpadeo coordinado ε3.2 en canales CH2-CH5
  if (blinkVal == 1 && !isBlinking) {
    isBlinking = true;
    blinkStartTime = millis();
    setEyelids(LID_TOP_CLOSED, LID_BOT_SQUINT);
  }

  // 3. Control de Luz / Relé
  if (lightVal == 1) {
    digitalWrite(PIN_LED, HIGH);
  } else if (lightVal == 0) {
    digitalWrite(PIN_LED, LOW);
  }

  Serial.print(F("[CMD APLICADO] EH="));
  Serial.print(currentEyeHPos);
  Serial.print(F(" EV="));
  Serial.print(currentEyeVPos);
  Serial.print(F(" L="));
  Serial.println(digitalRead(PIN_LED));
}

// ============================================================================
// GESTOR DE VIDA AUTÓNOMA
// ============================================================================

void updateAutonomy() {
  unsigned long now = millis();

  // 1. Parpadeo autónomo
  if (!isBlinking && now >= nextBlinkTime) {
    isBlinking = true;
    blinkStartTime = now;
    setEyelids(LID_TOP_CLOSED, LID_BOT_SQUINT);
  }

  if (isBlinking && (now - blinkStartTime >= BLINK_DURATION_MS)) {
    setEyelids(LID_TOP_OPEN, LID_BOT_REST);
    isBlinking = false;
    nextBlinkTime = now + random(3500, 6500);
  }

  // 2. Micro-sacadas oculares si no hay comandos activos
  if (now - lastCommandTime > IDLE_SACCADE_TIMEOUT) {
    if (now >= nextSaccadeTime) {
      int subtleH = random(82, 99);
      int subtleV = random(85, 96);
      setServoAngle(PCA_CH_EYE_H, subtleH);
      setServoAngle(PCA_CH_EYE_V, subtleV);
      currentEyeHPos = subtleH;
      currentEyeVPos = subtleV;
      nextSaccadeTime = now + random(2500, 5500);
    }
  }
}

// ============================================================================
// SETUP Y LOOP PRINCIPAL
// ============================================================================

void setup() {
  Serial.begin(115200);
  espSerial.begin(9600);

  Wire.begin();
  dht.begin();

  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);

  // Inicializar controlador PCA9685 a 50Hz para servomotores estándar
  pca.begin();
  pca.setPWMFreq(50);

  // Posicionar los 6 servos del ε3.2 en posición neutra de arranque
  setServoAngle(PCA_CH_EYE_H, EYE_H_NEUTRAL);
  setServoAngle(PCA_CH_EYE_V, EYE_V_NEUTRAL);
  setEyelids(LID_TOP_OPEN, LID_BOT_REST);

  randomSeed(analogRead(A0));
  nextBlinkTime = millis() + 3000;
  nextSaccadeTime = millis() + 5000;
  lastTelemetryTime = millis();

  Serial.println(F("=================================================="));
  Serial.println(F(" Arduino Uno R3: Mecanismo Ocular ε3.2 + PCA9685 "));
  Serial.println(F(" PCA9685 I2C (0x40): CH0-CH5 para 6 Servos Ojos  "));
  Serial.println(F(" Audio: Smartphone Manos Libres (Microfono/Altavoz)"));
  Serial.println(F(" Sensores: LM75A (I2C: 0x48) | DHT11 (Pin D4)    "));
  Serial.println(F(" SoftwareSerial ESP32: D2 (RX), D3 (TX)          "));
  Serial.println(F(" Pines D10/D11: Libres para futura expansion     "));
  Serial.println(F("=================================================="));
}

void loop() {
  while (espSerial.available() > 0) {
    char c = espSerial.read();
    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 0) {
        processCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      if (inputBuffer.length() < 64) {
        inputBuffer += c;
      }
    }
  }

  updateAutonomy();

  unsigned long now = millis();
  if (now - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryTime = now;
    sendTelemetry();
  }
}
