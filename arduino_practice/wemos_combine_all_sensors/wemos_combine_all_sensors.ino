/*
 * ================================================================
 * WeMos D1 R1 — COMBINED (same DB path as wemos_receiver_no_shield)
 * Board: LOLIN(WEMOS) D1 R1
 *
 * = receiver_no_shield (Arduino sensors → sensor_api.php → MySQL)
 * + feeder (ultrasonic + continuous servo)
 *
 *   1. Receives TEMP/PH/NTU/TDS from Arduino (~5s) via SoftSerial
 *   2. POSTs water sensors to sensor_api.php  (same as working receiver)
 *   3. Reads HC-SR04 every 10s → POSTs to feeder_api.php
 *   4. Website Servo ON → spin LEFT (L); Servo OFF → spin RIGHT (R)
 *      (polls servo_cmd_api.php + optional HTTP /api/servo/on|/off)
 *   5. USB Serial still accepts: L / R / L90 / 0
 *
 * Copy to XAMPP htdocs (same place as sensor_api.php):
 *   C:\xampp\htdocs\sensor_api.php
 *   C:\xampp\htdocs\feeder_api.php
 *   C:\xampp\htdocs\servo_cmd_api.php
 * ================================================================
 */

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ESP8266WebServer.h>
#include <WiFiClient.h>
#include <SoftwareSerial.h>
#include <Servo.h>

// ── Wi-Fi (same as working receiver) ─────────────────────────────
const char* WIFI_SSID     = "thiss";
const char* WIFI_PASSWORD = "123456789";

// ── Server / Database (PHP → MySQL) ──────────────────────────────
// Same style as wemos_receiver_no_shield (NO custom Apache port).
// Run ipconfig → use this PC's Wi-Fi IPv4. WeMos must be on the SAME Wi-Fi.
//
// Normal XAMPP Apache = port 80 → URL has NO :number
//   http://YOUR_PC_IP/sensor_api.php
//
// If phpMyAdmin only opens with :54884, Apache was moved off port 80
// (another app took 80, or httpd.conf was changed). That is an XAMPP
// setting — the WeMos sketch does NOT change database/Apache ports.
// Fix Apache back to port 80, then keep these URLs as below.
//
// Update IP when Wi-Fi reconnects (ipconfig → Wireless LAN → IPv4):
// Current PC Wi-Fi IP on hotspot "thiss": 10.131.237.87
const char* SERVER_URL = "http://10.131.237.87/sensor_api.php";
const char* FEEDER_URL = "http://10.131.237.87/feeder_api.php";
const char* SERVO_CMD_URL = "http://10.131.237.87/servo_cmd_api.php";

// ── SoftSerial from Arduino (same as receiver) ───────────────────
#define SW_RX_PIN D5
#define SW_TX_PIN D6
SoftwareSerial arduinoSerial(SW_RX_PIN, SW_TX_PIN);
#define ARDUINO_BAUD 9600

// ── Ultrasonic + servo (from wemos_feeder) ───────────────────────
#define TRIG_PIN D3
#define ECHO_PIN D4
#define SERVO_PIN D7

const int STOP_US = 1500;
const int SPIN_LEFT_US  = 1000;
const int SPIN_RIGHT_US = 2000;
const float MS_PER_DEGREE = 10;
const unsigned long STOP_HOLD_MS = 400;
const unsigned long DISTANCE_INTERVAL_MS = 10000;
const unsigned long SERVO_CMD_POLL_MS = 1500;

String receivedLine = "";
String usbSerialBuffer = "";
unsigned long lastWifiAttempt = 0;
unsigned long lastDistanceMs = 0;
unsigned long lastServoCmdPollMs = 0;
bool servoBusy = false;
String lastMotorState = "OFF";
float lastDistanceCm = -1.0;
long lastWebServoCmdId = 0;
bool pendingLeft = false;
bool pendingRight = false;

Servo feederServo;
ESP8266WebServer httpServer(80);

