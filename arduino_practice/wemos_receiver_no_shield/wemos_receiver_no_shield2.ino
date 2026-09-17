/*
 * ================================================================
 * WeMos D1 R1 — Receiver + Feeder (NO Sensor Shield)
 * = wemos_receiver_no_shield2 (Arduino sensors → sensor_api.php)
 * + wemos_feeder (HC-SR04 + continuous servo)
 * ================================================================
 * Board: LOLIN(WEMOS) D1 R1  ← select in Arduino IDE
 *
 * ----------------------------------------------------------------
 * PINS (no conflicts)
 *   SoftSerial (Arduino):  D5 RX ← Uno D10 (1k/2k divider)
 *                          D6 TX → Uno D11
 *   HC-SR04:               D3 Trig | D4 Echo
 *   Servo:                 D7 SIG  (external 5–6V + common GND)
 *   USB Serial:            hardware RX/TX only (115200)
 *
 * ----------------------------------------------------------------
 * EXTERNAL 5V SUPPLY → WEMOS D1 R1 (required for servo + sensors)
 * Use a 5V wall adapter / power bank / buck converter (≥2A).
 * Do NOT power the servo from USB / WeMos 5V pin alone.
 *
 *   Adapter RED  (+5V)  → WeMos  5V pin   (the 5V pin, NEVER 3.3V)
 *   Adapter BLACK (GND) → WeMos  GND pin
 *
 * Then share that SAME 5V and GND with the feeder parts:
 *
 *   +5V rail (all RED together):
 *     Adapter +5V ──┬── WeMos 5V
 *                   ├── Servo RED
 *                   └── HC-SR04 VCC
 *
 *   GND rail (all BLACK / BROWN together) — required:
 *     Adapter GND ──┬── WeMos GND
 *                   ├── Servo BROWN
 *                   ├── HC-SR04 GND
 *                   └── Arduino GND  (SoftSerial common ground)
 *
 *   Signal only (no power):
 *     Servo YELLOW  → WeMos D7
 *     HC-SR04 Trig  → WeMos D3
 *     HC-SR04 Echo  → WeMos D4  (Echo is 5V: use 1k/2k divider if needed)
 *
 * USB WHILE POWERED:
 *   OK to plug USB for Serial Monitor IF adapter GND is already common.
 *   If the board resets or gets hot: unplug USB and use only the 5V adapter,
 *   or unplug the adapter 5V wire and use USB only for code upload.
 *
 * NEVER:
 *   - Put 5V on the 3.3V pin (kills ESP8266)
 *   - Skip common GND (servo/ultrasonic will glitch, HTTP -1, random resets)
 *   - Feed VIN with 5V AND 5V pin at the same time from two supplies
 *
 * Serial servo commands (USB monitor, Newline):
 *   L / L45      → same as Feeding Servo ON  (spin ~45° left)
 *   R / R45      → same as Feeding Servo OFF (spin ~45° right)
 *   L90 / R90    → custom degrees (1–180)
 *   0            → force STOP / OFF
 *
 * HOW IT WORKS:
 *   1. Arduino SoftSerial every ~5s → POST sensor_api.php
 *   2. Ultrasonic every 5s → Serial + POST feeder_api.php (website)
 *   3. Website Servo ON → spin LEFT (L); Servo OFF → spin RIGHT (R)
 *      (WeMos polls servo_cmd_api.php)
 *   4. USB Serial still accepts: L / R / L90 / R45 / 1–180 / 0
 * ================================================================
 */

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <SoftwareSerial.h>
#include <Servo.h>

// ── Wi-Fi Credentials ────────────────────────────────────────────
const char* WIFI_SSID     = "thiss";
const char* WIFI_PASSWORD = "123456789";

// ── Server / Database Endpoint ───────────────────────────────────
// Run ipconfig → Wireless LAN → IPv4. Update EVERY time PC/hotspot IP changes.
// Must match: ipconfig → Wireless LAN adapter Wi-Fi → IPv4
// This PC on hotspot "thiss" is currently 10.111.44.87
const char* SERVER_URL = "http://10.111.44.87/sensor_api.php";
const char* FEEDER_URL = "http://10.111.44.87/feeder_api.php";
const char* SERVO_CMD_URL = "http://10.111.44.87/servo_cmd_api.php";

