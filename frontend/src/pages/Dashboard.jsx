import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getThresholds, fetchThresholds } from '../services/settings'
import { classifySensor, summarizeOverallQuality, TONE_BADGE_CLASS } from '../services/sensorLabels'
import { fetchLatestSensors, getSensorReadings, isSensorDisconnected, isSensorStreamFresh, normalizeSensorValue } from '../services/sensors'
import { getWaterQualityStatus } from '../services/waterQuality'
import { controlBuzzer, playBeeperSound } from '../services/buzzer'
import { fetchActiveAlerts } from '../services/alerts'
import { Line } from 'react-chartjs-2'
import PageLoader from '../components/PageLoader'
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
import GaugeRing from '../components/GaugeRing'
import { useLanguage } from '../context/LanguageContext'
import { getChannelsWebSocketUrl } from '../services/apiConfig'
import { fetchCurrentWeather } from '../services/weatherApi'
import { fetchFeederState, hopperPercentFromDistance, isFeederTelemetryFresh, feedOnce } from '../services/feeder'
import { wemosApi } from '../services/wemos'

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

function formatOfflineDuration(ms) {
  const totalSec = Math.max(45, Math.round((Number.isFinite(ms) ? ms : 45000) / 1000))
  const hours = Math.floor(totalSec / 3600)
  const minutes = Math.floor((totalSec % 3600) / 60)
  const seconds = totalSec % 60
  const parts = []
  if (hours > 0) parts.push(`${hours}h`)
  if (minutes > 0 || hours > 0) parts.push(`${minutes}m`)
  parts.push(`${seconds}s`)
  return parts.join(' ')
}

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
  const [feedBusy, setFeedBusy] = useState(false)
  const [weatherSnap, setWeatherSnap] = useState(null)
  const [feederSnap, setFeederSnap] = useState(null)
  const [feederTel, setFeederTel] = useState(null)
  const [buzzerToggling, setBuzzerToggling] = useState(false)

  const applySensorPayload = (sensorsData) => {
    setTemperature(normalizeSensorValue('temperature', sensorsData.temperature))
    setPhLevel(normalizeSensorValue('ph', sensorsData.ph))
    setTurbidity(normalizeSensorValue('turbidity', sensorsData.turbidity))
    setTds(normalizeSensorValue('tds', sensorsData.tds))
    setLastSensorTimestamp(sensorsData.timestamp || null)
  }

  const reloadChartHistory = async () => {
    try {
      const resp = await getSensorReadings(7, 1, 100)
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
      const [sensorsData, thresholdsData, qualityData, feederState, feederTelemetry] = await Promise.all([
        fetchLatestSensors(),
        fetchThresholds(),
        getWaterQualityStatus(),
        fetchFeederState().catch(() => null),
        wemosApi.getLatestTelemetry().catch(() => null),
      ])
      applySensorPayload(sensorsData)
      setThresholds(thresholdsData)
      setWaterQuality(qualityData)
      if (feederState) setFeederSnap(feederState)
      setFeederTel(feederTelemetry)
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

  // Always poll latest sensors from DB (WeMosâ†’PHP does not push over Django WebSocket).
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
          console.warn('[WS] Disconnected - will retry in 5s (DB polling continues)')
          reconnectTimeout = setTimeout(connectWebSocket, 5000)
        }

        ws.onerror = (err) => {
          console.warn('[WS] Error:', err)
          ws.close()
        }
      } catch (err) {
        console.warn('[WS] Could not connect - DB polling continues')
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
          borderColor: '#fb7185',
          backgroundColor: 'rgba(251, 113, 133, 0.16)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: '#fb7185',
        },
      ],
    },
    ph: {
      labels: [],
      datasets: [
        {
          label: 'pH Level',
          data: [],
          borderColor: '#2dd4bf',
          backgroundColor: 'rgba(45, 212, 191, 0.16)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: '#2dd4bf',
        },
      ],
    },
    turbidity: {
      labels: [],
      datasets: [
        {
          label: 'Turbidity (NTU)',
          data: [],
          borderColor: '#60a5fa',
          backgroundColor: 'rgba(96, 165, 250, 0.12)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: '#60a5fa',
        },
      ],
    },
    tds: {
      labels: [],
      datasets: [
        {
          label: 'TDS/EC (ppm)',
          data: [],
          borderColor: '#94a3b8',
          backgroundColor: 'rgba(148, 163, 184, 0.12)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: '#94a3b8',
        },
      ],
    },
  })

  // Load historical sensor readings to populate chart lines (initial)
  useEffect(() => {
    reloadChartHistory()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    fetchCurrentWeather('Calapan').then(setWeatherSnap).catch(() => setWeatherSnap(null))
    fetchFeederState().then(setFeederSnap).catch(() => setFeederSnap(null))
    const pollFeeder = () => {
      wemosApi.getLatestTelemetry().then(setFeederTel).catch(() => setFeederTel(null))
    }
    pollFeeder()
    const id = setInterval(pollFeeder, 3000)
    return () => clearInterval(id)
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
          color: 'rgba(103, 232, 249, 0.08)',
        },
        ticks: {
          color: '#8fb8cc',
          font: {
            size: 11,
          },
        },
      },
      y: {
        grid: {
          color: 'rgba(103, 232, 249, 0.08)',
        },
        ticks: {
          color: '#8fb8cc',
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

  // Metrics configuration - values from sensors, ranges from thresholds
  const metrics = [
    {
      key: 'temperature',
      title: t('temperature'),
      value: temperature,
      unit: '°C',
      icon: 'ðŸŒ¡ï¸',
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
      icon: 'ðŸ§ª',
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
      icon: 'ðŸ«§',
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
      icon: 'âš¡',
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

  /** Bar fill relative to Min-Max thresholds (0-100%). Out-of-range clamps to edges. */
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

  const sensorAgeMs = lastSensorTimestamp ? (nowTs - new Date(lastSensorTimestamp).getTime()) : Number.POSITIVE_INFINITY
  const sensorOnline = isSensorStreamFresh(lastSensorTimestamp, nowTs)
  const overallQuality = summarizeOverallQuality({
    temperature,
    ph: phLevel,
    turbidity,
    tds,
  })
  const overallPoorText = overallQuality.poor
    .map((row) => `${t(row.nameKey)}: ${t(row.labelKey)} - ${t(row.verdictKey)}`)
    .join(', ')
  const overallLevel = !sensorOnline ? 'offline' : (overallQuality.status || 'offline')
  const overallTitle = !sensorOnline ? 'N/A OFFLINE' : overallQuality.title
  const overallSummary = !sensorOnline
    ? 'No live water-quality packet from WeMos. Last saved values are shown in history only.'
    : overallQuality.tone === 'good'
      ? overallQuality.summary
      : [overallQuality.summary, overallPoorText].filter(Boolean).join(' ')

  const toneOf = (key, value) => {
    if (!sensorOnline || isSensorDisconnected(key, value)) return 'offline'
    const tone = classifySensor(key, value).tone
    if (tone === 'good') return 'normal'
    if (tone === 'caution') return 'warning'
    if (tone === 'bad') return 'critical'
    return 'offline'
  }

  const gauges = [
    { key: 'temperature', title: 'Temperature', value: temperature, unit: '°C', min: 20, max: 36 },
    { key: 'ph', title: 'pH', value: phLevel, unit: 'pH', min: 6, max: 9 },
    { key: 'turbidity', title: 'Turbidity', value: turbidity, unit: 'NTU', min: 0, max: 40 },
    { key: 'tds', title: 'TDS / EC', value: tds, unit: 'ppm', min: 0, max: 600 },
  ]

  const feederOnline = isFeederTelemetryFresh(feederTel?.timestamp, nowTs)
  const feedPct = feederOnline ? hopperPercentFromDistance(feederTel?.distance_cm) : null
  const insights = []
  if (!sensorOnline) insights.push(`Water quality sensors are disconnected. No live packet from WeMos for ${formatOfflineDuration(sensorAgeMs)}.`)
  else {
    insights.push(overallQuality.summary)
    if (overallQuality.poor.length) insights.push(`Out of range: ${overallPoorText}.`)
  }
  if (!feederOnline) insights.push('Automatic feeder ultrasonic sensor is disconnected.')
  if (feedPct != null && feedPct <= 10) insights.push(`Automatic feeder hopper is low (${feedPct}%). Refill before the next scheduled drop.`)
  if (weatherSnap?.description) insights.push(`Calapan weather: ${weatherSnap.description}${weatherSnap.temperature != null ? ` at ${weatherSnap.temperature}°C` : ''}.`)
  if (sensorOnline && waterQuality?.recommendations?.length) {
    insights.push(...waterQuality.recommendations.slice(0, 2))
  }
  if (!insights.length) insights.push('Command deck is standing by for live pond telemetry.')

  const runFeed = async () => {
    setFeedBusy(true)
    try {
      await feedOnce()
      const next = await fetchFeederState()
      setFeederSnap(next)
    } catch (err) {
      console.warn('Manual feed failed', err)
    } finally {
      setFeedBusy(false)
    }
  }

  if (loading) {
    return <PageLoader />
  }

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4 mb-5">
        <div>
          <div className="pond-kicker">Pond overview</div>
          <h1 className="aq-title">Aqua Command Deck</h1>
          <p className="aq-sub">Live shrimp-pond telemetry, feeder IoT, weather and AI insights.</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`aq-live ${sensorOnline ? '' : 'is-off'}`}>
            <i />
            {sensorOnline ? 'Sensors live' : 'Sensors offline'}
          </span>
          <button className="btn-modern" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? 'Syncing...' : 'Sync pond'}
          </button>
        </div>
      </div>

      <div className="aq-hero mb-4">
        <div className="pond-stage" style={{ minHeight: 280 }}>
          <img src="/shrimp_pond_pic/shrimps-pond.jpg" alt="Shrimp pond" />
          <div className="veil" />
          <div className="copy">
            <div className="pond-kicker">Vannamei production pond</div>
            <h2 className="text-2xl md:text-3xl font-bold text-white mt-1" style={{ fontFamily: 'Orbitron, sans-serif' }}>
              Shrimply Smart - Pond 01
            </h2>
            <span className={`verdict ${overallLevel}`}>
              {overallTitle}
            </span>
            <p className="mt-2 text-slate-200 text-sm max-w-xl">
              {overallSummary}
            </p>
          </div>
        </div>

        <div className="card ai-panel">
          <div className="ai-kicker">AI / Data analytics</div>
          <h3 className="text-xl font-bold mt-1 mb-2" style={{ fontFamily: 'Orbitron, sans-serif' }}>Neural pond advisor</h3>
          <ul className="ai-list">
            {insights.slice(0, 5).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <div className="flex gap-2 mt-4">
            <Link to="/analytics" className="btn-modern">Open analytics</Link>
            <Link to="/water-quality" className="btn-secondary">Water lab</Link>
          </div>
        </div>
      </div>

      <h2 className="aq-title text-lg mb-3">Water quality monitoring</h2>
      <div className="gauge-grid mb-4">
        {gauges.map((g) => {
          const level = toneOf(g.key, g.value)
          const reading = classifySensor(g.key, g.value)
          return (
            <div key={g.key} className="card gauge-card">
              <GaugeRing value={sensorOnline ? g.value : null} min={g.min} max={g.max} unit={g.unit} tone={level} />
              <h3>{g.title}</h3>
              <span className={`tone-chip ${level}`}>
                {level === 'offline' ? 'Sensor disconnected' : `${t(reading.labelKey)} - ${t(reading.verdictKey)}`}
              </span>
            </div>
          )
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="card">
          <div className="pond-kicker mb-2">Historical sensor data</div>
          <h3 className="font-semibold mb-3">Temperature trend</h3>
          <div className="h-52"><Line data={chartData.temperature} options={chartOptions} /></div>
        </div>
        <div className="card">
          <div className="pond-kicker mb-2">Historical sensor data</div>
          <h3 className="font-semibold mb-3">pH trend</h3>
          <div className="h-52"><Line data={chartData.ph} options={chartOptions} /></div>
        </div>
        <div className="card">
          <h3 className="font-semibold mb-3">Turbidity trend</h3>
          <div className="h-52"><Line data={chartData.turbidity} options={chartOptions} /></div>
        </div>
        <div className="card">
          <h3 className="font-semibold mb-3">TDS / EC trend</h3>
          <div className="h-52"><Line data={chartData.tds} options={chartOptions} /></div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <div className="pond-kicker">Weather conditions</div>
          <div className="text-3xl font-bold mt-2" style={{ fontFamily: 'Orbitron, sans-serif' }}>
            {weatherSnap?.temperature != null ? `${weatherSnap.temperature}°C` : '-'}
          </div>
          <p className="text-cyan-100/80 mt-1">{weatherSnap?.description || 'Calapan forecast unavailable'}</p>
          <p className="text-sm text-cyan-200/60 mt-2">Humidity {weatherSnap?.humidity ?? '-'}% - Wind {weatherSnap?.windKmh ?? '-'} km/h</p>
          <Link to="/weather" className="btn-secondary mt-4 inline-flex">Full weather deck</Link>
        </div>

        <div className="card">
          <div className="pond-kicker">Automatic feeder</div>
          <div className="text-3xl font-bold mt-2" style={{ fontFamily: 'Orbitron, sans-serif', fontSize: feedPct == null ? '1.35rem' : undefined }}>
            {feedPct != null ? `${feedPct}%` : 'Sensor disconnected'}
          </div>
          <p className="text-cyan-100/80 mt-1">
            {feedPct != null
              ? `Hopper capacity - ${feederSnap?.autoEnabled ? 'AUTO MODE' : 'MANUAL'}`
              : 'Ultrasonic hopper sensor is not connected'}
          </p>
          <p className="text-sm text-cyan-200/60 mt-2">
            Next feed: {feederSnap?.nextFeedTime || feederSnap?.nextFeedAt || 'not scheduled'}
          </p>
          <button className="btn-modern mt-4" onClick={runFeed} disabled={feedBusy}>
            {feedBusy ? 'Dispensing...' : 'Feed now'}
          </button>
          <Link to="/feeding" className="btn-secondary mt-2 inline-flex ml-2">Feeder controls</Link>
        </div>

        <div className="card">
          <div className="pond-kicker">Alerts and notifications</div>
          <div className="text-3xl font-bold mt-2" style={{ color: activeAlerts.length ? '#fb7185' : '#34d399', fontFamily: 'Orbitron, sans-serif' }}>
            {activeAlerts.length}
          </div>
          <p className="text-cyan-100/80 mt-1">Active pond alerts</p>
          <ul className="mt-3 space-y-1 text-sm text-cyan-100/80">
            {activeAlerts.slice(0, 3).map((alert) => (
              <li key={alert.id || alert.message}>- {alert.message || alert.parameter}</li>
            ))}
            {!activeAlerts.length ? <li>No critical events on this cycle.</li> : null}
          </ul>
          <Link to="/alerts" className="btn-secondary mt-4 inline-flex">Open alert center</Link>
        </div>
      </div>
    </div>
  )
}

export default Dashboard

