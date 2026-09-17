/*
 * ================================================================
 * WeMos D1 R1 — Servo + Ultrasonic Feeder Test
 * Board: LOLIN(WEMOS) D1 R1  ← select in Arduino IDE
 * ================================================================
 *
 * Your servo keeps spinning = it is acting as a CONTINUOUS (360°)
 * servo. On those, the Serial number is NOT a park angle:
 *   - ~1500 us (90) = STOP
 *   - lower / higher us   = spin left / right
 *   - we spin for a timed burst, then hard-STOP and cut the signal
 *
 * Serial commands:
 *   L        → spin LEFT→RIGHT 180°, then STOP
 *   R        → spin RIGHT→LEFT 180°, then STOP
 *   L90 / R45→ same directions, custom degrees (1–180)
 *   1–180    → spin default direction (L), then STOP
 *   0        → force STOP / OFF
 *
 * ----------------------------------------------------------------
 * WIRING
 *   HC-SR04: VCC→5V  Trig→D3  Echo→D4  GND→GND
 *
 *   Servo cable colors (typical 3-wire):
 *     BROWN  = GND  → common GND with WeMos + external supply
 *     RED    = VCC  → EXTERNAL 5–6V (do NOT use WeMos 5V alone)
 *     YELLOW = DATA / SIG (PWM) → WeMos D7
 *
 *   Servo: Yellow→D7 | Red→ext 5–6V | Brown→GND (shared)
 * SERIAL: 115200, Newline
 * ================================================================
 */

 #include <Servo.h>

 // ── Pins (WeMos D1 R1) ───────────────────────────────────────────
 #define TRIG_PIN  D3
 #define ECHO_PIN  D4
 #define SERVO_PIN D7
 
 // ── Continuous servo timing (tune these) ─────────────────────────
 // Neutral stop pulse. If it creeps after "stop", try 1480–1520.
 const int STOP_US = 1500;
 // Spin speed pulses (symmetric around STOP_US).
 // L = left→right, R = right→left. Swap the two values if directions feel reversed.
 const int SPIN_LEFT_US  = 1000;   // L
 const int SPIN_RIGHT_US = 2000;   // R
