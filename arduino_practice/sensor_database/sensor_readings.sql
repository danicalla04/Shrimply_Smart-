-- ================================================================
-- Sensor Readings Database
-- For: Arduino Uno + WeMos ESP8266 (TX/RX communication)
-- Sensors: Temperature | pH | Turbidity | TDS
-- ================================================================
-- How to use:
--   1. Open phpMyAdmin (WAMP/XAMPP)
--   2. Create a new database named: sensor_readings
--   3. Import this file OR paste and run in SQL tab
-- ================================================================

CREATE DATABASE IF NOT EXISTS `sensor_readings`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `sensor_readings`;

-- ----------------------------------------------------------------
-- 1 TABLE with 4 sensor rows
-- ----------------------------------------------------------------
DROP TABLE IF EXISTS `sensor_readings`;
CREATE TABLE `sensor_readings` (
  `id`          INT           NOT NULL AUTO_INCREMENT,
  `temperature` DECIMAL(6,2)  NULL COMMENT 'DS18B20 — degrees Celsius',
  `ph`          DECIMAL(5,2)  NULL COMMENT 'PH-4502C — pH value (0-14)',
  `turbidity`   DECIMAL(6,1)  NULL COMMENT 'KIE-TS-300B — NTU value',
  `tds`         DECIMAL(8,1)  NULL COMMENT 'TDS board — parts per million (ppm)',
  `recorded_at` DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='All sensor readings from Arduino via WeMos TX/RX';

-- ================================================================
-- SAMPLE DATA
-- ================================================================
INSERT INTO `sensor_readings` (`temperature`, `ph`, `turbidity`, `tds`) VALUES
  (27.50, 7.07,  5.0,  342.5),
  (28.00, 6.95, 12.0,  310.0),
  (27.80, 7.20,  8.5,  355.0),
  (28.50, 6.80, 45.0,  400.0);

-- ================================================================
-- USEFUL QUERIES
-- ================================================================

-- Get latest reading:
-- SELECT * FROM sensor_readings ORDER BY recorded_at DESC LIMIT 1;

-- Get all readings from today:
-- SELECT * FROM sensor_readings WHERE DATE(recorded_at) = CURDATE();

-- Get average of all sensors:
-- SELECT
--   AVG(temperature) AS avg_temp,
--   AVG(ph)          AS avg_ph,
--   AVG(turbidity)   AS avg_turbidity,
--   AVG(tds)         AS avg_tds
-- FROM sensor_readings;
