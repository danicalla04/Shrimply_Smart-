<?php
/*
 * sensor_api.php
 * ─────────────────────────────────────────────────────────────
 * WeMos POSTs about every 5 seconds (live dashboard).
 *
 * Behavior:
 *   - Always refresh the newest row (live display every ~5s)
 *   - INSERT a new history row only every 10 minutes
 *     (clock uses the previous frozen row, not the live timestamp)
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

/** Settings → Sensor Data Adjustment: adjusted = (raw * scale) + offset */
function applyCalibration($conn, $parameter, $value, $asInt = false) {
    if ($value === null) {
        return null;
    }
    $scale = 1.0;
    $offset = 0.0;
    $safe = $conn->real_escape_string($parameter);
    $res = $conn->query(
        "SELECT scale, offset FROM api_sensorcalibration WHERE parameter='{$safe}' LIMIT 1"
    );
    if ($res && ($row = $res->fetch_assoc())) {
        $scale = (float)$row["scale"];
        $offset = (float)$row["offset"];
    }
    $adjusted = ((float)$value * $scale) + $offset;
    if ($asInt) {
        return (int)round($adjusted);
    }
    return round($adjusted, 2);
}

$temperature = applyCalibration($conn, "temperature", getNullableFloat("temperature"));
$ph          = applyCalibration($conn, "ph", getNullableFloat("ph"));
$turbidity   = applyCalibration($conn, "turbidity", getNullableFloat("turbidity"));
$tds         = applyCalibration($conn, "tds", getNullableInt("tds"), true);

$tempSql = sqlNumOrNull($temperature);
$phSql   = sqlNumOrNull($ph);
$ntuSql  = sqlNumOrNull($turbidity);
$tdsSql  = sqlNumOrNull($tds, true);

// Live UPDATE always refreshes the newest row (and its timestamp) so gauges
// stay online. That reset used to make "age" 0 forever, so no history INSERTs.
// The 10-minute clock now uses the *previous* row, which stays frozen.
$tip = $conn->query(
    "SELECT id, TIMESTAMPDIFF(SECOND, timestamp, UTC_TIMESTAMP()) AS age_sec
     FROM `{$table}`
     ORDER BY id DESC
     LIMIT 2"
);

$needInsert = true;
$latestId = null;
$ageSec = null;
$prevAgeSec = null;

if ($tip) {
    $first = $tip->fetch_assoc();
    $second = $tip->fetch_assoc();
    if ($first) {
        $latestId = (int)$first["id"];
        $ageSec = (int)$first["age_sec"];
        if ($second) {
            $prevAgeSec = (int)$second["age_sec"];
            if ($prevAgeSec < ($HISTORY_INTERVAL_MIN * 60)) {
                $needInsert = false;
            }
        }
        // Only one row: INSERT on the next POST so a frozen row exists
        // for the 10-minute clock. Live UPDATE cannot use its own timestamp.
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
        echo "OK - LIVE UPDATE id={$latestId} live_age={$ageSec}s prev_age=" . ($prevAgeSec === null ? "none" : $prevAgeSec . "s")
           . " (temp={$tempSql}, ph={$phSql}, ntu={$ntuSql}, tds={$tdsSql})";
    } else {
        http_response_code(500);
        echo "Error: " . $conn->error;
    }
}

$conn->close();
?>
