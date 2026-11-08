// Fallback ranges when Settings has no saved value for a sensor.
export const DEFAULT_THRESHOLDS = Object.freeze({
  temperature: { min: 25, max: 30, unit: '°C', step: 0.1 },
  ph: { min: 6.5, max: 8.5, unit: '', step: 0.1 },
  turbidity: { min: 1, max: 25, unit: 'NTU', step: 0.1 },
  tds: { min: 20, max: 325, unit: 'ppm', step: 5 },
})
