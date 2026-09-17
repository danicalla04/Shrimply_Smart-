import { authService } from './auth'
import API_BASE from './apiConfig'

export const DEFAULT_CALIBRATION = Object.freeze({
  temperature: { scale: 1, offset: 0, unit: '°C' },
  ph: { scale: 1, offset: 0, unit: '' },
  turbidity: { scale: 1, offset: 0, unit: 'NTU' },
  tds: { scale: 1, offset: 0, unit: 'ppm' },
})

export function getDefaultCalibration() {
  return JSON.parse(JSON.stringify(DEFAULT_CALIBRATION))
}

/** adjusted = (raw * scale) + offset */
export function applyCalibration(raw, scale = 1, offset = 0) {
  if (raw === null || raw === undefined || raw === '') return null
  return Number(raw) * Number(scale) + Number(offset)
}

export async function fetchCalibration() {
  try {
    const response = await authService.apiCall(`${API_BASE}/calibration/all/`)
    if (!response.ok) throw new Error(`Server returned ${response.status}`)
    const data = await response.json()
    const merged = getDefaultCalibration()
    for (const key of Object.keys(merged)) {
      if (data[key]) merged[key] = { ...merged[key], ...data[key] }
    }
    return merged
  } catch (error) {
    console.error('[CALIBRATION] fetch failed:', error)
    return getDefaultCalibration()
  }
}

export async function updateCalibrationOnServer(calibration) {
  const response = await authService.apiCall(`${API_BASE}/calibration/update_all/`, {
    method: 'POST',
    body: JSON.stringify(calibration),
  })
  const data = await response.json()
  if (!response.ok) throw new Error(data.error || `Server error ${response.status}`)
  const merged = getDefaultCalibration()
  for (const key of Object.keys(merged)) {
    if (data[key]) merged[key] = { ...merged[key], ...data[key] }
  }
  return merged
}
