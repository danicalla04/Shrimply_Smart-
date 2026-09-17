// Weather API client now targets Django backend
// Contract:
// - fetchCurrentWeather(city: string) -> Promise<{
//     city, country, temperature, description, humidity, windKmh, pressure, visibilityKm, icon, iconUrl, forecast
//   }>
// - fetchCompleteWeather(city: string) -> Promise<{ current, tomorrow, weekly, impact }>
// - Throws on network/API errors with message suitable for UI
// Client-side caching retained (10 min) to reduce server hits if user switches cities rapidly.

import API_BASE from './apiConfig'

const CACHE = new Map()
const TTL_MS = 10 * 60 * 1000 // 10 minutes

const buildUrl = (endpoint, city) => {
  const params = new URLSearchParams({ city })
  return `${API_BASE}${endpoint}?${params.toString()}`
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
  const url = buildUrl('/weather/current/', city)
  return await fetchData(url, `current-${city.toLowerCase().trim()}`)
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
