/*
 * ================================================================
 * Turbidity Sensor — Arduino Uno (honest live diagnostics)
 * ================================================================
 * G→GND  A→A0  V→5V
 * Probe: 1=Red  2=Yellow  3=Blue  4=empty
 *
 * Serial 9600. Type  r + Enter  to reset the recent-change window.
 * ================================================================
 */

#define ANALOG_PIN  A0
#define SAMPLES     30

// Cal — edit after you capture clean vs dirty voltages from Serial
#define VOLTAGE_CLEAN  4.20
#define VOLTAGE_DIRTY  2.50

float recentMin = 99.0;
float recentMax = 0.0;
unsigned long windowStartMs = 0;
const unsigned long WINDOW_MS = 5000;  // only look at last 5 seconds

int readRawAverage() {
  long sum = 0;
  for (int i = 0; i < SAMPLES; i++) {
    sum += analogRead(ANALOG_PIN);
    delay(3);
  }
  return (int)(sum / SAMPLES);
}

float rawToVoltage(int raw) {
  return raw * (5.0 / 1023.0);
}

float voltageToNTU(float v) {
  float span = VOLTAGE_CLEAN - VOLTAGE_DIRTY;
  if (span < 0.01) return 0;
  return constrain((VOLTAGE_CLEAN - v) / span * 100.0, 0.0, 100.0);
}

void resetWindow(float v) {
  recentMin = v;
  recentMax = v;
  windowStartMs = millis();
}

void setup() {
  Serial.begin(9600);
  pinMode(ANALOG_PIN, INPUT);
  delay(500);

  float v0 = rawToVoltage(readRawAverage());
  resetWindow(v0);

  Serial.println();
  Serial.println("================================================");
  Serial.println("  Turbidity LIVE (5-second change window)");
  Serial.println("================================================");
  Serial.println("NTU follows Voltage. If V does not move, NTU will not.");
  Serial.println("Dip probe, wait 3s. Type 'r' to reset window.");
  Serial.println("------------------------------------------------");
}

void loop() {
  // Optional: reset window from Serial Monitor
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'r' || c == 'R') {
      float v = rawToVoltage(readRawAverage());
      resetWindow(v);
      Serial.println("*** window reset ***");
    }
  }

  int raw = readRawAverage();
  float v = rawToVoltage(raw);
  float ntu = voltageToNTU(v);

  if (millis() - windowStartMs > WINDOW_MS) {
    resetWindow(v);  // start a fresh 5s window
  }
  if (v < recentMin) recentMin = v;
  if (v > recentMax) recentMax = v;
  float recentSwing = recentMax - recentMin;

  Serial.println("------------------------------------------------");
  Serial.print("NOW  RAW=");
  Serial.print(raw);
  Serial.print("  V=");
  Serial.print(v, 3);
  Serial.print(" V  NTU=");
  Serial.print(ntu, 1);
  Serial.println();

  Serial.print("Last 5s: minV=");
  Serial.print(recentMin, 3);
  Serial.print("  maxV=");
  Serial.print(recentMax, 3);
  Serial.print("  swing=");
  Serial.print(recentSwing, 3);
  Serial.println(" V");

  if (recentSwing < 0.03) {
    Serial.println("LIVE: NO CHANGE in last 5s (reading frozen).");
    Serial.println("  -> Dip deeper / stir muddy water / clean glass");
    Serial.println("  -> Or probe optics not responding to THIS water");
  } else {
    Serial.print("LIVE: Voltage moved ");
    Serial.print(recentSwing, 3);
    Serial.println(" V in last 5s (real change).");
  }

  delay(500);
}
