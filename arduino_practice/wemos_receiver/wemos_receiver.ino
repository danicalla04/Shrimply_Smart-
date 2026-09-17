/*
 * ================================================================
 * WeMos D1 R1 — Receive Sensor Data from Arduino via RX/TX
 * Then sends data to MySQL database via Wi-Fi (HTTP POST)
 * ================================================================
 * Board: LOLIN(WEMOS) D1 R1  ← select in Arduino IDE
 *
 * ============================================================
 * INSTALL LIBRARIES (Sketch → Include Library → Manage Libraries):
 *   1. "ESP8266WiFi"         — built-in with ESP8266 board package
 *   2. "ESP8266HTTPClient"   — built-in with ESP8266 board package
 *   3. "ArduinoJson"         by Benoit Blanchon → Install (v6.x)
 * ============================================================
 *
 * ----------------------------------------------------------------
 * WIRING (Arduino → WeMos):
 *
 *   Arduino Pin 10 (TX) → WeMos D5 pin
 *                          ⚠️ VOLTAGE DIVIDER REQUIRED (5V→3.3V):
 *                          Arduino Pin10 → 1kΩ → WeMos D5
 *                                                    |
 *                                                   2kΩ
 *                                                    |
 *                                                   GND
 *   Arduino Pin 11 (RX) → WeMos D6 pin  (direct, no divider)
 *   Arduino GND         → WeMos GND     (MUST share ground!)
 *   Arduino USB powered separately OR same USB hub
 *
 *   ⚠️ DO NOT use WeMos D0/D1 (RX/TX) pins anymore —
 *      those are now reserved for USB Serial Monitor only.
 *
 * ----------------------------------------------------------------
 * HOW IT WORKS:
 *   1. Arduino reads all sensors every 5 seconds
 *   2. Arduino sends: TEMP:27.50,PH:7.07,NTU:5.0,TDS:342.5
 *   3. WeMos receives, parses, prints to Serial Monitor
 *   4. WeMos sends HTTP POST to your server/database
 * ================================================================
 */

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <SoftwareSerial.h>

// ── Wi-Fi Credentials ────────────────────────────────────────────
const char* WIFI_SSID     = "this";
const char* WIFI_PASSWORD = "12345678";

// ── Server / Database Endpoint ───────────────────────────────────
// Run ipconfig on your PC while connected to the SAME hotspot.
// Update this IP every time your PC gets a new IP from the hotspot.
const char* SERVER_URL = "http://10.131.237.87/sensor_api.php";

// ── SoftwareSerial pins (for receiving from Arduino) ─────────────
// WeMos D5 (GPIO14) = RX from Arduino  → connect to Arduino Pin 10 (via voltage divider)
// WeMos D6 (GPIO12) = TX to Arduino    → connect to Arduino Pin 11 (direct)
#define SW_RX_PIN D5   // receives from Arduino
#define SW_TX_PIN D6   // sends to Arduino (optional)
SoftwareSerial arduinoSerial(SW_RX_PIN, SW_TX_PIN);

#define ARDUINO_BAUD 9600

String receivedLine = "";

// ── Setup ─────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);           // Hardware Serial = USB Serial Monitor only
  arduinoSerial.begin(ARDUINO_BAUD); // SoftwareSerial = reads from Arduino
 
   // Small delay so Serial Monitor can catch startup messages
   delay(1000);
 
   Serial.println("\n================================");
   Serial.println("WeMos Receiver — Starting Up");
   Serial.println("================================");
 
   // Connect to Wi-Fi
   WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
   Serial.print("Connecting to Wi-Fi");
   int tries = 0;
   while (WiFi.status() != WL_CONNECTED && tries < 30) {
     delay(500);
     Serial.print(".");
     tries++;
   }
 
   if (WiFi.status() == WL_CONNECTED) {
     Serial.println("\nWi-Fi connected!");
     Serial.print("IP Address: ");
     Serial.println(WiFi.localIP());
   } else {
     Serial.println("\nWi-Fi FAILED — will still receive and display data.");
   }
 
   Serial.println("Waiting for data from Arduino...");
   Serial.println("--------------------------------");
 }
 
 // ── Parse a value from the data string ───────────────────────────
 // Input: "TEMP:27.50,PH:7.07,NTU:5.0,TDS:342.5"
 // Key: "TEMP", "PH", "NTU", "TDS"
 String extractValue(String data, String key) {
   String search = key + ":";
   int startIdx = data.indexOf(search);
   if (startIdx == -1) return "NULL";
   startIdx += search.length();
   int endIdx = data.indexOf(",", startIdx);
   if (endIdx == -1) endIdx = data.length();
   return data.substring(startIdx, endIdx);
 }
 
 // ── Send Data to Database via HTTP POST ──────────────────────────
 void sendToDatabase(String temp, String ph, String ntu, String tds) {
   if (WiFi.status() != WL_CONNECTED) {
     Serial.println("[WiFi] Not connected — skipping upload.");
     return;
   }
 
   WiFiClient client;
   HTTPClient http;
 
   http.begin(client, SERVER_URL);
   http.addHeader("Content-Type", "application/x-www-form-urlencoded");
 
   // Build POST body: temperature=27.50&ph=7.07&turbidity=5.0&tds=342.5
   String postBody = "temperature=" + temp
                   + "&ph="         + ph
                   + "&turbidity="  + ntu
                   + "&tds="        + tds;
 
   int httpCode = http.POST(postBody);
 
   Serial.print("[HTTP] Response code: ");
   Serial.println(httpCode);
 
   if (httpCode == 200) {
     Serial.println("[HTTP] Data saved to database!");
   } else {
     Serial.print("[HTTP] Failed: ");
     Serial.println(http.getString());
   }
 
   http.end();
 }
 
// ── Loop ──────────────────────────────────────────────────────────
void loop() {
  // Read incoming characters from Arduino (via SoftwareSerial D5)
  while (arduinoSerial.available() > 0) {
    char c = arduinoSerial.read();
 
     if (c == '\n') {
       // Full line received — process it
       receivedLine.trim();
 
       if (receivedLine.length() > 0 && receivedLine.startsWith("TEMP:")) {
         Serial.println("---- New Reading ----");
         Serial.println("Raw: " + receivedLine);
 
         // Parse each value
         String temp = extractValue(receivedLine, "TEMP");
         String ph   = extractValue(receivedLine, "PH");
         String ntu  = extractValue(receivedLine, "NTU");
         String tds  = extractValue(receivedLine, "TDS");
 
         Serial.println("Temperature : " + temp + " C");
         Serial.println("pH          : " + ph);
         Serial.println("Turbidity   : " + ntu + " NTU");
         Serial.println("TDS         : " + tds + " ppm");
         Serial.println("---------------------");
 
         // Send to database
         sendToDatabase(temp, ph, ntu, tds);
       }
 
       receivedLine = "";  // Clear for next line
     } else {
       receivedLine += c;  // Build line character by character
     }
   }
 }
 