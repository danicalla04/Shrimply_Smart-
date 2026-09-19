import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import PageLoader from './PageLoader'
import { applyTheme, getStoredTheme } from '../services/theme'

const COLLAPSE_KEY = 'aq-sidebar-collapsed'

const DashboardLayout = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === '1'
    } catch {
      return false
    }
  })
  const [clock, setClock] = useState(() => new Date())
  const [theme, setTheme] = useState(() => getStoredTheme())
  const location = useLocation()
  const [routeLoading, setRouteLoading] = useState(true)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  useEffect(() => {
    const onTheme = (e) => {
      const next = e.detail
      if (next === 'light' || next === 'dark') setTheme(next)
    }
    window.addEventListener('aq-theme-changed', onTheme)
    return () => window.removeEventListener('aq-theme-changed', onTheme)
  }, [])

  useEffect(() => {
    const id = setInterval(() => setClock(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    setRouteLoading(true)
    const id = setTimeout(() => setRouteLoading(false), 600)
    return () => clearTimeout(id)
  }, [location.pathname])

  const toggleSidebar = () => {
    if (window.matchMedia('(max-width: 900px)').matches) {
      setMobileOpen((v) => !v)
      return
    }
    setCollapsed((v) => {
      const next = !v
      try {
        localStorage.setItem(COLLAPSE_KEY, next ? '1' : '0')
      } catch { /* ignore */ }
      return next
    })
  }

  const toggleTheme = () => {
    setTheme((current) => (current === 'light' ? 'dark' : 'light'))
  }

  return (
    <div className={`aq-shell ${mobileOpen ? 'nav-open' : ''} ${collapsed ? 'nav-collapsed' : ''}`}>
      {mobileOpen ? <button type="button" className="aq-overlay" aria-label="Close menu" onClick={() => setMobileOpen(false)} /> : null}
      <Sidebar
        open={mobileOpen}
        collapsed={collapsed}
        onToggle={toggleSidebar}
        onNavigate={() => setMobileOpen(false)}
      />

      <div className="aq-main">
        <div className="aq-bubbles" aria-hidden="true">
          {Array.from({ length: 16 }).map((_, i) => (
            <span
              key={i}
              style={{
                left: `${3 + (i * 6.1) % 94}%`,
                animationDelay: `${(i * 0.28) % 3}s`,
                animationDuration: `${5 + (i % 5) * 0.6}s`,
                width: `${9 + (i % 5) * 3}px`,
                height: `${9 + (i % 5) * 3}px`,
              }}
            />
          ))}
        </div>
        {routeLoading ? <PageLoader /> : null}
        <header className="aq-topbar">
          <div className="flex items-center gap-3 min-w-0">
            <button type="button" className="aq-menu-btn" onClick={toggleSidebar} aria-label={collapsed ? 'Expand menu' : 'Collapse menu'}>☰</button>
            <div className="aq-topbar-title">Smart Aquaculture Platform</div>
          </div>
          <div className="aq-topbar-tools">
            <time className="aq-clock" dateTime={clock.toISOString()}>
              {clock.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
            </time>
            <button
              type="button"
              className="aq-theme-toggle"
              onClick={toggleTheme}
              aria-label={theme === 'light' ? 'Switch to night mode' : 'Switch to light mode'}
              title={theme === 'light' ? 'Night mode' : 'Light mode'}
            >
              <span className={theme === 'light' ? 'is-on' : ''} aria-hidden="true">☀️</span>
              <span className={theme === 'dark' ? 'is-on' : ''} aria-hidden="true">🌙</span>
            </button>
          </div>
        </header>
        <div className="aq-canvas">
          <div className="aq-canvas-body">
            {children}
            <div className="aq-pond-floor" aria-hidden="true">
              <svg className="aq-pond-soil" viewBox="0 0 1440 140" preserveAspectRatio="none">
                <path fill="#6b4f32" d="M0,70 C160,42 300,92 460,62 C620,32 760,88 920,54 C1080,22 1220,80 1440,46 L1440,140 L0,140 Z" />
                <path fill="#4a3420" d="M0,94 C180,72 340,112 520,86 C720,58 880,108 1080,82 C1220,68 1340,98 1440,84 L1440,140 L0,140 Z" />
                <path fill="#2e2014" d="M0,118 C150,108 330,128 520,116 C740,102 940,130 1160,114 C1280,106 1370,122 1440,116 L1440,140 L0,140 Z" />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DashboardLayout
