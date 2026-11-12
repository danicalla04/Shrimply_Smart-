# WeMos D1 R1 receiver, feeder, LEDs, and buzzer

Open `wemos_with_led_and_buzzer_update.ino` in Arduino IDE and select **LOLIN(WEMOS) D1 R1**. This is a new sketch; the original receiver sketch is unchanged. The receiver still uploads sensor readings, reports ultrasonic distance, and polls servo commands.

## Pin wiring

| Device | WeMos pin | D1 R1 GPIO | Wiring |
| --- | --- | --- | --- |
| Arduino Uno TX (D10) | D5 | GPIO14 | Uno D10 through a 5 V to 3.3 V divider to WeMos D5 |
| Arduino Uno RX (D11) | D6 | GPIO12 | WeMos D6 to Uno D11; share ground |
| HC-SR04 trigger | D3 | GPIO5 | WeMos D3 to TRIG |
| HC-SR04 echo | D4 | GPIO4 | ECHO through a 5 V to 3.3 V divider to WeMos D4 |
| Continuous servo signal | D7 | GPIO13 | Servo signal to D7; external 5 to 6 V supply |
| LED 1 | D9 | GPIO2 | D9 → 330 Ω resistor → LED anode; LED cathode → ground |
| LED 2 | D2 | GPIO16 | D2 → 330 Ω resistor → LED anode; LED cathode → ground |
| LED 3 | D8 | GPIO0 | D8 → 330 Ω resistor → LED anode; LED cathode → ground |
| Passive buzzer driver | D10 | GPIO15 | D10 → 1 kΩ resistor → NPN base; 10 kΩ base to ground; emitter to ground; collector to buzzer negative; buzzer positive to its rated supply |

All grounds must be connected together: WeMos, Uno, ultrasonic sensor, servo supply, and buzzer supply. Use the existing external supply for the servo. Do not connect 5 V directly to any WeMos GPIO pin.

The three LEDs are **active HIGH**, matching the tested wiring: the sketch drives their pins HIGH for ON and LOW for OFF. D8/GPIO0 and D9/GPIO2 must remain HIGH during the ESP8266 boot sequence, before the sketch runs. If the board fails to boot with an LED connected to either pin, use a transistor or buffer so the LED circuit does not pull the boot pin LOW. D10/GPIO15 must be LOW while booting, so the buzzer uses the transistor with a base pulldown. If you use a magnetic buzzer instead of a passive piezo buzzer, add a flyback diode across it.

The separate LED sketch's D11 and D12 pins cannot be reused: on this board **D11 is the same GPIO as D7** (servo) and **D12 is the same GPIO as D6** (Arduino serial). Move those two LED wires to D2 and D8 before uploading the combined sketch.

## Test from the website

1. Deploy the backend and frontend update and run the Django migration.
2. Upload this new sketch to the WeMos. Open Serial Monitor at **115200 baud**. Confirm Wi-Fi connects and the output command URL is printed.
3. Sign in as `admin123`. Open **Hardware Controls**, directly below **Logs** in the sidebar.
4. Press each LED's ON and OFF buttons, then the buzzer's ON and OFF buttons. Watch the physical output and Serial Monitor. The website reports that a command was **queued**; the monitor then shows the output pin states reported by the WeMos.
5. Manual LED and buzzer commands last 30 seconds before sensor-based status resumes. Test the servo separately with its ON and OFF buttons.

The WeMos polls the new `/api/hardware/commands/poll/` endpoint. Sensor, feeder, and servo endpoints from the original receiver sketch stay in use. The output command endpoint is read-only for the device; only the signed-in `admin123` account can queue LED or buzzer commands.

You can also test the outputs over USB Serial Monitor by sending `LED1 ON`, `LED1 OFF`, `LED2 ON`, `LED3 ON`, `BUZZER ON`, `BUZZER OFF`, `ALL ON`, or `ALL OFF` followed by a newline. The original servo serial commands (`L`, `R`, `L90`, `R45`, `0`) still work.

## Automatic lights

- D9 is blue, D2 is yellow, and D8 is red. Only one color lights at a time.
- Blue and buzzer off: all four sensor values are within the saved Settings ranges.
- Yellow and buzzer on: one to three sensor values are outside their saved ranges.
- Red and buzzer on: all four sensor values are outside range, a sensor reading is missing, or sensor readings are over 30 seconds old. A lost website connection also turns the WeMos red after 20 seconds because current sensor status is unavailable.

The WeMos checks the website every five seconds. The buzzer turns off once the status returns to blue. The LED and buzzer monitor shows the board's reported color and the sensor readings that led to it. Feeder capacity, feeder connection, and feeding activity do not affect the LEDs or buzzer.

Hardware Controls also has an LED and buzzer monitor. The WeMos reports the states of its output pins every five seconds, including during manual tests. The page shows **Unknown** if no report arrives for 15 seconds. Upload the updated sketch for this monitor to work. The report describes GPIO output levels; it cannot detect a failed LED, buzzer, or wire.