// ── Wi-Fi (same logic as receiver) ───────────────────────────────
const char* wifiStatusText(wl_status_t s) {
  switch (s) {
    case WL_IDLE_STATUS:     return "IDLE";
    case WL_NO_SSID_AVAIL:   return "NO_SSID (name not found / out of range)";
    case WL_SCAN_COMPLETED:  return "SCAN_DONE";
    case WL_CONNECTED:       return "CONNECTED";
    case WL_CONNECT_FAILED:  return "CONNECT_FAILED (wrong password?)";
    case WL_CONNECTION_LOST: return "CONNECTION_LOST";
    case WL_DISCONNECTED:    return "DISCONNECTED";
    default:                 return "UNKNOWN";
  }
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("[WiFi] Connecting to \"");
  Serial.print(WIFI_SSID);
  Serial.println("\"");

  WiFi.persistent(false);
  WiFi.mode(WIFI_OFF);
  delay(200);
  WiFi.mode(WIFI_STA);
  WiFi.setSleepMode(WIFI_NONE_SLEEP);
  WiFi.disconnect(true);
  delay(200);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  // ~25 seconds (ESP8266 + some extenders are slow)
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 50) {
    delay(500);
    Serial.print(".");
    if (tries % 10 == 9) {
      Serial.print(" [");
      Serial.print(wifiStatusText(WiFi.status()));
      Serial.print("]");
    }
    tries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected!");
    Serial.print("[WiFi] IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("[WiFi] Gateway: ");
    Serial.println(WiFi.gatewayIP());
  } else {
    Serial.println();
    Serial.print("[WiFi] FAILED status=");
    Serial.print((int)WiFi.status());
    Serial.print(" ");
    Serial.println(wifiStatusText(WiFi.status()));
    Serial.println("[WiFi] Check: 2.4GHz, SSID/password exact, WeMos near extender.");
  }
  lastWifiAttempt = millis();
}

bool ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  // Retry every 10s when offline (was 30s)
  if (millis() - lastWifiAttempt > 10000) connectWiFi();
  return WiFi.status() == WL_CONNECTED;
}

// ── Water sensors → sensor_api.php (identical to receiver) ───────
void sendToDatabase(String temp, String ph, String ntu, String tds) {
  if (!ensureWiFi()) {
    Serial.println("[WiFi] Not connected — skipping upload.");
    return;
  }

  WiFiClient client;
  HTTPClient http;

  http.begin(client, SERVER_URL);
  http.addHeader("Content-Type", "application/x-www-form-urlencoded");

  String postBody = "temperature=" + temp
                  + "&ph="         + ph
                  + "&turbidity="  + ntu
                  + "&tds="        + tds;

  Serial.print("[HTTP] POST sensor from ");
  Serial.print(WiFi.localIP());
  Serial.print(" → ");
  Serial.println(SERVER_URL);

  int httpCode = http.POST(postBody);

  Serial.print("[HTTP] sensor_api code: ");
  Serial.println(httpCode);

  if (httpCode == 200) {
    Serial.println("[HTTP] Data saved to database!");
  } else {
    Serial.print("[HTTP] Failed: ");
    Serial.println(http.errorToString(httpCode));
    Serial.println(http.getString());
  }

  http.end();
}

// ── Ultrasonic / servo → feeder_api.php ──────────────────────────
void sendFeederToDatabase(float distanceCm, const String& motorState, const char* deviceId = "wemos-combine") {
  if (!ensureWiFi()) {
    Serial.println("[WiFi] Not connected — skipping feeder upload.");
    return;
  }

  WiFiClient client;
  HTTPClient http;

  http.begin(client, FEEDER_URL);
  http.addHeader("Content-Type", "application/x-www-form-urlencoded");

  String postBody = "device_id=";
  postBody += deviceId;
  postBody += "&motor_state=" + motorState;
  if (distanceCm >= 0) {
    postBody += "&distance_cm=" + String(distanceCm, 1);
  }

  Serial.print("[HTTP] POST feeder from ");
  Serial.print(WiFi.localIP());
  Serial.print(" → ");
  Serial.println(FEEDER_URL);

  int httpCode = http.POST(postBody);
  Serial.print("[HTTP] feeder_api code: ");
  Serial.println(httpCode);
  if (httpCode != 200) {
    Serial.print("[HTTP] Failed: ");
    Serial.println(http.errorToString(httpCode));
    Serial.println(http.getString());
  } else {
    Serial.println("[HTTP] Feeder distance saved!");
  }
  http.end();
}

