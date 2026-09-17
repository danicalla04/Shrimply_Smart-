/**
 * WeatherAPI Service
 * Secondary weather data source for validation and cross-checking
 * Provides real-time, hourly, and daily forecasts
 * API: https://www.weatherapi.com/
 */

const WEATHERAPI_BASE = 'https://api.weatherapi.com/v1';
const WEATHERAPI_KEY = 'a7d6d7e8f4c5b6a9e2d3f1a5b8c2d9e0'; // Free tier key (limited)

// In-memory cache for API responses
const cache = new Map();

/**
 * Get cached data or null if expired
 */
function cacheGet(key, ttlMs = 300000) {
  const cached = cache.get(key);
  if (!cached) return null;
  if (Date.now() - cached.timestamp > ttlMs) {
    cache.delete(key);
    return null;
  }
  return cached.data;
}

/**
 * Set cache data with timestamp
 */
function cacheSet(key, data) {
  cache.set(key, { data, timestamp: Date.now() });
}

/**
 * Fetch JSON from WeatherAPI with error handling
 */
async function fetchJson(url, { signal } = {}) {
  try {
    const response = await fetch(url, { signal });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error('WeatherAPI fetch error:', error);
    return null;
  }
}

/**
 * Get current weather from WeatherAPI
 * Returns: { temperature, feelslike, condition, humidity, pressure, windspeed, aqi, alerts }
 */
export async function fetchCurrentWeather(lat, lon, { signal } = {}) {
  const cacheKey = `weatherapi-current-${lat}-${lon}`;
  const cached = cacheGet(cacheKey, 600000); // 10 min cache
  if (cached) return cached;

  const url = `${WEATHERAPI_BASE}/current.json?key=${WEATHERAPI_KEY}&q=${lat},${lon}&aqi=yes&alerts=yes`;
  const data = await fetchJson(url, { signal });
  
  if (!data || !data.current) return null;

  const result = {
    temperature: data.current.temp_c,
    temperatureF: data.current.temp_f,
    feelslike: data.current.feelslike_c,
    condition: data.current.condition.text,
    icon: data.current.condition.code,
    humidity: data.current.humidity,
    pressure: data.current.pressure_mb,
    windspeed: data.current.wind_kph,
    windDirection: data.current.wind_degree,
    visibility: data.current.vis_km,
    precip: data.current.precip_mm,
    uvIndex: data.current.uv,
    isDay: data.current.is_day,
    aqi: {
      usAqi: data.current.air_quality?.us_epa_index,
      pm25: data.current.air_quality?.pm2_5,
      pm10: data.current.air_quality?.pm10,
      no2: data.current.air_quality?.no2,
      o3: data.current.air_quality?.o3,
      so2: data.current.air_quality?.so2,
      co: data.current.air_quality?.co,
    },
    alerts: data.alerts?.alert ? data.alerts.alert.map(a => ({
      headline: a.headline,
      desc: a.desc,
      severity: a.severity,
      effective: a.effective,
      expires: a.expires,
    })) : [],
    source: 'weatherapi',
    timestamp: new Date(data.current.last_updated).getTime(),
  };

  cacheSet(cacheKey, result);
  return result;
}

/**
 * Get forecast from WeatherAPI
 * Returns: { current, hourly (24h), daily (7-10 days), astronomy }
 */
