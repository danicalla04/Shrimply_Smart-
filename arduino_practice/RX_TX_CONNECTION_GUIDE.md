# RX/TX Connection Guide
## Arduino Uno → WeMos D1 R1 via Serial

---

## What You Need

- Arduino Uno + Sensor Shield v5.0
- WeMos D1 R1 (ESP8266)
- 2 resistors: **1kΩ** and **2kΩ** (for voltage divider)
- 3 jumper wires (male-to-male)

---

## Why a Voltage Divider?

| Board   | Logic Level |
|---------|-------------|
| Arduino | 5V          |
| WeMos   | 3.3V        |

Arduino TX sends 5V signals. WeMos RX only tolerates 3.3V max.
Sending 5V directly into WeMos RX **can damage the ESP8266**.

WeMos TX sends 3.3V. Arduino RX can read 3.3V as HIGH — so that
direction is safe without a divider.

---

## Exact Pin Locations

### On the Arduino Sensor Shield v5.0
The shield has groups of 3 holes labeled **S**, **+**, **–** for each pin number.
For digital pins 10 and 11, look for the row labeled **10** and **11**.

```
Shield Digital Pin Groups (each group has 3 holes):
  ┌───┬───┬───┐
  │ S │ + │ – │  ← S = Signal, + = 5V, – = GND
  └───┴───┴───┘
```

- **For TX (Pin 10):** Use the **S hole** of the **"10"** group on the shield.
- **For RX (Pin 11):** Use the **S hole** of the **"11"** group on the shield.
- **For GND:** Use any **– hole** on the shield (they are all connected to GND).

### On the WeMos D1 R1
Look at the right side of the board. The pins from top to bottom are labeled on the board:

```
WeMos D1 R1 — Right side pin row (looking at the board face up):
  ┌──────┐
  │  TX  │  ← This is WeMos TX (connects to Arduino Pin 11)
  │  RX  │  ← This is WeMos RX (connects to Arduino Pin 10 via divider)
  │  D1  │
  │  D2  │
  │  D3  │
  │  D4  │
  │  GND │  ← Connect this to Arduino GND
  │  5V  │
  └──────┘
```

The **TX** and **RX** labels are printed directly on the WeMos board next to the pin holes.

---

## Step 1 — Build the Voltage Divider

This goes between Arduino Shield Pin 10 (S hole) and WeMos RX.
Use a small breadboard to hold the resistors.

```
Arduino Shield Pin 10 (S) ── [1kΩ] ──┬── WeMos RX pin
                                      │
                                    [2kΩ]
                                      │
                                     GND (breadboard rail → Arduino GND)
```

**Breadboard steps:**
1. Place the **1kΩ resistor** across two rows (e.g. row 1 to row 3).
2. Place the **2kΩ resistor** from row 3 down to row 5.
3. Connect row 5 to the **GND rail** (blue/black rail) on the breadboard.
4. Connect the breadboard GND rail to the **– hole** of any group on the Sensor Shield.
5. Connect row 1 (top of 1kΩ) to the **S hole of Digital 10** on the Sensor Shield.
6. Connect row 3 (middle / junction point) to the **RX pin on WeMos**.

---

## Step 2 — Wire Arduino Pin 11 → WeMos TX (direct, no divider)

```
Arduino Shield Pin 11 (S hole) ────── WeMos TX pin
```

1. Take one jumper wire.
2. One end → **S hole of Digital 11** group on the Sensor Shield.
3. Other end → **TX pin on WeMos** (labeled TX on the board).

> Note: This seems backwards but it is correct.
> Arduino Pin 11 **receives** (RX), WeMos TX **sends** — they connect to each other.

---

## Step 3 — Share Ground

```
Arduino Shield GND ────── WeMos GND pin
```

1. Take one jumper wire.
2. One end → **– hole** of any group on the Sensor Shield (e.g. the – of Digital 10 group).
3. Other end → **GND pin on WeMos** (labeled GND on the right side of the board).

---

## Step 4 — Power Both Boards