// ── SoftSerial (Arduino ↔ WeMos) — D5 / D6 ───────────────────────
#define SW_RX_PIN D5
#define SW_TX_PIN D6
SoftwareSerial arduinoSerial(SW_RX_PIN, SW_TX_PIN);
#define ARDUINO_BAUD 9600

// ── Feeder: ultrasonic + servo — D3 / D4 / D7 ────────────────────
#define TRIG_PIN  D3
#define ECHO_PIN  D4
#define SERVO_PIN D7

const int STOP_US = 1500;
const int SPIN_LEFT_US  = 1000;   // L / website Servo ON
const int SPIN_RIGHT_US = 2000;   // R / website Servo OFF
const int SPIN_DEGREES = 45;      // website + Serial L/R → L45 / R45
const float MS_PER_DEGREE = 10;   // 160° → 1600 ms. Raise if rotation is short.
const unsigned long DISTANCE_INTERVAL_MS = 5000;
const unsigned long SERVO_CMD_POLL_MS = 1500;

String receivedLine = "";
String usbSerialBuffer = "";
unsigned long lastWifiAttempt = 0;
unsigned long lastDistanceMs = 0;
unsigned long lastServoCmdPollMs = 0;
bool servoBusy = false;
String lastMotorState = "OFF";
long lastWebServoCmdId = 0;
bool pendingLeft = false;
bool pendingRight = false;

Servo feederServo;

// ── Wi-Fi ─────────────────────────────────────────────────────────
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("[WiFi] Connecting to \"");
  Serial.print(WIFI_SSID);
  Serial.print("\"");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 20) {
    delay(500);
    Serial.print(".");
    tries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected!");
    Serial.print("[WiFi] IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WiFi] FAILED — will retry later. Sensor display still works.");
  }
  lastWifiAttempt = millis();
}

// ── Feeder helpers (from wemos_feeder) ────────────────────────────
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

void sendFeederTelemetry(float cm) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[FEEDER] WiFi down — skip website upload.");
    return;
  }

  WiFiClient client;
  HTTPClient http;
  http.setTimeout(1500);
  http.begin(client, FEEDER_URL);
  http.addHeader("Content-Type", "application/x-www-form-urlencoded");

  String postBody = "device_id=wemos-feeder&motor_state=" + lastMotorState;
  if (cm >= 0) {
    postBody += "&distance_cm=";
    postBody += String(cm, 1);
  }

  int httpCode = http.POST(postBody);
  Serial.print("[FEEDER] HTTP ");
  Serial.println(httpCode);
  if (httpCode > 0) {
    Serial.print("[FEEDER] ");
    Serial.println(http.getString());
  }
  http.end();
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
  sendFeederTelemetry(cm);
}

void servoOff() {
  feederServo.detach();
  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW);
}

void servoHardStop() {
  // Cut the PWM immediately. Holding 1500 us after a spin makes
  // continuous servos creep another ~30° because 1500 is rarely true-stop.
  servoOff();
  lastMotorState = "OFF";
  Serial.println("Servo STOP / OFF");
}

void feedSpin(int degrees, int spinUs) {
  degrees = constrain(degrees, 1, 180);
  unsigned long spinMs = (unsigned long)(degrees * MS_PER_DEGREE);

  servoBusy = true;
  lastMotorState = (spinUs < STOP_US) ? "ON" : "OFF";

  Serial.print(spinUs < STOP_US ? "L→R spin ~" : "R→L spin ~");
  Serial.print(degrees);
  Serial.print(" deg for ");
  Serial.print(spinMs);
  Serial.println(" ms");

  feederServo.attach(SERVO_PIN);
  feederServo.writeMicroseconds(spinUs);
  delay(spinMs);
  servoOff();   // stop here — no extra 1500 us "park" twitch

  servoBusy = false;
  Serial.println("Done. Servo stopped. Ready.");
}

