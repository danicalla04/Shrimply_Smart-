import { useState, useEffect } from 'react'
import { getThresholds, fetchThresholds } from '../services/settings'
import { fetchLatestSensors, getSensorReadings, isSensorDisconnected, normalizeSensorValue } from '../services/sensors'
import { getWaterQualityStatus } from '../services/waterQuality'
import { controlBuzzer, playBeeperSound } from '../services/buzzer'
import { fetchActiveAlerts } from '../services/alerts'
import { useNavigate } from 'react-router-dom'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import MetricCard from '../components/MetricCard'
import { useLanguage } from '../context/LanguageContext'
import { getChannelsWebSocketUrl } from '../services/apiConfig'

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const Dashboard = () => {
  const { t } = useLanguage()
  // Core metric states (read from sensors)
  const [temperature, setTemperature] = useState(null)
  const [phLevel, setPhLevel] = useState(null)
  const [turbidity, setTurbidity] = useState(null)
  const [tds, setTds] = useState(null)
  const [lastSensorTimestamp, setLastSensorTimestamp] = useState(null)
  const [nowTs, setNowTs] = useState(() => Date.now())
  const [thresholds, setThresholds] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [waterQuality, setWaterQuality] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  // Buzzer states
  const [buzzerOn, setBuzzerOn] = useState(false)
  const [activeAlerts, setActiveAlerts] = useState([])
  const [buzzerToggling, setBuzzerToggling] = useState(false)

  const navigate = useNavigate()

  const applySensorPayload = (sensorsData) => {
    setTemperature(normalizeSensorValue('temperature', sensorsData.temperature))
    setPhLevel(normalizeSensorValue('ph', sensorsData.ph))
    setTurbidity(normalizeSensorValue('turbidity', sensorsData.turbidity))
    setTds(normalizeSensorValue('tds', sensorsData.tds))
    setLastSensorTimestamp(sensorsData.timestamp || null)
  }

  const reloadChartHistory = async () => {
    try {
      const resp = await getSensorReadings(1, 1, 50)
      const readings = resp.results || []
      if (readings.length === 0) return
      const sorted = [...readings].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
      const labels = sorted.map(r => {
        const d = new Date(r.timestamp)
        return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
      })
      const temps = sorted.map(r => r.temperature)
      const phs = sorted.map(r => r.ph)
      const turbidities = sorted.map(r => r.turbidity)
      const tdss = sorted.map(r => r.tds)
      setChartData(prev => ({
        temperature: {
          ...prev.temperature,
          labels: labels.slice(-20),
          datasets: [{ ...prev.temperature.datasets[0], data: temps.slice(-20) }],
        },
        ph: {
          ...prev.ph,
          labels: labels.slice(-20),
          datasets: [{ ...prev.ph.datasets[0], data: phs.slice(-20) }],
        },
        turbidity: {
          ...prev.turbidity,
          labels: labels.slice(-20),
          datasets: [{ ...prev.turbidity.datasets[0], data: turbidities.slice(-20) }],
        },
        tds: {
          ...prev.tds,
          labels: labels.slice(-20),
          datasets: [{ ...prev.tds.datasets[0], data: tdss.slice(-20) }],
        },
      }))
    } catch (err) {
      console.warn('Failed to load sensor history for charts:', err)
    }
  }

  // Refresh latest sensors + water quality + charts (Dashboard only)
  const refreshDashboardData = async ({ showSpinner = false } = {}) => {
    if (showSpinner) setRefreshing(true)
    try {
      const [sensorsData, thresholdsData, qualityData] = await Promise.all([
        fetchLatestSensors(),
        fetchThresholds(),
        getWaterQualityStatus(),
      ])
      applySensorPayload(sensorsData)
      setThresholds(thresholdsData)
      setWaterQuality(qualityData)
    } catch (error) {
      console.error('Dashboard refresh failed:', error)
    } finally {
      if (showSpinner) setRefreshing(false)
    }
  }

  const handleRefresh = async () => {
    await refreshDashboardData({ showSpinner: true })
  }

  // Auto-refresh full dashboard (WQ banner + thresholds + charts) every 1 minute
  useEffect(() => {
    const id = setInterval(() => {
      refreshDashboardData({ showSpinner: false })
    }, 60_000)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Keep a ticking clock so freshness labels update.
  useEffect(() => {
    const id = setInterval(() => setNowTs(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  // Always poll latest sensors from DB (WeMos→PHP does not push over Django WebSocket).
  // Without this, a connected-but-silent WS freezes lastSensorTimestamp and shows Offline after 30s.
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const sensorsData = await fetchLatestSensors()
        if (cancelled) return
        if (sensorsData.timestamp || sensorsData.temperature != null || sensorsData.tds != null) {
          setTemperature(normalizeSensorValue('temperature', sensorsData.temperature))
          setPhLevel(normalizeSensorValue('ph', sensorsData.ph))
          setTurbidity(normalizeSensorValue('turbidity', sensorsData.turbidity))
          setTds(normalizeSensorValue('tds', sensorsData.tds))
          setLastSensorTimestamp(sensorsData.timestamp || null)
        }
      } catch (e) {
        console.warn('Sensor poll failed:', e)
      }
    }
    poll()
    const id = setInterval(poll, 5_000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  // Manual buzzer toggle handler
  const handleBuzzerToggle = async () => {
    setBuzzerToggling(true)
    try {
      const newState = !buzzerOn
      const response = await controlBuzzer(newState)

      if (!response.error) {
        setBuzzerOn(newState)
        playBeeperSound(200, 1000) // Browser beep feedback
      } else {
        console.error('Failed to control buzzer:', response.error)
      }
    } catch (error) {
      console.error('Buzzer toggle failed:', error)
    } finally {
      setBuzzerToggling(false)
    }
  }

  // Fetch initial data from backend
  useEffect(() => {
    const loadData = async () => {
      try {
        console.log('[DASHBOARD] Loading initial sensor data...')
        // Always fetch fresh from API, don't use cached values
        const thresholdsData = await fetchThresholds()
        const [sensorsData, qualityData] = await Promise.all([
          fetchLatestSensors(),
          getWaterQualityStatus()
        ])

        console.log('[DASHBOARD] Sensor data received:', sensorsData)
        console.log('[DASHBOARD] Fresh thresholds:', thresholdsData)

        setTemperature(normalizeSensorValue('temperature', sensorsData.temperature))
        setPhLevel(normalizeSensorValue('ph', sensorsData.ph))
        setTurbidity(normalizeSensorValue('turbidity', sensorsData.turbidity))
        setTds(normalizeSensorValue('tds', sensorsData.tds))
        setLastSensorTimestamp(sensorsData.timestamp || null)
        setThresholds(thresholdsData)
        setWaterQuality(qualityData)
      } catch (error) {
        console.error('Failed to load data:', error)
        // Fallback to defaults
        setThresholds(getThresholds())
      } finally {
        setLoading(false)
      }
    }
    loadData()

    // WebSocket is optional (live only when Django broadcasts). Polling above is source of truth for PHP uploads.
    let ws = null
    let reconnectTimeout = null
    const WS_URL = getChannelsWebSocketUrl('/ws/sensors/')

    const connectWebSocket = () => {
      try {
        ws = new WebSocket(WS_URL)

        ws.onopen = () => {
          console.log('[WS] Connected to sensor stream (polling still active for PHP uploads)')
        }

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (data.temperature !== undefined) setTemperature(normalizeSensorValue('temperature', data.temperature))
            if (data.ph !== undefined) setPhLevel(normalizeSensorValue('ph', data.ph))
            if (data.turbidity !== undefined) setTurbidity(normalizeSensorValue('turbidity', data.turbidity))
            if (data.tds !== undefined) setTds(normalizeSensorValue('tds', data.tds))
            if (data.timestamp) setLastSensorTimestamp(data.timestamp)
          } catch (err) {
            console.warn('[WS] Failed to parse message:', err)
          }
        }

        ws.onclose = () => {
          console.warn('[WS] Disconnected — will retry in 5s (DB polling continues)')
          reconnectTimeout = setTimeout(connectWebSocket, 5000)
        }

        ws.onerror = (err) => {
          console.warn('[WS] Error:', err)
          ws.close()
        }
      } catch (err) {
        console.warn('[WS] Could not connect — DB polling continues')
        reconnectTimeout = setTimeout(connectWebSocket, 5000)
      }
    }

    connectWebSocket()

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout)
      if (ws) ws.close()
    }
  }, [])

  // Reload thresholds when coming back from settings page
  useEffect(() => {
    const handleFocus = async () => {
      const thresholdsData = await fetchThresholds()
      setThresholds(thresholdsData)
    }
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [])

  // Check for active alerts and control buzzer automatically
  useEffect(() => {
    const checkAlerts = async () => {
      try {
        const alerts = await fetchActiveAlerts()
        const alertList = Array.isArray(alerts) ? alerts : (alerts.results || [])
        setActiveAlerts(alertList)

        // Auto-trigger buzzer if there are active alerts
        if (alertList.length > 0 && !buzzerOn) {
          await controlBuzzer(true)
          setBuzzerOn(true)
          playBeeperSound(200, 1000) // Browser beep as fallback
        }
        // Turn off buzzer if no alerts
        else if (alertList.length === 0 && buzzerOn) {
          await controlBuzzer(false)
          setBuzzerOn(false)
        }
      } catch (error) {
        console.error('Failed to check alerts:', error)
      }
    }

    // Check alerts every 5 seconds
    const alertInterval = setInterval(checkAlerts, 5000)
    checkAlerts() // Check immediately on mount

    return () => clearInterval(alertInterval)
  }, [buzzerOn])

  const [chartData, setChartData] = useState({
    temperature: {
      labels: [],
      datasets: [
        {
          label: 'Temperature (°C)',
          data: [],
          borderColor: 'rgb(239, 68, 68)',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: 'rgb(239, 68, 68)',
        },
      ],
    },
    ph: {
      labels: [],
      datasets: [
        {
          label: 'pH Level',
          data: [],
          borderColor: 'rgb(34, 197, 94)',
          backgroundColor: 'rgba(34, 197, 94, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: 'rgb(34, 197, 94)',
        },
      ],
    },
    turbidity: {
      labels: [],
      datasets: [
        {
          label: 'Turbidity (NTU)',
          data: [],
          borderColor: 'rgb(14, 165, 233)',
          backgroundColor: 'rgba(14, 165, 233, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: 'rgb(14, 165, 233)',
        },
      ],
    },
    tds: {
      labels: [],
      datasets: [
        {
          label: 'TDS/EC (ppm)',
          data: [],
          borderColor: 'rgb(249, 115, 22)',
          backgroundColor: 'rgba(249, 115, 22, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: 'rgb(249, 115, 22)',
        },
      ],
    },
  })

  // Load historical sensor readings to populate chart lines (initial)
  useEffect(() => {
    reloadChartHistory()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Remove random auto updates; temperature changes only via manual controls
  // Persist sensor values whenever they change so other pages (Alerts) can read them
  // Note: Now using backend storage instead of localStorage

  // On first mount, if there is no stored value for TDS, set it to 300
  // (Removed localStorage check since we use backend now)

  // Update chart data for all metrics
  useEffect(() => {
    const now = new Date()
    const timeLabel = now.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    })
    // Only update charts when we have real sensor values
    if (temperature == null && phLevel == null && turbidity == null && tds == null) {
      return
    }

    setChartData(prev => ({
      temperature: temperature != null ? {
        ...prev.temperature,
        labels: [...prev.temperature.labels, timeLabel].slice(-20),
        datasets: [{
          ...prev.temperature.datasets[0],
          data: [...prev.temperature.datasets[0].data, temperature].slice(-20),
        }],
      } : prev.temperature,
      ph: phLevel != null ? {
        ...prev.ph,
        labels: [...prev.ph.labels, timeLabel].slice(-20),
        datasets: [{
          ...prev.ph.datasets[0],
          data: [...prev.ph.datasets[0].data, phLevel].slice(-20),
        }],
      } : prev.ph,
      turbidity: turbidity != null ? {
        ...prev.turbidity,
        labels: [...prev.turbidity.labels, timeLabel].slice(-20),
        datasets: [{
          ...prev.turbidity.datasets[0],
          data: [...prev.turbidity.datasets[0].data, turbidity].slice(-20),
        }],
      } : prev.turbidity,
      tds: tds != null ? {
        ...prev.tds,
        labels: [...prev.tds.labels, timeLabel].slice(-20),
        datasets: [{
          ...prev.tds.datasets[0],
          data: [...prev.tds.datasets[0].data, tds].slice(-20),
        }],
      } : prev.tds,
    }))
  }, [temperature, phLevel, turbidity, tds])

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        titleColor: '#fff',
        bodyColor: '#fff',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderWidth: 1,
      },
    },
    scales: {
      x: {
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
        ticks: {
          color: '#9ca3af',
          font: {
            size: 11,
          },
        },
      },
      y: {
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
        ticks: {
          color: '#9ca3af',
          font: {
            size: 11,
          },
        },
      },
    },
    elements: {
      point: {
        radius: 3,
        hoverRadius: 5,
      },
      line: {
        tension: 0.3,
      },
    },
  }

  // Metrics configuration — values from sensors, ranges from thresholds
  const metrics = [
    {
      key: 'temperature',
      title: t('temperature'),
      value: temperature,
      unit: '°C',
      icon: '🌡️',
      color: 'danger',
      min: thresholds.temperature?.min || 20,
      max: thresholds.temperature?.max || 35,
      step: 0.1,
      thresholdMin: thresholds.temperature?.min,
      thresholdMax: thresholds.temperature?.max
    },
    {
      key: 'ph',
      title: t('phLevel'),
      value: phLevel,
      unit: '',
      icon: '🧪',
      color: 'success',
      min: thresholds.ph?.min || 3.0,
      max: thresholds.ph?.max || 8.0,
      step: 0.1,
      thresholdMin: thresholds.ph?.min,
      thresholdMax: thresholds.ph?.max
    },
    {
      key: 'turbidity',
      title: t('turbidity'),
      value: turbidity,
      unit: 'NTU',
      icon: '🫧',
      color: 'info',
      min: thresholds.turbidity?.min || 25,
      max: thresholds.turbidity?.max || 50,
      step: 0.1,
      thresholdMin: thresholds.turbidity?.min,
      thresholdMax: thresholds.turbidity?.max
    },
    {
      key: 'tds',
      title: t('tdsEc'),
      value: tds,
      unit: 'ppm',
      icon: '⚡',
      color: 'warning',
      min: thresholds.tds?.min || 100,
      max: thresholds.tds?.max || 160,
      step: 10,
      thresholdMin: thresholds.tds?.min,
      thresholdMax: thresholds.tds?.max
    }
  ]

  const getRangeBounds = (metric) => {
    const rangeMin = Number(metric.thresholdMin ?? metric.min)
    const rangeMax = Number(metric.thresholdMax ?? metric.max)
    return { rangeMin, rangeMax }
  }

  /** Bar fill relative to Min–Max thresholds (0–100%). Out-of-range clamps to edges. */
  const getRangeProgress = (metric) => {
    const value = Number(metric.value)
    const { rangeMin, rangeMax } = getRangeBounds(metric)
    if (!Number.isFinite(value) || !Number.isFinite(rangeMin) || !Number.isFinite(rangeMax) || rangeMax === rangeMin) {
      return { pct: 0, belowMin: false, aboveMax: false, inRange: false }
    }
    const raw = ((value - rangeMin) / (rangeMax - rangeMin)) * 100
    const belowMin = value < rangeMin
    const aboveMax = value > rangeMax
    return {
      pct: Math.min(100, Math.max(0, raw)),
      belowMin,
      aboveMax,
      inRange: !belowMin && !aboveMax,
    }
  }

  // Manual adjustment controls removed — readings come from real sensors now
  // Loading placeholder skeleton to avoid blank screen and unsafe renders
  if (loading) {
    return (
      <div className="p-8 min-h-full bg-gradient-to-br from-slate-50 to-slate-100">
        <h1 className="text-4xl font-bold text-gradient mb-6">{t('dashboard')}</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="h-40 bg-gray-200 rounded-xl animate-pulse" />
          <div className="h-40 bg-gray-200 rounded-xl animate-pulse" />
          <div className="h-40 bg-gray-200 rounded-xl animate-pulse" />
          <div className="h-40 bg-gray-200 rounded-xl animate-pulse" />
        </div>
      </div>
    )
  }

  // Offline if DB latest reading is older than this (poll 5s; WeMos ~5s)
  const SENSOR_ONLINE_MAX_AGE_MS = 45_000
  const sensorAgeMs = lastSensorTimestamp ? (nowTs - new Date(lastSensorTimestamp).getTime()) : Number.POSITIVE_INFINITY
  const sensorOnline = Number.isFinite(sensorAgeMs) && sensorAgeMs >= 0 && sensorAgeMs <= SENSOR_ONLINE_MAX_AGE_MS

  return (
    <div className="p-8 min-h-full bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Hero Header */}
      <div className="mb-8 relative">
        <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 to-blue-500/10 rounded-2xl"></div>
        <div className="relative z-10 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-gradient mb-2">{t('dashboard')}</h1>
              <p className="text-slate-600 text-lg">{t('dashboardSubtitle')}</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 px-3 py-2 bg-white border border-slate-200 rounded-xl shadow-sm">
                <div className={`w-3 h-3 rounded-full ${sensorOnline ? 'bg-green-500' : 'bg-red-500'}`} />
                <div className="text-sm font-medium text-slate-700">
                  {sensorOnline ? (t('sensorsOnline') || 'Sensors Online') : (t('sensorsOffline') || 'Sensors Offline')}
                </div>
              </div>
              <div className="hidden sm:block text-xs text-slate-500 px-2">
                Sensor poll: 5s
              </div>
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-xl shadow-sm hover:bg-slate-50 hover:shadow-md transition-all duration-200 text-slate-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                title="Refresh sensor readings"
              >
                <span className={`text-lg ${refreshing ? 'animate-spin' : ''}`}>🔄</span>
                <span className="hidden sm:inline">{refreshing ? t('refreshing') || 'Refreshing...' : t('refresh') || 'Refresh'}</span>
              </button>
              <div className="hidden md:block">
                <div
                  className="w-24 h-24 bg-cover bg-center rounded-2xl shadow-lg animate-float"
                  style={{ backgroundImage: "url('/shrimp_pond_pic/raw-shrimps-on-hand-washing-shrimp-on-bowl-shrimps-background-fresh-shrimp-prawns-for-cooking-seafood-food-in-the-kitchen-free-photo.jpg')" }}
                ></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Water Quality Status Banner — skip stale ML/threshold UI when feed is offline */}
      {!sensorOnline ? (
        <div className="mb-8 p-6 rounded-2xl border-2 shadow-lg bg-gradient-to-r from-slate-50 to-gray-100 border-slate-300">
          <div className="flex items-center space-x-4">
            <div className="w-16 h-16 rounded-full flex items-center justify-center text-3xl text-white bg-red-500">
              ✕
            </div>
            <div>
              <h2 className="text-2xl font-bold text-slate-800">
                Sensors Offline
              </h2>
              <p className="text-lg text-slate-600">
                No new sensor data for {Math.max(45, Math.round((Number.isFinite(sensorAgeMs) ? sensorAgeMs : 45000) / 1000))}s.
                Showing last saved readings below (may be stale).
              </p>
            </div>
          </div>
        </div>
      ) : waterQuality && (() => {
        const st = waterQuality.status
        const mlClass = waterQuality.ml?.class
        const isGood = st === 'good'
        const isCaution = st === 'caution'
        const bannerCls = isGood
          ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-300'
          : isCaution
            ? 'bg-gradient-to-r from-amber-50 to-yellow-50 border-amber-300'
            : 'bg-gradient-to-r from-red-50 to-orange-50 border-red-300'
        const iconCls = isGood ? 'bg-green-500' : isCaution ? 'bg-amber-500' : 'bg-red-500'
        const titleCls = isGood ? 'text-green-800' : isCaution ? 'text-amber-900' : 'text-red-800'
        const bodyCls = isGood ? 'text-green-700' : isCaution ? 'text-amber-800' : 'text-red-700'
        const statusLabel = isGood
          ? t('waterQualityGood')
          : isCaution
            ? (mlClass || 'CAUTION')
            : (mlClass === 'Severe' ? 'SEVERE' : t('waterQualityPoor'))
        return (
        <div className={`mb-8 p-6 rounded-2xl border-2 shadow-lg ${bannerCls}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className={`w-16 h-16 rounded-full flex items-center justify-center text-3xl text-white ${iconCls}`}>
                {isGood ? '✓' : '⚠'}
              </div>
              <div>
                <h2 className={`text-2xl font-bold ${titleCls}`}>
                  {t('waterQuality')}: {statusLabel}{mlClass ? ` · ${mlClass}` : ''}
                </h2>
                <p className={`text-lg ${bodyCls}`}>
                  {waterQuality.message}
                </p>
                {waterQuality.assessment_mode && (
                  <p className="text-xs text-slate-500 mt-1">
                    Mode: {waterQuality.assessment_mode}
                    {waterQuality.ml?.confidence != null
                      ? ` · ML confidence ${waterQuality.ml.confidence}%`
                      : ''}
                  </p>
                )}
                {waterQuality.issues && waterQuality.issues.length > 0 && (
                  <div className="mt-2">
                    <p className="text-sm font-semibold text-red-900">{t('issuesDetected')}:</p>
                    <ul className="list-disc list-inside text-sm text-red-800">
                      {waterQuality.issues.map((issue, idx) => (
                        <li key={idx}>{issue}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>

          {waterQuality.recommendations && waterQuality.recommendations.length > 0 && (
            <div className="mt-4 p-4 bg-white/50 rounded-lg border border-slate-200">
              <p className="font-semibold text-slate-800 mb-2">🔧 {t('recommendations')}:</p>
              <ul className="space-y-1">
                {waterQuality.recommendations.map((rec, idx) => (
                  <li key={idx} className="text-sm text-slate-700 flex items-start">
                    <span className="mr-2">•</span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        )
      })()}

      {/* Metrics Grid */}
      <div className="grid-modern mb-8">
        {metrics.map((metric) => {
          const valueMissing = isSensorDisconnected(metric.key, metric.value)
          // Always print last DB value when present — even if feed is offline/stale
          const hasValue = !valueMissing && metric.value !== null && metric.value !== undefined && metric.value !== ''
          const displayValue = hasValue ? metric.value : '—'
          const statusBadge = !sensorOnline ? 'Offline (last)' : (valueMissing ? 'Disconnected' : null)
          const statusHint = !sensorOnline
            ? 'Stale — no new packet for 45s+; showing last saved value'
            : valueMissing
              ? 'No value in DB for this sensor'
              : null
          const { rangeMin, rangeMax } = getRangeBounds(metric)
          const { pct, belowMin, aboveMax, inRange } = hasValue
            ? getRangeProgress(metric)
            : { pct: 0, belowMin: false, aboveMax: false, inRange: false }
          const accent = !hasValue
            ? 'from-slate-400 to-slate-500'
            : !sensorOnline
              ? 'from-slate-400 to-slate-500'
              : !inRange
                ? 'from-red-500 to-rose-500'
                : metric.color === 'success'
                  ? 'from-green-500 to-teal-500'
                  : metric.color === 'warning'
                    ? 'from-yellow-500 to-orange-500'
                    : metric.color === 'danger'
                      ? 'from-red-500 to-pink-500'
                      : 'from-blue-500 to-cyan-500'
          const barColor = !hasValue || !sensorOnline
            ? 'bg-slate-400'
            : !inRange
              ? 'bg-gradient-to-r from-red-500 to-rose-500'
              : metric.color === 'success'
                ? 'bg-gradient-to-r from-green-500 to-teal-500'
                : metric.color === 'warning'
                  ? 'bg-gradient-to-r from-yellow-500 to-orange-500'
                  : metric.color === 'danger'
                    ? 'bg-gradient-to-r from-red-500 to-pink-500'
                    : 'bg-gradient-to-r from-blue-500 to-cyan-500'
          const valueClass = !hasValue
            ? 'text-slate-400'
            : !sensorOnline
              ? 'text-slate-600'
              : !inRange
                ? 'text-red-600'
                : 'text-slate-800'

          return (
          <div key={metric.key} className="relative group">
            <div className={`metric-card-modern ${hasValue && sensorOnline && !inRange ? 'ring-1 ring-red-200' : ''}`}>
              <div className="flex items-center justify-between mb-4">
                <div className={`p-3 rounded-xl bg-gradient-to-r ${accent} text-white shadow-lg`}>
                  <span className="text-2xl">{metric.icon}</span>
                </div>
                <div className="text-right">
                  <div className={`text-3xl font-bold ${valueClass}`}>{displayValue}</div>
                  <div className="text-sm text-slate-500">{metric.unit}</div>
                  {statusBadge && (
                    <div className={`text-xs font-semibold mt-0.5 ${!sensorOnline ? 'text-slate-500' : 'text-amber-600'}`}>
                      {statusBadge}
                    </div>
                  )}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <h3 className="text-lg font-semibold text-slate-800">{metric.title}</h3>
                  {hasValue && sensorOnline && !inRange && (
                    <span className="text-xs font-medium text-red-600">
                      {aboveMax ? 'Above max' : belowMin ? 'Below min' : 'Out of range'}
                    </span>
                  )}
                </div>
                {statusHint ? (
                  <div className={`mt-1 px-2 py-1.5 rounded-lg border text-xs ${
                    !sensorOnline
                      ? 'bg-slate-50 border-slate-200 text-slate-700'
                      : 'bg-amber-50 border-amber-200 text-amber-800'
                  }`}>
                    {statusHint}
                  </div>
                ) : null}
                {hasValue && (
                  <>
                    <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden mt-2">
                      <div
                        className={`h-2 rounded-full transition-all duration-500 ${barColor}`}
                        style={{ width: `${pct}%` }}
                      ></div>
                    </div>
                    <div className="flex justify-between text-xs text-slate-500 mt-1">
                      <span>Min: {rangeMin}</span>
                      <span>Max: {rangeMax}</span>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
          )
        })}
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Temperature Chart */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('temperatureTrend')}</h3>
          <div className="h-64">
            <Line data={chartData.temperature} options={chartOptions} />
          </div>
        </div>

        {/* pH Chart */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('phLevelTrend')}</h3>
          <div className="h-64">
            <Line data={chartData.ph} options={chartOptions} />
          </div>
        </div>

        {/* Turbidity Chart */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('turbidityTrend')}</h3>
          <div className="h-64">
            <Line data={chartData.turbidity} options={chartOptions} />
          </div>
        </div>

        {/* TDS/EC Chart */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('tdsEcTrend')}</h3>
          <div className="h-64">
            <Line data={chartData.tds} options={chartOptions} />
          </div>
        </div>
      </div>

      {/* Water Quality Status */}
      <div className="card mb-8">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('waterQualityStatus')}</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {waterQuality && waterQuality.parameters && (() => {
            const statusItems = [
              { key: 'temperature', label: t('temperature'), icon: '🌡️' },
              { key: 'ph', label: t('phLevel'), icon: '🧪' },
              { key: 'turbidity', label: t('turbidity'), icon: '🫧' },
              { key: 'tds', label: t('tdsEc'), icon: '⚡' }
            ]
            return statusItems.map(item => {
              const param = waterQuality.parameters[item.key]
              if (!param) return null

              const isDisconnected = param.status === 'disconnected' || param.value == null
              const isOptimal = param.status === 'optimal'
              const statusConfig = isDisconnected
                ? {
                  bg: 'bg-amber-50 border-amber-300',
                  text: 'text-amber-800',
                  badge: 'bg-amber-500 text-white',
                  label: 'Disconnected'
                }
                : isOptimal
                  ? {
                    bg: 'bg-green-50 border-green-300',
                    text: 'text-green-800',
                    badge: 'bg-green-500 text-white',
                    label: '✓ ' + t('goodForShrimp')
                  }
                  : {
                    bg: 'bg-red-50 border-red-300',
                    text: 'text-red-800',
                    badge: 'bg-red-500 text-white',
                    label: '✗ ' + t('badForShrimp')
                  }

              return (
                <div key={item.key} className={`relative p-4 rounded-lg border-2 shadow-md ${statusConfig.bg}`}>
                  {/* Status Badge */}
                  <div className={`absolute top-2 right-2 px-2 py-1 rounded-full text-xs font-bold ${statusConfig.badge}`}>
                    {isDisconnected ? 'OFF' : isOptimal ? 'GOOD' : 'BAD'}
                  </div>

                  <div className="flex items-center mb-3">
                    <span className="text-3xl mr-3">{item.icon}</span>
                    <div>
                      <h4 className={`font-bold text-sm ${statusConfig.text}`}>{item.label}</h4>
                      <p className="text-xs text-gray-600">
                        {t('optimal')}: {param.min} – {param.max} {param.unit}
                      </p>
                    </div>
                  </div>

                  <div className="text-center py-2">
                    <div className={`text-3xl font-bold ${statusConfig.text}`}>
                      {param.value != null && param.value !== '' ? (
                        <>
                          {Number(param.value).toFixed(1)}
                          <span className="text-lg ml-1">{param.unit}</span>
                        </>
                      ) : (
                        <span className="text-lg">—</span>
                      )}
                    </div>
                    <div className={`mt-2 text-xs font-semibold uppercase tracking-wide ${statusConfig.text}`}>
                      {statusConfig.label}
                    </div>
                  </div>

                  {/* Visual indicator bar — show even if offline/disconnected when value exists */}
                  {param.value != null && param.value !== '' && (
                    <div className="mt-3 w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all duration-500 ${isDisconnected ? 'bg-slate-400' : isOptimal ? 'bg-green-500' : 'bg-red-500'}`}
                        style={{
                          width: `${Math.min(100, Math.max(0, ((param.value - param.min) / (param.max - param.min)) * 100))}%`
                        }}
                      ></div>
                    </div>
                  )}
                </div>
              )
            })
          })()}
        </div>

        {/* Overall Status Summary */}
        {waterQuality && (() => {
          const st = waterQuality.status
          const isGood = st === 'good'
          const isCaution = st === 'caution'
          const box = isGood
            ? 'bg-green-100 border-green-400'
            : isCaution
              ? 'bg-amber-100 border-amber-400'
              : 'bg-red-100 border-red-400'
          const title = isGood ? 'text-green-800' : isCaution ? 'text-amber-900' : 'text-red-800'
          const body = isGood ? 'text-green-700' : isCaution ? 'text-amber-800' : 'text-red-700'
          const label = isGood
            ? t('goodForShrimp')
            : isCaution
              ? (waterQuality.ml?.class || 'Caution')
              : t('badForShrimp')
          return (
          <div className={`mt-6 p-4 rounded-lg border-2 ${box}`}>
            <div className="flex items-center">
              <span className="text-4xl mr-4">
                {isGood ? '✅' : '⚠️'}
              </span>
              <div>
                <h4 className={`text-xl font-bold ${title}`}>
                  {t('overallWaterQuality')}: {label}
                </h4>
                <p className={`text-sm ${body}`}>
                  {waterQuality.message}
                </p>
              </div>
            </div>
          </div>
          )
        })()}
      </div>

      {/* Quick Actions */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('quickActions')}</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            className="btn-primary flex items-center justify-center py-3"
            onClick={() => navigate('/reports')}
          >
            <span className="mr-2">📊</span>
            {t('generateReport')}
          </button>
          <button
            className="btn-secondary flex items-center justify-center py-3"
            onClick={() => navigate('/settings')}
          >
            <span className="mr-2">⚙️</span>
            {t('systemSettings')}
          </button>
          <button
            className="btn-secondary flex items-center justify-center py-3 relative"
            onClick={() => navigate('/alerts')}
          >
            <span className="mr-2">🔔</span>
            {t('viewAlerts')}
            {activeAlerts.length > 0 && (
              <span className="absolute top-1 right-1 bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                {activeAlerts.length}
              </span>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
