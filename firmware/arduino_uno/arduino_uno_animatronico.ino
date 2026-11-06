/**
 * ============================================================================
 * PROYECTO: Cabeza Animatrónica con IA Local
 * NODO: Arduino Uno R3 (Controlador de Tiempo Real, Actuadores y Sensores)
 * ÁREA: Sistemas Embebidos y Robótica
 * ============================================================================
 * 
 * DISTRIBUCIÓN DE PINES OFICIAL:
 *   - Pin D2  : SoftwareSerial RX (desde ESP32 TX2 / GPIO 17 - 3.3V)
 *   - Pin D3  : SoftwareSerial TX (hacia Divisor Resistivo 1k/2k -> ESP32 RX2)
 *   - Pin D4  : DATA Sensor de Humedad DHT11
 *   - Pin D7  : Control LED Indicador de Luz (con resistencia 220 Ohm)
 *   - Pin D9  : PWM Servo 1 (Ojos Horizontal: 60° a 120°, neutro 90°)
 *   - Pin D10 : PWM Servo 2 (Párpados: 50° cerrado a 100° abierto, neutro 90°)
 *   - Pin D11 : PWM Servo 3 (Boca Lip-Sync: 90° cerrado a 130° apertura máx)
 *   - Pin A4  : SDA Bus I2C Sensor Temperatura LM75A (Dirección 0x48)
 *   - Pin A5  : SCL Bus I2C Sensor Temperatura LM75A
 *   - Pin 5V  : VCC exclusivo para lógica de sensores LM75A y DHT11
 *   - Pin GND : Tierra común (unida a ESP32 y a fuente externa de 5V)
 * ============================================================================
 */

#include <Wire.h>
#include <Servo.h>
#include <DHT.h>
#include <SoftwareSerial.h>

// ----------------------------------------------------------------------------
// CONFIGURACIÓN DE PINES Y CONSTANTES
// ----------------------------------------------------------------------------
#define PIN_SW_RX       2
#define PIN_SW_TX       3
#define PIN_DHT         4
#define PIN_LED         7
#define PIN_SERVO_EYES  9
#define PIN_SERVO_LIDS 10
#define PIN_SERVO_MOUTH 11

#define DHTTYPE DHT11
#define LM75_ADDR 0x48

// Límites físicos de seguridad de los servomotores (Para proteger engranajes)
const int EYES_MIN   = 60;
const int EYES_MAX   = 120;
const int EYES_NEUTRAL = 90;

const int LIDS_CLOSED = 50;
const int LIDS_OPEN   = 90;
const int LIDS_WIDE   = 100;

const int MOUTH_CLOSED = 90;
const int MOUTH_MAX    = 130;

// Temporizaciones asíncronas (millis)
const unsigned long TELEMETRY_INTERVAL_MS = 3000; // Enviar clima cada 3 seg
const unsigned long BLINK_DURATION_MS     = 140;  // Duración párpado cerrado
const unsigned long IDLE_SACCADE_TIMEOUT  = 8000; // Miradas aleatorias si no hay comandos

// ----------------------------------------------------------------------------
// INSTANCIAS DE OBJETOS
// ----------------------------------------------------------------------------
SoftwareSerial espSerial(PIN_SW_RX, PIN_SW_TX);
DHT dht(PIN_DHT, DHTTYPE);

Servo servoEyes;
Servo servoLids;
Servo servoMouth;

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
int currentEyesPos = EYES_NEUTRAL;
int currentMouthPos = MOUTH_CLOSED;
int currentLidsPos = LIDS_OPEN;

// ============================================================================
// FUNCIONES AUXILIARES DE LECTURA DE SENSORES
// ============================================================================

/**
 * Lee la temperatura en grados Celsius desde el sensor digital LM75A mediante I2C.
 * Resolución nativa: 0.5 °C en los 9 bits más significativos.
 */