void handleUsbServoSerial() {
  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '\n' || c == '\r') {
      usbSerialBuffer.trim();
      if (usbSerialBuffer.length() > 0) {
        if (servoBusy) {
          Serial.println("Busy — wait for stop.");
          usbSerialBuffer = "";
          continue;
        }

        int spinUs = SPIN_LEFT_US;
        String arg = usbSerialBuffer;
        char dir = toupper(arg.charAt(0));
        if (dir == 'L' || dir == 'R') {
          spinUs = (dir == 'L') ? SPIN_LEFT_US : SPIN_RIGHT_US;
          arg = arg.substring(1);
          arg.trim();
          if (arg.length() == 0) arg = String(SPIN_DEGREES);
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
      usbSerialBuffer = "";
    } else {
      usbSerialBuffer += c;
      if (usbSerialBuffer.length() > 8) usbSerialBuffer = "";
    }
  }
}

void syncLastWebServoCmdId() {
  if (WiFi.status() != WL_CONNECTED) return;
  WiFiClient client;
  HTTPClient http;
  http.setTimeout(1500);
  if (!http.begin(client, SERVO_CMD_URL)) return;
  int code = http.GET();
  if (code == 200) {
    String body = http.getString();
    body.trim();
    int idIdx = body.indexOf("id=");
    if (idIdx >= 0) {
      int amp = body.indexOf('&', idIdx);
      String idStr = (amp > idIdx) ? body.substring(idIdx + 3, amp) : body.substring(idIdx + 3);
      lastWebServoCmdId = idStr.toInt();
      Serial.print("[ServoCmd] synced last id=");
      Serial.println(lastWebServoCmdId);
    }
  }
  http.end();
}

void pollWebServoCommands() {
  if (servoBusy || WiFi.status() != WL_CONNECTED) return;

  WiFiClient client;
  HTTPClient http;
  http.setTimeout(1500);
  if (!http.begin(client, SERVO_CMD_URL)) return;
  int code = http.GET();
  if (code == 200) {
    String body = http.getString();
    body.trim();
    int idIdx = body.indexOf("id=");
    int stateIdx = body.indexOf("state=");
    if (idIdx >= 0 && stateIdx >= 0) {
      int amp = body.indexOf('&', idIdx);
      long id = ((amp > idIdx) ? body.substring(idIdx + 3, amp) : body.substring(idIdx + 3)).toInt();
      String state = body.substring(stateIdx + 6);
      int ampState = state.indexOf('&');
      if (ampState >= 0) state = state.substring(0, ampState);
      state.toUpperCase();
      state.trim();

      if (id > lastWebServoCmdId) {
        lastWebServoCmdId = id;
        Serial.print("[WEB] New command id=");
        Serial.print(id);
        Serial.print(" state=");
        Serial.print(state);
        int cmdIdx = body.indexOf("cmd=");
        if (cmdIdx >= 0) {
          Serial.print(" cmd=");
          Serial.print(body.substring(cmdIdx + 4));
        }
        Serial.println();
        if (state == "ON") {
          pendingLeft = true;
          pendingRight = false;
        } else if (state == "OFF") {
          pendingRight = true;
          pendingLeft = false;
        }
      }
    }
  } else {
    Serial.print("[WEB] servo_cmd_api HTTP ");
    Serial.println(code);
  }
  http.end();
}

void runPendingServoJobs() {
  if (servoBusy) return;
  if (pendingLeft) {
    pendingLeft = false;
    Serial.println("[Web] Servo ON → L45");
    feedSpin(SPIN_DEGREES, SPIN_LEFT_US);
    return;
  }
  if (pendingRight) {
    pendingRight = false;
    Serial.println("[Web] Servo OFF → R45");
    feedSpin(SPIN_DEGREES, SPIN_RIGHT_US);
  }
}

// ── Parse sensor packet ───────────────────────────────────────────
String extractValue(String data, String key) {
  String search = key + ":";
  int startIdx = data.indexOf(search);
  if (startIdx == -1) return "NULL";
  startIdx += search.length();
  int endIdx = data.indexOf(",", startIdx);
  if (endIdx == -1) endIdx = data.length();
  return data.substring(startIdx, endIdx);
}