// How long to spin per commanded "degree" (ms). Raise if rotation is short.
// FINAL CALIBRATION: 10 → 180 = 1800 ms, 90 = 900 ms, 45 = 450 ms.
const float MS_PER_DEGREE = 10;
 const unsigned long STOP_HOLD_MS = 400;
 
 const unsigned long DISTANCE_INTERVAL_MS = 10000;
 unsigned long lastDistanceMs = 0;
 
 Servo feederServo;
 String serialBuffer = "";
 bool servoBusy = false;
 
 float readDistanceCm() {
   digitalWrite(TRIG_PIN, LOW);
   delayMicroseconds(2);
   digitalWrite(TRIG_PIN, HIGH);
   delayMicroseconds(10);
   digitalWrite(TRIG_PIN, LOW);
 
   unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000UL);
   if (duration == 0) return -1.0;
 
   float cm = duration * 0.0343 / 2.0;
   if (cm < 2.0 || cm > 400.0) return -1.0;
   return cm;
 }
 
 void printDistance() {
   float cm = readDistanceCm();
   Serial.println("---- Ultrasonic ----");
   if (cm < 0) {
     Serial.println("Distance: out of range / no echo");
   } else {
     Serial.print("Distance: ");
     Serial.print(cm, 1);
     Serial.println(" cm");
   }
   Serial.println("--------------------");
 }
 
 // Cut PWM completely — motor must stop
 void servoOff() {
   feederServo.detach();
   pinMode(SERVO_PIN, OUTPUT);
   digitalWrite(SERVO_PIN, LOW);
 }
 
 // Neutral pulse, then cut signal
 void servoHardStop() {
   feederServo.attach(SERVO_PIN);
   feederServo.writeMicroseconds(STOP_US);
   delay(STOP_HOLD_MS);
   servoOff();
   Serial.println("Servo STOP / OFF");
 }
 
 // Timed spin in a direction, then hard stop.
 // spinUs = SPIN_LEFT_US (L) or SPIN_RIGHT_US (R)
 void feedSpin(int degrees, int spinUs) {
   degrees = constrain(degrees, 1, 180);
   unsigned long spinMs = (unsigned long)(degrees * MS_PER_DEGREE);
 
   servoBusy = true;
 
   Serial.print(spinUs < STOP_US ? "L→R spin ~" : "R→L spin ~");
   Serial.print(degrees);
   Serial.print(" deg for ");
   Serial.print(spinMs);
   Serial.println(" ms");
 
   // Start from STOP so it does not fly off at attach
   feederServo.attach(SERVO_PIN);
   feederServo.writeMicroseconds(STOP_US);
   delay(200);
 
   // Spin in requested direction
   feederServo.writeMicroseconds(spinUs);
   delay(spinMs);
 
   // MUST stop: neutral, then detach
   feederServo.writeMicroseconds(STOP_US);
   delay(STOP_HOLD_MS);
   servoOff();
 
   servoBusy = false;
   Serial.println("Done. Servo stopped. Ready.");
 }
 
 void handleSerial() {
   while (Serial.available() > 0) {
     char c = Serial.read();
 
     if (c == '\n' || c == '\r') {
       serialBuffer.trim();
       if (serialBuffer.length() > 0) {
         if (servoBusy) {
           Serial.println("Busy — wait for stop.");
           serialBuffer = "";
           continue;
         }
 
         // Optional direction prefix: L (left→right) or R (right→left)
         int spinUs = SPIN_LEFT_US;   // default direction
         String arg = serialBuffer;
         char dir = toupper(arg.charAt(0));
         if (dir == 'L' || dir == 'R') {
           spinUs = (dir == 'L') ? SPIN_LEFT_US : SPIN_RIGHT_US;
           arg = arg.substring(1);   // drop the letter
           arg.trim();
           if (arg.length() == 0) arg = "180";  // bare L / R = full 180°
         }
 
         bool valid = arg.length() > 0;
         for (unsigned int i = 0; i < arg.length(); i++) {
           if (!isDigit(arg.charAt(i))) {
             valid = false;
             break;
           }
         }
 
         if (valid) {
           int value = arg.toInt();
           if (value == 0) {
             servoHardStop();
           } else if (value >= 1 && value <= 180) {
             feedSpin(value, spinUs);
           } else {
             Serial.println("Use L, R, L90, R45, 1–180, or 0 (stop).");
           }
         } else {
           Serial.println("Use L, R, L90, R45, 1–180, or 0 (stop).");
         }
       }
       serialBuffer = "";
     } else {
       serialBuffer += c;
       if (serialBuffer.length() > 8) serialBuffer = "";
     }
   }
 }
 
 void setup() {
   Serial.begin(115200);
   delay(500);
 
   pinMode(TRIG_PIN, OUTPUT);
   pinMode(ECHO_PIN, INPUT);
   digitalWrite(TRIG_PIN, LOW);
 
   servoHardStop();  // ensure OFF at boot
 
   Serial.println();
   Serial.println("================================");
   Serial.println("WeMos D1 R1 — Feeder (360 stop)");
   Serial.println("================================");
   Serial.println("Continuous servo control:");
   Serial.println("  L    → left→right 180 deg, then STOP");
   Serial.println("  R    → right→left 180 deg, then STOP");
   Serial.println("  L90  → left→right 90 deg (or R45, etc.)");
   Serial.println("  1-180→ default dir (L), then STOP");
   Serial.println("  0    → force STOP / OFF");
   Serial.println("Tune STOP_US if it creeps when stopped");
   Serial.println("Swap SPIN_LEFT/RIGHT_US if L/R reversed");
   Serial.println("--------------------------------");
   Serial.println("Trig D3 | Echo D4 | Servo D7");
   Serial.println("Servo wires: YELLOW=data(D7) RED=VCC BROWN=GND");
   Serial.println("Distance every 10 seconds");
   Serial.println("================================");
 
   printDistance();
   lastDistanceMs = millis();
 }
 
 void loop() {
   handleSerial();
 
   unsigned long now = millis();
   if (now - lastDistanceMs >= DISTANCE_INTERVAL_MS) {
     lastDistanceMs = now;
     printDistance();
   }
 }
 