  /*
  * ================================================================
  * ALL SENSORS COMBINED — Arduino Uno (NO Sensor Shield)  [v2]
  * Logic from: temp / ph / turbidity / tds standalone sketches
  *
  * Serial Monitor: every 1 second (pH EMA needs fast samples to settle)
  * WeMos SoftSerial: every 5 seconds (TEMP,PH,NTU,TDS)
  * ================================================================
  * Board: Arduino Uno
  *
  * Libraries: OneWire + DallasTemperature (SoftwareSerial built-in)
  *
  * Pins (combined — turbidity/TDS remapped to avoid A0/A1 clash):
  *   Temp D2 | pH A0 | Turb A1 | Turb D D3 | TDS A2
  *   D10→WeMos D5 (1k/2k divider) | D11→D6 | GND shared
  *
  * Serial Monitor: 9600 baud
  * ================================================================
  */

  #include <OneWire.h>
  #include <DallasTemperature.h>
  #include <SoftwareSerial.h>

  #define TEMP_PIN        2
  #define PH_PIN          A0
  #define TURBIDITY_PIN   A1
  #define TURBIDITY_DIG   3
  #define TDS_PIN         A2
  #define SW_TX_PIN       10
  #define SW_RX_PIN       11

  #define SERIAL_INTERVAL_MS  1000UL   // print + update pH every 1s
  #define WEMOS_INTERVAL_MS   5000UL   // upload to WeMos every 5s

  SoftwareSerial wemosSerial(SW_RX_PIN, SW_TX_PIN);
  OneWire oneWire(TEMP_PIN);
  DallasTemperature tempSensor(&oneWire);

  // ── pH (ph_sensor_arduino) ───────────────────────────────────────
  #define PH_SAMPLES       10
  #define PH_SAMPLE_DELAY  10
  #define PH_SMOOTHING     0.20
  #define RAW_AT_WATER     540
  #define RAW_AT_VINEGAR   602
  #define PH_WATER         7.2
  #define PH_VINEGAR       2.5

  // ── Turbidity ────────────────────────────────────────────────────
  #define TURB_SAMPLES     10
  #define VOLTAGE_CLEAN    4.20
  #define VOLTAGE_DIRTY    2.50

  // ── TDS ──────────────────────────────────────────────────────────
  #define TDS_SAMPLES      30
  #define TDS_SAMPLE_DELAY 10
  #define VREF             5.0

  float currentTemp = 25.0;
  float smoothedPhRaw = -1;
  float lastTempC = -999;
  float lastPh = 7.0;
  float lastNtu = 0;
  float lastTds = -999;

  unsigned long lastSerialMs = 0;
  unsigned long lastWemosMs = 0;
  unsigned int phSampleCount = 0;  // how many 1s pH updates since boot

  float readVoltage(int pin, int samples, int sampleDelayMs) {
    long sum = 0;
    for (int i = 0; i < samples; i++) {
      sum += analogRead(pin);
      delay(sampleDelayMs);
    }
    return (sum / (float)samples) * (VREF / 1023.0);
  }

  int readRawAverage(int pin, int samples, int sampleDelayMs) {
    long sum = 0;
    for (int i = 0; i < samples; i++) {
      sum += analogRead(pin);
      delay(sampleDelayMs);
    }
    return (int)(sum / samples);
  }

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

  float readTemperature() {
    tempSensor.requestTemperatures();
    float t = tempSensor.getTempCByIndex(0);
    if (t == DEVICE_DISCONNECTED_C) return -999;
    return t;
  }

  float smoothPhRaw(int newRaw) {
    if (smoothedPhRaw < 0) smoothedPhRaw = newRaw;
    else smoothedPhRaw = (PH_SMOOTHING * newRaw) + ((1.0 - PH_SMOOTHING) * smoothedPhRaw);
    return smoothedPhRaw;
  }

  float rawToPH(float raw) {
    float slope = (PH_VINEGAR - PH_WATER) / (float)(RAW_AT_VINEGAR - RAW_AT_WATER);
    return PH_WATER + (raw - RAW_AT_WATER) * slope;
  }

  float voltageToNTU(float voltage) {
    float span = VOLTAGE_CLEAN - VOLTAGE_DIRTY;
    if (span < 0.01) return 0;
    return constrain((VOLTAGE_CLEAN - voltage) / span * 100.0, 0.0, 100.0);
  }

  float voltageToTDS(float voltage, float temperatureC) {
    float compensationCoeff = 1.0 + 0.02 * (temperatureC - 25.0);
    float compensatedVoltage = voltage / compensationCoeff;
    float tds = (133.42 * pow(compensatedVoltage, 3)
              - 255.86 * pow(compensatedVoltage, 2)
              + 857.39 * compensatedVoltage) * 0.5;
    return constrain(tds, 0, 9999);
  }

  void setup() {
    Serial.begin(9600);
    wemosSerial.begin(9600);

    pinMode(TEMP_PIN, INPUT_PULLUP);
    pinMode(TURBIDITY_DIG, INPUT);

    tempSensor.begin();
    delay(200);
    tempSensor.setResolution(9);

    Serial.println("================================================");
    Serial.println("  All Sensors v2");
    Serial.println("  Serial every 1s (pH smoothing) | WeMos every 5s");
    Serial.println("================================================");
    Serial.println("Pins: Temp D2 | pH A0 | Turb A1 | TDS A2");
    Serial.println("Link: D10→WeMos D5 (divider) | D11→D6 | GND");
    Serial.println("------------------------------------------------");

    int count = tempSensor.getDeviceCount();
    Serial.print("DS18B20 sensors found: ");
    Serial.println(count);
    if (count == 0) Serial.println("WARNING: Check temp wiring (D2)!");
    Serial.println("pH needs ~15–20s of 1s samples before EMA settles.");
    Serial.println("------------------------------------------------");
    delay(1000);

    lastSerialMs = millis();
    lastWemosMs = millis();
  }

  void loop() {
    unsigned long now = millis();

    // ── Every 1s: read sensors + print Serial (feeds pH EMA) ───────
    if (now - lastSerialMs >= SERIAL_INTERVAL_MS) {
      lastSerialMs = now;

      float tempC = readTemperature();
      if (tempC != -999) currentTemp = tempC;
      lastTempC = tempC;

      int phRaw = readRawAverage(PH_PIN, PH_SAMPLES, PH_SAMPLE_DELAY);
      float phSteady = smoothPhRaw(phRaw);
      lastPh = constrain(rawToPH(phSteady), 0.0, 14.0);
      phSampleCount++;

      float turbV = readVoltage(TURBIDITY_PIN, TURB_SAMPLES, 10);
      lastNtu = voltageToNTU(turbV);

      float tdsV = -1;
      lastTds = -999;
      if (isSensorConnected(TDS_PIN)) {
        tdsV = readVoltage(TDS_PIN, TDS_SAMPLES, TDS_SAMPLE_DELAY);
        lastTds = voltageToTDS(tdsV, currentTemp);
      }

      Serial.println("================================================");
      Serial.print("Temperature : ");
      if (lastTempC == -999) Serial.println("NOT CONNECTED");
      else {
        Serial.print(lastTempC, 2);
        Serial.println(" C");
      }

      Serial.print("pH          : ");
      Serial.print(lastPh, 2);
      Serial.print("  (raw ");
      Serial.print(phRaw);
      Serial.print(" smooth ");
      Serial.print(phSteady, 0);
      Serial.print(")  samples=");
      Serial.print(phSampleCount);
      if (phSampleCount < 15) Serial.print("  [settling...]");
      else Serial.print("  [ready]");
      Serial.println();

      Serial.print("Turbidity   : ");
      Serial.print(lastNtu, 1);
      Serial.print(" NTU  (");
      Serial.print(turbV, 3);
      Serial.println(" V on A1)");

      Serial.print("TDS         : ");
      if (lastTds == -999) Serial.println("NOT CONNECTED");
      else {
        Serial.print(lastTds, 1);
        Serial.print(" ppm  (");
        Serial.print(tdsV, 3);
        Serial.print(" V on A2, T=");
        Serial.print(currentTemp, 1);
        Serial.println(" C)");
      }
    }

    // ── Every 5s: send latest values to WeMos ──────────────────────
    if (now - lastWemosMs >= WEMOS_INTERVAL_MS) {
      lastWemosMs = now;

      String dataString = "";
      dataString += "TEMP:" + (lastTempC == -999 ? String("NULL") : String(lastTempC, 2));
      dataString += ",PH:"  + String(lastPh, 2);
      dataString += ",NTU:" + String(lastNtu, 1);
      dataString += ",TDS:" + (lastTds == -999 ? String("NULL") : String(lastTds, 1));

      wemosSerial.println(dataString);
      Serial.print("Sent to WeMos: ");
      Serial.println(dataString);
      Serial.println("------------------------------------------------");
    }
  }
