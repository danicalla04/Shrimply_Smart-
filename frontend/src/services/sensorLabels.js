import { DEFAULT_THRESHOLDS } from './sensorDefaults.js'

const VERDICT_KEY = {
  good: 'verdictGood',
  caution: 'verdictCaution',
  bad: 'verdictPoor',
  neutral: 'verdictUnknown',
}

export function classifySensor(param, value, thresholds = DEFAULT_THRESHOLDS) {
  if (value === null || value === undefined || value === '' || (typeof value === 'string' && !value.trim())) {
    return { labelKey: 'labelUnknown', hintKey: 'hintUnknown', tone: 'neutral', verdictKey: 'verdictUnknown' }
  }
  const n = Number(value)
  if (!Number.isFinite(n)) {
    return {
      labelKey: 'labelUnknown',
      hintKey: 'hintUnknown',
      tone: 'neutral',
      verdictKey: 'verdictUnknown',
    }
  }
  const range = thresholds?.[param]
  const fallback = DEFAULT_THRESHOLDS[param]
  const min = Number(range?.min ?? fallback?.min)
  const max = Number(range?.max ?? fallback?.max)
  if (!Number.isFinite(min) || !Number.isFinite(max) || min >= max) {
    return {
      labelKey: 'labelUnknown',
      hintKey: 'hintUnknown',
      tone: 'neutral',
      verdictKey: 'verdictUnknown',
    }
  }
  const band = n < min
    ? { labelKey: 'labelBelowRange', hintKey: 'hintBelowRange', tone: 'bad' }
    : n > max
      ? { labelKey: 'labelAboveRange', hintKey: 'hintAboveRange', tone: 'bad' }
      : { labelKey: 'labelInRange', hintKey: 'hintInRange', tone: 'good' }
  return { ...band, verdictKey: VERDICT_KEY[band.tone] }
}

export const SENSOR_NAME_KEY = {
  temperature: 'temperature',
  ph: 'phLevel',
  turbidity: 'turbidity',
  tds: 'tdsEc',
}

/**
 * Overall pond status from how many of the 4 sensors are in the good band.
 * 4 good, 3 moderate, 2 poor, 1 bad, 0 critical, none readable = N/A offline.
 */
export const OVERALL_STATUS = {
  good: { level: 'normal', title: 'WATER QUALITY GOOD', summary: 'All 4 sensors are in range.' },
  moderate: { level: 'moderate', title: 'WATER QUALITY MODERATE', summary: '3 of 4 sensors are in range.' },
  poor: { level: 'poor', title: 'WATER QUALITY POOR', summary: '2 of 4 sensors are in range.' },
  bad: { level: 'bad', title: 'WATER QUALITY BAD', summary: '1 of 4 sensors is in range.' },
  critical: { level: 'critical', title: 'WATER QUALITY CRITICAL', summary: '0 of 4 sensors are in range.' },
  neutral: { level: 'offline', title: 'N/A OFFLINE', summary: 'Sensor readings are unavailable.' },
}

export function summarizeOverallQuality(values = {}, thresholds = DEFAULT_THRESHOLDS) {
  const keys = ['temperature', 'ph', 'turbidity', 'tds']
  const rows = keys.map((key) => ({
    key,
    nameKey: SENSOR_NAME_KEY[key],
    ...classifySensor(key, values[key], thresholds),
  }))
  const known = rows.filter((row) => row.tone !== 'neutral')
  const inRange = rows.filter((row) => row.tone === 'good')
  const poor = rows.filter((row) => row.tone === 'bad' || row.tone === 'caution')
  const goodCount = inRange.length
  let tone = 'neutral'
  if (known.length === 0) tone = 'neutral'
  else if (goodCount >= 4) tone = 'good'
  else if (goodCount === 3) tone = 'moderate'
  else if (goodCount === 2) tone = 'poor'
  else if (goodCount === 1) tone = 'bad'
  else tone = 'critical'
  const meta = OVERALL_STATUS[tone] || OVERALL_STATUS.neutral
  return {
    tone,
    status: meta.level,
    title: meta.title,
    summary: meta.summary,
    goodCount,
    rows,
    poor,
    known,
    inRange,
  }
}

export const TONE_BADGE_CLASS = {
  good: 'bg-blue-100 text-blue-800 border-blue-200',
  caution: 'bg-red-50 text-red-800 border-red-200',
  bad: 'bg-red-100 text-red-800 border-red-200',
  neutral: 'bg-slate-100 text-slate-700 border-slate-200',
}

export const TONE_TEXT_CLASS = {
  good: 'text-green-700',
  caution: 'text-amber-800',
  bad: 'text-red-700',
  neutral: 'text-slate-600',
}