export async function fetchForecast(lat, lon, { days = 7, signal } = {}) {
  const cacheKey = `weatherapi-forecast-${lat}-${lon}-${days}`;
  const cached = cacheGet(cacheKey, 1800000); // 30 min cache
  if (cached) return cached;

  const url = `${WEATHERAPI_BASE}/forecast.json?key=${WEATHERAPI_KEY}&q=${lat},${lon}&days=${Math.min(days, 10)}&aqi=yes&alerts=yes&tp=1`;
  const data = await fetchJson(url, { signal });

  if (!data || !data.forecast) return null;

  // Process daily forecast
  const daily = data.forecast.forecastday.map(day => ({
    date: day.date,
    maxTemp: day.day.maxtemp_c,
    minTemp: day.day.mintemp_c,
    condition: day.day.condition.text,
    icon: day.day.condition.code,
    rainProb: day.day.daily_chance_of_rain,
    rainMm: day.day.totalprecip_mm,
    windSpeed: day.day.maxwind_kph,
    humidity: day.day.avg_humidity,
    uvIndex: day.day.uv,
    sunrise: day.astro.sunrise,
    sunset: day.astro.sunset,
    moonrise: day.astro.moonrise,
    moonset: day.astro.moonset,
    moonphase: day.astro.moon_phase,
  }));

  // Process hourly forecast (if available)
  const hourly = [];
  data.forecast.forecastday.forEach(day => {
    if (day.hour) {
      day.hour.forEach(hour => {
        hourly.push({
          time: hour.time,
          temperature: hour.temp_c,
          condition: hour.condition.text,
          icon: hour.condition.code,
          humidity: hour.humidity,
          windSpeed: hour.wind_kph,
          rainProb: hour.chance_of_rain,
          rainMm: hour.precip_mm,
          pressure: hour.pressure_mb,
          visibility: hour.vis_km,
          uvIndex: hour.uv,
          feelslike: hour.feelslike_c,
        });
      });
    }
  });

  const result = {
    current: data.current ? {
      temperature: data.current.temp_c,
      feelslike: data.current.feelslike_c,
      condition: data.current.condition.text,
      humidity: data.current.humidity,
      windSpeed: data.current.wind_kph,
      pressure: data.current.pressure_mb,
    } : null,
    daily,
    hourly: hourly.slice(0, 48), // 48 hours
    source: 'weatherapi',
    timestamp: Date.now(),
  };

  cacheSet(cacheKey, result);
  return result;
}

/**
 * Get weather alerts for a location
 * Returns: array of active alerts with severity and time windows
 */
export async function fetchAlerts(lat, lon, { signal } = {}) {
  const cacheKey = `weatherapi-alerts-${lat}-${lon}`;
  const cached = cacheGet(cacheKey, 300000); // 5 min cache
  if (cached) return cached;

  const url = `${WEATHERAPI_BASE}/alerts.json?key=${WEATHERAPI_KEY}&q=${lat},${lon}`;
  const data = await fetchJson(url, { signal });

  if (!data || !data.alerts) return [];

  const alerts = data.alerts.alert.map(alert => ({
    headline: alert.headline,
    description: alert.desc,
    severity: alert.severity, // Extreme, Severe, Moderate, Minor
    effective: alert.effective,
    expires: alert.expires,
    areas: alert.areas,
    source: 'weatherapi',
  }));

  cacheSet(cacheKey, alerts);
  return alerts;
}

/**
 * Search for locations by name
 * Returns: array of { id, name, latitude, longitude, region, country }
 */
export async function searchLocations(query, { signal } = {}) {
  const cacheKey = `weatherapi-search-${query}`;
  const cached = cacheGet(cacheKey, 600000); // 10 min cache
  if (cached) return cached;

  const url = `${WEATHERAPI_BASE}/search.json?key=${WEATHERAPI_KEY}&q=${encodeURIComponent(query)}`;
  const data = await fetchJson(url, { signal });

  if (!Array.isArray(data)) return [];

  const results = data.map(location => ({
    id: `${location.lat}-${location.lon}`,
    name: location.name,
    latitude: location.lat,
    longitude: location.lon,
    region: location.region,
    country: location.country,
    url: location.url,
  }));

  cacheSet(cacheKey, results);
  return results;
}

/**
 * Get astronomy data for a location and date
 * Returns: { sunrise, sunset, moonrise, moonset, moonphase, moonillumination }
 */
export async function fetchAstronomy(lat, lon, date, { signal } = {}) {
  const cacheKey = `weatherapi-astronomy-${lat}-${lon}-${date}`;
  const cached = cacheGet(cacheKey, 3600000); // 1 hour cache
  if (cached) return cached;

  const url = `${WEATHERAPI_BASE}/astronomy.json?key=${WEATHERAPI_KEY}&q=${lat},${lon}&dt=${date}`;
  const data = await fetchJson(url, { signal });

  if (!data || !data.astronomy) return null;

  const astro = data.astronomy.astro;
  const result = {
    sunrise: astro.sunrise,
    sunset: astro.sunset,
    moonrise: astro.moonrise,
    moonset: astro.moonset,
    moonphase: astro.moon_phase,
    moonillumination: astro.moon_illumination,
    isInternalObject: astro.is_moon_up,
    isSunUp: astro.is_sun_up,
  };

  cacheSet(cacheKey, result);
  return result;
}

export default {
  fetchCurrentWeather,
  fetchForecast,
  fetchAlerts,
  searchLocations,
  fetchAstronomy,
};