String extractValue(String data, String key) {
  String search = key + ":";
  int startIdx = data.indexOf(search);
  if (startIdx == -1) return "NULL";
  startIdx += search.length();
  int endIdx = data.indexOf(",", startIdx);
  if (endIdx == -1) endIdx = data.length();
  return data.substring(startIdx, endIdx);
}

// ── Ultrasonic helpers ───────────────────────────────────────────
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

void printAndUploadDistance() {
  float cm = readDistanceCm();
  lastDistanceCm = cm;

  Serial.println("---- Ultrasonic ----");
  if (cm < 0) Serial.println("Distance: out of range / no echo");
  else {
    Serial.print("Distance: ");
    Serial.print(cm, 1);
    Serial.println(" cm");
  }
  Serial.println("--------------------");

  sendFeederToDatabase(cm, lastMotorState);
}

// ── Servo (continuous 360°) ──────────────────────────────────────
void servoOff() {
  feederServo.detach();
  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW);
  lastMotorState = "OFF";
}

void servoHardStop() {
  feederServo.attach(SERVO_PIN);
  feederServo.writeMicroseconds(STOP_US);
  delay(STOP_HOLD_MS);
  servoOff();
  Serial.println("Servo STOP / OFF");
  sendFeederToDatabase(lastDistanceCm, "OFF");
}

void feedSpin(int degrees, int spinUs) {
  degrees = constrain(degrees, 1, 180);
  unsigned long spinMs = (unsigned long)(degrees * MS_PER_DEGREE);

  servoBusy = true;
  lastMotorState = "ON";

  Serial.print(spinUs < STOP_US ? "L→R spin ~" : "R→L spin ~");
  Serial.print(degrees);
  Serial.print(" deg for ");
  Serial.print(spinMs);
  Serial.println(" ms");

  feederServo.attach(SERVO_PIN);
  feederServo.writeMicroseconds(STOP_US);
  delay(200);
  feederServo.writeMicroseconds(spinUs);
  delay(spinMs);
  feederServo.writeMicroseconds(STOP_US);
  delay(STOP_HOLD_MS);
  servoOff();

  servoBusy = false;
  Serial.println("Done. Servo stopped. Ready.");
  sendFeederToDatabase(lastDistanceCm, "OFF");
}

// Website: Servo ON → LEFT (L), Servo OFF → RIGHT (R)
void runPendingServoJobs() {
  if (servoBusy) return;
  if (pendingLeft) {
    pendingLeft = false;
    Serial.println("[Web] Servo ON → LEFT (L)");
    sendFeederToDatabase(lastDistanceCm, "LEFT", "wemos-servo-ack");
    feedSpin(180, SPIN_LEFT_US);
    return;
  }
  if (pendingRight) {
    pendingRight = false;
    Serial.println("[Web] Servo OFF → RIGHT (R)");
    sendFeederToDatabase(lastDistanceCm, "RIGHT", "wemos-servo-ack");
    feedSpin(180, SPIN_RIGHT_US);
  }
}

void handleHttpServoStatus() {
  httpServer.send(200, "text/plain", lastMotorState);
}

void handleHttpServoOn() {
  httpServer.send(200, "text/plain", "ON");
  pendingLeft = true;   // ON = L
  pendingRight = false;
}

void handleHttpServoOff() {
  httpServer.send(200, "text/plain", "OFF");
  pendingRight = true;  // OFF = R
  pendingLeft = false;
}

void handleHttpDistance() {
  if (lastDistanceCm < 0) httpServer.send(200, "text/plain", "NA");
  else httpServer.send(200, "text/plain", String(lastDistanceCm, 1));
}

void startHttpServoServer() {
  httpServer.on("/api/servo", HTTP_GET, handleHttpServoStatus);
  httpServer.on("/api/servo/on", HTTP_GET, handleHttpServoOn);
  httpServer.on("/api/servo/off", HTTP_GET, handleHttpServoOff);
  httpServer.on("/open", HTTP_GET, handleHttpServoOn);
  httpServer.on("/close", HTTP_GET, handleHttpServoOff);
  httpServer.on("/api/distance", HTTP_GET, handleHttpDistance);
  httpServer.on("/distance", HTTP_GET, handleHttpDistance);
  httpServer.begin();
  Serial.println("[HTTP] Servo server on port 80");
  Serial.println("[HTTP] ON=/api/servo/on (LEFT)  OFF=/api/servo/off (RIGHT)");
}

