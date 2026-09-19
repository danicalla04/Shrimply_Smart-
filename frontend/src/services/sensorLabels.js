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

export const TONE_BADGE_CLASS = {
  good: 'bg-green-100 text-green-800 border-green-200',
  caution: 'bg-amber-100 text-amber-900 border-amber-200',
  bad: 'bg-red-100 text-red-800 border-red-200',
  neutral: 'bg-slate-100 text-slate-600 border-slate-200',
}

export const TONE_TEXT_CLASS = {
  good: 'text-green-700',
  caution: 'text-amber-800',
  bad: 'text-red-700',
  neutral: 'text-slate-600',
}
