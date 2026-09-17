  /*
  * pH Sensor (PH-4502C + probe) — 2-POINT CALIBRATION (water + vinegar)
  * Board: Arduino Uno / Nano / Mega
  *
  * ============================================================
  * SIMPLE, SINGLE-STAGE CALIBRATION
  * ------------------------------------------------------------
  * We map two RAW readings straight to their real pH:
  *      RAW in DRINKING WATER  ->  pH 7.0   (neutral)
  *      RAW in WHITE VINEGAR   ->  pH 2.5   (acidic)
  * Everything else falls on the straight line between them.
  *
  * -------- HOW TO CALIBRATE (do once) ------------------------
  *   1. Upload, open Serial Monitor @ 9600 baud.
  *   2. Put probe in WATER. Wait until the (smooth ###) value is
  *      steady. Put that number into RAW_AT_WATER below.
  *   3. Rinse. Put probe in VINEGAR. Wait until (smooth ###) is
  *      steady. Put that number into RAW_AT_VINEGAR below.
  *   4. Upload again. Now water reads ~7.0 and vinegar ~2.5.
  * ============================================================
  *
  * Wiring:  VCC->5V   GND->GND   Po->A0   Probe->BNC (push + twist)
  */

  #define PH_PIN       A0
  #define SAMPLES      10
  #define SAMPLE_DELAY 10

  // ===== CALIBRATION — EDIT THESE TWO RAW NUMBERS =====
  // Use the (smooth ###) value you see in each liquid.
#define RAW_AT_WATER    540    // <-- steady RAW in DRINKING WATER (= PH_WATER)
#define RAW_AT_VINEGAR  602    // <-- steady RAW in VINEGAR        (= PH_VINEGAR)

#define PH_WATER        7.2    // drinking water shown as ~7.2 (your 7.0-7.5 target)
#define PH_VINEGAR      2.5    // white vinegar is ~2.5
  // ====================================================

  // ---- SMOOTHING ----------------------------------------------------
  // Exponential moving average to stop the number bouncing around.
  //   0.05 = very smooth but slow to react
  //   0.20 = balanced (default)
  //   0.50 = fast reacting but still a little jumpy
  #define SMOOTHING 0.20

  float smoothedRaw = -1;   // -1 means "not started yet"

  int readRawAverage() {
    long sum = 0;
    for (int i = 0; i < SAMPLES; i++) {
      sum += analogRead(PH_PIN);
      delay(SAMPLE_DELAY);
    }
    return (int)(sum / SAMPLES);
  }

  // Blend the newest raw reading into the running average.
  float smoothRaw(int newRaw) {
    if (smoothedRaw < 0) {
      smoothedRaw = newRaw;            // first reading: start here
    } else {
      smoothedRaw = (SMOOTHING * newRaw) + ((1.0 - SMOOTHING) * smoothedRaw);
    }
    return smoothedRaw;
  }

  // One straight-line fit: RAW -> pH, anchored on water and vinegar.
  float rawToPH(float raw) {
    float slope = (PH_VINEGAR - PH_WATER) /
                  (float)(RAW_AT_VINEGAR - RAW_AT_WATER);
    return PH_WATER + (raw - RAW_AT_WATER) * slope;
  }

  void setup() {
    Serial.begin(9600);
    Serial.println();
    Serial.println("=== pH READING (water=7.0, vinegar=2.5) ===");
    Serial.println("Calibrate: set RAW_AT_WATER & RAW_AT_VINEGAR.");
    Serial.println("-------------------------------------------");
  }

  void loop() {
    int   raw    = readRawAverage();      // fresh reading (still jumpy)
    float steady = smoothRaw(raw);        // smoothed reading (calm)
    float ph     = rawToPH(steady);       // calibrated pH
    ph = constrain(ph, 0.0, 14.0);

    Serial.print("RAW: ");
    Serial.print(raw);
    Serial.print("  (smooth ");
    Serial.print(steady, 0);
    Serial.print(")   |   pH: ");
    Serial.print(ph, 2);

    if (ph < 6.5) {
      Serial.println("   -> ACIDIC");
    } else if (ph > 8.5) {
      Serial.println("   -> ALKALINE");
    } else {
      Serial.println("   -> NORMAL (6.5 - 8.5)");
    }

    delay(1000);
  }
