import { useState, useEffect, useCallback } from 'react'
import { Line, Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import * as reportsService from '../services/reports'
import { getSensorReadings } from '../services/sensors'
import { fetchHistorySettings } from '../services/historySettings'
import { listSeasons } from '../services/seasonBackend'
import { useLanguage } from '../context/LanguageContext'

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const DatePickerField = ({ value, onChange }) => {
  const openPicker = (e) => {
    const input = e.currentTarget.closest('.date-picker')?.querySelector('input[type="date"]')
    try { input?.showPicker?.() } catch { /* ignore */ }
  }
  return (
    <div className="date-picker">
      <input
        type="date"
        value={value}
        onChange={onChange}
        onClick={(e) => { try { e.currentTarget.showPicker?.() } catch { /* ignore */ } }}
      />
      <button type="button" className="date-picker-btn" title="Select date" onClick={openPicker}>📅</button>
    </div>
  )
}
const Toast = ({ message, type, onClose }) => {
  useEffect(() => { const id = setTimeout(onClose, 3500); return () => clearTimeout(id) }, [onClose])
  const bg = type === 'success' ? 'bg-green-500' : type === 'error' ? 'bg-red-500' : 'bg-blue-500'
  return (
    <div className={`fixed top-6 right-6 z-50 ${bg} text-white px-5 py-3 rounded-xl shadow-2xl flex items-center gap-3 animate-slide-in`}>
      <span>{type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span>
      <span className="text-sm font-medium">{message}</span>
      <button onClick={onClose} className="ml-2 opacity-70 hover:opacity-100">&times;</button>
    </div>
  )
}

const SummaryCard = ({ icon, label, value, unit, min, max, colorClass }) => (
  <div className="glass-card p-5 rounded-2xl">
    <div className="flex items-center gap-2 mb-2 text-slate-600 text-sm">{icon} {label}</div>
    <div className={`text-3xl font-bold ${colorClass}`}>{value}<span className="text-base ml-1 opacity-70">{unit}</span></div>
    {(min !== undefined && max !== undefined) && (
      <div className="text-xs text-slate-500 mt-1">Min {min} — Max {max}</div>
    )}
  </div>
)

/* ─── main component ───────────────────────────────────────────── */
const Reports = () => {
  const { t } = useLanguage()

  /* ── state ─────────────────────────────────────────────────── */
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [sensorData, setSensorData] = useState([])
  const [currentPage, setCurrentPage] = useState(1)
  const [sensorTotalCount, setSensorTotalCount] = useState(0)
  const [dateSearch, setDateSearch] = useState('')
  // How many historical rows to show per page (admin-selectable; default 5)
  const [itemsPerPage, setItemsPerPage] = useState(5)
  const [customPageSizeInput, setCustomPageSizeInput] = useState('5')
  // Fetch chart/table sensor history for the last N days (no preset buttons)
  const HISTORY_DAYS = 30

  // Active report (last generated / viewed)
  const [activeReport, setActiveReport] = useState(null)
  // Report history (paginated)
  const [reportHistory, setReportHistory] = useState([])
  const [reportPage, setReportPage] = useState(1)
  const [reportTotalCount, setReportTotalCount] = useState(0)
  const REPORTS_PER_PAGE = 5
  // Custom date range
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')

  // Seasonal report picker
  const [seasons, setSeasons] = useState([])
  const [seasonModalOpen, setSeasonModalOpen] = useState(false)
  const [selectedSeasonId, setSelectedSeasonId] = useState('')

  // Email modal
  const [emailModal, setEmailModal] = useState({ open: false, reportId: null })
  const [emailAddress, setEmailAddress] = useState('')
  const [emailSending, setEmailSending] = useState(false)
  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)

  // Toast
  const [toast, setToast] = useState(null)
  const showToast = useCallback((message, type = 'success') => setToast({ message, type }), [])

  // Chart data & stats from raw sensor
  const [chartData, setChartData] = useState({
    temperature: { labels: [], data: [] },
    ph: { labels: [], data: [] },
    turbidity: { labels: [], data: [] },
    tds: { labels: [], data: [] },
  })
  const [stats, setStats] = useState({
    avgTemp: 0, avgPh: 0, avgTurb: 0, avgTds: 0,
    minTemp: 0, maxTemp: 0, minPh: 0, maxPh: 0,
    minTurb: 0, maxTurb: 0, minTds: 0, maxTds: 0,
    tempChange: 0,
  })

  /* ── init ──────────────────────────────────────────────────── */
  useEffect(() => { setCurrentPage(1); fetchData(1) }, [itemsPerPage])
  useEffect(() => { loadReportHistory(1); loadDefaultEmail(); loadSeasons() }, [])

  const loadDefaultEmail = async () => {
    try {
      const s = await fetchHistorySettings()
      if (s?.notification_email) setEmailAddress(s.notification_email)
    } catch { /* ignore */ }
  }

  const loadSeasons = async () => {
    try {
      const data = await listSeasons()
      const list = Array.isArray(data) ? data : (data?.results || [])
      setSeasons(list)
      if (list.length && !selectedSeasonId) {
        const active = list.find(s => s.is_active) || list[0]
        setSelectedSeasonId(String(active.id))
      }
    } catch (err) {
      console.error('Failed to load seasons', err)
    }
  }

  const loadReportHistory = async (page = reportPage) => {
    try {
      const data = await reportsService.getReports(page, REPORTS_PER_PAGE)
      setReportHistory(Array.isArray(data.results) ? data.results : [])
      setReportTotalCount(data.count || 0)
      setReportPage(page)
    } catch (err) { console.error('Failed to load report history', err) }
  }

  /* ── fetch sensor data (server-side paginated) ─────────────── */
  const fetchData = async (page = currentPage) => {
    setLoading(true)
    try {
      // Table page (admin-selected row count) + wider pull for 12–12 averages/charts
      const [tableResp, statsResp] = await Promise.all([
        getSensorReadings(HISTORY_DAYS, page, itemsPerPage),
        getSensorReadings(2, 1, 500),
      ])
      const readings = Array.isArray(tableResp.results) ? tableResp.results : []
      const statsReadings = Array.isArray(statsResp.results) ? statsResp.results : readings
      setSensorData(readings)
      setSensorTotalCount(tableResp.count || 0)
      setCurrentPage(page)
      if (statsReadings.length) {
        processChartData(statsReadings)
        calculateStats(statsReadings)
      } else {
        setChartData({
          temperature: { labels: [], data: [] },
          ph: { labels: [], data: [] },
          turbidity: { labels: [], data: [] },
          tds: { labels: [], data: [] },
        })
      }
    } catch (error) { console.error('Error fetching sensor data:', error) }
    finally { setLoading(false) }
  }

  const applyCustomPageSize = () => {
    const n = Math.max(1, Math.min(200, parseInt(customPageSizeInput, 10) || 5))
    setCustomPageSizeInput(String(n))
    setItemsPerPage(n)
    setCurrentPage(1)
  }

  const processChartData = (readings) => {
    const subset = readings.slice(0, 20).reverse()
    const labels = subset.map(r => new Date(r.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }))
    setChartData({
      temperature: { labels, data: subset.map(r => parseFloat(r.temperature) || 0) },
      ph: { labels, data: subset.map(r => parseFloat(r.ph) || 0) },
      turbidity: { labels, data: subset.map(r => parseFloat(r.turbidity) || 0) },
      tds: { labels, data: subset.map(r => parseFloat(r.tds) || 0) },
    })
  }

  const calculateStats = (readings) => {
    if (!readings.length) return
    const nums = (arr) => arr.map(v => (v == null || v === '' ? NaN : Number(v))).filter(n => Number.isFinite(n))
    const avg = (arr) => (arr.length ? arr.reduce((s, v) => s + v, 0) / arr.length : 0)

    // All sensor averages use current noon→noon window (12:00–12:00)
    const now = new Date()
    const noonToday = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12, 0, 0, 0)
    const windowStart = now >= noonToday ? noonToday : new Date(noonToday.getTime() - 24 * 60 * 60 * 1000)
    const windowEnd = new Date(windowStart.getTime() + 24 * 60 * 60 * 1000)
    const dayReadings = readings.filter(r => {
      const t = new Date(r.timestamp).getTime()
      return t >= windowStart.getTime() && t < windowEnd.getTime()
    })
    const source = dayReadings.length ? dayReadings : readings

    const temps = nums(source.map(r => r.temperature))
    const phs = nums(source.map(r => r.ph))
    const turbidities = nums(source.map(r => r.turbidity))
    const tdss = nums(source.map(r => r.tds))

    const recent = temps.slice(0, 7)
    const previous = temps.slice(7, 14)
    const tempChange = previous.length ? (avg(recent) - avg(previous)).toFixed(1) : 0

    setStats({
      avgTemp: temps.length ? avg(temps).toFixed(1) : '—',
      minTemp: temps.length ? Math.min(...temps).toFixed(1) : '—',
      maxTemp: temps.length ? Math.max(...temps).toFixed(1) : '—',
      avgPh: phs.length ? avg(phs).toFixed(1) : '—',
      minPh: phs.length ? Math.min(...phs).toFixed(1) : '—',
      maxPh: phs.length ? Math.max(...phs).toFixed(1) : '—',
      avgTurb: turbidities.length ? avg(turbidities).toFixed(2) : '—',
      minTurb: turbidities.length ? Math.min(...turbidities).toFixed(2) : '—',
      maxTurb: turbidities.length ? Math.max(...turbidities).toFixed(2) : '—',
      avgTds: tdss.length ? Math.round(avg(tdss)) : '—',
      minTds: tdss.length ? Math.round(Math.min(...tdss)) : '—',
      maxTds: tdss.length ? Math.round(Math.max(...tdss)) : '—',
      tempChange,
    })
  }

  /* ── report generation ─────────────────────────────────────── */
  const handleGenerateReport = async (type) => {
    if (type === 'seasonal') {
      setSeasonModalOpen(true)
      return
    }
    setGenerating(true)
    try {
      let report
      switch (type) {
        case 'daily': report = await reportsService.generateDailyReport(); break
        case 'weekly': report = await reportsService.generateWeeklyReport(); break
        case 'monthly': report = await reportsService.generateMonthlyReport(); break
        case 'custom':
          if (!customStart || !customEnd) { showToast('Select both start and end dates', 'error'); setGenerating(false); return }
          report = await reportsService.generateCustomReport(customStart, customEnd); break
        default: return
      }
      setActiveReport(report)
      showToast(`${type.charAt(0).toUpperCase() + type.slice(1)} report generated!`)
      loadReportHistory()
    } catch (error) { showToast('Error generating report: ' + error.message, 'error') }
    finally { setGenerating(false) }
  }

  const handleGenerateSeasonal = async () => {
    if (!selectedSeasonId) {
      showToast('Select a season first', 'error')
      return
    }
    setGenerating(true)
    try {
      const report = await reportsService.generateSeasonalReport(Number(selectedSeasonId))
      setActiveReport(report)
      setSeasonModalOpen(false)
      showToast('Seasonal report generated!')
      loadReportHistory()
    } catch (error) {
      showToast('Error generating seasonal report: ' + error.message, 'error')
    } finally {
      setGenerating(false)
    }
  }

  const handleViewReport = async (id) => {
    try {
      const report = await reportsService.getReport(id)
      setActiveReport(report)
      showToast('Report loaded')
    } catch (err) { showToast('Failed to load report', 'error') }
  }

  const handleDeleteReport = (report) => {
    setPendingDelete(report)
  }

  const confirmDeleteReport = async () => {
    if (!pendingDelete?.id) return
    setDeleting(true)
    try {
      await reportsService.deleteReport(pendingDelete.id)
      if (activeReport?.id === pendingDelete.id) setActiveReport(null)
      setPendingDelete(null)
      showToast('Report deleted')
      loadReportHistory()
    } catch (err) {
      showToast('Failed to delete', 'error')
    } finally {
      setDeleting(false)
    }
  }

  /* ── email ─────────────────────────────────────────────────── */
  const openEmailModal = (reportId) => { setEmailModal({ open: true, reportId }); }
  const closeEmailModal = () => { setEmailModal({ open: false, reportId: null }); setEmailSending(false) }
  const handleSendEmail = async () => {
    if (!emailAddress) { showToast('Enter an email address', 'error'); return }
    setEmailSending(true)
    try {
      await reportsService.emailReport(emailModal.reportId, emailAddress)
      showToast(`Report sent to ${emailAddress}`)
      closeEmailModal()
    } catch (err) { showToast('Failed to send email: ' + err.message, 'error'); setEmailSending(false) }
  }

  /* ── export helpers ────────────────────────────────────────── */
  const loadFullReport = async (id) => {
    if (activeReport?.id === id && activeReport.summary) return activeReport
    return reportsService.getReport(id)
  }

  const exportExcelForReport = async (report) => {
    if (!report) {
      showToast('Generate a report first', 'error')
      return
    }
    if (report.report_type === 'seasonal') {
      if (!report.summary?.daily_rows) {
        showToast('This seasonal report has no daily rows to export', 'error')
        return
      }
      const filename = await reportsService.exportSeasonalExcel(report)
      showToast(`Exported ${filename}`)
      return
    }

    const daily = Array.isArray(report.summary?.daily_rows) ? report.summary.daily_rows : []
    const data = daily.length
      ? daily.map((r) => ({
          date: r.date,
          temperature: r.avg_temperature,
          ph: r.avg_ph,
          turbidity: r.avg_turbidity,
          tds: r.avg_tds,
          status: r.status || '',
        }))
      : [{
          date: `${report.start_date || ''} → ${report.end_date || ''}`,
          temperature: report.summary?.sensor_data?.temperature?.avg ?? null,
          ph: report.summary?.sensor_data?.ph?.avg ?? null,
          turbidity: report.summary?.sensor_data?.turbidity?.avg ?? null,
          tds: report.summary?.sensor_data?.tds?.avg ?? null,
          status: 'summary',
        }]
    const filename = `${(report.title || 'report').replace(/[^\w\-]+/g, '_')}.xlsx`
    await reportsService.exportToExcel(data, filename)
    showToast('Excel exported!')
  }

  const exportPdfForReport = async (report) => {
    if (!report) {
      showToast('Generate a report first', 'error')
      return
    }
    if (report.report_type === 'seasonal') {
      if (!report.summary?.daily_rows) {
        showToast('This seasonal report has no daily rows to export', 'error')
        return
      }
      await reportsService.generateSeasonalPDF(report)
      return
    }

    const daily = Array.isArray(report.summary?.daily_rows) ? report.summary.daily_rows : []
    const title = report.title || 'Report'
    const data = daily.length
      ? daily.map((r) => ({
          date: r.date,
          temperature: r.avg_temperature,
          ph: r.avg_ph,
          turbidity: r.avg_turbidity,
          tds: r.avg_tds,
          status: r.status || '',
        }))
      : [{
          date: `${report.start_date || ''} → ${report.end_date || ''}`,
          temperature: report.summary?.sensor_data?.temperature?.avg ?? null,
          ph: report.summary?.sensor_data?.ph?.avg ?? null,
          turbidity: report.summary?.sensor_data?.turbidity?.avg ?? null,
          tds: report.summary?.sensor_data?.tds?.avg ?? null,
          status: 'summary',
        }]
    await reportsService.generatePDFReport(data, title)
  }

  const handleExportExcel = async () => {
    try {
      await exportExcelForReport(activeReport)
    } catch (error) { showToast('Export failed: ' + error.message, 'error') }
  }

  const handleGeneratePDF = async () => {
    try {
      await exportPdfForReport(activeReport)
    } catch (error) { showToast('PDF generation failed: ' + error.message, 'error') }
  }

  const handleHistoryExcel = async (id) => {
    try {
      const report = await loadFullReport(id)
      setActiveReport(report)
      await exportExcelForReport(report)
    } catch (error) { showToast('Export failed: ' + error.message, 'error') }
  }

  const handleHistoryPdf = async (id) => {
    try {
      const report = await loadFullReport(id)
      setActiveReport(report)
      await exportPdfForReport(report)
    } catch (error) { showToast('PDF generation failed: ' + error.message, 'error') }
  }

  /* ── derived: active report data ───────────────────────────── */
  const summary = activeReport?.summary || {}
  const sensorSummary = summary.sensor_data || {}
  const alertSummary = summary.alerts || {}
  const feedingSummary = summary.feeding || {}
  const seasonSummary = summary.season || null
  const harvestSummary = summary.harvest || null
  const weatherSummary = summary.weather || null
  const feedingLogs = Array.isArray(feedingSummary.logs) ? feedingSummary.logs : []
  const harvestEntries = Array.isArray(harvestSummary?.entries) ? harvestSummary.entries : []
  const weatherDays = Array.isArray(weatherSummary?.daily) ? weatherSummary.daily : []
  const dailyRows = Array.isArray(summary.daily_rows) ? summary.daily_rows : []
  const growthForecast = summary.growth_forecast || null
  const insights = Array.isArray(activeReport?.insights) ? activeReport.insights : []

  // Use report summary for cards when available, else fall back to sensor stats
  const cardTemp = sensorSummary.temperature || {}
  const cardPh = sensorSummary.ph || {}
  const cardTurb = sensorSummary.turbidity || {}
  const cardTds = sensorSummary.tds || {}

  /* ── alert bar-chart data ──────────────────────────────────── */
  const alertBarData = {
    labels: Object.keys(alertSummary.by_parameter || {}).map(k => k.charAt(0).toUpperCase() + k.slice(1)),
    datasets: [{
      label: 'Alerts',
      data: Object.values(alertSummary.by_parameter || {}),
      backgroundColor: ['rgba(239,68,68,0.7)', 'rgba(34,197,94,0.7)', 'rgba(59,130,246,0.7)', 'rgba(234,179,8,0.7)'],
      borderRadius: 6,
    }],
  }

  /* ── feeding bar-chart data ────────────────────────────────── */
  const feedingBarData = {
    labels: Object.keys(feedingSummary.by_type || {}).map(k => k.replace(/_/g, ' ')),
    datasets: [{
      label: 'Events',
      data: Object.values(feedingSummary.by_type || {}),
      backgroundColor: ['rgba(14,165,233,0.7)', 'rgba(168,85,247,0.7)', 'rgba(249,115,22,0.7)', 'rgba(20,184,166,0.7)'],
      borderRadius: 6,
    }],
  }

  const barOptions = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { backgroundColor: 'rgba(0,0,0,0.8)', titleColor: '#fff', bodyColor: '#fff' } },
    scales: {
      x: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#9ca3af' } },
      y: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#9ca3af', stepSize: 1 }, beginAtZero: true },
    },
  }

  /* ── growth forecast chart (downsample long seasons) ───────── */
  const growthAbwChart = (() => {
    const series = Array.isArray(growthForecast?.abw_series) ? growthForecast.abw_series : []
    if (!series.length) return null
    const step = series.length > 90 ? 3 : series.length > 45 ? 2 : 1
    const sampled = series.filter((_, i) => i % step === 0 || i === series.length - 1)
    return {
      labels: sampled.map((p) => p.date?.slice(5) || ''),
      datasets: [
        {
          label: 'Predicted ABW (g)',
          data: sampled.map((p) => p.abw_predicted),
          borderColor: 'rgb(14, 165, 233)',
          backgroundColor: 'rgba(14, 165, 233, 0.12)',
          fill: true,
          tension: 0.25,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: 'Observed ABW (sampling)',
          data: sampled.map((p) => p.abw_observed),
          borderColor: 'rgb(234, 88, 12)',
          backgroundColor: 'rgb(234, 88, 12)',
          showLine: false,
          pointRadius: sampled.map((p) => (p.abw_observed != null ? 4 : 0)),
          pointHoverRadius: 6,
        },
      ],
    }
  })()

  const growthChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { position: 'top', labels: { color: '#475569', boxWidth: 12 } },
      tooltip: { backgroundColor: 'rgba(15,23,42,0.9)' },
    },
    scales: {
      x: {
        ticks: { color: '#94a3b8', maxRotation: 0, autoSkip: true, maxTicksLimit: 12 },
        grid: { color: 'rgba(148,163,184,0.15)' },
      },
      y: {
        title: { display: true, text: 'ABW (g)', color: '#64748b' },
        ticks: { color: '#94a3b8' },
        grid: { color: 'rgba(148,163,184,0.15)' },
        beginAtZero: true,
      },
    },
  }

  /* ── line chart configs ────────────────────────────────────── */
  const makeLineDataset = (label, data, color) => ({
    labels: chartData.temperature.labels,
    datasets: [{
      label,
      data,
      borderColor: color,
      backgroundColor: color.replace('rgb', 'rgba').replace(')', ',0.1)'),
      borderWidth: 2,
      fill: true,
      tension: 0.4,
      pointRadius: 3,
      pointHoverRadius: 5,
      pointBackgroundColor: color,
    }],
  })
  const temperatureData = makeLineDataset('Temperature (°C)', chartData.temperature.data, 'rgb(239,68,68)')
  const phData = makeLineDataset('pH Level', chartData.ph.data, 'rgb(34,197,94)')
  const turbidityData = makeLineDataset('Turbidity (NTU)', chartData.turbidity.data, 'rgb(14,165,233)')
  const tdsData = makeLineDataset('TDS/EC (ppm)', chartData.tds.data, 'rgb(249,115,22)')

  const chartOptions = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { backgroundColor: 'rgba(0,0,0,0.8)', titleColor: '#fff', bodyColor: '#fff', borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1 } },
    scales: {
      x: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#9ca3af', font: { size: 11 } } },
      y: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#9ca3af', font: { size: 11 } } },
    },
    elements: { point: { radius: 3, hoverRadius: 5 }, line: { tension: 0.3 } },
  }
  const temperatureOptions = { ...chartOptions, scales: { ...chartOptions.scales, y: { ...chartOptions.scales.y, min: 25, max: 35 } } }
  const phOptions = { ...chartOptions, scales: { ...chartOptions.scales, y: { ...chartOptions.scales.y, min: 5, max: 9 } } }
  const turbidityOptions = { ...chartOptions, scales: { ...chartOptions.scales, y: { ...chartOptions.scales.y, min: 0, max: 5 } } }
  const tdsOptions = { ...chartOptions, scales: { ...chartOptions.scales, y: { ...chartOptions.scales.y, beginAtZero: false } } }

  /* ── table helpers ─────────────────────────────────────────── */
  const allHistoricalData = sensorData.map(reading => {
    const dt = new Date(reading.timestamp)
    return {
      date: dt.toLocaleDateString(), time: dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      rawDate: dt, temperature: parseFloat(reading.temperature).toFixed(1),
      ph: parseFloat(reading.ph).toFixed(1), turb: parseFloat(reading.turbidity).toFixed(1),
      tds: Math.round(parseFloat(reading.tds)), status: getStatusFromReading(reading),
    }
  })
  // Server-side pagination: sensorData is already the current page.
  // Client-side date filter applies on top of what we have.
  const filteredData = dateSearch
    ? allHistoricalData.filter(row => { const sd = new Date(dateSearch); return row.rawDate.getFullYear() === sd.getFullYear() && row.rawDate.getMonth() === sd.getMonth() && row.rawDate.getDate() === sd.getDate() })
    : allHistoricalData
  const sensorTotalPages = Math.ceil(sensorTotalCount / itemsPerPage) || 1
  // When date search is active we show filtered results directly (within the current server page)
  const historicalData = filteredData

  function getStatusFromReading(reading) {
    const temp = parseFloat(reading.temperature), ph = parseFloat(reading.ph), turb = parseFloat(reading.turbidity)
    const tempOk = temp >= 28 && temp <= 32, phOk = ph >= 7.0 && ph <= 8.5, turbOk = turb >= 0.5 && turb <= 3.0
    if (tempOk && phOk && turbOk) return 'Excellent'
    if (tempOk && phOk) return 'Good'
    if (!tempOk || !phOk || turb > 4.0) return 'Warning'
    return 'Critical'
  }
  const getStatusColor = (s) => ({ Excellent: 'text-green-700 bg-green-100', Good: 'text-blue-700 bg-blue-100', Warning: 'text-yellow-700 bg-yellow-100', Critical: 'text-red-700 bg-red-100' }[s] || 'text-slate-600 bg-slate-100')

  const insightColor = (type) => ({ critical: 'border-red-400 bg-red-50 text-red-700', warning: 'border-yellow-400 bg-yellow-50 text-yellow-700', info: 'border-blue-400 bg-blue-50 text-blue-700' }[type] || 'border-slate-400 bg-slate-50 text-slate-700')
  const insightIcon = (type) => ({ critical: '🔴', warning: '🟡', info: '🔵' }[type] || 'ℹ️')

  const exportIdle = !activeReport
  const exportBtnBase = 'px-4 py-2.5 text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm font-medium'
  const exportIdleClass = `${exportBtnBase} bg-cyan-600 hover:bg-cyan-700`

  /* ─── RENDER ─────────────────────────────────────────────────── */
  return (
    <div className="p-6 space-y-8">
      {/* Toast */}
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-slate-800 mb-1">{t('reportsAndAnalytics')}</h1>
        <p className="text-slate-600">{t('reportsSubtitle')}</p>
      </div>

      {/* ═══ Section A: Report Generation ═══ */}
      <div className="glass-card p-6 rounded-2xl space-y-5">
        <h2 className="text-xl font-semibold text-slate-800 flex items-center gap-2">📊 {t('reportPeriod')}</h2>

        {/* Generate Report buttons */}
        <div>
          <h3 className="text-sm font-medium text-slate-600 mb-3">{t('quickReportGeneration')}</h3>
          <div className="flex flex-wrap gap-3">
            <button onClick={() => handleGenerateReport('daily')} disabled={generating}
              className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm font-medium">
              {generating ? <span className="animate-spin">⏳</span> : '📅'} {t('dailyReport')}
            </button>
            <button onClick={() => handleGenerateReport('weekly')} disabled={generating}
              className="px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm font-medium">
              {generating ? <span className="animate-spin">⏳</span> : '📊'} {t('weeklyReport')}
            </button>
            <button onClick={() => handleGenerateReport('monthly')} disabled={generating}
              className="px-4 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm font-medium">
              {generating ? <span className="animate-spin">⏳</span> : '📈'} {t('monthlyReport')}
            </button>
            <button onClick={() => handleGenerateReport('seasonal')} disabled={generating}
              className="px-4 py-2.5 bg-amber-600 hover:bg-amber-700 text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm font-medium">
              {generating ? <span className="animate-spin">⏳</span> : '🦐'} Seasonal Report
            </button>
          </div>
        </div>

        {/* Custom date range */}
        <div className="border-t border-slate-200 pt-4">
          <h3 className="text-sm font-medium text-slate-600 mb-3">Custom Date Range</h3>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-xs text-slate-600 mb-1">Start Date</label>
              <DatePickerField value={customStart} onChange={e => setCustomStart(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs text-slate-600 mb-1">End Date</label>
              <DatePickerField value={customEnd} onChange={e => setCustomEnd(e.target.value)} />
            </div>
            <button onClick={() => handleGenerateReport('custom')} disabled={generating || !customStart || !customEnd}
              className="px-4 py-2.5 bg-cyan-600 hover:bg-cyan-700 text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium">
              Generate Custom
            </button>
          </div>
        </div>

        {/* Export Data (inside Report Period) */}
        <div className="border-t border-slate-200 pt-4">
          <h3 className="text-sm font-medium text-slate-600 mb-3">{t('exportData')}</h3>
          <div className="flex flex-wrap gap-3">
            <button
              onClick={handleExportExcel}
              disabled={exportIdle || loading || (activeReport?.report_type !== 'seasonal' && sensorData.length === 0)}
              className={exportIdle ? exportIdleClass : `${exportBtnBase} bg-emerald-700 hover:bg-emerald-800`}
              title={exportIdle ? 'Generate a report first' : (activeReport?.report_type === 'seasonal' ? 'Export seasonal daily Excel' : 'Export sensor readings')}
            >
              📊 {t('exportToExcel')}
            </button>
            <button onClick={handleGeneratePDF} disabled={exportIdle || loading}
              className={exportIdle ? exportIdleClass : `${exportBtnBase} bg-rose-700 hover:bg-rose-800`}
              title={exportIdle ? 'Generate a report first' : 'Export the generated report as PDF'}>
              📄 {t('generatePDFReport')}
            </button>
            <button onClick={() => { if (activeReport) openEmailModal(activeReport.id); else showToast('Generate a report first', 'error') }}
              disabled={exportIdle || loading}
              className={exportIdle ? exportIdleClass : `${exportBtnBase} bg-indigo-700 hover:bg-indigo-800`}
              title={exportIdle ? 'Generate a report first' : undefined}>
              📧 {t('emailReport')}
            </button>
          </div>
        </div>

        {generating && (
          <div className="flex items-center gap-2 text-cyan-700 text-sm">
            <span className="animate-spin">⏳</span> Generating report…
          </div>
        )}
      </div>

      {/* ═══ Section B: Summary Cards ═══ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard icon="🌡️" label={t('averageTemperature')} colorClass="text-red-600"
          value={cardTemp.avg ?? stats.avgTemp} unit="°C"
          min={cardTemp.min ?? stats.minTemp} max={cardTemp.max ?? stats.maxTemp} />
        <SummaryCard icon="🧪" label={t('averagePh')} colorClass="text-green-600"
          value={cardPh.avg ?? stats.avgPh} unit=""
          min={cardPh.min ?? stats.minPh} max={cardPh.max ?? stats.maxPh} />
        <SummaryCard icon="🫧" label={t('turbidity')} colorClass="text-blue-600"
          value={cardTurb.avg ?? stats.avgTurb} unit="NTU"
          min={cardTurb.min ?? stats.minTurb} max={cardTurb.max ?? stats.maxTurb} />
        <SummaryCard icon="📏" label={t('averageTds')} colorClass="text-yellow-600"
          value={cardTds.avg ?? stats.avgTds} unit="ppm"
          min={cardTds.min ?? stats.minTds} max={cardTds.max ?? stats.maxTds} />
      </div>

      {/* ═══ Section C: Charts ═══ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('temperatureTrend')}</h3>
          <div className="h-64"><Line data={temperatureData} options={temperatureOptions} /></div>
        </div>
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('phLevelTrend')}</h3>
          <div className="h-64"><Line data={phData} options={phOptions} /></div>
        </div>
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('turbidityTrend')}</h3>
          <div className="h-64"><Line data={turbidityData} options={turbidityOptions} /></div>
        </div>
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('tdsEcTrend')}</h3>
          <div className="h-64"><Line data={tdsData} options={tdsOptions} /></div>
        </div>

        {/* Bar charts — only show when a report is active */}
        {Object.keys(alertSummary.by_parameter || {}).length > 0 && (
          <div className="glass-card p-5 rounded-2xl">
            <h3 className="text-lg font-semibold text-slate-800 mb-4">⚠️ Alerts by Parameter</h3>
            <div className="h-64"><Bar data={alertBarData} options={barOptions} /></div>
            <p className="text-xs text-slate-500 mt-2">{alertSummary.total} total alerts, {alertSummary.unresolved} unresolved</p>
          </div>
        )}
        {Object.keys(feedingSummary.by_type || {}).length > 0 && (
          <div className="glass-card p-5 rounded-2xl">
            <h3 className="text-lg font-semibold text-slate-800 mb-4">🦐 Feeding by Type</h3>
            <div className="h-64"><Bar data={feedingBarData} options={barOptions} /></div>
            <p className="text-xs text-slate-500 mt-2">
              {feedingSummary.total_events} events,{' '}
              {feedingSummary.total_kg != null
                ? `${Number(feedingSummary.total_kg).toFixed(1)} kg total`
                : `${Number(feedingSummary.total_grams || 0).toFixed(0)}g total`}
            </p>
          </div>
        )}
      </div>

      {/* ═══ Seasonal Report Details ═══ */}
      {activeReport?.report_type === 'seasonal' && seasonSummary && (
        <div className="space-y-6">
          <div className="glass-card p-6 rounded-2xl">
            <h2 className="text-xl font-semibold text-slate-800 mb-3 flex items-center gap-2">
              🦐 Season Overview — {seasonSummary.name}
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div className="bg-slate-50 rounded-xl p-3"><div className="text-slate-500 text-xs">Start</div><div className="font-semibold text-slate-800">{seasonSummary.start_date}</div></div>
              <div className="bg-slate-50 rounded-xl p-3"><div className="text-slate-500 text-xs">End</div><div className="font-semibold text-slate-800">{seasonSummary.end_date || 'Active'}</div></div>
              <div className="bg-slate-50 rounded-xl p-3"><div className="text-slate-500 text-xs">Days</div><div className="font-semibold text-slate-800">{seasonSummary.days_active}</div></div>
              <div className="bg-slate-50 rounded-xl p-3"><div className="text-slate-500 text-xs">Status</div><div className="font-semibold text-slate-800">{seasonSummary.is_active ? 'Active' : 'Ended'}</div></div>
              <div className="bg-slate-50 rounded-xl p-3"><div className="text-slate-500 text-xs">Initial qty</div><div className="font-semibold text-slate-800">{seasonSummary.initial_shrimp_quantity ?? '—'}</div></div>
              <div className="bg-slate-50 rounded-xl p-3"><div className="text-slate-500 text-xs">Current qty</div><div className="font-semibold text-slate-800">{seasonSummary.current_shrimp_quantity ?? '—'}</div></div>
              <div className="bg-slate-50 rounded-xl p-3"><div className="text-slate-500 text-xs">Avg weight</div><div className="font-semibold text-slate-800">{seasonSummary.average_shrimp_weight_grams != null ? `${seasonSummary.average_shrimp_weight_grams} g` : '—'}</div></div>
              <div className="bg-slate-50 rounded-xl p-3"><div className="text-slate-500 text-xs">Stocking density</div><div className="font-semibold text-slate-800">{seasonSummary.stocking_density ?? '—'}</div></div>
            </div>
            {seasonSummary.notes ? <p className="text-sm text-slate-600 mt-3">{seasonSummary.notes}</p> : null}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="glass-card p-6 rounded-2xl">
              <h3 className="text-lg font-semibold text-slate-800 mb-3">🌾 Harvest</h3>
              <div className="flex flex-wrap gap-4 mb-4 text-sm">
                <div><span className="text-slate-500">Total</span> <span className="font-bold text-slate-800 ml-1">{harvestSummary?.total_kg ?? 0} kg</span></div>
                <div><span className="text-slate-500">Harvest events</span> <span className="font-bold text-slate-800 ml-1">{harvestSummary?.harvest_count ?? 0}</span></div>
                <div><span className="text-slate-500">Entries</span> <span className="font-bold text-slate-800 ml-1">{harvestSummary?.entry_count ?? 0}</span></div>
              </div>
              <div className="overflow-x-auto max-h-64">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs text-slate-500 uppercase">
                      <th className="py-2 pr-3">Date</th>
                      <th className="py-2 pr-3">Amount</th>
                      <th className="py-2 pr-3">Note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {harvestEntries.length === 0 ? (
                      <tr><td colSpan="3" className="py-4 text-slate-500">No harvest entries for this season.</td></tr>
                    ) : harvestEntries.map((e) => (
                      <tr key={e.id} className="border-b border-slate-100">
                        <td className="py-2 pr-3 text-slate-700">{e.date}</td>
                        <td className="py-2 pr-3 text-slate-700">{e.amount} {e.unit}{e.is_all ? ' (all)' : ''}</td>
                        <td className="py-2 pr-3 text-slate-500">{e.note || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="glass-card p-6 rounded-2xl">
              <h3 className="text-lg font-semibold text-slate-800 mb-3">🌤️ Weather</h3>
              <div className="flex flex-wrap gap-4 mb-4 text-sm">
                <div><span className="text-slate-500">Days</span> <span className="font-bold text-slate-800 ml-1">{weatherSummary?.days_with_data ?? 0}</span></div>
                <div><span className="text-slate-500">Avg temp</span> <span className="font-bold text-slate-800 ml-1">{weatherSummary?.avg_temperature ?? '—'}°C</span></div>
                <div><span className="text-slate-500">Precip</span> <span className="font-bold text-slate-800 ml-1">{weatherSummary?.total_precipitation_mm ?? 0} mm</span></div>
                <div><span className="text-slate-500">Humidity</span> <span className="font-bold text-slate-800 ml-1">{weatherSummary?.avg_humidity ?? '—'}%</span></div>
              </div>
              <div className="overflow-x-auto max-h-64">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs text-slate-500 uppercase">
                      <th className="py-2 pr-3">Date</th>
                      <th className="py-2 pr-3">Temp</th>
                      <th className="py-2 pr-3">Condition</th>
                      <th className="py-2 pr-3">Rain</th>
                    </tr>
                  </thead>
                  <tbody>
                    {weatherDays.length === 0 ? (
                      <tr><td colSpan="4" className="py-4 text-slate-500">No weather records stored for this season window.</td></tr>
                    ) : weatherDays.map((w) => (
                      <tr key={w.date} className="border-b border-slate-100">
                        <td className="py-2 pr-3 text-slate-700">{w.date}</td>
                        <td className="py-2 pr-3 text-slate-700">{w.temperature}°C</td>
                        <td className="py-2 pr-3 text-slate-700">{w.condition || '—'}</td>
                        <td className="py-2 pr-3 text-slate-700">{w.precipitation ?? 0} mm</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Growth forecast: ABW curve + harvest + recommendations */}
          {growthForecast && (
            <div className="glass-card p-6 rounded-2xl space-y-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-slate-800">📈 Growth Forecast</h3>
                  <p className="text-xs text-slate-500 mt-1">
                    Day-by-day ABW from feed + weather + water quality modifiers
                    {growthForecast.meta?.model_version ? ` · ${growthForecast.meta.model_version}` : ''}
                  </p>
                </div>
                <div className="flex flex-wrap gap-3 text-sm">
                  <div className="bg-sky-50 border border-sky-100 rounded-xl px-3 py-2">
                    <div className="text-xs text-sky-600">Predicted harvest</div>
                    <div className="font-bold text-sky-900">{Number(growthForecast.predicted_harvest_kg || 0).toFixed(0)} kg</div>
                  </div>
                  {growthForecast.actual_harvest_kg != null && (
                    <div className="bg-emerald-50 border border-emerald-100 rounded-xl px-3 py-2">
                      <div className="text-xs text-emerald-600">Actual harvest</div>
                      <div className="font-bold text-emerald-900">{Number(growthForecast.actual_harvest_kg).toFixed(0)} kg</div>
                    </div>
                  )}
                  <div className="bg-slate-50 border border-slate-100 rounded-xl px-3 py-2">
                    <div className="text-xs text-slate-500">Final ABW</div>
                    <div className="font-bold text-slate-800">{growthForecast.final_abw_g ?? '—'} g</div>
                  </div>
                  <div className="bg-slate-50 border border-slate-100 rounded-xl px-3 py-2">
                    <div className="text-xs text-slate-500">Sampling points</div>
                    <div className="font-bold text-slate-800">{growthForecast.meta?.sampling_points ?? 0}</div>
                  </div>
                </div>
              </div>

              {growthAbwChart ? (
                <div className="h-72">
                  <Line data={growthAbwChart} options={growthChartOptions} />
                </div>
              ) : (
                <p className="text-sm text-slate-500">No ABW series for this season.</p>
              )}

              <div>
                <h4 className="text-sm font-semibold text-slate-700 mb-2">Recommendations</h4>
                <div className="grid gap-2 sm:grid-cols-2">
                  {(growthForecast.recommendations || []).length === 0 ? (
                    <p className="text-sm text-slate-500">No recommendations generated.</p>
                  ) : growthForecast.recommendations.map((rec, i) => (
                    <div
                      key={i}
                      className={`text-sm rounded-xl border px-3 py-2 ${
                        rec.type === 'critical'
                          ? 'border-red-200 bg-red-50 text-red-800'
                          : rec.type === 'warning'
                            ? 'border-amber-200 bg-amber-50 text-amber-900'
                            : 'border-slate-200 bg-slate-50 text-slate-700'
                      }`}
                    >
                      {rec.message}
                    </div>
                  ))}
                </div>
              </div>

              {Array.isArray(growthForecast.feature_table_preview) && growthForecast.feature_table_preview.length > 0 && (
                <details className="text-sm">
                  <summary className="cursor-pointer text-slate-600 font-medium">
                    Daily feature table preview ({growthForecast.feature_table_days || 0} days)
                  </summary>
                  <div className="overflow-x-auto mt-2 max-h-56">
                    <table className="min-w-full text-xs">
                      <thead>
                        <tr className="border-b border-slate-200 text-left text-slate-500 uppercase">
                          <th className="py-1 pr-2">Date</th>
                          <th className="py-1 pr-2">DOC</th>
                          <th className="py-1 pr-2">Feed kg</th>
                          <th className="py-1 pr-2">Wx °C</th>
                          <th className="py-1 pr-2">Rain</th>
                          <th className="py-1 pr-2">WQ</th>
                          <th className="py-1 pr-2">ABW pred</th>
                          <th className="py-1 pr-2">ABW obs</th>
                        </tr>
                      </thead>
                      <tbody>
                        {growthForecast.feature_table_preview.map((r) => (
                          <tr key={r.date} className="border-b border-slate-100">
                            <td className="py-1 pr-2">{r.date}</td>
                            <td className="py-1 pr-2">{r.doc}</td>
                            <td className="py-1 pr-2">{r.feed_kg ?? '—'}</td>
                            <td className="py-1 pr-2">{r.weather_temperature ?? '—'}</td>
                            <td className="py-1 pr-2">{r.weather_precipitation_mm ?? '—'}</td>
                            <td className="py-1 pr-2">{r.wq_class ?? '—'}</td>
                            <td className="py-1 pr-2">{r.abw_predicted}</td>
                            <td className="py-1 pr-2">{r.abw_observed ?? '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              )}
            </div>
          )}

          <div className="glass-card p-6 rounded-2xl">
            <h3 className="text-lg font-semibold text-slate-800 mb-3">📅 Season Daily Data</h3>
            <p className="text-xs text-slate-500 mb-3">
              Sensors, weather, feed, harvest, and shrimp quantity (blank when not recorded that day).
            </p>
            <div className="overflow-x-auto max-h-96">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs text-slate-500 uppercase sticky top-0 bg-white">
                    <th className="py-2 pr-3">Date</th>
                    <th className="py-2 pr-3">Shrimp qty</th>
                    <th className="py-2 pr-3">Avg wt (g)</th>
                    <th className="py-2 pr-3">Temp</th>
                    <th className="py-2 pr-3">pH</th>
                    <th className="py-2 pr-3">Turbidity</th>
                    <th className="py-2 pr-3">TDS</th>
                    <th className="py-2 pr-3">Feed (kg)</th>
                    <th className="py-2 pr-3">Harvest (kg)</th>
                  </tr>
                </thead>
                <tbody>
                  {dailyRows.length === 0 ? (
                    <tr>
                      <td colSpan="9" className="py-4 text-slate-500">
                        No daily rows yet. Regenerate this seasonal report after saving growth / sensor data.
                      </td>
                    </tr>
                  ) : dailyRows.map((r) => (
                    <tr key={r.date} className="border-b border-slate-100">
                      <td className="py-2 pr-3 text-slate-700 whitespace-nowrap">{r.date}</td>
                      <td className="py-2 pr-3 text-slate-700">
                        {r.shrimp_count != null && r.shrimp_count !== ''
                          ? Number(r.shrimp_count).toLocaleString()
                          : ''}
                      </td>
                      <td className="py-2 pr-3 text-slate-700">
                        {r.avg_weight_grams != null && r.avg_weight_grams !== '' ? r.avg_weight_grams : ''}
                      </td>
                      <td className="py-2 pr-3 text-slate-700">
                        {r.avg_temperature != null ? r.avg_temperature : ''}
                      </td>
                      <td className="py-2 pr-3 text-slate-700">{r.avg_ph != null ? r.avg_ph : ''}</td>
                      <td className="py-2 pr-3 text-slate-700">
                        {r.avg_turbidity != null ? r.avg_turbidity : ''}
                      </td>
                      <td className="py-2 pr-3 text-slate-700">{r.avg_tds != null ? r.avg_tds : ''}</td>
                      <td className="py-2 pr-3 text-slate-700">
                        {r.feed_kg != null ? r.feed_kg : (r.feed_grams != null ? (r.feed_grams / 1000).toFixed(3) : '')}
                      </td>
                      <td className="py-2 pr-3 text-slate-700">
                        {r.harvest_kg != null ? r.harvest_kg : ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="glass-card p-6 rounded-2xl">
            <h3 className="text-lg font-semibold text-slate-800 mb-3">🍤 Feeding Logs</h3>
            <div className="flex flex-wrap gap-4 mb-4 text-sm">
              <div><span className="text-slate-500">Days / events</span> <span className="font-bold text-slate-800 ml-1">{feedingSummary.total_events ?? 0}</span></div>
              <div>
                <span className="text-slate-500">Total feed</span>{' '}
                <span className="font-bold text-slate-800 ml-1">
                  {feedingSummary.total_kg != null
                    ? `${Number(feedingSummary.total_kg).toFixed(1)} kg`
                    : `${Number(feedingSummary.total_grams || 0).toFixed(0)} g`}
                </span>
              </div>
              {feedingSummary.source && (
                <div className="text-xs text-slate-400 w-full">Source: pond feed sheets ({feedingSummary.source})</div>
              )}
            </div>
            <div className="overflow-x-auto max-h-72">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs text-slate-500 uppercase">
                    <th className="py-2 pr-3">Date / Time</th>
                    <th className="py-2 pr-3">Type</th>
                    <th className="py-2 pr-3">Portion</th>
                    <th className="py-2 pr-3">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {feedingLogs.length === 0 ? (
                    <tr><td colSpan="4" className="py-4 text-slate-500">No feeding logs in this season window.</td></tr>
                  ) : feedingLogs.map((log) => (
                    <tr key={log.id} className="border-b border-slate-100">
                      <td className="py-2 pr-3 text-slate-700">
                        {log.feed_type === 'pond_record'
                          ? (log.timestamp || '').slice(0, 10)
                          : new Date(log.timestamp).toLocaleString()}
                      </td>
                      <td className="py-2 pr-3 text-slate-700">{(log.feed_type || '').replace(/_/g, ' ')}</td>
                      <td className="py-2 pr-3 text-slate-700">
                        {log.portion_kg != null ? `${log.portion_kg} kg` : `${log.portion_grams} g`}
                      </td>
                      <td className="py-2 pr-3 text-slate-500">{log.notes || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ═══ Section D: Insights Panel ═══ */}
      {insights.length > 0 && (
        <div className="glass-card p-6 rounded-2xl">
          <h2 className="text-xl font-semibold text-slate-800 mb-4 flex items-center gap-2">💡 Insights</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {insights.map((ins, i) => (
              <div key={i} className={`border rounded-xl p-4 ${insightColor(ins.type)}`}>
                <div className="flex items-start gap-2">
                  <span className="text-lg">{insightIcon(ins.type)}</span>
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider">{ins.parameter?.replace(/_/g, ' ')}</span>
                    <p className="text-sm mt-0.5 opacity-90">{ins.message}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═══ Section E: Sensor Data Table ═══ */}
      <div className="glass-card p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h3 className="text-lg font-semibold text-slate-800">{t('historicalReadings')}</h3>
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-600 whitespace-nowrap">Show</label>
              <input
                type="number"
                min={1}
                max={200}
                value={customPageSizeInput}
                onChange={(e) => setCustomPageSizeInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') applyCustomPageSize() }}
                className="input-field text-sm px-3 py-2 rounded-xl w-20"
                title="How many readings to show per page"
              />
              <button
                type="button"
                onClick={applyCustomPageSize}
                className="px-3 py-2 text-sm bg-cyan-600 hover:bg-cyan-700 text-white rounded-xl"
              >
                Apply
              </button>
              <span className="text-xs text-slate-500">rows</span>
            </div>
            <DatePickerField
              value={dateSearch}
              onChange={(e) => { setDateSearch(e.target.value); setCurrentPage(1) }}
            />
            {dateSearch && (
              <button onClick={() => { setDateSearch(''); setCurrentPage(1) }} className="px-3 py-2 text-sm text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors">
                {t('clear')}
              </button>
            )}
            <span className="text-sm text-slate-500">
              {dateSearch ? `${filteredData.length} ${filteredData.length === 1 ? t('reading') : t('readings')} ${t('found')}` : `${sensorTotalCount} ${t('readings')} ${t('total')}`}
            </span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Date</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">{t('temperature')} (°C)</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">{t('phLevel')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Turbidity (NTU)</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">TDS (ppm)</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">{t('status')}</th>
              </tr>
            </thead>
            <tbody>
              {historicalData.length === 0 ? (
                <tr><td colSpan="6" className="px-4 py-8 text-center text-slate-500">{dateSearch ? t('noReadingsFound') : t('noReadingsAvailable')}</td></tr>
              ) : historicalData.map((row, index) => (
                <tr key={index} className="reports-history-row">
                  <td className="px-4 py-3 text-sm text-slate-700"><div>{row.date}</div><div className="text-xs text-slate-500">{row.time}</div></td>
                  <td className="px-4 py-3 text-sm text-slate-700">{row.temperature}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{row.ph}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{row.turb}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{row.tds}</td>
                  <td className="px-4 py-3"><span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(row.status)}`}>{row.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {sensorTotalPages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-200 px-4 py-4 mt-2">
            <div className="text-sm text-slate-600">
              {t('showing')} {((currentPage - 1) * itemsPerPage) + 1}–{Math.min(currentPage * itemsPerPage, sensorTotalCount)} {t('of')} {sensorTotalCount} {t('readings')}
            </div>
            <div className="flex items-center space-x-1">
              <button onClick={() => fetchData(1)} disabled={currentPage === 1}
                className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">««</button>
              <button onClick={() => fetchData(Math.max(currentPage - 1, 1))} disabled={currentPage === 1}
                className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">‹</button>
              {Array.from({ length: sensorTotalPages }, (_, i) => i + 1)
                .filter(page => { if (sensorTotalPages <= 7) return true; if (page === 1 || page === sensorTotalPages) return true; return Math.abs(page - currentPage) <= 1 })
                .reduce((acc, page, idx, arr) => { if (idx > 0 && page - arr[idx - 1] > 1) acc.push('...'); acc.push(page); return acc }, [])
                .map((page, idx) => page === '...'
                  ? <span key={`e-${idx}`} className="px-2 py-1.5 text-sm text-slate-400">…</span>
                  : <button key={page} onClick={() => fetchData(page)}
                    className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${currentPage === page ? 'bg-cyan-600 text-white border-cyan-600' : 'border-slate-300 text-slate-600 hover:bg-slate-100'}`}>{page}</button>
                )}
              <button onClick={() => fetchData(Math.min(currentPage + 1, sensorTotalPages))} disabled={currentPage === sensorTotalPages}
                className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">›</button>
              <button onClick={() => fetchData(sensorTotalPages)} disabled={currentPage === sensorTotalPages}
                className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">»»</button>
            </div>
          </div>
        )}
      </div>

      {/* ═══ Section F: Report History ═══ */}
      <div className="glass-card p-6 rounded-2xl">
        <h2 className="text-xl font-semibold text-slate-800 mb-4 flex items-center gap-2">🗂️ Report History</h2>
        {reportHistory.length === 0 ? (
          <p className="text-slate-500 text-sm">No reports generated yet. Use the buttons above to create one.</p>
        ) : (
          <>
            <div className="space-y-2">
              {reportHistory.map(r => (
                <div key={r.id} className={`flex items-center justify-between p-3 rounded-xl border transition-all ${activeReport?.id === r.id ? 'border-cyan-500/50 bg-cyan-50' : 'border-slate-200 hover:border-slate-300 bg-slate-50'}`}>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-slate-800 truncate">{r.title}</div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {r.report_type} &middot; {r.status}
                      {r.generated_at && <> &middot; {new Date(r.generated_at).toLocaleDateString()}</>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 ml-3 flex-shrink-0">
                    <button onClick={() => handleViewReport(r.id)} title="View"
                      className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors text-sm">👁️</button>
                    <button onClick={() => handleHistoryExcel(r.id)} title="Export Excel"
                      className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors text-sm">📊</button>
                    <button onClick={() => handleHistoryPdf(r.id)} title="Export PDF"
                      className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors text-sm">📄</button>
                    <button onClick={() => openEmailModal(r.id)} title="Email"
                      className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors text-sm">📧</button>
                    <button onClick={() => handleDeleteReport(r)} title="Delete"
                      className="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors text-sm">🗑️</button>
                  </div>
                </div>
              ))}
            </div>
            {/* Report History Pagination */}
            {(() => {
              const rTotalPages = Math.ceil(reportTotalCount / REPORTS_PER_PAGE); return rTotalPages > 1 ? (
                <div className="flex items-center justify-between border-t border-slate-200 px-2 py-4 mt-3">
                  <div className="text-sm text-slate-600">
                    {((reportPage - 1) * REPORTS_PER_PAGE) + 1}–{Math.min(reportPage * REPORTS_PER_PAGE, reportTotalCount)} of {reportTotalCount} reports
                  </div>
                  <div className="flex items-center space-x-1">
                    <button onClick={() => loadReportHistory(1)} disabled={reportPage === 1}
                      className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">««</button>
                    <button onClick={() => loadReportHistory(Math.max(reportPage - 1, 1))} disabled={reportPage === 1}
                      className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">‹</button>
                    {Array.from({ length: rTotalPages }, (_, i) => i + 1)
                      .filter(p => { if (rTotalPages <= 7) return true; if (p === 1 || p === rTotalPages) return true; return Math.abs(p - reportPage) <= 1 })
                      .reduce((acc, p, idx, arr) => { if (idx > 0 && p - arr[idx - 1] > 1) acc.push('...'); acc.push(p); return acc }, [])
                      .map((p, idx) => p === '...'
                        ? <span key={`re-${idx}`} className="px-2 py-1.5 text-sm text-slate-400">…</span>
                        : <button key={p} onClick={() => loadReportHistory(p)}
                          className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${reportPage === p ? 'bg-cyan-600 text-white border-cyan-600' : 'border-slate-300 text-slate-600 hover:bg-slate-100'}`}>{p}</button>
                      )}
                    <button onClick={() => loadReportHistory(Math.min(reportPage + 1, rTotalPages))} disabled={reportPage === rTotalPages}
                      className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">›</button>
                    <button onClick={() => loadReportHistory(rTotalPages)} disabled={reportPage === rTotalPages}
                      className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">»»</button>
                  </div>
                </div>
              ) : null
            })()}
          </>
        )}
      </div>

      {/* ═══ Seasonal Season Picker Modal ═══ */}
      {seasonModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setSeasonModalOpen(false)}>
          <div className="glass-card p-6 rounded-2xl w-full max-w-md mx-4 space-y-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-slate-800 flex items-center gap-2">🦐 Select Season</h3>
            <p className="text-sm text-slate-600">
              Seasonal report includes sensors, weather, feeding logs, and harvest for the selected season.
            </p>
            {seasons.length === 0 ? (
              <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-xl p-3">
                No seasons found. Create a season in History Overview first.
              </p>
            ) : (
              <div>
                <label className="block text-sm text-slate-600 mb-1">Season</label>
                <select
                  value={selectedSeasonId}
                  onChange={(e) => setSelectedSeasonId(e.target.value)}
                  className="input-field w-full px-4 py-2.5 rounded-xl text-sm"
                >
                  {seasons.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.start_date} → {s.end_date || 'active'}){s.is_active ? ' • active' : ''}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="flex justify-end gap-3 pt-2">
              <button onClick={() => setSeasonModalOpen(false)} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-sm transition-all">
                Cancel
              </button>
              <button
                onClick={handleGenerateSeasonal}
                disabled={generating || !selectedSeasonId || seasons.length === 0}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {generating ? <><span className="animate-spin">⏳</span> Generating…</> : 'Generate Seasonal Report'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ Section G: Email Modal ═══ */}
      {emailModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={closeEmailModal}>
          <div className="glass-card p-6 rounded-2xl w-full max-w-md mx-4 space-y-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-slate-800 flex items-center gap-2">📧 Email Report</h3>
            <div>
              <label className="block text-sm text-slate-600 mb-1">Recipient Email</label>
              <input type="email" value={emailAddress} onChange={e => setEmailAddress(e.target.value)}
                placeholder="example@email.com"
                className="input-field w-full px-4 py-2.5 rounded-xl text-sm" />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button onClick={closeEmailModal} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-sm transition-all">Cancel</button>
              <button onClick={handleSendEmail} disabled={emailSending || !emailAddress}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-xl text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2">
                {emailSending ? <><span className="animate-spin">⏳</span> Sending…</> : 'Send Report'}
              </button>
            </div>
          </div>
        </div>
      )}

      {pendingDelete ? (
        <div className="aq-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="delete-report-title">
          <div className="card aq-modal">
            <h3 id="delete-report-title" className="text-lg font-semibold mb-2">Delete report</h3>
            <p className="text-sm text-cyan-100/80 mb-4">
              Are you sure you want to delete this report? This cannot be undone.
            </p>
            <p className="text-xs text-cyan-200/60 mb-5">{pendingDelete.title}</p>
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-secondary" onClick={() => setPendingDelete(null)} disabled={deleting}>
                Cancel
              </button>
              <button type="button" className="btn-modern" onClick={confirmDeleteReport} disabled={deleting}>
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

export default Reports
