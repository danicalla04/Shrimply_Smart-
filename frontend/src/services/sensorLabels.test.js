import test from 'node:test'
import assert from 'node:assert/strict'
import { classifySensor, summarizeOverallQuality } from './sensorLabels.js'

const ranges = {
  temperature: { min: 25, max: 30 },
  ph: { min: 6.5, max: 8.5 },
  turbidity: { min: 1, max: 25 },
  tds: { min: 20, max: 325 },
}

test('every sensor uses its Settings range, including both boundaries', () => {
  for (const [key, range] of Object.entries(ranges)) {
    assert.equal(classifySensor(key, range.min, ranges).tone, 'good', key)
    assert.equal(classifySensor(key, range.max, ranges).tone, 'good', key)
    assert.equal(classifySensor(key, range.min - 0.1, ranges).labelKey, 'labelBelowRange', key)
    assert.equal(classifySensor(key, range.max + 0.1, ranges).labelKey, 'labelAboveRange', key)
  }
  assert.equal(classifySensor('ph', 7.2, ranges).tone, 'good')
})

test('changing Settings changes both the sensor label and overall status', () => {
  const values = { temperature: 26, ph: 7.2, turbidity: 2, tds: 25 }
  assert.equal(summarizeOverallQuality(values, ranges).status, 'normal')
  const changed = { ...ranges, ph: { min: 7.5, max: 8.5 } }
  assert.equal(classifySensor('ph', 7.2, changed).labelKey, 'labelBelowRange')
  assert.equal(summarizeOverallQuality(values, changed).goodCount, 3)
  assert.equal(classifySensor('ph', null, ranges).tone, 'neutral')
})
