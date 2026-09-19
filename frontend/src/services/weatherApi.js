// Weather API client now targets Django backend
// Contract:
// - fetchCurrentWeather(city: string) -> Promise<{
//     city, country, temperature, description, humidity, windKmh, pressure, visibilityKm, icon, iconUrl, forecast
//   }>
// - fetchCompleteWeather(city: string) -> Promise<{ current, tomorrow, weekly, impact }>
// - Throws on network/API errors with message suitable for UI
// Client-side caching retained (10 min) to reduce server hits if user switches cities rapidly.

import API_BASE from './apiConfig'
import { wmoLabel } from './weather/weatherCodes'

const CACHE = new Map()
const TTL_MS = 10 * 60 * 1000 // 10 minutes

const CALAPAN = { lat: 13.4117, lon: 121.1803 }

const buildUrl = (endpoint, city) => {
  const params = new URLSearchParams({ city })
  return `${API_BASE}${endpoint}?${params.toString()}`
}

async function fetchOpenMeteoCurrent(city) {
  const params = new URLSearchParams({
    latitude: String(CALAPAN.lat),
    longitude: String(CALAPAN.lon),
    current: 'temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,pressure_msl',
    wind_speed_unit: 'kmh',
    timezone: 'Asia/Manila',
  })
  const res = await fetch(`https://api.open-meteo.com/v1/forecast?${params.toString()}`)
  if (!res.ok) {
    throw new Error(`Open-Meteo error (${res.status})`)
  }
  const json = await res.json()
  const current = json?.current || {}
  const temp = current.temperature_2m
  const wind = current.wind_speed_10m
  return {
    city,
    country: 'Philippines',
    temperature: temp == null ? null : Math.round(temp * 10) / 10,
    description: wmoLabel(current.weather_code),
    humidity: current.relative_humidity_2m ?? null,
    windKmh: wind == null ? null : Math.round(wind * 10) / 10,
    pressure: current.pressure_msl ?? null,
    source: 'open-meteo',
  }
}

async function fetchData(url, cacheKey, retries = 2) {
  const now = Date.now()
  const cached = CACHE.get(cacheKey)
  if (cached && now - cached.time < TTL_MS) {
    return cached.data
  }

  let lastError
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      // Add 180-second timeout for forecast generation
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 180000)

      const res = await fetch(url, { signal: controller.signal })
      clearTimeout(timeout)

      if (!res.ok) {
        let detail = ''
        try {
          const errJson = await res.json()
          if (errJson?.error) detail = `: ${errJson.error}`
        } catch (_) { }

        if (res.status === 404) {
          throw new Error(`Weather data not found for this location.`)
        }
        if (res.status === 503) {
          // Retry on 503 Service Unavailable (backend is starting/loading models)
          lastError = new Error(`Weather service is loading. Please wait and try again.`)
          if (attempt < retries || true) { // Always retry 503 during startup up to a max (like 20)
            const retryDelay = attempt < 3 ? 2000 : 5000;
            await new Promise(r => setTimeout(r, retryDelay))
            // Increase max attempts if it's just 503 from backend starting
            if (attempt >= retries && attempt < 25) { attempt--; }
            continue
          }
          throw lastError
        }
        throw new Error(`Weather API error (${res.status})${detail}`)
      }

      const json = await res.json()
      CACHE.set(cacheKey, { time: now, data: json })
      return json
    } catch (e) {
      console.error(`Weather API fetch attempt ${attempt + 1}/${retries + 1} failed:`, e.message)
      lastError = e

      // Retry on network errors and timeouts (but not on client errors like 404)
      if (attempt < retries && (e.name === 'AbortError' || e.message.includes('Network'))) {
        const delay = 1000 * (attempt + 1)
        await new Promise(r => setTimeout(r, delay))
        continue
      }

      if (e.name === 'AbortError') {
        throw new Error('Weather forecast generation timed out. The ML models may be processing. Please try again in a moment.')
      }
      throw e
    }
  }

  throw lastError || new Error('Network error while fetching weather. Please check your connection.')
}

export async function fetchCurrentWeather(city) {
  const cacheKey = `current-${String(city || 'calapan').toLowerCase().trim()}`
  const cached = CACHE.get(cacheKey)
  if (cached && Date.now() - cached.time < TTL_MS) {
    return cached.data
  }

  try {
    const url = buildUrl('/weather/current/', city)
    const data = await fetchData(url, cacheKey, 0)
    if (data?.temperature != null || data?.description) {
      return data
    }
  } catch (e) {
    console.warn('Django current weather unavailable, using Open-Meteo:', e.message)
  }

  const fallback = await fetchOpenMeteoCurrent(city)
  CACHE.set(cacheKey, { time: Date.now(), data: fallback })
  return fallback
}

export async function fetchTomorrowWeather(city) {
  const url = buildUrl('/weather/tomorrow/', city)
  return await fetchData(url, `tomorrow-${city.toLowerCase().trim()}`)
}

export async function fetchWeeklyWeather(city, days = 7) {
  const params = new URLSearchParams({ city, days: days.toString() })
  const url = `${API_BASE}/weather/weekly/?${params.toString()}`
  return await fetchData(url, `weekly-${city.toLowerCase().trim()}-${days}`)
}

export async function fetchCompleteWeather(city) {
  const url = buildUrl('/weather/complete/', city)
  return await fetchData(url, `complete-${city.toLowerCase().trim()}`)
}

export default {
  fetchCurrentWeather,
  fetchTomorrowWeather,
  fetchWeeklyWeather,
  fetchCompleteWeather
}
