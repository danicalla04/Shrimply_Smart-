const CACHE = new Map();

function cacheGet(key, ttlMs) {
  const hit = CACHE.get(key);
  if (!hit) return null;
  if (Date.now() - hit.time > ttlMs) return null;
  return hit.data;
}

function cacheSet(key, data) {
  CACHE.set(key, { time: Date.now(), data });
}

async function fetchJson(url, { signal } = {}) {
  const res = await fetch(url, { signal });
  if (!res.ok) {
    let extra = '';
    try {
      const err = await res.json();
      if (err?.reason) extra = `: ${err.reason}`;
    } catch {
      // ignore
    }
    throw new Error(`Request failed (${res.status})${extra}`);
  }
  return await res.json();
}

export async function searchLocations(name, { count = 8, language = 'en', signal } = {}) {
  const q = String(name || '').trim();
  if (!q) return [];

  const params = new URLSearchParams({
    name: q,
    count: String(count),
    language,
    format: 'json',
  });

  const url = `https://geocoding-api.open-meteo.com/v1/search?${params.toString()}`;
  const cacheKey = `geo.search:${language}:${count}:${q.toLowerCase()}`;
  const cached = cacheGet(cacheKey, 5 * 60 * 1000);
  if (cached) return cached;

  const json = await fetchJson(url, { signal });
  const results = Array.isArray(json?.results) ? json.results : [];

  const normalized = results
    .map((r) => ({
      id: r.id,
      name: r.name,
      latitude: r.latitude,
      longitude: r.longitude,
      country: r.country,
      country_code: r.country_code,
      admin1: r.admin1,
      admin2: r.admin2,
      timezone: r.timezone,
      elevation: r.elevation,
      population: r.population,
      feature_code: r.feature_code,
    }))
    .filter((r) => typeof r.latitude === 'number' && typeof r.longitude === 'number');

  cacheSet(cacheKey, normalized);
  return normalized;
}

export async function reverseGeocode(latitude, longitude, { count = 1, language = 'en', signal } = {}) {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;

  const params = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    count: String(count),
    language,
    format: 'json',
  });

  const url = `https://geocoding-api.open-meteo.com/v1/reverse?${params.toString()}`;
  const cacheKey = `geo.rev:${language}:${count}:${latitude.toFixed(4)},${longitude.toFixed(4)}`;
  const cached = cacheGet(cacheKey, 30 * 60 * 1000);
  if (cached) return cached;

  const json = await fetchJson(url, { signal });
  const first = Array.isArray(json?.results) ? json.results[0] : null;
  const normalized = first
    ? {
        id: first.id,
        name: first.name,
        latitude: first.latitude,
        longitude: first.longitude,
        country: first.country,
        country_code: first.country_code,
        admin1: first.admin1,
        timezone: first.timezone,
        elevation: first.elevation,
      }
    : null;

  cacheSet(cacheKey, normalized);
  return normalized;
}

export function buildForecastUrl({
  latitude,
  longitude,
  temperatureUnit = 'celsius',
  windSpeedUnit = 'kmh',
  precipitationUnit = 'mm',
  timezone = 'auto',
  forecastDays = 7,
}) {
  const params = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    timezone,
    temperature_unit: temperatureUnit,
    wind_speed_unit: windSpeedUnit,
    precipitation_unit: precipitationUnit,
    forecast_days: String(forecastDays),
  });

  // CURRENT
  params.append(
    'current',
    [
      'temperature_2m',
      'apparent_temperature',
      'relative_humidity_2m',
      'weather_code',
      'wind_speed_10m',
      'wind_direction_10m',
      'pressure_msl',
      'visibility',
      'is_day',
      'precipitation',
    ].join(',')
  );

  // HOURLY
  params.append(
    'hourly',
    [
      'temperature_2m',
      'relative_humidity_2m',
      'apparent_temperature',
      'precipitation_probability',
      'precipitation',
      'weather_code',
      'wind_speed_10m',
      'wind_direction_10m',
      'visibility',
      'pressure_msl',
    ].join(',')
  );

  // DAILY
  params.append(
    'daily',
    [
      'temperature_2m_max',
      'temperature_2m_min',
      'weather_code',
      'precipitation_probability_max',
      'wind_speed_10m_max',
      'wind_gusts_10m_max',
      'sunrise',
      'sunset',
      'uv_index_max',
    ].join(',')
  );

  return `https://api.open-meteo.com/v1/forecast?${params.toString()}`;
}

export async function fetchForecast(options, { signal } = {}) {
  const { latitude, longitude } = options || {};
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    throw new Error('Invalid coordinates');
  }

  const url = buildForecastUrl(options);
  const cacheKey = `forecast:${url}`;
  const cached = cacheGet(cacheKey, 2 * 60 * 1000);
  if (cached) return cached;

  const json = await fetchJson(url, { signal });
  cacheSet(cacheKey, json);
  return json;
}

export function buildAirQualityUrl({ latitude, longitude, timezone = 'auto' }) {
  const params = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    timezone,
  });

  params.append('current', ['us_aqi', 'european_aqi', 'pm2_5', 'pm10', 'carbon_monoxide', 'ozone'].join(','));
  params.append('hourly', ['us_aqi', 'european_aqi', 'pm2_5', 'pm10', 'carbon_monoxide', 'ozone'].join(','));

  return `https://air-quality-api.open-meteo.com/v1/air-quality?${params.toString()}`;
}

export async function fetchAirQuality(options, { signal } = {}) {
  const { latitude, longitude } = options || {};
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    throw new Error('Invalid coordinates');
  }

  const url = buildAirQualityUrl(options);
  const cacheKey = `air:${url}`;
  const cached = cacheGet(cacheKey, 5 * 60 * 1000);
  if (cached) return cached;

  const json = await fetchJson(url, { signal });
  cacheSet(cacheKey, json);
  return json;
}