- Plug Arduino into PC via USB (for uploading and Serial Monitor).
- Plug WeMos into PC via a second USB port (for uploading and Serial Monitor).
- Do NOT power the WeMos from Arduino's 3.3V pin — it may not supply enough current.

---

## Step 5 — Upload the Correct Code

| Board   | Sketch File                                           |
|---------|-------------------------------------------------------|
| Arduino | `all_sensors_combined/all_sensors_combined.ino`       |
| WeMos   | `wemos_receiver/wemos_receiver.ino`                   |

**Before uploading wemos_receiver.ino, edit these 3 lines:**
```cpp
const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL    = "http://YOUR_SERVER_IP/sensor_api.php";
```

Replace YOUR_SERVER_IP with the IP address of your PC running XAMPP.
To find your PC's IP: open Command Prompt → type `ipconfig` → look for IPv4 Address.

---

## Step 6 — Open Serial Monitor to Verify

### On Arduino (COM port of Arduino):
- Baud rate: **9600**
- You should see sensor readings printed every 5 seconds.
- Last line of each cycle will say: `Sent to WeMos: TEMP:xx.xx,PH:x.xx,...`

### On WeMos (COM port of WeMos):
- Baud rate: **9600**
- You should see:
  ```
  ---- New Reading ----
  Raw: TEMP:27.50,PH:7.07,NTU:5.0,TDS:342.5
  Temperature : 27.50 C
  pH          : 7.07
  Turbidity   : 5.0 NTU
  TDS         : 342.5 ppm
  ---------------------
  [HTTP] Response code: 200
  [HTTP] Data saved to database!
  ```

---

## Step 7 — Check the Database

1. Open XAMPP → Start **Apache** and **MySQL**.
2. Go to `http://localhost/phpmyadmin`.
3. Open database `sensor_db` → table `sensor_readings`.
4. New rows should appear every 5 seconds.

---

## Full Wiring Summary

```
SENSOR SHIELD v5.0                         WEMOS D1 R1
(on top of Arduino Uno)                    (right side pins)

  Digital 10 group                          ┌──────┐
  ┌───┬───┬───┐                             │  TX  │──────────────────── Arduino Shield Pin 11 (S)
  │ S │ + │ – │ ← S goes to breadboard      │  RX  │──── breadboard junction (middle of divider)
  └───┴───┴───┘                             │  D1  │
     │                                      │  D2  │
     │  [1kΩ on breadboard]                 │  D3  │
     │       │                              │  D4  │
     │   junction ──────────────────────────┘  GND │──── Arduino Shield any (–) hole
     │       │                                 5V  │
     │  [2kΩ on breadboard]                 └──────┘
     │       │
     └── GND rail ──── Arduino Shield any (–) hole

  Digital 11 group
  ┌───┬───┬───┐
  │ S │ + │ – │ ← S goes directly to WeMos TX pin
  └───┴───┴───┘


JUMPER WIRE CONNECTIONS (3 total):
  Wire 1: Shield Digital 10 (S) ──→ Breadboard (top of 1kΩ)
  Wire 2: Breadboard junction    ──→ WeMos RX
  Wire 3: Shield Digital 11 (S) ──→ WeMos TX
  Wire 4: Shield any (–) hole   ──→ WeMos GND
  Wire 5: Breadboard GND rail   ──→ Shield any (–) hole  [or same wire as Wire 4]
```

---

## Troubleshooting

| Problem                          | Solution                                                       |
|----------------------------------|----------------------------------------------------------------|
| WeMos Serial shows nothing       | Check GND is shared. Check baud rate is 9600.                  |
| Garbled text on Serial Monitor   | Baud rate mismatch. Set both to 9600.                          |
| HTTP code -1 or no response      | Check Wi-Fi credentials. Check server IP is correct.           |
| HTTP code 500                    | Check sensor_api.php is in htdocs and MySQL is running.        |
| Data not appearing in database   | Check sensor_db database and sensor_readings table exist.      |
| WeMos restarts / crashes         | Arduino 5V going directly into WeMos RX. Add voltage divider.  |
| Arduino reads garbage from WeMos | Check Pin 11 is connected to WeMos TX, not RX.                 |
