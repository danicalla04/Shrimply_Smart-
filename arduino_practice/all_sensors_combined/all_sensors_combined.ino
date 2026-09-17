/*
 * ================================================================
 * ALL SENSORS COMBINED — Arduino Uno + Sensor Shield v5.0
 * Sends data to WeMos ESP8266 via TX/RX (SoftwareSerial)
 * ================================================================
 * Board: Arduino Uno  ← select in Arduino IDE
 *
 * ============================================================
 * INSTALL THESE 2 LIBRARIES BEFORE COMPILING:
 *   Sketch → Include Library → Manage Libraries, then search:
 *   1. "OneWire"           by Paul Stoffregen  → Install
 *   2. "DallasTemperature" by Miles Burton     → Install
 *   (SoftwareSerial is built-in — no install needed)
 * ============================================================
 *
 * ----------------------------------------------------------------
 * SENSOR WIRING (all sensors use 5V via Sensor Shield):
 *
 *  [DS18B20 Temperature — Plugable Terminal module]
 *   DAT (purple) → S  of Digital 2 group on shield
 *   VCC (white)  → +  of Digital 2 group on shield
 *   GND (green)  → -  of Digital 2 group on shield
 *
 *  [pH Sensor — PH-4502C module]
 *   Po  → S of A2 group on shield
 *   VCC → + of A2 group on shield
 *   GND → - of A2 group on shield
 *
 *  [Turbidity Sensor — KIE-TS-300B probe + module]
 *   A   → S of A4 group on shield
 *   V   → + of A4 group on shield
 *   G   → - of A4 group on shield
 *
 *  [TDS Sensor — TDS board + 2-prong probe]
 *   AOUT → S of A0 group on shield
 *   +    → + of A0 group on shield
 *   -    → - of A0 group on shield
 *
 * ----------------------------------------------------------------
 * TX/RX WIRING (Arduino → WeMos ESP8266):
 *
 *   Arduino Pin 10 (TX) → WeMos RX pin
 *                          ⚠️ USE VOLTAGE DIVIDER:
 *                          Pin10 → 1kΩ → WeMos RX
 *                                    |
 *                                   2kΩ
 *                                    |
 *                                   GND
 *   Arduino Pin 11 (RX) → WeMos TX pin  (direct, no divider needed)
 *   Arduino GND         → WeMos GND     (must share ground!)
 *
 * ----------------------------------------------------------------
 * PIN SUMMARY:
 *   Digital 2  → DS18B20 temperature (DAT)
 *   Digital 10 → WeMos RX  (SoftwareSerial TX)
 *   Digital 11 → WeMos TX  (SoftwareSerial RX)
 *   A0         → TDS sensor (AOUT)
 *   A2         → pH sensor (Po)
 *   A4         → Turbidity sensor (A)
 *
 * Data format sent to WeMos every 5 seconds:
 *   TEMP:27.50,PH:7.07,NTU:5.0,TDS:342.5\n
 * ================================================================
 */

#include <OneWire.h>
#include <DallasTemperature.h>
#include <SoftwareSerial.h>

// ── Pin Definitions ─────────────────────────────────────────────
#define TEMP_PIN      2     // DS18B20 DAT
#define TDS_PIN       A0    // TDS AOUT
#define PH_PIN        A2    // pH Po
#define TURBIDITY_PIN A4    // Turbidity A
#define SW_TX_PIN     10    // SoftwareSerial TX → WeMos RX
#define SW_RX_PIN     11    // SoftwareSerial RX ← WeMos TX

// ── Serial Setup ─────────────────────────────────────────────────
SoftwareSerial wemosSerial(SW_RX_PIN, SW_TX_PIN);

// ── Sensor Setup ─────────────────────────────────────────────────
OneWire           oneWire(TEMP_PIN);
DallasTemperature tempSensor(&oneWire);

// ── Calibration Values ───────────────────────────────────────────
#define PH_NEUTRAL_VOLTAGE  2.5
#define PH_SLOPE            0.18
#define TURBIDITY_CLEAN     3.50
#define TURBIDITY_DIRTY     2.89

// ── Sampling ─────────────────────────────────────────────────────
#define SAMPLES      10
#define SAMPLE_DELAY 10

float currentTemp = 25.0;

// ── Helper: Read averaged voltage ────────────────────────────────
float readVoltage(int pin) {
  long sum = 0;
  for (int i = 0; i < SAMPLES; i++) {
    sum += analogRead(pin);
    delay(SAMPLE_DELAY);
  }
  return (sum / (float)SAMPLES) * (5.0 / 1023.0);
}

