import { useState } from 'react'
import { useNavigate, Link, useLocation } from 'react-router-dom'
import { authService } from '../services/auth'
import { useLanguage } from '../context/LanguageContext'

const Login = () => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useLanguage()
  const justRegistered = location.state?.registered

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await authService.login(username, password)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || t('loginFailed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen aq-root-bg login-stage flex items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute inset-0">
        <div
          className="login-photo"
          style={{ backgroundImage: "url('/shrimp_pond_pic/shrimps-pond.jpg')" }}
        />
        <div className="login-veil" />
      </div>
      <div className="login-orbs" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="login-bubbles" aria-hidden="true">
        <span /><span /><span /><span /><span /><span /><span /><span />
      </div>
      <div className="w-full max-w-md relative z-10">
        <div className="card p-8 login-card">
          <div className="text-center mb-8">
            <div className="aq-logo login-logo mx-auto mb-4" style={{ width: 64, height: 64 }}>
              <img src="/shrimply-logo.jpg" alt="" />
            </div>
            <div className="pond-kicker">Smart aquaculture platform</div>
            <h1 className="aq-title mt-2">{t('appName')}</h1>
            <p className="aq-sub">{t('appTagline')}</p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-5">
            {justRegistered && (
              <div className="alert-modern alert-success-modern text-sm text-center">{t('accountCreated')}</div>
            )}
            <div>
              <label htmlFor="username" className="block text-sm mb-2 text-cyan-100">{t('username')}</label>
              <input id="username" className="input-modern" value={username} onChange={(e) => setUsername(e.target.value)} required />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm mb-2 text-cyan-100">{t('password')}</label>
              <input id="password" type="password" className="input-modern" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            {error && <div className="alert-modern alert-critical-modern text-sm">{error}</div>}
            <button type="submit" disabled={loading} className="btn-modern w-full">
              {loading ? t('signingIn') : t('signIn')}
            </button>
          </form>
          <p className="text-center text-sm mt-6 text-cyan-200/70">
            {t('noAccount')}{' '}
            <Link to="/register" className="text-cyan-300 font-semibold">{t('createAccount')}</Link>
          </p>
        </div>
      </div>
    </div>
  )
}

export default Login
