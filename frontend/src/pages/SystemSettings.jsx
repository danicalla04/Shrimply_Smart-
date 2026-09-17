import { useState, useEffect } from 'react'
import { getThresholds, saveThresholds, fetchThresholds, updateThresholdsOnServer, DEFAULT_THRESHOLDS, clearThresholdCache } from '../services/settings'
import { fetchCalibration, updateCalibrationOnServer, DEFAULT_CALIBRATION, applyCalibration } from '../services/calibration'
import { fetchHistorySettings, updateHistorySettings } from '../services/historySettings'
import { useLanguage } from '../context/LanguageContext'

const CYCLE_PRESETS = [90, 120, 150]

const SystemSettings = () => {
  const { t } = useLanguage()
  const [thresholds, setThresholds] = useState({})
  const [loading, setLoading] = useState(true)
  const [dirty, setDirty] = useState(false)
  const [saved, setSaved] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  // Harvest cycle state
  const [harvestDays, setHarvestDays] = useState(90)
  const [harvestTime, setHarvestTime] = useState('09:30')
  const [notifEmail, setNotifEmail] = useState('')
  const [daysBeforeNotif, setDaysBeforeNotif] = useState(2)
  const [harvestDirty, setHarvestDirty] = useState(false)
  const [harvestSaved, setHarvestSaved] = useState(false)
  const [harvestSaving, setHarvestSaving] = useState(false)

  const [calibration, setCalibration] = useState({})
  const [calDirty, setCalDirty] = useState(false)
  const [calSaved, setCalSaved] = useState(false)
  const [calSaving, setCalSaving] = useState(false)

  useEffect(() => {
    const loadAll = async () => {
      try {
        // Always fetch fresh from API for current values
        const [threshData, calData] = await Promise.all([
          fetchThresholds(),
          fetchCalibration(),
        ])
        const histData = await fetchHistorySettings().catch(() => null)

        console.log('[SETTINGS] Fresh thresholds loaded:', threshData)
        setThresholds(threshData)
        setCalibration(calData)

        if (histData) {
          const h = Array.isArray(histData) ? histData[0] : histData
          if (h) {
            setHarvestDays(h.harvest_lead_days ?? 90)
            setHarvestTime(h.harvest_time ? h.harvest_time.slice(0, 5) : '09:30')
            setNotifEmail(h.notification_email ?? '')
            setDaysBeforeNotif(h.days_before_notification ?? 2)
          }
        }
      } catch (error) {
        console.error('Failed to fetch settings:', error)
        setThresholds(getThresholds())
      } finally {
        setLoading(false)
      }
    }
    loadAll()
  }, [])

  useEffect(() => {
    if (dirty) setSaved(false)
  }, [thresholds, dirty])

  const handleChange = (sensor, field, value) => {
    setThresholds(prev => ({
      ...prev,
      [sensor]: { ...prev[sensor], [field]: value === '' ? '' : Number(value) }
    }))
    setDirty(true)
  }

  const handleUseDefault = (sensor) => {
    const def = DEFAULT_THRESHOLDS[sensor]
    if (!def) return
    setThresholds(prev => ({
      ...prev,
      [sensor]: {
        ...prev[sensor],
        min: def.min,
        max: def.max,
        unit: def.unit,
        step: def.step,
      }
    }))
    setDirty(true)
  }

  const handleRefreshThresholds = async () => {
    setRefreshing(true)
    try {
      clearThresholdCache()
      const freshData = await fetchThresholds()
      setThresholds(freshData)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (error) {
      alert('Failed to refresh thresholds: ' + error.message)
    } finally {
      setRefreshing(false)
    }
  }

  const handleReset = () => {
    setThresholds(JSON.parse(JSON.stringify(DEFAULT_THRESHOLDS)))
    setDirty(true)
  }

  const handleCalChange = (sensor, field, value) => {
    setCalibration(prev => ({
      ...prev,
      [sensor]: { ...prev[sensor], [field]: value === '' ? '' : Number(value) },
    }))
    setCalDirty(true)
  }

  const handleCalDefault = (sensor) => {
    const def = DEFAULT_CALIBRATION[sensor]
    if (!def) return
    setCalibration(prev => ({
      ...prev,
      [sensor]: { ...prev[sensor], scale: def.scale, offset: def.offset },
    }))
    setCalDirty(true)
  }

  const handleCalResetAll = () => {
    setCalibration(JSON.parse(JSON.stringify(DEFAULT_CALIBRATION)))
    setCalDirty(true)
  }

  const saveCalibration = async () => {
    setCalSaving(true)
    try {
      for (const [k, r] of Object.entries(calibration)) {
        if (r.scale === '' || r.offset === '' || isNaN(r.scale) || isNaN(r.offset)) {
          alert(`Incomplete calibration for ${k}`)
          return
        }
      }
      const updated = await updateCalibrationOnServer(calibration)
      setCalibration(updated)
      setCalDirty(false)
      setCalSaved(true)
      setTimeout(() => setCalSaved(false), 3000)
    } catch (error) {
      alert('Failed to save calibration: ' + error.message)
    } finally {
      setCalSaving(false)
    }
  }

  const saveHarvestSettings = async () => {
    setHarvestSaving(true)
    try {
      await updateHistorySettings({
        harvest_lead_days: harvestDays,
        harvest_time: harvestTime + ':00',
        notification_email: notifEmail,
        days_before_notification: daysBeforeNotif,
      })
      setHarvestDirty(false)
      setHarvestSaved(true)
      setTimeout(() => setHarvestSaved(false), 3000)
    } catch (e) {
      alert('Failed to save harvest settings: ' + e.message)
    } finally {
      setHarvestSaving(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    console.log('[SETTINGS] handleSubmit called with thresholds:', thresholds)
    
    // Validate: min < max and non-empty
    for (const [k, r] of Object.entries(thresholds)) {
      if (r.min === '' || r.max === '' || isNaN(r.min) || isNaN(r.max)) {
        alert(`Incomplete range for ${k}`)
        console.warn('[SETTINGS] Incomplete range for:', k, r)
        return
      }
      if (r.min >= r.max) {
        alert(`Min must be less than max for ${k}`)
        console.warn('[SETTINGS] Invalid range for:', k, r)
        return
      }
    }
    
    try {
      console.log('[SETTINGS] Sending thresholds to server...')
      const updated = await updateThresholdsOnServer(thresholds)
      console.log('[SETTINGS] Server response:', updated)
      setThresholds(updated)
      setDirty(false)
      setSaved(true)
      console.log('[SETTINGS] ✓ Thresholds saved successfully')
      setTimeout(() => setSaved(false), 3000)
    } catch (error) {
      console.error('[SETTINGS] ❌ Failed to save thresholds:', error)
      alert('Failed to save thresholds: ' + error.message)
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">{t('systemSettingsTitle')}</h1>
      <p className="text-gray-600 mb-6">{t('settingsSubtitle')}</p>

      {/* ── Quick Actions ───────────────────────────────────── */}
      <div className="mb-8 flex gap-3">
        <button
          type="button"
          onClick={handleRefreshThresholds}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 bg-blue-50 text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm"
          title="Refresh thresholds from database"
        >
          <span className={refreshing ? 'animate-spin' : ''}>🔄</span>
          {refreshing ? 'Refreshing...' : 'Refresh Thresholds from Database'}
        </button>
      </div>

      {/* ── Harvest Cycle Length ───────────────────────────────────── */}
      <div className="card p-5 mb-8">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">Harvest Cycle Length</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">Days from season start</label>
            <input
              type="number"
              min="1"
              value={harvestDays}
              onChange={e => { setHarvestDays(Number(e.target.value)); setHarvestDirty(true) }}
              className="w-full rounded border-gray-300 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">Preferred harvest time</label>
            <input
              type="time"
              value={harvestTime}
              onChange={e => { setHarvestTime(e.target.value); setHarvestDirty(true) }}
              className="w-full rounded border-gray-300 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">Notification email (optional)</label>
            <input
              type="email"
              placeholder="you@example.com"
              value={notifEmail}
              onChange={e => { setNotifEmail(e.target.value); setHarvestDirty(true) }}
              className="w-full rounded border-gray-300 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end mt-4">
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">Days before notification</label>
            <input
              type="number"
              min="0"
              value={daysBeforeNotif}
              onChange={e => { setDaysBeforeNotif(Number(e.target.value)); setHarvestDirty(true) }}
              className="w-full rounded border-gray-300 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
          <div className="flex space-x-3">
            {CYCLE_PRESETS.map(d => (
              <button
                key={d}
                type="button"
                onClick={() => { setHarvestDays(d); setHarvestDirty(true) }}
                className={`px-4 py-2 rounded border text-sm font-medium transition
                  ${harvestDays === d
                    ? 'bg-primary-500 text-white border-primary-500'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}`}
              >{d}d</button>
            ))}
          </div>
        </div>
        <p className="text-sm text-gray-500 mt-3">
          Used for harvest reminders and <strong>every</strong> new alert (temperature, pH, TDS, turbidity,
          sensors offline, feeder). Save an email here to receive alert notifications.
        </p>
        {harvestDirty && (
          <div className="flex items-center gap-3 mt-4">
            <button
              type="button"
              onClick={saveHarvestSettings}
              disabled={harvestSaving}
              className="btn-primary px-6 py-2"
            >{harvestSaving ? 'Saving...' : 'Save Harvest Settings'}</button>
          </div>
        )}
        {harvestSaved && (
          <p className="text-green-600 font-medium mt-3">Saved!</p>
        )}
      </div>

      {/* ── Sensor Data Adjustment (replaces Arduino calibration constants) ── */}
      <div className="card p-5 mb-8 border-2 border-cyan-100">
        <h2 className="text-xl font-semibold text-gray-800 mb-2">Sensor Data Adjustment</h2>
        <p className="text-sm text-gray-600 mb-4">
          Change how raw sensor values appear on the dashboard — no Arduino re-upload needed.
          Formula: <span className="font-mono bg-slate-100 px-1 rounded">display = (raw × scale) + offset</span>
          <br />
          Example: pH reads <strong>1.3</strong> but should show <strong>7.3</strong> → set offset <strong>+6.0</strong>, scale <strong>1</strong>.
        </p>
        {!loading && Object.entries(calibration).map(([key, cal]) => (
          <div key={`cal-${key}`} className="mb-6 pb-6 border-b border-slate-100 last:border-0 last:mb-0 last:pb-0">
            <h3 className="text-lg font-medium text-gray-800 mb-3 capitalize">
              {key === 'ph' ? 'pH' : key} adjustment
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Scale (multiply)</label>
                <input
                  type="number"
                  step="any"
                  value={cal.scale}
                  onChange={e => handleCalChange(key, 'scale', e.target.value)}
                  className="w-full rounded border-gray-300 focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Offset (add)</label>
                <input
                  type="number"
                  step="any"
                  value={cal.offset}
                  onChange={e => handleCalChange(key, 'offset', e.target.value)}
                  className="w-full rounded border-gray-300 focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
              <div>
                <button
                  type="button"
                  onClick={() => handleCalDefault(key)}
                  className="btn-secondary w-full"
                >Reset to 1 / 0</button>
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Preview: raw 10 → {applyCalibration(10, cal.scale, cal.offset)?.toFixed?.(2) ?? applyCalibration(10, cal.scale, cal.offset)} {cal.unit}
            </p>
          </div>
        ))}
        <div className="flex items-center gap-3 mt-4">
          <button
            type="button"
            onClick={saveCalibration}
            disabled={!calDirty || calSaving}
            className="btn-primary px-6 py-2 disabled:opacity-50"
          >{calSaving ? 'Saving...' : 'Save Data Adjustment'}</button>
          <button type="button" onClick={handleCalResetAll} className="btn-secondary px-6 py-2">
            Reset All Adjustments
          </button>
          {calSaved && <span className="text-green-600 font-medium">Saved!</span>}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8">
        <h2 className="text-2xl font-bold text-gray-900 -mb-4">Normal Ranges (Alerts)</h2>
        <p className="text-sm text-gray-600 mb-2">Min/max for dashboard &quot;Above max&quot; / &quot;Below min&quot; — not the same as data adjustment above.</p>
        {Object.entries(thresholds).map(([key, range]) => (
          <div key={key} className="card p-5">
            <h2 className="text-xl font-semibold text-gray-800 mb-4 capitalize">{key === 'ph' ? t('phLevelRange') : key === 'turbidity' ? t('turbidityRange') : key === 'tds' ? t('tdsRange') : t('temperatureRange')}</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">{t('minimum')} ({range.unit})</label>
                <input
                  type="number"
                  step="any"
                  value={range.min}
                  onChange={e => handleChange(key, 'min', e.target.value)}
                  className="w-full rounded border-gray-300 focus:ring-primary-500 focus:border-primary-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">{t('maximum')} ({range.unit})</label>
                <input
                  type="number"
                  step="any"
                  value={range.max}
                  onChange={e => handleChange(key, 'max', e.target.value)}
                  className="w-full rounded border-gray-300 focus:ring-primary-500 focus:border-primary-500"
                  required
                />
              </div>
              <div className="flex space-x-3 mt-2 md:mt-0">
                <button
                  type="button"
                  onClick={() => handleUseDefault(key)}
                  className="btn-secondary flex-1"
                >{t('useDefault')}</button>
              </div>
            </div>
            <p className="text-sm text-gray-500 mt-3">{t('currentRange')}: <span className="font-medium">{range.min} – {range.max} {range.unit}</span></p>
          </div>
        ))}

        <div className="flex items-center space-x-4">
          <button
            type="submit"
            className="btn-primary px-6 py-3"
            disabled={!dirty}
          >{t('saveRanges')}</button>
          <button
            type="button"
            onClick={handleReset}
            className="btn-secondary px-6 py-3"
          >{t('resetAllToDefaults')}</button>
          {saved && (
            <span className="text-green-600 font-medium">{t('savedSuccess')}</span>
          )}
        </div>
      </form>
    </div>
  )
}

export default SystemSettings
