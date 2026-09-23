import { useEffect, useState } from 'react'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
} from 'chart.js'
import GaugeRing from '../components/GaugeRing'
import SeasonSensorAverages from '../components/SeasonSensorAverages'
import { classifySensor, summarizeOverallQuality } from '../services/sensorLabels'
import { fetchLatestSensors, getSensorReadings, getSensorChart, isSensorDisconnected, isSensorStreamFresh, normalizeSensorValue } from '../services/sensors'
import { fetchThresholds } from '../services/settings'
import { useLanguage } from '../context/LanguageContext'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip)

const HISTORY_RANGES = [
  { id: 'min', label: 'Min', hours: 0.25 },
  { id: 'hour', label: 'Hour', hours: 1 },
  { id: 'day', label: 'Day', hours: 24 },
  { id: 'week', label: 'Week', hours: 168 },
  { id: 'month', label: 'Month', hours: 720 },
]

function formatChartLabel(iso, rangeId) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  if (rangeId === 'min') {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }
  if (rangeId === 'hour') {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  if (rangeId === 'day') {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { grid: { color: 'rgba(103,232,249,0.08)' }, ticks: { color: '#8fb8cc', maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
    y: { grid: { color: 'rgba(103,232,249,0.08)' }, ticks: { color: '#8fb8cc' } },
  },
}

function series(color) {
  return {
    labels: [],
    datasets: [{
      data: [],
      borderColor: color,
      backgroundColor: color.replace('1)', '0.16)'),
      fill: true,
      tension: 0.25,
      pointRadius: 3,
      pointHoverRadius: 5,
      spanGaps: true,
    }],
  }
}

export default function WaterQuality() {
  const { t } = useLanguage()
  const [temperature, setTemperature] = useState(null)
  const [ph, setPh] = useState(null)
  const [turbidity, setTurbidity] = useState(null)
  const [tds, setTds] = useState(null)
  const [stamp, setStamp] = useState(null)
  const [nowTs, setNowTs] = useState(() => Date.now())
  const [history, setHistory] = useState([])
  const [rangeId, setRangeId] = useState('hour')
  const [charts, setCharts] = useState({
    temperature: series('rgba(251,113,133,1)'),
    ph: series('rgba(45,212,191,1)'),
    turbidity: series('rgba(56,189,248,1)'),
    tds: series('rgba(103,232,249,1)'),
  })

  useEffect(() => {
    const range = HISTORY_RANGES.find((r) => r.id === rangeId) || HISTORY_RANGES[1]
    const load = async () => {
      const [latest, readings, chart] = await Promise.all([
        fetchLatestSensors().catch(() => ({})),
        getSensorReadings(1, 1, 12).catch(() => ({ results: [] })),
        getSensorChart(range.hours).catch(() => ({ results: [] })),
      ])
      setTemperature(normalizeSensorValue('temperature', latest.temperature))
      setPh(normalizeSensorValue('ph', latest.ph))
      setTurbidity(normalizeSensorValue('turbidity', latest.turbidity))
      setTds(normalizeSensorValue('tds', latest.tds))
      setStamp(latest.timestamp || null)
      const packetRows = [...(readings.results || [])]
      setHistory(packetRows)
      const rows = [...(chart.results || [])].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
      const labels = rows.map((r) => formatChartLabel(r.timestamp, range.id))
      setCharts((prev) => ({
        temperature: { ...prev.temperature, labels, datasets: [{ ...prev.temperature.datasets[0], data: rows.map((r) => r.temperature) }] },
        ph: { ...prev.ph, labels, datasets: [{ ...prev.ph.datasets[0], data: rows.map((r) => r.ph) }] },
        turbidity: { ...prev.turbidity, labels, datasets: [{ ...prev.turbidity.datasets[0], data: rows.map((r) => r.turbidity) }] },
        tds: { ...prev.tds, labels, datasets: [{ ...prev.tds.datasets[0], data: rows.map((r) => r.tds) }] },
      }))
    }
    load()
    fetchThresholds().catch(() => {})
    const id = setInterval(load, 8000)
    return () => clearInterval(id)
  }, [rangeId])

  useEffect(() => {
    const id = setInterval(() => setNowTs(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  const sensorOnline = isSensorStreamFresh(stamp, nowTs)
  const overall = summarizeOverallQuality({ temperature, ph, turbidity, tds })
  const toneOf = (key, value) => {
    if (!sensorOnline || isSensorDisconnected(key, value)) return 'offline'
    const tone = classifySensor(key, value).tone
    return tone === 'good' ? 'normal' : tone === 'caution' ? 'warning' : tone === 'bad' ? 'critical' : 'offline'
  }

  const gauges = [
    { key: 'temperature', title: 'Water temperature', value: temperature, unit: 'C', min: 20, max: 36 },
    { key: 'ph', title: 'pH', value: ph, unit: 'pH', min: 6, max: 9 },
    { key: 'turbidity', title: 'Turbidity', value: turbidity, unit: 'NTU', min: 0, max: 40 },
    { key: 'tds', title: 'TDS', value: tds, unit: 'ppm', min: 0, max: 600 },
  ]

  return (
    <div>
      <div className="pond-kicker">Sensor laboratory</div>
      <h1 className="aq-title">Water Quality</h1>
      <p className="aq-sub mb-5">
        Gauges, live status and historical packets. Last reading: {stamp ? new Date(stamp).toLocaleString() : 'none yet'}.
        Overall: {!sensorOnline ? 'N/A OFFLINE' : overall.title}
        {history.length ? ` · ${history.length} recent packets shown` : ' · no packets in this window'}
      </p>

      <div className="gauge-grid mb-5">
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

      <SeasonSensorAverages />

      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div>
          <div className="pond-kicker mb-1">Historical sensor data</div>
          <h2 className="font-semibold">Trend window</h2>
        </div>
        <div className="aq-range" role="tablist" aria-label="History range">
          {HISTORY_RANGES.map((r) => (
            <button
              key={r.id}
              type="button"
              role="tab"
              aria-selected={rangeId === r.id}
              className={rangeId === r.id ? 'is-on' : ''}
              onClick={() => setRangeId(r.id)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
        {['temperature', 'ph', 'turbidity', 'tds'].map((key) => (
          <div key={key} className="card">
            <h3 className="font-semibold mb-3 capitalize">{key} history</h3>
            <div className="h-52"><Line data={charts[key]} options={chartOptions} /></div>
          </div>
        ))}
      </div>
      {!Object.values(charts).some((c) => (c.datasets?.[0]?.data || []).some((v) => v != null)) && (
        <p className="aq-sub mb-5">Charts are empty if this window has no stored snapshots yet. Gauges always show the latest row.</p>
      )}

      <div className="card">
        <div className="pond-kicker mb-2">Sensor activity</div>
        <h3 className="font-semibold mb-3">Latest packets</h3>
        <div className="overflow-x-auto">
          <table className="wq-packets-table text-sm">
            <thead>
              <tr className="text-cyan-200/70">
                <th className="py-2">Time</th>
                <th>Temp</th>
                <th>pH</th>
                <th>Turbidity</th>
                <th>TDS</th>
              </tr>
            </thead>
            <tbody>
              {history.length ? history.map((row) => (
                <tr key={row.id || row.timestamp} className="border-t border-cyan-400/10">
                  <td className="py-2">{row.timestamp ? new Date(row.timestamp).toLocaleString() : '-'}</td>
                  <td>{row.temperature ?? '-'}</td>
                  <td>{row.ph ?? '-'}</td>
                  <td>{row.turbidity ?? '-'}</td>
                  <td>{row.tds ?? '-'}</td>
                </tr>
              )) : (
                <tr>
                  <td className="py-4 text-cyan-200/60" colSpan={5}>No stored packets in this window.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
