// Backend-integrated feeder service with advanced scheduling
import { authService } from './auth'
import API_BASE from './apiConfig'
const STORAGE_KEY = 'feeder_state_v1'; // fallback for offline

export const DEFAULT_FEEDER_STATE = {
  // Basic settings
  autoEnabled: false,
  intervalMinutes: 60,
  portionGrams: 50,
  capacityMax: 1000,
  capacityCurrent: 1000,
  lowPercent: 15,
  nextFeedAt: null,
  lastFedAt: null,
  id: null,

  // Advanced scheduling
  scheduleType: 'interval',
  dailySchedule: [],

  // Weather adaptation
  weatherAdaptation: false,
  rainReductionPercent: 20,
  heatIncreasePercent: 10,
  extremeWeatherPause: true,

  // Smart optimization
  smartOptimization: false,
  behaviorAdjustment: true,
  waterQualityAdjustment: true,

  // Alert settings
  alertsEnabled: true,
  missedFeedAlert: true,
  lowFeedAlert: true,
  weatherAlert: true,

  // Computed fields
  nextFeedTime: null,
  status: 'manual',
  feedingLogs: []
};

// Fallback functions for localStorage (when backend unavailable)
export function getFeederState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_FEEDER_STATE };
    const parsed = JSON.parse(raw);
    return { ...DEFAULT_FEEDER_STATE, ...parsed };
  } catch (e) {
    return { ...DEFAULT_FEEDER_STATE };
  }
}

export function saveFeederState(state) {
  const safe = { ...DEFAULT_FEEDER_STATE, ...state };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(safe));
  return safe;
}

// Backend API functions
export async function fetchFeederState() {
  try {
    const response = await authService.apiCall(`${API_BASE}/feeder/`)
    if (response && typeof response.json === 'function') {
      const data = await response.json()
      return data.length > 0 ? normalizeFeederData(data[0]) : DEFAULT_FEEDER_STATE
    }
    return response?.data?.length > 0 ? normalizeFeederData(response.data[0]) : DEFAULT_FEEDER_STATE
  } catch (error) {
    console.error('Failed to fetch feeder state:', error)
    return getFeederState() // fallback
  }
}

export async function fetchMlFeedRecommendation(seasonId = null, opts = {}) {
  const params = new URLSearchParams()
  if (seasonId) params.set('season_id', String(seasonId))
  if (opts.shrimpCount != null && opts.shrimpCount !== '') {
    params.set('shrimp_count', String(opts.shrimpCount))
  }
  if (opts.abwG != null && opts.abwG !== '') {
    params.set('abw_g', String(opts.abwG))
  }
  const q = params.toString() ? `?${params.toString()}` : ''
  const response = await authService.apiCall(`${API_BASE}/feeder/ml_feed_recommendation/${q}`)
  if (response && typeof response.json === 'function') {
    return await response.json()
  }
  return response
}

/** Save ML recommendation as today's feed plan + daily schedule */
export async function applyMlTodayFeed(plan) {
  const response = await authService.apiCall(`${API_BASE}/feeder/apply_ml_today_feed/`, {
    method: 'POST',
    body: JSON.stringify(plan ? { plan } : {}),
  })
  if (response && typeof response.json === 'function') {
    return await response.json()
  }
  return response
}

export async function updateFeederSettings(settings) {
  try {
    const response = await authService.apiCall(`${API_BASE}/feeder/update_settings/`, {
      method: 'POST',
      body: JSON.stringify(settings)
    })
    if (response && typeof response.json === 'function') {
      return normalizeFeederData(await response.json())
    }
    return normalizeFeederData(response?.data || {})
  } catch (error) {
    console.error('Failed to update feeder settings:', error)
    // Update localStorage as fallback
    const current = getFeederState()
    const updated = { ...current, ...settings }
    saveFeederState(updated)
    return updated
  }
}

export async function toggleAutoFeeding(enabled) {
  try {
    const response = await authService.apiCall(`${API_BASE}/feeder/toggle_auto/`, {
      method: 'POST',
      body: JSON.stringify({ enabled })
    })
    if (response && typeof response.json === 'function') {
      return normalizeFeederData(await response.json())
    }
    return normalizeFeederData(response?.data || {})
  } catch (error) {
    console.error('Failed to toggle auto feeding:', error)
    // Update localStorage as fallback
    const current = getFeederState()
    const updated = toggleAuto(current, enabled)
    saveFeederState(updated)
    return updated
  }
}

