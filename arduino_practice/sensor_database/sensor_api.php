<?php
/*
 * sensor_api.php
 * ─────────────────────────────────────────────────────────────
 * WeMos POSTs about every 5 seconds (live dashboard).
 *
 * Behavior:
 *   - Always refresh the newest row (live display every ~5s)
 *   - INSERT a new history row only every 10 minutes
 *     (avoids flooding api_sensorreading)
 *
 * Place in: C:\xampp\htdocs\sensor_api.php
 * ─────────────────────────────────────────────────────────────
 */

$host     = "localhost";
$user     = "root";
$password = "";
$database = "shrimp";
$table    = "api_sensorreading";

/** Minutes between permanent history INSERTs */
$HISTORY_INTERVAL_MIN = 10;

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

function getNullableInt($key) {
    $v = getNullableFloat($key);
    if ($v === null) {
        return null;
    }
    return (int)round($v);
}

function sqlNumOrNull($value, $asInt = false) {
    if ($value === null) {
        return "NULL";
    }
    if ($asInt) {
        return (string)(int)$value;
    }
    return (string)(float)$value;
}

$temperature = getNullableFloat("temperature");
$ph          = getNullableFloat("ph");
$turbidity   = getNullableFloat("turbidity");
$tds         = getNullableInt("tds");

$tempSql = sqlNumOrNull($temperature);
$phSql   = sqlNumOrNull($ph);
$ntuSql  = sqlNumOrNull($turbidity);
$tdsSql  = sqlNumOrNull($tds, true);

// Newest row + age in seconds (UTC)
$latest = $conn->query(
    "SELECT id, TIMESTAMPDIFF(SECOND, timestamp, UTC_TIMESTAMP()) AS age_sec
     FROM `{$table}`
     ORDER BY id DESC
     LIMIT 1"
);

$needInsert = true;
$latestId = null;
$ageSec = null;

if ($latest && ($row = $latest->fetch_assoc())) {
    $latestId = (int)$row["id"];
    $ageSec = (int)$row["age_sec"];
    // Keep updating the tip for live dashboard; insert only every N minutes
    if ($ageSec < ($HISTORY_INTERVAL_MIN * 60)) {
        $needInsert = false;
    }
}

if ($needInsert) {
    $sql = "INSERT INTO `{$table}` (temperature, ph, turbidity, tds, timestamp)
            VALUES ({$tempSql}, {$phSql}, {$ntuSql}, {$tdsSql}, UTC_TIMESTAMP())";
    if ($conn->query($sql) === true) {
        http_response_code(200);
        echo "OK - HISTORY INSERT id=" . $conn->insert_id
           . " (temp={$tempSql}, ph={$phSql}, ntu={$ntuSql}, tds={$tdsSql})";
    } else {
        http_response_code(500);
        echo "Error: " . $conn->error;
    }
} else {
    $sql = "UPDATE `{$table}`
            SET temperature={$tempSql},
                ph={$phSql},
                turbidity={$ntuSql},
                tds={$tdsSql},
                timestamp=UTC_TIMESTAMP()
            WHERE id={$latestId}";
    if ($conn->query($sql) === true) {
        http_response_code(200);
        echo "OK - LIVE UPDATE id={$latestId} age_was={$ageSec}s"
           . " (temp={$tempSql}, ph={$phSql}, ntu={$ntuSql}, tds={$tdsSql})";
    } else {
        http_response_code(500);
        echo "Error: " . $conn->error;
    }
}

$conn->close();
?>
