    /*
    * ================================================================
    * TDS Sensor (Total Dissolved Solids) — Arduino Uno
    * Board : TDS BOARD (blue module) + 2-prong white probe
    * ================================================================
    * Board : Arduino Uno  ← select in Arduino IDE
    *
    * NO LIBRARY NEEDED — uses built-in analogRead()
    *
    * ----------------------------------------------------------------
    * WHAT IS TDS?
    *   TDS measures dissolved minerals, salts, and metals in water.
    *   Unit: ppm (parts per million)
    *   Safe drinking water : 0–500 ppm
    *   Shrimp pond water   : 0–5000 ppm (brackish/saltwater)
    *
    * ----------------------------------------------------------------
    * WIRING TABLE:
    *   TDS Module Pin | Arduino Pin
    *   ---------------|------------
    *   GND  is -          | GND
    *   VCC  is +          | 5V
    *   AOUT (Analog)      | A1
    *
    *   White probe    → JST connector on the TDS board (plug directly)
    *
    * ----------------------------------------------------------------
    * NO CALIBRATION NEEDED for basic readings.
    * For accurate ppm, use a known TDS reference solution.
    *
    * Open Serial Monitor at 9600 baud to see readings.
    * ================================================================
    */

    #define TDS_PIN      A1     // Analog pin connected to AOUT on TDS board
    #define VREF         5.0    // Arduino Uno reference voltage
    #define SAMPLES      30     // Samples to average for stable reading
    #define SAMPLE_DELAY 10     // ms between samples

    // Temperature compensation (default 25°C)
    // If you have a temp sensor, replace 25.0 with actual temperature
    #define TEMPERATURE  25.0

    float readVoltage() {
      long sum = 0;
      for (int i = 0; i < SAMPLES; i++) {
        sum += analogRead(TDS_PIN);
        delay(SAMPLE_DELAY);
      }
      float average = sum / (float)SAMPLES;
      return average * (VREF / 1023.0);
    }

    float voltageToTDS(float voltage) {
      // Temperature compensation factor
      float compensationCoeff = 1.0 + 0.02 * (TEMPERATURE - 25.0);
      float compensatedVoltage = voltage / compensationCoeff;

      // TDS formula (standard conversion)
      float tds = (133.42 * pow(compensatedVoltage, 3)
                - 255.86 * pow(compensatedVoltage, 2)
                + 857.39 * compensatedVoltage) * 0.5;
      return tds;
    }

    void setup() {
      Serial.begin(9600);
      Serial.println("================================================");
      Serial.println("     TDS Sensor (Total Dissolved Solids)        ");
      Serial.println("         Arduino Uno + TDS Board                ");
      Serial.println("================================================");
      Serial.println("Wiring:");
      Serial.println("  TDS GND  → Arduino GND");
      Serial.println("  TDS VCC  → Arduino 5V");
      Serial.println("  TDS AOUT → Arduino A1");
      Serial.println("  Probe   → JST connector on TDS board");
      Serial.println("------------------------------------------------");
      Serial.println("TDS Scale:");
      Serial.println("  0-300 ppm   → Excellent (very clean)");
      Serial.println("  300-500 ppm → Good");
      Serial.println("  500-900 ppm → Fair");
      Serial.println("  900+ ppm    → Poor / High mineral content");
      Serial.println("------------------------------------------------");
      Serial.println("Dip probe in water to start reading...");
      Serial.println("------------------------------------------------");
      delay(2000);
    }

    void loop() {
      float voltage = readVoltage();
      float tds     = voltageToTDS(voltage);

      // Water quality label
      String quality;
      if (tds < 300) {
        quality = "EXCELLENT";
      } else if (tds < 500) {
        quality = "GOOD";
      } else if (tds < 900) {
        quality = "FAIR";
      } else {
        quality = "HIGH MINERALS";
      }

      Serial.println("------------------------------------------------");
      Serial.print("Voltage : ");
      Serial.print(voltage, 3);
      Serial.println(" V");

      Serial.print("TDS     : ");
      Serial.print(tds, 1);
      Serial.print(" ppm  → ");
      Serial.println(quality);

      delay(1000);
    }