// ── Detect if sensor is connected ────────────────────────────────
bool isSensorConnected(int pin) {
  pinMode(pin, INPUT);
  delay(10);
  int normalRead = analogRead(pin);
  int minVal = 1023, maxVal = 0;
  for (int i = 0; i < 20; i++) {
    int val = analogRead(pin);
    if (val < minVal) minVal = val;
    if (val > maxVal) maxVal = val;
    delay(2);
  }
  int spread = maxVal - minVal;
  if (spread > 30 || normalRead > 900) return false;
  return true;
}

// ── Temperature ──────────────────────────────────────────────────
float readTemperature() {
  tempSensor.requestTemperatures();
  float t = tempSensor.getTempCByIndex(0);
  if (t == DEVICE_DISCONNECTED_C) return -999;
  return t;
}

// ── pH ───────────────────────────────────────────────────────────
// Do not use isSensorConnected() — pH modules are noisy and get
// falsely marked as disconnected (standalone ph sketch never checks).
float readPH() {
  float voltage = readVoltage(PH_PIN);
  return constrain(7.0 + ((PH_NEUTRAL_VOLTAGE - voltage) / PH_SLOPE), 0, 14);
}

// ── Turbidity ────────────────────────────────────────────────────
float readTurbidityNTU() {
  if (!isSensorConnected(TURBIDITY_PIN)) return -999;
  float voltage = readVoltage(TURBIDITY_PIN);
  float ntu = map(voltage * 100, TURBIDITY_CLEAN * 100, TURBIDITY_DIRTY * 100, 0, 100);
  return constrain(ntu, 0, 100);
}

// ── TDS ──────────────────────────────────────────────────────────
float readTDS() {
  if (!isSensorConnected(TDS_PIN)) return -999;
  float voltage = readVoltage(TDS_PIN);
  float compensationCoeff = 1.0 + 0.02 * (currentTemp - 25.0);
  float compensatedVoltage = voltage / compensationCoeff;
  float tds = (133.42 * pow(compensatedVoltage, 3)
             - 255.86 * pow(compensatedVoltage, 2)
             + 857.39 * compensatedVoltage) * 0.5;
  return constrain(tds, 0, 9999);
}

// ── Setup ─────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);        // USB Serial Monitor
  wemosSerial.begin(9600);   // SoftwareSerial to WeMos
  tempSensor.begin();

  Serial.println("================================================");
  Serial.println("  All Sensors + TX/RX to WeMos — Arduino Uno   ");
  Serial.println("================================================");
  Serial.println("TX Pin 10 → WeMos RX (via voltage divider)");
  Serial.println("RX Pin 11 ← WeMos TX (direct)");
  Serial.println("GND       → WeMos GND (shared)");
  Serial.println("------------------------------------------------");

  int count = tempSensor.getDeviceCount();
  Serial.print("DS18B20 sensors found: ");
  Serial.println(count);
  if (count == 0) Serial.println("WARNING: Check temp sensor wiring!");
  Serial.println("------------------------------------------------");
  delay(2000);
}

// ── Loop ──────────────────────────────────────────────────────────
void loop() {
  // --- Read all sensors ---
  float tempC = readTemperature();
  if (tempC != -999) currentTemp = tempC;

  float ph  = readPH();
  float ntu = readTurbidityNTU();
  float tds = readTDS();

  // --- Print to Serial Monitor (debug) ---
  Serial.println("================================================");
  Serial.print("Temperature : ");
  Serial.println(tempC == -999 ? "NOT CONNECTED" : String(tempC, 2) + " C");

  Serial.print("pH          : ");
  Serial.println(ph == -999 ? "NOT CONNECTED" : String(ph, 2));

  Serial.print("Turbidity   : ");
  Serial.println(ntu == -999 ? "NOT CONNECTED" : String(ntu, 1) + " NTU");

  Serial.print("TDS         : ");
  Serial.println(tds == -999 ? "NOT CONNECTED" : String(tds, 1) + " ppm");

  // --- Send to WeMos via SoftwareSerial ---
  // Format: TEMP:27.50,PH:7.07,NTU:5.0,TDS:342.5
  String dataString = "";
  dataString += "TEMP:" + (tempC == -999 ? "NULL" : String(tempC, 2));
  dataString += ",PH:"  + (ph   == -999 ? "NULL" : String(ph, 2));
  dataString += ",NTU:" + (ntu  == -999 ? "NULL" : String(ntu, 1));
  dataString += ",TDS:" + (tds  == -999 ? "NULL" : String(tds, 1));

  wemosSerial.println(dataString);  // Send to WeMos

  Serial.print("Sent to WeMos: ");
  Serial.println(dataString);
  Serial.println("------------------------------------------------");

  delay(5000); // Send every 5 seconds
}
