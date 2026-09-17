import { useEffect, useMemo, useState } from 'react'
import AlertCard from '../components/AlertCard'
import { useLanguage } from '../context/LanguageContext'
import { fetchAlerts, resolveAlert, resolveAllAlerts } from '../services/alerts'

const PARAM_LABELS = {
  temperature: 'Temperature',
  ph: 'pH',
  turbidity: 'Turbidity',
  tds: 'TDS',
  sensor_offline: 'Sensors Offline',
  feeder_connection: 'Ultrasonic / Feeder',
  feeder_capacity: 'Feeder Capacity',
  feeder_level: 'Feeder Level',
}

function alertTitle(alert) {
  const param = alert?.parameter || 'sensor'
  const label = PARAM_LABELS[param] || param
  const sev = (alert?.severity || 'warning').toUpperCase()
  return `${sev} · ${label}`
}
import { getThresholds } from '../services/settings'
import { fetchLatestSensors } from '../services/sensors'
import { getFeederState, capacityPercent } from '../services/feeder'
import { alertWebSocket } from '../services/alertWebSocket'

const Alert = () => {
  const { t } = useLanguage()
  const [alerts, setAlerts] = useState([])
  const thresholds = useMemo(() => getThresholds(), [])

  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const ALERTS_PER_PAGE = 20

  // Fetch alerts from backend (paginated)
  const loadAlerts = async (page = 1) => {
    try {
      const data = await fetchAlerts(page, ALERTS_PER_PAGE)
      const results = Array.isArray(data.results) ? data.results : []
      setTotalCount(data.count || 0)
      setCurrentPage(page)
      setAlerts(results.map(alert => ({
        id: alert.id,
        title: alertTitle(alert),
        message: alert.message,
        type: alert.severity === 'high' || alert.severity === 'critical' ? 'critical' : 'warning',
        timestamp: new Date(alert.timestamp).toLocaleString(),
        isRead: alert.resolved,
      })))
    } catch (error) {
      console.error('Failed to fetch alerts:', error)
      // Fallback to local alerts
      generateLocalAlerts()
    }
  }

  // Handle new alert from WebSocket
  const handleNewAlert = (data) => {
    console.log('[ALERT_PAGE] Received new alert via WebSocket:', data)

    if (data.alert) {
      const newAlert = {
        id: data.alert.id,
        title: alertTitle(data.alert),
        message: data.alert.message,
        type: data.alert.severity === 'high' || data.alert.severity === 'critical' ? 'critical' : 'warning',
        timestamp: new Date(data.alert.timestamp).toLocaleString(),
        isRead: data.alert.resolved,
      }

      // Add to top of alerts list
      setAlerts(prev => [newAlert, ...prev])
      setTotalCount(prev => prev + 1)
      window.dispatchEvent(new Event('alerts-changed'))

      // Show browser notification if supported
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('🚨 New Alert', {
          body: `${data.alert.parameter}: ${data.alert.message}`,
          icon: '/alert-icon.png'
        })
      }
    }
  }

  // Connect to WebSocket on mount
  useEffect(() => {
    console.log('[ALERT_PAGE] Connecting to alert WebSocket...')
    alertWebSocket.connect(handleNewAlert)

    return () => {
      alertWebSocket.disconnect(handleNewAlert)
    }
  }, [])

  useEffect(() => { loadAlerts(1) }, [])

  useEffect(() => {
    fetchLatestSensors().catch(() => null)
  }, [])

  // Generate local alerts as fallback
  const generateLocalAlerts = async () => {
    try {
      const sensors = await fetchLatestSensors()
      const feeder = getFeederState()
      const now = new Date()
      const ts = now.toLocaleString()

      const list = []
      const pushAlert = (key, label, unit, value) => {
        const range = thresholds[key]
        if (!range) return
        if (value < range.min) {
          list.push({
            id: `${key}-low-${now.getTime()}`,
            title: `${label} Low`,
            message: `${label} is low at ${value}${unit}. Normal range is ${range.min}–${range.max} ${unit}.`,
            type: 'warning',
            timestamp: ts,
            isRead: false,
          })
        } else if (value > range.max) {
          list.push({
            id: `${key}-high-${now.getTime()}`,
            title: `${label} High`,
            message: `${label} is high at ${value}${unit}. Normal range is ${range.min}–${range.max} ${unit}.`,
            type: 'critical',
            timestamp: ts,
            isRead: false,
          })
        }
      }

      pushAlert('temperature', 'Temperature', '°C', Number(sensors.temperature.toFixed ? sensors.temperature.toFixed(1) : sensors.temperature))
      pushAlert('ph', 'pH Level', '', Number(sensors.ph.toFixed ? sensors.ph.toFixed(1) : sensors.ph))
      pushAlert('turbidity', 'Turbidity', ' NTU', Number(sensors.turbidity.toFixed ? sensors.turbidity.toFixed(1) : sensors.turbidity))
      pushAlert('tds', 'TDS', ' ppm', Number(sensors.tds))

      // Feeder capacity alert
      const pct = capacityPercent(feeder)
      if (pct <= feeder.lowPercent) {
        list.push({
          id: `feeder-low-${now.getTime()}`,
          title: pct === 0 ? 'Feeder Empty' : 'Feeder Low',
          message: pct === 0
            ? `Feeder is empty. Refill to resume feeding.`
            : `Feeder capacity low at ${pct}%. Consider refilling soon (max ${feeder.capacityMax} g).`,
          type: pct === 0 ? 'critical' : 'warning',
          timestamp: ts,
          isRead: false,
        })
      }

      setAlerts(list)
    } catch (error) {
      console.error('Failed to generate local alerts:', error)
    }
  }

  const [filter, setFilter] = useState('all')

  const handleMarkAsRead = async (id) => {
    try {
      await resolveAlert(id)
      setAlerts(alerts.map(alert =>
        alert.id === id ? { ...alert, isRead: true } : alert
      ))
      window.dispatchEvent(new Event('alerts-changed'))
    } catch (error) {
      console.error('Failed to resolve alert:', error)
    }
  }

  const handleDismissAlert = (id) => {
    setAlerts(alerts.filter(alert => alert.id !== id))
  }

  const handleMarkAllAsRead = async () => {
    try {
      await resolveAllAlerts()
      setAlerts(alerts.map(alert => ({ ...alert, isRead: true })))
      window.dispatchEvent(new Event('alerts-changed'))
    } catch (error) {
      console.error('Failed to resolve all alerts:', error)
    }
  }

  const filteredAlerts = alerts.filter(alert => {
    if (filter === 'all') return true
    if (filter === 'unread') return !alert.isRead
    return alert.type === filter
  })

  const unreadCount = alerts.filter(alert => !alert.isRead).length
  // Counts include acknowledged items of that severity so Critical/Warning tabs match the list
  const criticalCount = alerts.filter(alert => alert.type === 'critical').length
  const warningCount = alerts.filter(alert => alert.type === 'warning').length
  const unreadCritical = alerts.filter(alert => alert.type === 'critical' && !alert.isRead).length
  const unreadWarning = alerts.filter(alert => alert.type === 'warning' && !alert.isRead).length

  return (
    <div className="p-6">
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">{t('systemAlerts')}</h1>
            <p className="text-gray-600">{t('alertsSubtitle')}</p>
          </div>
          <div className="flex items-center space-x-4">
            <div className="text-right">
              <div className="text-2xl font-bold text-red-600">{unreadCount}</div>
              <div className="text-sm text-gray-600">{t('unreadAlerts')}</div>
            </div>
            <button
              onClick={handleMarkAllAsRead}
              className="btn-primary"
              disabled={unreadCount === 0}
            >
              {t('markAllAsRead')}
            </button>
          </div>
        </div>

        {/* Alert Summary */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="card-gradient border-red-200">
            <div className="flex items-center">
              <div className="p-3 bg-red-100 rounded-lg mr-4">
                <span className="text-2xl">🔴</span>
              </div>
              <div>
                <div className="text-2xl font-bold text-red-600">{unreadCritical}</div>
                <div className="text-sm text-gray-600">{t('criticalAlerts')}</div>
              </div>
            </div>
          </div>
          <div className="card-gradient border-yellow-200">
            <div className="flex items-center">
              <div className="p-3 bg-yellow-100 rounded-lg mr-4">
                <span className="text-2xl">🟡</span>
              </div>
              <div>
                <div className="text-2xl font-bold text-yellow-600">{unreadWarning}</div>
                <div className="text-sm text-gray-600">{t('warningAlerts')}</div>
              </div>
            </div>
          </div>
          <div className="card-gradient border-green-200">
            <div className="flex items-center">
              <div className="p-3 bg-green-100 rounded-lg mr-4">
                <span className="text-2xl">🟢</span>
              </div>
              <div>
                <div className="text-2xl font-bold text-green-600">
                  {alerts.filter(alert => alert.type === 'safe' && !alert.isRead).length}
                </div>
                <div className="text-sm text-gray-600">{t('safeStatus')}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="card mb-6">
        <div className="flex space-x-4">
          {[
            { value: 'all', label: t('allAlerts'), count: alerts.length },
            { value: 'unread', label: t('unread'), count: unreadCount },
            { value: 'critical', label: t('critical'), count: criticalCount },
            { value: 'warning', label: t('warning'), count: warningCount }
          ].map((filterOption) => (
            <button
              key={filterOption.value}
              onClick={() => setFilter(filterOption.value)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${filter === filterOption.value
                ? 'bg-primary-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
            >
              {filterOption.label} ({filterOption.count})
            </button>
          ))}
        </div>
      </div>

      {/* Alerts List */}
      <div className="space-y-4">
        {filteredAlerts.length === 0 ? (
          <div className="card text-center py-12">
            <div className="text-6xl mb-4">✅</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">{t('noAlertsFound')}</h3>
            <p className="text-gray-600">{t('allSensorsNormal')}</p>
          </div>
        ) : (
          filteredAlerts.map((alert) => (
            <AlertCard
              key={alert.id}
              title={alert.title}
              message={alert.message}
              type={alert.type}
              timestamp={alert.timestamp}
              isRead={alert.isRead}
              onMarkAsRead={() => handleMarkAsRead(alert.id)}
              onDismiss={() => handleDismissAlert(alert.id)}
            />
          ))
        )}
      </div>

      {/* Alerts Pagination */}
      {(() => {
        const alertTotalPages = Math.ceil(totalCount / ALERTS_PER_PAGE)
        return alertTotalPages > 1 ? (
          <div className="card mt-4">
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-500">
                Showing {((currentPage - 1) * ALERTS_PER_PAGE) + 1}–{Math.min(currentPage * ALERTS_PER_PAGE, totalCount)} of {totalCount} alerts
              </div>
              <div className="flex items-center space-x-1">
                <button onClick={() => loadAlerts(1)} disabled={currentPage === 1}
                  className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">««</button>
                <button onClick={() => loadAlerts(Math.max(currentPage - 1, 1))} disabled={currentPage === 1}
                  className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">‹</button>
                {Array.from({ length: alertTotalPages }, (_, i) => i + 1)
                  .filter(p => { if (alertTotalPages <= 7) return true; if (p === 1 || p === alertTotalPages) return true; return Math.abs(p - currentPage) <= 1 })
                  .reduce((acc, p, idx, arr) => { if (idx > 0 && p - arr[idx - 1] > 1) acc.push('...'); acc.push(p); return acc }, [])
                  .map((p, idx) => p === '...'
                    ? <span key={`ae-${idx}`} className="px-2 py-1.5 text-sm text-gray-400">…</span>
                    : <button key={p} onClick={() => loadAlerts(p)}
                      className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${currentPage === p ? 'bg-primary-600 text-white border-primary-600' : 'border-gray-300 text-gray-600 hover:bg-gray-100'}`}>{p}</button>
                  )}
                <button onClick={() => loadAlerts(Math.min(currentPage + 1, alertTotalPages))} disabled={currentPage === alertTotalPages}
                  className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">›</button>
                <button onClick={() => loadAlerts(alertTotalPages)} disabled={currentPage === alertTotalPages}
                  className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">»»</button>
              </div>
            </div>
          </div>
        ) : null
      })()}

      {/* Alert Guidelines */}
      <div className="card mt-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('alertGuidelines')}</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="p-4 bg-red-50 rounded-lg border border-red-200">
            <div className="flex items-center mb-2">
              <span className="text-2xl mr-2">🔴</span>
              <h4 className="font-semibold text-red-800">{t('criticalAlerts')}</h4>
            </div>
            <p className="text-sm text-red-600">
              {t('criticalAlertsDesc')}
            </p>
          </div>
          <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
            <div className="flex items-center mb-2">
              <span className="text-2xl mr-2">🟡</span>
              <h4 className="font-semibold text-yellow-800">{t('warningAlerts')}</h4>
            </div>
            <p className="text-sm text-yellow-600">
              {t('warningAlertsDesc')}
            </p>
          </div>
          <div className="p-4 bg-green-50 rounded-lg border border-green-200">
            <div className="flex items-center mb-2">
              <span className="text-2xl mr-2">🟢</span>
              <h4 className="font-semibold text-green-800">{t('safeStatus')}</h4>
            </div>
            <p className="text-sm text-green-600">
              {t('safeStatusDesc')}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Alert