void sendToDatabase(String temp, String ph, String ntu, String tds) {
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastWifiAttempt > 30000) {
      connectWiFi();
    }
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[WiFi] Not connected — skipping upload.");
      return;
    }
  }

  WiFiClient client;
  HTTPClient http;
  http.setTimeout(1500);

  http.begin(client, SERVER_URL);
  http.addHeader("Content-Type", "application/x-www-form-urlencoded");

  String postBody = "temperature=" + temp
                  + "&ph="         + ph
                  + "&turbidity="  + ntu
                  + "&tds="        + tds;

  int httpCode = http.POST(postBody);

  Serial.print("[HTTP] Response code: ");
  Serial.println(httpCode);

  if (httpCode == 200) {
    Serial.print("[HTTP] ");
    Serial.println(http.getString());
  } else {
    Serial.print("[HTTP] Failed: ");
    Serial.println(http.getString());
  }

  http.end();
}

void handleArduinoSerial() {
  while (arduinoSerial.available() > 0) {
    char c = arduinoSerial.read();

    if (c == '\n') {
      receivedLine.trim();

      if (receivedLine.length() > 0 && receivedLine.startsWith("TEMP:")) {
        Serial.println("---- New Reading ----");
        Serial.println("Raw: " + receivedLine);

        String temp = extractValue(receivedLine, "TEMP");
        String ph   = extractValue(receivedLine, "PH");
        String ntu  = extractValue(receivedLine, "NTU");
        String tds  = extractValue(receivedLine, "TDS");

        Serial.println("Temperature : " + temp + " C");
        Serial.println("pH          : " + ph);
        Serial.println("Turbidity   : " + ntu + " NTU");
        Serial.println("TDS         : " + tds + " ppm");
        Serial.println("---------------------");

        sendToDatabase(temp, ph, ntu, tds);
      }

      receivedLine = "";
    } else {
      receivedLine += c;
    }
  }
}

void setup() {
  Serial.begin(115200);
  arduinoSerial.begin(ARDUINO_BAUD);
  delay(1000);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  servoHardStop();

  Serial.println("\n================================");
  Serial.println("WeMos Receiver + Feeder");
  Serial.println("Pairs with: all_sensors_no_shield2");
  Serial.println("================================");
  Serial.println("Pins (no conflict):");
  Serial.println("  SoftSerial D5/D6 | Trig D3 | Echo D4 | Servo D7");
  Serial.println("Arduino link:");
  Serial.println("  Uno D10 → WeMos D5 (divider) | Uno D11 → D6 | GND");
  Serial.println("Servo USB cmds: L, R, L90, R45, 1-180, 0");
  Serial.println("--------------------------------");

  connectWiFi();
  Serial.print("[HTTP] Sensors → ");
  Serial.println(SERVER_URL);
  Serial.print("[HTTP] Feeder  → ");
  Serial.println(FEEDER_URL);
  Serial.print("[HTTP] Servo   → ");
  Serial.println(SERVO_CMD_URL);
  Serial.println("[WEB] Polling servo_cmd_api.php every 1.5s");
  Serial.println("[WEB] If you do NOT see this line, you uploaded the wrong tab (sketch_sepNNa).");
  Serial.println("[WEB] File → Open: arduino_practice/wemos_receiver_no_shield/wemos_receiver_no_shield2.ino");

  printDistance();
  lastDistanceMs = millis();
  syncLastWebServoCmdId();

  Serial.println("Waiting for Arduino + website servo + USB cmds...");
  Serial.println("After upload, click Servo ON on the website once more.");
  Serial.println("--------------------------------");
}

void loop() {
  handleUsbServoSerial();
  handleArduinoSerial();
  runPendingServoJobs();

  unsigned long now = millis();
  if (!servoBusy && (now - lastServoCmdPollMs >= SERVO_CMD_POLL_MS)) {
    lastServoCmdPollMs = now;
    pollWebServoCommands();
  }
  if (!servoBusy && (now - lastDistanceMs >= DISTANCE_INTERVAL_MS)) {
    lastDistanceMs = now;
    printDistance();
  }
}
