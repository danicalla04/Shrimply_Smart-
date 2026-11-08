import axios from 'axios'
import { authService } from './auth'
import API_BASE from './apiConfig'
import { DEFAULT_THRESHOLDS } from './sensorDefaults'

export { DEFAULT_THRESHOLDS } from './sensorDefaults'

const STORAGE_KEY = 'sensorThresholds'

export function getDefaultThresholds() {
  return JSON.parse(JSON.stringify(DEFAULT_THRESHOLDS))
}

export async function fetchThresholds() {
  try {
    console.log('[SETTINGS] Fetching thresholds from:', `${API_BASE}/thresholds/all/`)
    const response = await authService.apiCall(`${API_BASE}/thresholds/all/`)
    
    if (!response.ok) {
      console.error('[SETTINGS] API returned non-OK status:', response.status)
      throw new Error(`Server returned ${response.status}`)
    }
    
    // Parse response body (Fetch API - always use .json() method)
    let data
    try {
      data = await response.json()
      console.log('[SETTINGS] Raw API response:', data)
    } catch (parseError) {
      console.error('[SETTINGS] Failed to parse response JSON:', parseError)
      throw new Error(`Failed to parse server response: ${parseError.message}`)
    }
    
    // Ensure data is an object (handle null/undefined)
    if (!data || typeof data !== 'object') {
      console.warn('[SETTINGS] API returned invalid data format, using defaults:', data)
      return getDefaultThresholds()
    }
    
    // Merge with defaults so missing sensors / fields (e.g. step, unit) are filled
    const merged = getDefaultThresholds()
    for (const key of Object.keys(merged)) {
      if (data[key] && typeof data[key] === 'object') {
        merged[key] = { ...merged[key], ...data[key] }
        console.log(`[SETTINGS] Merged ${key}:`, merged[key])
      }
    }
    
    console.log('[SETTINGS] ✓ Final merged thresholds:', merged)
    return merged
  } catch (error) {
    console.error('[SETTINGS] ❌ Failed to fetch thresholds:', error)
    console.warn('[SETTINGS] Falling back to default thresholds')
    return getDefaultThresholds()
  }
}

export function getThresholds() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return getDefaultThresholds()
    const parsed = JSON.parse(raw)
    // Merge with defaults in case of missing fields
    const merged = { ...getDefaultThresholds() }
    for (const key of Object.keys(merged)) {
      merged[key] = { ...merged[key], ...(parsed?.[key] || {}) }
    }
    return merged
  } catch {
    return getDefaultThresholds()
  }
}

export function saveThresholds(thresholds) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(thresholds))
}

export function clearThresholdCache() {
  localStorage.removeItem(STORAGE_KEY)
  console.log('[SETTINGS] Threshold cache cleared')
}

export async function updateThresholdsOnServer(thresholds) {
  const response = await authService.apiCall(`${API_BASE}/thresholds/update_all/`, {
    method: 'POST',
    body: JSON.stringify(thresholds)
  })
  
  // Parse response body once (can only be called once in Fetch API)
  let data
  try {
    data = await response.json()
  } catch (error) {
    console.error('[SETTINGS] Failed to parse response JSON:', error)
    throw new Error(`Failed to parse server response: ${error.message}`)
  }
  
  if (!response.ok) {
    throw new Error(data.error || `Server error ${response.status}`)
  }
  
  console.log('[SETTINGS] Server update successful:', data)
  
  // Merge with defaults to keep client-only fields like step
  const merged = getDefaultThresholds()
  for (const key of Object.keys(merged)) {
    if (data[key]) {
      merged[key] = { ...merged[key], ...data[key] }
    }
  }
  saveThresholds(merged)
  return merged
}

export function evaluateStatus(value, range) {
  // Gracefully handle missing or partial range data
  if (!range || typeof range.min !== 'number' || typeof range.max !== 'number') {
    return 'unknown'
  }
  if (value < range.min) return 'low'
  if (value > range.max) return 'high'
  return 'normal'
}

export function formatRange(range) {
  return `${range.min} – ${range.max}`
}
