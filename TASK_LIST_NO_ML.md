# Shrimply Smart — Task List (No ML)
## Capstone Improvement Tracker — Hardware, Feeder, Alerts, Integration

Last updated: July 14, 2026

Mark tasks as:
- [ ] Not started
- [~] In progress
- [x] Done

---

## HARDWARE (Arduino / WeMos)

### Sensors
- [ ] Verify all 4 sensors work (Temperature, pH, Turbidity, TDS)
- [ ] Confirm sensor data reaches phpMyAdmin via WeMos → PHP → MySQL
- [ ] Confirm sensor data reaches Django dashboard via WeMos → HTTP POST
- [ ] Test RX/TX connection stability (no data loss over long run)
- [ ] Fix voltage divider on Arduino Pin 10 → WeMos D5 (5V → 3.3V)

### Feeder Hardware
- [ ] Confirm servo motor opens and closes correctly
- [ ] Confirm ultrasonic sensor reads distance inside feeder container
- [ ] Measure MAX distance (empty container) and MIN distance (full container)
- [ ] Write down those 2 numbers — needed for feed level formula

---

## BACKEND (Django / Python)

### Device Offline Detection ⭐ Priority 1
- [ ] Write a function that checks: "Was there a sensor reading in the last 1 minute?"
- [ ] If no reading → create a CRITICAL Alert in the database
- [ ] Broadcast the alert via WebSocket to the dashboard
- [ ] Show a red "Sensor Offline" banner on the web dashboard
- [ ] Auto-resolve the alert when sensor comes back online

### Data Send Rate vs Display Rate
- [ ] Arduino sends sensor data to database every 1 minute (save to DB)
- [ ] Dashboard display refreshes every 5 seconds (just re-reads latest value from DB)
- [ ] These are TWO separate things:
      - DB write rate  = 1 per minute  (controlled in Arduino/WeMos code)
      - UI refresh rate = every 5 sec   (controlled in React Dashboard fetch interval)
- [ ] Update all_sensors_combined.ino: change loop delay from 5000ms to 60000ms (1 min)
- [ ] Keep wemos_receiver.ino unchanged (it just forwards whatever Arduino sends)
- [ ] Dashboard.jsx polling interval stays at 5 seconds (reads cached latest value)

### Feeder — Feed Level Detection ⭐ Priority 2
- [ ] Add formula to convert ultrasonic distance_cm → feed level percentage
      Formula: % = (max_dist - current_dist) / (max_dist - min_dist) × 100
- [ ] Update Feeder.capacity_current automatically using this formula
- [ ] Test "Feeder Low" alert fires when feed drops below low_percent (default 15%)
- [ ] Test "Feeder Empty" alert fires when feed reaches 0%
- [ ] Show feed level bar/percentage on the Feeding page

### Feeder — Weather Adjustment ⭐ Priority 3
- [ ] Connect weather API data to should_feed_based_on_weather() when auto-feeding runs
- [ ] Test: raining → portion reduced by rain_reduction_percent (default 20%)
- [ ] Test: hot day (>30°C) → portion increased by heat_increase_percent (default 10%)
- [ ] Test: storm/extreme → feeding paused (extreme_weather_pause = True)
- [ ] Show current weather adjustment reason on Feeding page

### Feeder — Capacity Tracking
- [ ] Subtract portion_grams from capacity_current after every successful feed
- [ ] Reset capacity_current to capacity_max when farmer refills the feeder

---

## FRONTEND (React / Website)

### Dashboard
- [ ] Show "Sensor Offline" red banner when device not sending data
- [ ] Show last reading timestamp ("Last updated: X minutes ago")
- [ ] Test all 4 metric cards update in real-time via WebSocket

### Feeding Page
- [ ] Show feed level bar (Full / Half / Low / Empty)
- [ ] Show next scheduled feed time
- [ ] Show weather-based adjustment reason (e.g. "Reduced 20% due to rain")
- [ ] Show feeding history log

### Alerts Page
- [ ] Confirm threshold alerts fire (e.g. pH too low → warning appears)
- [ ] Confirm device offline alert appears when sensor disconnects
- [ ] Confirm feeder low/empty alerts appear

### General
- [ ] Test login and registration work correctly
- [ ] Test WebSocket real-time updates on Dashboard
- [ ] Test weather page loads for Oriental Mindoro municipalities

---

## DATABASE

### Practice Database (sensor_readings — phpMyAdmin)
- [x] Created sensor_readings database and table
- [x] Created sensor_api.php in htdocs
- [ ] Confirm data flows in continuously from WeMos every 1 minute
- [ ] Confirm no duplicate or NULL rows appearing

### Main App Database (shrimply_smart — Django)
- [ ] Run migrations (python manage.py migrate)
- [ ] Create demo user (python manage.py create_demo_user or register via website)
- [ ] Populate default thresholds (python manage.py populate_thresholds)
- [ ] Import weather CSV data (python manage.py load_weather_data)

---

## INTEGRATION (Connect everything together)

- [ ] Connect Arduino → WeMos → Django dashboard (not just phpMyAdmin)
- [ ] Confirm sensor readings appear on http://localhost:5173/dashboard
- [ ] Confirm alerts appear on dashboard when thresholds are crossed
- [ ] Confirm feeder servo can be triggered from Feeding page
- [ ] Confirm feeder telemetry (distance + motor state) updates on Feeding page

---

## NICE TO HAVE (Future improvements)

- [ ] Email notification when sensor goes offline
- [ ] Email notification when feeder is empty
- [ ] Mobile-responsive design check on all pages

---

## NOTES

- Practice flow:   Arduino → WeMos → sensor_api.php → sensor_readings DB (phpMyAdmin)
- Main app flow:   Arduino → WeMos → Django API → shrimply_smart DB → React Dashboard
- Both flows are SEPARATE right now — they do not share data
- WeMos IP in wemos_receiver.ino must be updated every time PC reconnects to hotspot
- Hotspot "this" is 2.4GHz — WeMos cannot connect to 5GHz networks
- Server URL format: http://[PC_IP]/sensor_api.php