float readLM75A() {
  Wire.beginTransmission(LM75_ADDR);
  Wire.write(0x00); // Registro Pointer 0: Temperatura
  if (Wire.endTransmission() != 0) {
    return -999.0; // Error en bus I2C
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

/**
 * Empaqueta y transmite la telemetría ambiental hacia el ESP32 y el monitor USB.
 * Formato de trama: SENS:T=24.5,H=60.0\n
 */
void sendTelemetry() {
  float temp = readLM75A();
  float hum = dht.readHumidity();

  // Si hay error en el DHT11, asignar 0.0 para no romper la trama
  if (isnan(hum)) hum = 0.0;
  if (temp < -100.0) temp = 0.0;

  String packet = "SENS:T=" + String(temp, 1) + ",H=" + String(hum, 1);
  espSerial.println(packet);

  // Depuración por USB a la PC
  Serial.print(F("[ARDUINO TX -> ESP32] "));
  Serial.println(packet);
}

// ============================================================================
// PARSER DE COMANDOS DESDE EL ESP32 / PC
// ============================================================================

/**
 * Procesa la trama recibida en formato: CMD:M=115,E=90,B=0,L=1
 * Parámetros:
 *   M: Mandíbula / Boca (90 - 130)
 *   E: Ojos (60 - 120)
 *   B: Forzar Parpadeo (1 = sí, 0 = no)
 *   L: Luz / LED (1 = encendido, 0 = apagado)
 */
void processCommand(String cmd) {
  cmd.trim();
  if (!cmd.startsWith("CMD:")) return;

  lastCommandTime = millis();
  String params = cmd.substring(4); // Remover "CMD:"

  int mouthVal = currentMouthPos;
  int eyesVal = currentEyesPos;
  int blinkVal = 0;
  int lightVal = -1;

  int startIdx = 0;
  while (startIdx < params.length()) {
    int commaIdx = params.indexOf(',', startIdx);
    if (commaIdx == -1) commaIdx = params.length();

    String pair = params.substring(startIdx, commaIdx);
    int eqIdx = pair.indexOf('=');
    if (eqIdx != -1) {
      char key = pair.charAt(0);
      int val = pair.substring(eqIdx + 1).toInt();

      if (key == 'M' || key == 'm') mouthVal = val;
      else if (key == 'E' || key == 'e') eyesVal = val;
      else if (key == 'B' || key == 'b') blinkVal = val;
      else if (key == 'L' || key == 'l') lightVal = val;
    }
    startIdx = commaIdx + 1;
  }

  // 1. Aplicar posición de Boca con restricción de seguridad
  currentMouthPos = constrain(mouthVal, MOUTH_CLOSED, MOUTH_MAX);
  servoMouth.write(currentMouthPos);

  // 2. Aplicar posición de Ojos
  currentEyesPos = constrain(eyesVal, EYES_MIN, EYES_MAX);
  servoEyes.write(currentEyesPos);

  // 3. Forzar parpadeo si se solicitó
  if (blinkVal == 1 && !isBlinking) {
    isBlinking = true;
    blinkStartTime = millis();
    servoLids.write(LIDS_CLOSED);
  }

  // 4. Control de Luz / Relé
  if (lightVal == 1) {
    digitalWrite(PIN_LED, HIGH);
  } else if (lightVal == 0) {
    digitalWrite(PIN_LED, LOW);
  }

  Serial.print(F("[CMD APLICADO] M="));
  Serial.print(currentMouthPos);
  Serial.print(F(" E="));
  Serial.print(currentEyesPos);
  Serial.print(F(" L="));
  Serial.println(digitalRead(PIN_LED));
}

// ============================================================================
// GESTOR DE VIDA AUTÓNOMA (Sin Bloqueos)
// ============================================================================

void updateAutonomy() {
  unsigned long now = millis();

  // 1. PARPADEO AUTÓNOMO
  if (!isBlinking && now >= nextBlinkTime) {
    isBlinking = true;
    blinkStartTime = now;
    servoLids.write(LIDS_CLOSED);
  }

  // Terminar fase de párpados cerrados
  if (isBlinking && (now - blinkStartTime >= BLINK_DURATION_MS)) {
    servoLids.write(LIDS_OPEN);
    isBlinking = false;
    // Programar siguiente parpadeo aleatorio entre 3.5 y 6.5 segundos
    nextBlinkTime = now + random(3500, 6500);
  }

  // 2. MICRO-SACADAS OCULARES SI NO HAY COMANDOS ACTIVOS
  if (now - lastCommandTime > IDLE_SACCADE_TIMEOUT) {
    if (now >= nextSaccadeTime) {
      // Movimiento ocular sutil entre 82° y 98°
      int subtleAngle = random(82, 99);
      servoEyes.write(subtleAngle);
      currentEyesPos = subtleAngle;
      nextSaccadeTime = now + random(2000, 5000);
    }
  }
}

// ============================================================================
// SETUP Y LOOP PRINCIPAL
// ============================================================================

void setup() {
  // Comunicación serie USB con la PC (Depuración)
  Serial.begin(115200);
  
  // Comunicación SoftwareSerial con ESP32 (9600 baudios ultra-estable)
  espSerial.begin(9600);

  // Inicializar bus I2C y sensores
  Wire.begin();
  dht.begin();

  // Configuración de pin LED
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);

  // Inicialización de servomotores
  servoEyes.attach(PIN_SERVO_EYES);
  servoLids.attach(PIN_SERVO_LIDS);
  servoMouth.attach(PIN_SERVO_MOUTH);

  // Posicionamiento neutro de reposo
  servoEyes.write(EYES_NEUTRAL);
  servoLids.write(LIDS_OPEN);
  servoMouth.write(MOUTH_CLOSED);

  // Inicializar temporizadores
  randomSeed(analogRead(A0));
  nextBlinkTime = millis() + 3000;
  nextSaccadeTime = millis() + 5000;
  lastTelemetryTime = millis();

  Serial.println(F("=================================================="));
  Serial.println(F(" Arduino Uno R3: Firmware Animatrónico Iniciado "));
  Serial.println(F(" LM75A (I2C: 0x48) | DHT11 (D4) | 3x SG90 (D9-D11)"));
  Serial.println(F(" SoftwareSerial (9600 bps): D2 (RX), D3 (TX)     "));
  Serial.println(F("=================================================="));
}

void loop() {
  // 1. Escuchar datos que llegan desde el ESP32
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

  // 2. Gestionar vida autónoma (parpadeo y miradas sutiles)
  updateAutonomy();

  // 3. Transmisión periódica de telemetría de sensores cada 3 segundos
  unsigned long now = millis();
  if (now - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryTime = now;
    sendTelemetry();
  }
}

