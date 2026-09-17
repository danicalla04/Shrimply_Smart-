/*
 * Temperature Sensor (DS18B20 Waterproof Probe) with Arduino
 * Board: Arduino Uno / Nano / Mega  ← select your board in Arduino IDE
 *
 * ============================================================
 * INSTALL THESE 2 LIBRARIES BEFORE COMPILING:
 *   Sketch → Include Library → Manage Libraries, then search:
 *
 *   1. "OneWire"           by Paul Stoffregen  → Install
 *   2. "DallasTemperature" by Miles Burton     → Install
 * ============================================================
 *
 * Wiring (3 wires only — NO resistor needed):
 *   Red wire    (VCC) → 5V  on Arduino
 *   Black wire  (GND) → GND on Arduino
 *   Yellow wire (DAT) → Pin 2 on Arduino
 *
 *   Internal pull-up is enabled in code — no external resistor needed.
 *   Works for short cables (under 1 meter).
 *
 * Open Serial Monitor at 9600 baud to see readings.
 */

#include <OneWire.h>
#include <DallasTemperature.h>

#define DAT_PIN 2   // Yellow wire (DAT) connects here

OneWire           oneWire(DAT_PIN);
DallasTemperature sensors(&oneWire);

void setup() {
  Serial.begin(9600);
  sensors.begin();
  delay(200);
  // Set lower resolution for more reliable readings
  sensors.setResolution(9);

  Serial.println("================================");
  Serial.println("   DS18B20 Temperature Sensor  ");
  Serial.println("         Arduino + Probe        ");
  Serial.println("================================");

  int count = sensors.getDeviceCount();
  Serial.print("Sensors found: ");
  Serial.println(count);
  if (count == 0) {
    Serial.println("ERROR: No sensor found!");
    Serial.println("Check wiring and 4.7k resistor.");
  }
  Serial.println("--------------------------------");
}

void loop() {
  sensors.requestTemperatures();

  float tempC = sensors.getTempCByIndex(0);
  float tempF = DallasTemperature::toFahrenheit(tempC);

  if (tempC == DEVICE_DISCONNECTED_C) {
    Serial.println("ERROR: Sensor disconnected — check wiring!");
  } else {
    Serial.print("Temperature : ");
    Serial.print(tempC, 2);
    Serial.print(" C  |  ");
    Serial.print(tempF, 2);
    Serial.println(" F");
  }

  delay(1000); // Read every 1 second
}
