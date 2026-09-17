import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import LanguageToggle from './LanguageToggle'
import { fetchAlertSummary } from '../services/alerts'
import { alertWebSocket } from '../services/alertWebSocket'

const Sidebar = () => {
  const location = useLocation()
  const navigate = useNavigate()
  const { t } = useLanguage()
  const [alertCount, setAlertCount] = useState(0)

  const menuItems = [
    { path: '/dashboard', labelKey: 'navDashboard', icon: '📊' },
    { path: '/weather', labelKey: 'navWeather', icon: '🌤️' },
    { path: '/feeding', labelKey: 'navFeeding', icon: '🍤' },
    { path: '/reports', labelKey: 'navReports', icon: '📈' },
    { path: '/history', labelKey: 'navHistory', icon: '📋' },
    { path: '/growth-dashboard', label: '🚀 Growth Dashboard', icon: '📈' },
    { path: '/growth-settings', label: '⚙️ Growth Settings', icon: '⚙️' },
    { path: '/alerts', labelKey: 'navAlerts', icon: '⚠️', showBadge: true },
    { path: '/settings', labelKey: 'navSettings', icon: '⚙️' },
    { path: '/about', labelKey: 'navAbout', icon: 'ℹ️' },
  ]

  const refreshAlertBadge = async () => {
    try {
      // Badge only — offline checks run on Dashboard /sensors/latest, not every 15s here
      const summary = await fetchAlertSummary()
      setAlertCount(Number(summary?.total) || 0)
    } catch (err) {
      console.warn('Failed to refresh alert badge:', err)
    }
  }

  useEffect(() => {
    refreshAlertBadge()
    const id = setInterval(refreshAlertBadge, 15_000)
    const onAlertsChanged = () => refreshAlertBadge()
    window.addEventListener('alerts-changed', onAlertsChanged)
    return () => {
      clearInterval(id)
      window.removeEventListener('alerts-changed', onAlertsChanged)
    }
  }, [location.pathname])

  // Browser notifications for EVERY alert, on any page (not only Alerts tab)
  useEffect(() => {
    if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
      Notification.requestPermission().catch(() => {})
    }
    const onAlertPush = (data) => {
      const alert = data?.alert || data?.data?.alert
      if (!alert) return
      window.dispatchEvent(new Event('alerts-changed'))
      if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
        const sev = (alert.severity || 'warning').toUpperCase()
        const param = alert.parameter || 'sensor'
        try {
          new Notification(`${sev}: ${param}`, {
            body: alert.message || 'New pond alert',
            tag: `alert-${alert.id || param}`,
          })
        } catch (e) {
          console.warn('Browser notification failed:', e)
        }
      }
    }
    alertWebSocket.connect(onAlertPush)
    return () => {
      alertWebSocket.disconnect(onAlertPush)
    }
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    navigate('/login')
  }

  return (
    <div className="w-72 glass-card m-4 rounded-2xl flex flex-col h-[calc(100vh-2rem)] overflow-hidden">
      {/* Header with Shrimp Image Background */}
      <div className="relative p-6 overflow-hidden">
        <div
          className="absolute inset-0 bg-cover bg-center opacity-10"
          style={{ backgroundImage: "url('/shrimp_pond_pic/vannamei-shrimp-Pacific-white-shrimp.avif')" }}
        ></div>
        <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 to-cyan-600/20"></div>

        <div className="relative z-10">
          <div className="flex items-center mb-4">
            <div className="w-12 h-12 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-xl flex items-center justify-center shadow-lg animate-pulse-glow">
              <span className="text-2xl">🦐</span>
            </div>
            <div className="ml-3">
              <h1 className="text-xl font-bold text-white text-shadow">Smart Shrimp</h1>
              <p className="text-cyan-100 text-sm">{t('aiMonitoring')}</p>
            </div>
          </div>
          <div className="h-px bg-gradient-to-r from-transparent via-cyan-300 to-transparent"></div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6">
        <ul className="space-y-2">
          {menuItems.map((item) => {
            const isActive =
              location.pathname === item.path ||
              (item.path === '/dashboard' && location.pathname === '/')
            const showCount = item.showBadge && alertCount > 0

            return (
              <li key={item.path}>
                <Link
                  to={item.path}
                  className={`group flex items-center px-4 py-3 rounded-xl transition-all duration-300 ${
                    isActive
                      ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/20 text-white shadow-lg border border-cyan-400/30'
                      : 'text-slate-300 hover:bg-white/10 hover:text-white hover:translate-x-1'
                  }`}
                >
                  <span className="text-xl mr-3 group-hover:scale-110 transition-transform duration-200">
                    {item.icon}
                  </span>
                  <span className="font-medium">{item.label || t(item.labelKey)}</span>
                  {showCount ? (
                    <span className="ml-auto min-w-[1.25rem] h-5 px-1.5 rounded-full bg-red-500 text-white text-xs font-bold flex items-center justify-center shadow">
                      {alertCount > 99 ? '99+' : alertCount}
                    </span>
                  ) : isActive ? (
                    <div className="ml-auto w-2 h-2 bg-cyan-400 rounded-full animate-pulse"></div>
                  ) : null}
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

      {/* Language Toggle */}
      <div className="px-4 pb-2">
        <LanguageToggle />
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-white/10">
        <button
          onClick={handleLogout}
          className="w-full flex items-center px-4 py-3 text-slate-300 hover:bg-red-500/20 hover:text-white rounded-xl transition-all duration-300 group"
        >
          <span className="text-xl mr-3 group-hover:rotate-180 transition-transform duration-300">🚪</span>
          <span className="font-medium">{t('signOut')}</span>
        </button>
      </div>
    </div>
  )
}

export default Sidebar