export async function logDummyFeed(portionGrams, seconds) {
  const response = await authService.apiCall(`${API_BASE}/feeder/dummy_feed/`, {
    method: 'POST',
    body: JSON.stringify({ portion_grams: portionGrams, seconds }),
  })
  if (response && typeof response.json === 'function') {
    const data = await response.json()
    if (!response.ok) throw new Error(data?.error || 'Could not save feeding history')
    return normalizeFeederData(data)
  }
  return normalizeFeederData(response?.data || {})
}

export async function feedOnce() {
  try {
    const response = await authService.apiCall(`${API_BASE}/feeder/feed_once/`, {
      method: 'POST'
    })
    if (response && typeof response.json === 'function') {
      return normalizeFeederData(await response.json())
    }
    return normalizeFeederData(response?.data || {})
  } catch (error) {
    console.error('Failed to feed once:', error)
    // Update localStorage as fallback
    const current = getFeederState()
    const updated = feedOnceLocal(current)
    saveFeederState(updated)
    return updated
  }
}

export async function refillFeeder() {
  try {
    const response = await authService.apiCall(`${API_BASE}/feeder/refill/`, {
      method: 'POST'
    })
    if (response && typeof response.json === 'function') {
      return normalizeFeederData(await response.json())
    }
    return normalizeFeederData(response?.data || {})
  } catch (error) {
    console.error('Failed to refill feeder:', error)
    // Update localStorage as fallback
    const current = getFeederState()
    const updated = refill(current)
    saveFeederState(updated)
    return updated
  }
}

export async function processAutoFeedTick() {
  try {
    const response = await authService.apiCall(`${API_BASE}/feeder/process_auto_feed/`)
    if (response && typeof response.json === 'function') {
      return normalizeFeederData(await response.json())
    }
    return normalizeFeederData(response?.data || {})
  } catch (error) {
    console.error('Failed to process auto feed:', error)
    // Process locally as fallback
    const current = getFeederState()
    const updated = processAutoFeedTickLocal(current)
    saveFeederState(updated)
    return updated
  }
}

export async function fetchFeedingHistory(limit = 50) {
  try {
    const response = await authService.apiCall(`${API_BASE}/feeder/feeding_history/?limit=${limit}`)
    if (response && typeof response.json === 'function') {
      const data = await response.json()
      const logs = data.logs || []
      logs.total = Number.isFinite(data.total) ? data.total : logs.length
      return logs
    }
    const logs = response?.data?.logs || []
    logs.total = Number.isFinite(response?.data?.total) ? response.data.total : logs.length
    return logs
  } catch (error) {
    console.error('Failed to fetch feeding history:', error)
    return []
  }
}

export async function fetchSmartRecommendations() {
  try {
    const response = await authService.apiCall(`${API_BASE}/feeder/smart_recommendations/`)
    if (response && typeof response.json === 'function') {
      const data = await response.json()
      return data.recommendations || []
    }
    return response?.data?.recommendations || []
  } catch (error) {
    console.error('Failed to fetch smart recommendations:', error)
    return []
  }
}

// Utility function to normalize backend data to frontend format
function normalizeFeederData(data) {
  if (!data) return DEFAULT_FEEDER_STATE

  return {
    // Basic settings
    autoEnabled: data.auto_enabled !== false,
    intervalMinutes: data.interval_minutes || 60,
    portionGrams: data.portion_grams || 50,
    capacityMax: data.capacity_max || 1000,
    capacityCurrent: data.capacity_current || 1000,
    lowPercent: data.low_percent || 15,
    nextFeedAt: data.next_feed_at,
    lastFedAt: data.last_fed_at,
    id: data.id,

    // Advanced scheduling
    scheduleType: data.schedule_type || 'interval',
    dailySchedule: (data.daily_schedule || []).filter(time => time && time.trim()), // Filter out empty strings

    // Weather adaptation
    weatherAdaptation: data.weather_adaptation || false,
    rainReductionPercent: data.rain_reduction_percent || 20,
    heatIncreasePercent: data.heat_increase_percent || 10,
    extremeWeatherPause: data.extreme_weather_pause !== false,
    todayFeedPlan: data.today_feed_plan || null,

    // Smart optimization
    smartOptimization: data.smart_optimization || false,
    behaviorAdjustment: data.behavior_adjustment !== false,
    waterQualityAdjustment: data.water_quality_adjustment !== false,

    // Alert settings
    alertsEnabled: data.alerts_enabled !== false,
    missedFeedAlert: data.missed_feed_alert !== false,
    lowFeedAlert: data.low_feed_alert !== false,
    weatherAlert: data.weather_alert !== false,

    // Computed fields
    nextFeedTime: data.next_feed_time,
    status: data.status || 'manual',
    feedingLogs: data.feeding_logs || []
  }
}