void syncLastWebServoCmdId() {
  if (WiFi.status() != WL_CONNECTED) return;
  WiFiClient client;
  HTTPClient http;
  if (!http.begin(client, SERVO_CMD_URL)) return;
  int code = http.GET();
  if (code == 200) {
    String body = http.getString();
    body.trim();
    // id=123&state=ON
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
      state.toUpperCase();
      state.trim();

      if (id > lastWebServoCmdId) {
        lastWebServoCmdId = id;
        if (state == "ON") {
          pendingLeft = true;
          pendingRight = false;
        } else if (state == "OFF") {
          pendingRight = true;
          pendingLeft = false;
        }
      }
    }
  }
  http.end();
}

void handleUsbServoCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;
  if (servoBusy) {
    Serial.println("Busy — wait for stop.");
    return;
  }

  int spinUs = SPIN_LEFT_US;
  String arg = cmd;
  char dir = toupper(arg.charAt(0));
  if (dir == 'L' || dir == 'R') {
    spinUs = (dir == 'L') ? SPIN_LEFT_US : SPIN_RIGHT_US;
    arg = arg.substring(1);
    arg.trim();
    if (arg.length() == 0) arg = "180";
  }

  bool valid = arg.length() > 0;
  for (unsigned int i = 0; i < arg.length(); i++) {
    if (!isDigit(arg.charAt(i))) { valid = false; break; }
  }
  if (!valid) {
    Serial.println("Use L, R, L90, R45, 1–180, or 0 (stop).");
    return;
  }

  int value = arg.toInt();
  if (value == 0) servoHardStop();
  else if (value >= 1 && value <= 180) feedSpin(value, spinUs);
  else Serial.println("Use L, R, L90, R45, 1–180, or 0 (stop).");
}

void pollUsbSerial() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (usbSerialBuffer.length() > 0) {
        handleUsbServoCommand(usbSerialBuffer);
        usbSerialBuffer = "";
      }
    } else {
      usbSerialBuffer += c;
      if (usbSerialBuffer.length() > 8) usbSerialBuffer = "";
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
  Serial.println("WeMos COMBINED (PHP MySQL path)");
  Serial.println("Same upload as wemos_receiver_no_shield");
  Serial.println("+ ultrasonic + servo");
  Serial.println("================================");
  Serial.println("Arduino 10→D5 (divider), 11→D6, GND");
  Serial.println("Ultrasonic Trig D3 | Echo D4");
  Serial.println("Servo SIG D7 (ext 5–6V + shared GND)");
  Serial.print("sensor_api: ");
  Serial.println(SERVER_URL);
  Serial.print("feeder_api: ");
  Serial.println(FEEDER_URL);
  Serial.println("Servo: website ON=LEFT (L), OFF=RIGHT (R)");
  Serial.println("USB cmds: L / R / L90 / 0");
  Serial.println("--------------------------------");

  connectWiFi();
  if (WiFi.status() == WL_CONNECTED) {
    startHttpServoServer();
    syncLastWebServoCmdId();
    Serial.print("[WiFi] Set WEMOS_BASE_URL=http://");
    Serial.println(WiFi.localIP());
  }
  Serial.println("Waiting for data from Arduino...");
  printAndUploadDistance();
  lastDistanceMs = millis();
  lastServoCmdPollMs = millis();
}

void loop() {
  pollUsbSerial();
  if (WiFi.status() == WL_CONNECTED) {
    httpServer.handleClient();
  }
  runPendingServoJobs();

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
    } else if (c != '\r') {
      receivedLine += c;
    }
  }

  unsigned long now = millis();
  if (!servoBusy && (now - lastServoCmdPollMs >= SERVO_CMD_POLL_MS)) {
    lastServoCmdPollMs = now;
    pollWebServoCommands();
  }
  if (!servoBusy && (now - lastDistanceMs >= DISTANCE_INTERVAL_MS)) {
    lastDistanceMs = now;
    printAndUploadDistance();
  }
}
