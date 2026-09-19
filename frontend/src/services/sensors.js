import { authService } from './auth'
import API_BASE from './apiConfig'

// Default to null values when device not available / before first reading
export const DEFAULT_SENSORS = Object.freeze({
  temperature: null,
  ph: null,
  turbidity: null,
  tds: null,
})

export const SENSOR_STALE_MS = 15_000

export function isSensorStreamFresh(timestamp, now = Date.now()) {
  if (!timestamp) return false
  const age = now - new Date(timestamp).getTime()
  return Number.isFinite(age) && age >= 0 && age <= SENSOR_STALE_MS
}

export function getDefaultSensors() {
  return JSON.parse(JSON.stringify(DEFAULT_SENSORS))
}

/**
 * True only when the reading is missing / NULL.
 * 0 is a real numeric value — NOT disconnected.
 */
export function isSensorDisconnected(_param, value) {
  if (value === null || value === undefined || value === '') return true
  if (typeof value === 'string' && value.trim().toUpperCase() === 'NULL') return true
  if (typeof value === 'number' && Number.isNaN(value)) return true
  return false
}

/** Keep numbers (including 0); only NULL/missing → null for UI */
export function normalizeSensorValue(_param, value) {
  if (isSensorDisconnected(_param, value)) return null
  const n = Number(value)
  return Number.isNaN(n) ? null : n
}

export async function fetchLatestSensors() {
  // Fetch from Django backend API (single data path)
  try {
    const response = await authService.apiCall(`${API_BASE}/sensors/latest/`)
    const data = response?.data ?? (typeof response?.json === 'function' ? await response.json() : response)

    // Validate and normalize response (null = disconnected for UI)
    const normalized = {
      temperature: normalizeSensorValue('temperature', data?.temperature),
      ph: normalizeSensorValue('ph', data?.ph),
      turbidity: normalizeSensorValue('turbidity', data?.turbidity),
      tds: normalizeSensorValue('tds', data?.tds),
      timestamp: data?.timestamp || null,
    }

    console.log('[API] Latest sensors response:', normalized)
    return normalized
  } catch (error) {
    console.error('[API] Failed to fetch sensors:', error)
    return getDefaultSensors()
  }
}

export function getSensors() {
  return getDefaultSensors()
}

export function saveSensors(values) {
  // No longer saving to localStorage - data is stored in backend
}

export async function updateSensors(data) {
  try {
    const response = await authService.apiCall(`${API_BASE}/update-sensors/`, {
      method: 'POST',
      body: JSON.stringify(data)
    })
    if (response && typeof response.json === 'function') {
      return await response.json()
    }
    return response?.data || {}
  } catch (error) {
    console.error('Failed to update sensors:', error)
    throw error
  }
}

// Get historical sensor readings for charts (supports pagination)
export async function getSensorReadings(days = 7, page = 1, pageSize = 20, hours = null) {
  try {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    })
    if (hours != null) params.set('hours', String(hours))
    else if (days != null) params.set('days', String(days))
    const response = await authService.apiCall(
      `${API_BASE}/sensors/?${params.toString()}`
    )
    const data = response?.data ?? (typeof response?.json === 'function' ? await response.json() : response)
    // Handle DRF paginated response
    if (data && typeof data === 'object' && 'results' in data) {
      return data
    }
    // Legacy non-paginated fallback
    return { count: Array.isArray(data) ? data.length : 0, results: Array.isArray(data) ? data : [], next: null, previous: null }
  } catch (error) {
    console.error('Failed to fetch sensor readings:', error)
    return { count: 0, results: [], next: null, previous: null }
  }
}

export async function getSensorChart(hours = 1, maxPoints = 160) {
  try {
    const params = new URLSearchParams({
      hours: String(hours),
      max_points: String(maxPoints),
    })
    const response = await authService.apiCall(`${API_BASE}/sensors/chart/?${params.toString()}`)
    const data = response?.data ?? (typeof response?.json === 'function' ? await response.json() : response)
    return {
      hours: data?.hours ?? hours,
      count: data?.count ?? 0,
      results: Array.isArray(data?.results) ? data.results : [],
    }
  } catch (error) {
    console.error('Failed to fetch sensor chart:', error)
    return { hours, count: 0, results: [] }
  }
}
