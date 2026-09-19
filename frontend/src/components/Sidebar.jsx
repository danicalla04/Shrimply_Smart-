import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import { fetchAlertSummary } from '../services/alerts'
import { alertWebSocket } from '../services/alertWebSocket'

const MENU = [
  { path: '/dashboard', label: 'Dashboard', icon: '📡' },
  { path: '/ponds', label: 'Ponds', icon: '🌊' },
  { path: '/water-quality', label: 'Water Quality', icon: '💧' },
  { path: '/feeding', label: 'Feeding', icon: '🍤' },
  { path: '/weather', label: 'Weather', icon: '🌦️' },
  { path: '/analytics', label: 'Analytics', icon: '📈' },
  { path: '/reports', label: 'Reports', icon: '📑' },
  { path: '/alerts', label: 'Alerts', icon: '🚨', badge: true },
  { path: '/settings', label: 'Settings', icon: '⚙️' },
]

const Sidebar = ({ open, collapsed, onToggle, onNavigate }) => {
  const location = useLocation()
  const navigate = useNavigate()
  const { t } = useLanguage()
  const [alertCount, setAlertCount] = useState(0)

  const refreshAlertBadge = async () => {
    try {
      const summary = await fetchAlertSummary()
      setAlertCount(Number(summary?.total) || 0)
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    refreshAlertBadge()
    const id = setInterval(refreshAlertBadge, 15_000)
    window.addEventListener('alerts-changed', refreshAlertBadge)
    return () => {
      clearInterval(id)
      window.removeEventListener('alerts-changed', refreshAlertBadge)
    }
  }, [location.pathname])

  useEffect(() => {
    if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
      Notification.requestPermission().catch(() => {})
    }
    const onAlertPush = (data) => {
      const alert = data?.alert || data?.data?.alert
      if (!alert) return
      window.dispatchEvent(new Event('alerts-changed'))
      if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
        try {
          new Notification(`${(alert.severity || 'warning').toUpperCase()}: ${alert.parameter || 'sensor'}`, {
            body: alert.message || 'New pond alert',
            tag: `alert-${alert.id || alert.parameter}`,
          })
        } catch { /* ignore */ }
      }
    }
    alertWebSocket.connect(onAlertPush)
    return () => alertWebSocket.disconnect(onAlertPush)
  }, [])

  const logout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    navigate('/login')
  }

  return (
    <aside className={`aq-sidebar ${open ? 'is-open' : ''} ${collapsed ? 'is-collapsed' : ''}`}>
      <div className="aq-brand">
        <div className="aq-logo">
          <img src="/shrimply-logo.jpg" alt="" />
        </div>
        <div className="aq-brand-copy">
          <h1>SHRIMPLY SMART</h1>
          <p>Aqua Command</p>
        </div>
        <button type="button" className="aq-collapse-btn" onClick={onToggle} aria-label={collapsed ? 'Expand menu' : 'Collapse menu'}>
          {collapsed ? '›' : '‹'}
        </button>
      </div>
      <nav className="aq-nav">
        {MENU.map((item) => {
          const active =
            location.pathname === item.path ||
            (item.path === '/weather' && location.pathname.startsWith('/weather')) ||
            (item.path === '/analytics' && location.pathname.startsWith('/growth')) ||
            (item.path === '/ponds' && location.pathname.startsWith('/history'))
          return (
            <Link
              key={item.path}
              to={item.path}
              className={active ? 'is-active' : ''}
              title={item.label}
              onClick={onNavigate}
            >
              <span className="aq-nav-ico">{item.icon}</span>
              <span className="aq-nav-label">{item.label}</span>
              {item.badge && alertCount > 0 ? (
                <span className="aq-badge">{alertCount > 99 ? '99+' : alertCount}</span>
              ) : null}
            </Link>
          )
        })}
      </nav>
      <div className="aq-side-foot">
        <button type="button" className="aq-ghost danger" onClick={logout} title={t('signOut')}>
          <span>⎋</span>
          <span className="aq-nav-label">{t('signOut')}</span>
        </button>
      </div>
    </aside>
  )
}

export default Sidebar