// Local fallback functions (keep existing logic)
export function capacityPercent(state) {
  const max = Math.max(1, state.capacityMax || state.capacity_max);
  const current = state.capacityCurrent || state.capacity_current;
  return Math.max(0, Math.min(100, Math.round((current / max) * 100)));
}

/** Ultrasonic hopper map: 20 cm = full, 32 cm = 10% (low-feed alert). */
export const HOPPER_FULL_CM = 20
export const HOPPER_TEN_PERCENT_CM = 32
export const FEEDER_TELEMETRY_STALE_MS = 20_000

export function hopperPercentFromDistance(distanceCm) {
  const d = Number(distanceCm)
  if (!Number.isFinite(d)) return null
  const span = HOPPER_TEN_PERCENT_CM - HOPPER_FULL_CM
  const pct = 100 + ((d - HOPPER_FULL_CM) * (10 - 100)) / span
  return Math.max(0, Math.min(100, Math.round(pct)))
}

export function isFeederTelemetryFresh(timestamp, now = Date.now()) {
  if (!timestamp) return false
  const age = now - new Date(timestamp).getTime()
  return Number.isFinite(age) && age >= 0 && age <= FEEDER_TELEMETRY_STALE_MS
}

export function scheduleNext(state, fromTs = Date.now()) {
  const ms = Math.max(1, Number(state.intervalMinutes || state.interval_minutes)) * 60 * 1000;
  return { ...state, nextFeedAt: fromTs + ms };
}

export function toggleAuto(state, enabled) {
  const now = Date.now();
  const updated = { ...state, autoEnabled: !!enabled };
  if (enabled) {
    if (!updated.nextFeedAt && !updated.next_feed_at) {
      return scheduleNext(updated, now);
    }
  } else {
    updated.nextFeedAt = null;
    updated.next_feed_at = null;
  }
  return updated;
}

export function feedOnceLocal(state) {
  const portion = Math.max(0, Number(state.portionGrams || state.portion_grams));
  if (portion <= 0) return state;
  const current = Math.max(0, Number(state.capacityCurrent || state.capacity_current));
  const newCurrent = Math.max(0, current - portion);
  const now = Date.now();
  const updated = { ...state, capacityCurrent: newCurrent, lastFedAt: now };
  return (state.autoEnabled !== false) ? scheduleNext(updated, now) : updated;
}

export function refill(state, amount) {
  const max = Math.max(1, Number(state.capacityMax || state.capacity_max));
  const to = typeof amount === 'number' ? Math.max(0, Math.min(max, amount)) : max;
  return { ...state, capacityCurrent: to };
}

export function updateSettings(state, settings) {
  let updated = { ...state };
  if (settings.intervalMinutes != null) updated.intervalMinutes = Math.max(1, Number(settings.intervalMinutes));
  if (settings.portionGrams != null) updated.portionGrams = Math.max(0, Number(settings.portionGrams));
  if (settings.capacityMax != null) {
    const newMax = Math.max(1, Number(settings.capacityMax));
    updated.capacityMax = newMax;
    updated.capacityCurrent = Math.min(updated.capacityCurrent || updated.capacity_current, newMax);
  }
  if (settings.lowPercent != null) updated.lowPercent = Math.max(1, Math.min(99, Number(settings.lowPercent)));
  if (updated.autoEnabled && !updated.nextFeedAt) {
    updated = scheduleNext(updated);
  }
  return updated;
}

export function processAutoFeedTickLocal(state, now = Date.now()) {
  if (!state.autoEnabled && state.autoEnabled !== undefined) return state;
  const nextFeed = state.nextFeedAt || state.next_feed_at;
  if (!nextFeed) return state;
  if (now >= nextFeed) {
    return feedOnceLocal(state);
  }
  return state;
}
