<?php
/*
 * feeder_api.php
 * ─────────────────────────────────────────────────────────────
 * WeMos POSTs ultrasonic / servo telemetry for the Feeding page.
 *
 * Place in: C:\xampp\htdocs\feeder_api.php
 * Table:    shrimp.api_feedertelemetry  (Django FeederTelemetry)
 * ─────────────────────────────────────────────────────────────
 */

$host     = "localhost";
$user     = "root";
$password = "";
$database = "shrimp";
$table    = "api_feedertelemetry";

$conn = new mysqli($host, $user, $password, $database);
if ($conn->connect_error) {
    http_response_code(500);
    die("Connection failed: " . $conn->connect_error);
}

if ($_SERVER["REQUEST_METHOD"] !== "POST") {
    http_response_code(405);
    die("Method Not Allowed");
}

function getNullableFloat($key) {
    if (!isset($_POST[$key])) {
        return null;
    }
    $raw = trim((string)$_POST[$key]);
    if ($raw === "" || strcasecmp($raw, "NULL") === 0 || strcasecmp($raw, "nan") === 0) {
        return null;
    }
    if (!is_numeric($raw)) {
        return null;
    }
    return (float)$raw;
}

$distance = getNullableFloat("distance_cm");
if ($distance === null) {
    $distance = getNullableFloat("distance");
}

$motor = isset($_POST["motor_state"]) ? trim((string)$_POST["motor_state"]) : "";
$motor = strtoupper(substr($motor, 0, 10));
$device = isset($_POST["device_id"]) ? trim((string)$_POST["device_id"]) : "wemos-feeder";
$device = substr($device, 0, 64);

$distSql = ($distance === null) ? "NULL" : (string)$distance;
$motorEsc = $conn->real_escape_string($motor);
$deviceEsc = $conn->real_escape_string($device);

$sql = "INSERT INTO `{$table}` (timestamp, motor_state, distance_cm, device_id)
        VALUES (UTC_TIMESTAMP(), '{$motorEsc}', {$distSql}, '{$deviceEsc}')";

if ($conn->query($sql) === true) {
    http_response_code(200);
    echo "OK - FEEDER id=" . $conn->insert_id . " distance={$distSql}";
} else {
    http_response_code(500);
    echo "Error: " . $conn->error;
}

$conn->close();
?>
