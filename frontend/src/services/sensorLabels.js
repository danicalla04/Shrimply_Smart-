/**
 * Card labels from the project’s water-quality table:
 * Low/Poor | Normal/Good | High/Poor
 */
function band(min, max, labelKey, hintKey, tone) {
  return { min, max, labelKey, hintKey, tone }
}

export const SENSOR_LABEL_BANDS = {
  temperature: [
    band(-Infinity, 25.999, 'labelTempCold', 'hintTempCold', 'bad'),
    band(26, 32, 'labelTempSuitable', 'hintTempSuitable', 'good'),
    band(32.001, Infinity, 'labelTempHot', 'hintTempHot', 'bad'),
  ],
  ph: [
    band(-Infinity, 6.999, 'labelPhAcidic', 'hintPhAcidic', 'bad'),
    band(7, 7, 'labelPhNeutral', 'hintPhNeutral', 'good'),
    band(7.001, Infinity, 'labelPhAlkaline', 'hintPhAlkaline', 'bad'),
  ],
  turbidity: [
    band(-Infinity, 4.999, 'labelTurbClear', 'hintTurbClear', 'bad'),
    band(5, 25, 'labelTurbModerate', 'hintTurbModerate', 'good'),
    band(25.001, Infinity, 'labelTurbCloudy', 'hintTurbCloudy', 'bad'),
  ],
  tds: [
    band(-Infinity, 99.999, 'labelTdsLow', 'hintTdsLow', 'bad'),
    band(100, 500, 'labelTdsModerate', 'hintTdsModerate', 'good'),
    band(500.001, Infinity, 'labelTdsHigh', 'hintTdsHigh', 'bad'),
  ],
}

export const SENSOR_GUIDE_KEY = {
  temperature: 'sensorLabelGuideTemp',
  ph: 'sensorLabelGuidePh',
  turbidity: 'sensorLabelGuideTurb',
  tds: 'sensorLabelGuideTds',
}

const VERDICT_KEY = {
  good: 'verdictGood',
  caution: 'verdictCaution',
  bad: 'verdictPoor',
  neutral: 'verdictUnknown',
}

export function classifySensor(param, value) {
  const n = Number(value)
  if (!Number.isFinite(n)) {
    return {
      labelKey: 'labelUnknown',
      hintKey: 'hintUnknown',
      tone: 'neutral',
      verdictKey: 'verdictUnknown',
    }
  }
  const bands = SENSOR_LABEL_BANDS[param] || []
  const match = bands.find((b) => n >= b.min && n <= b.max) || bands[bands.length - 1]
  if (!match) {
    return {
      labelKey: 'labelUnknown',
      hintKey: 'hintUnknown',
      tone: 'neutral',
      verdictKey: 'verdictUnknown',
    }
  }
  return {
    labelKey: match.labelKey,
    hintKey: match.hintKey,
    tone: match.tone,
    verdictKey: VERDICT_KEY[match.tone] || 'verdictUnknown',
  }
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

export function summarizeOverallQuality(values = {}) {
  const keys = ['temperature', 'ph', 'turbidity', 'tds']
  const rows = keys.map((key) => ({
    key,
    nameKey: SENSOR_NAME_KEY[key],
    ...classifySensor(key, values[key]),
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
