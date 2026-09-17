/*
 * ================================================================
 * ALL SENSORS COMBINED — Arduino Uno (NO Sensor Shield)
 * Direct wiring to Arduino pins using a breadboard.
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
 * SENSOR WIRING (direct to Arduino, no shield):
 *
 *  [DS18B20 Temperature Module]
 *   DAT (yellow) → Pin 2 on Arduino
 *   VCC (red)    → 5V on Arduino
 *   GND (black)  → GND on Arduino
 *   (module has built-in pull-up — no external resistor needed)
 *
 *  [pH Sensor — PH-4502C module]
 *   Po  → A0 on Arduino
 *   VCC → 5V on Arduino
 *   GND → GND on Arduino
 *   pH probe → BNC connector on pH module
 *
 *  [Turbidity Sensor — KIE-TS-300B probe + module]
 *   A (analog out) → A1 on Arduino
 *   V (power)      → 5V on Arduino
 *   G (ground)     → GND on Arduino
 *   Probe wires    → numbered pins on turbidity module
 *
 *  [TDS Sensor — TDS board + 2-prong probe]
 *   AOUT → A2 on Arduino
 *   +    → 5V on Arduino
 *   -    → GND on Arduino
 *   Probe → JST connector on TDS board
 *
 * ----------------------------------------------------------------
 * TX/RX WIRING (Arduino → WeMos D1 R1 — pairs with wemos_receiver_no_shield):
 *
 *   Arduino Pin 10 (TX) → WeMos D5
 *                          ⚠️ USE VOLTAGE DIVIDER (5V → 3.3V):
 *                          Pin10 → 1kΩ → WeMos D5
 *                                    |
 *                                   2kΩ
 *                                    |
 *                                   GND
 *   Arduino Pin 11 (RX) → WeMos D6  (direct, no divider)
 *   Arduino GND         → WeMos GND (must share ground!)
 *
 * ----------------------------------------------------------------
 * PIN SUMMARY:
 *   Digital 2  → DS18B20 temperature (DAT)
 *   Digital 10 → WeMos D5  (SoftwareSerial TX)
 *   Digital 11 → WeMos D6  (SoftwareSerial RX)
 *   A0         → pH sensor (Po)
 *   A1         → Turbidity sensor (A)
 *   A2         → TDS sensor (AOUT)
 *
 * Data format sent to WeMos every 5 seconds:
 *   TEMP:27.50,PH:7.07,NTU:5.0,TDS:342.5\n
 * ================================================================
 */

#include <OneWire.h>
#include <DallasTemperature.h>
#include <SoftwareSerial.h>

// ── Pin Definitions ─────────────────────────────────────────────
#define TEMP_PIN      2     // DS18B20 DAT      → Digital 2
#define PH_PIN        A0    // pH Po             → A0
#define TURBIDITY_PIN A1    // Turbidity analog  → A1
#define TDS_PIN       A2    // TDS AOUT          → A2
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
// No isSensorConnected() here — pH modules are noisy and that check
// falsely returns NULL even when the sensor is working (same as
// standalone ph_sensor_arduino.ino which always reads the pin).
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
  Serial.begin(9600);
  wemosSerial.begin(9600);
  tempSensor.begin();

  Serial.println("================================================");
  Serial.println("  All Sensors — Arduino Uno (No Shield)         ");
  Serial.println("================================================");
  Serial.println("Wiring: Direct to Arduino pins via breadboard");
  Serial.println("  Temp  → Pin 2  |  pH  → A0");
  Serial.println("  Turb  → A1     |  TDS → A2");
  Serial.println("  Arduino Pin 10 → WeMos D5 (via divider)");
  Serial.println("  Arduino Pin 11 → WeMos D6 (direct)");
  Serial.println("  Arduino GND    → WeMos GND");
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
  float tempC = readTemperature();
  if (tempC != -999) currentTemp = tempC;

  float phVoltage = readVoltage(PH_PIN);
  float ph  = readPH();   // always a number — never -999 / NULL
  float ntu = readTurbidityNTU();
  float tds = readTDS();

  // --- Print to Serial Monitor (Arduino USB @ 9600) ---
  Serial.println("================================================");
  Serial.print("Temperature : ");
  Serial.println(tempC == -999 ? "NOT CONNECTED" : String(tempC, 2) + " C");

  Serial.print("pH          : ");
  Serial.print(ph, 2);
  Serial.print("  (raw ");
  Serial.print(phVoltage, 3);
  Serial.println(" V on A0)");

  Serial.print("Turbidity   : ");
  Serial.println(ntu == -999 ? "NOT CONNECTED" : String(ntu, 1) + " NTU");

  Serial.print("TDS         : ");
  Serial.println(tds == -999 ? "NOT CONNECTED" : String(tds, 1) + " ppm");

  // --- Send to WeMos via SoftwareSerial ---
  // pH is always sent as a number (never NULL) — same as standalone test
  String dataString = "";
  dataString += "TEMP:" + (tempC == -999 ? "NULL" : String(tempC, 2));
  dataString += ",PH:"  + String(ph, 2);
  dataString += ",NTU:" + (ntu  == -999 ? "NULL" : String(ntu, 1));
  dataString += ",TDS:" + (tds  == -999 ? "NULL" : String(tds, 1));

  wemosSerial.println(dataString);

  Serial.print("Sent to WeMos: ");
  Serial.println(dataString);
  Serial.println("------------------------------------------------");

  delay(5000);
}
