<?php
/*
 * servo_cmd_api.php
 * ─────────────────────────────────────────────────────────────
 * Place in XAMPP htdocs next to sensor_api.php / feeder_api.php:
 *   C:\xampp\htdocs\servo_cmd_api.php
 *
 * WeMos GETs this to learn what the website requested:
 *   Servo ON  → motor_state=ON  → L45
 *   Servo OFF → motor_state=OFF → R45
 *
 * Response (plain text):
 *   id=<row_id>&state=ON|OFF&cmd=L45|R45
 *   or: NONE
 * ─────────────────────────────────────────────────────────────
 */

$host     = "localhost";
$user     = "root";
$password = "";
$database = "shrimp";
$table    = "api_feedertelemetry";

header("Content-Type: text/plain; charset=utf-8");
header("Access-Control-Allow-Origin: *");

$conn = new mysqli($host, $user, $password, $database);
if ($conn->connect_error) {
    http_response_code(500);
    die("Connection failed: " . $conn->connect_error);
}

$sql = "SELECT id, motor_state
        FROM `{$table}`
        WHERE device_id IN ('web-control', 'wemos-poller')
          AND UPPER(TRIM(motor_state)) IN ('ON', 'OFF')
        ORDER BY id DESC
        LIMIT 1";

$result = $conn->query($sql);
if ($result && ($row = $result->fetch_assoc())) {
    $id = (int)$row["id"];
    $state = strtoupper(trim((string)$row["motor_state"]));
    $cmd = ($state === "ON") ? "L45" : "R45";
    echo "id={$id}&state={$state}&cmd={$cmd}";
} else {
    echo "NONE";
}

$conn->close();
?>
