import { useState } from 'react'
import { useNavigate, Link, useLocation } from 'react-router-dom'
import { authService } from '../services/auth'
import { useLanguage } from '../context/LanguageContext'
import LanguageToggle from '../components/LanguageToggle'

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
    } catch (error) {
      setError(error.message || t('loginFailed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen modern-bg flex items-center justify-center p-4 relative overflow-hidden">
      <noscript style={{ position: 'absolute', top: 0, left: 0, padding: '1rem', background: '#fecaca', color: '#7f1d1d', zIndex: 999 }}>JavaScript is disabled.</noscript>
      {/* Language Toggle */}
      <div className="absolute top-4 right-4 z-20">
        <LanguageToggle compact />
      </div>
      {/* Hero Background with Shrimp Pond */}
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-900/20 via-cyan-900/10 to-teal-900/20"></div>
        <div
          className="absolute inset-0 bg-cover bg-center opacity-20 animate-float"
          style={{ backgroundImage: "url('/shrimp_pond_pic/shrimps-pond.jpg')" }}
        ></div>
        <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-transparent"></div>
      </div>

      {/* Floating Elements */}
      <div className="absolute top-20 left-10 w-20 h-20 bg-cyan-400/20 rounded-full blur-xl animate-pulse-glow"></div>
      <div className="absolute bottom-20 right-10 w-32 h-32 bg-blue-400/20 rounded-full blur-xl animate-float" style={{ animationDelay: '2s' }}></div>
      <div className="absolute top-1/2 left-1/4 w-16 h-16 bg-teal-400/20 rounded-full blur-xl animate-pulse-glow" style={{ animationDelay: '4s' }}></div>

      <div className="w-full max-w-md relative z-10">
        {/* Modern Login Card */}
        <div className="glass-card p-8 animate-float">
          {/* Logo Section */}
          <div className="text-center mb-8">
            <div className="relative inline-block">
              <div className="w-20 h-20 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-2xl flex items-center justify-center shadow-2xl animate-pulse-glow mx-auto mb-4">
                <span className="text-4xl">🦐</span>
              </div>
              <div className="absolute -top-2 -right-2 w-6 h-6 bg-orange-400 rounded-full animate-bounce"></div>
            </div>
            <h1 className="text-3xl font-bold text-gradient mb-2">{t('appName')}</h1>
            <p className="text-slate-600 text-sm">{t('appTagline')}</p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {justRegistered && (
              <div className="bg-green-50 border border-green-200 text-green-700 rounded-xl p-3 text-sm text-center">
                ✅ {t('accountCreated')}
              </div>
            )}
            <div className="space-y-4">
              <div>
                <label htmlFor="username" className="block text-sm font-semibold text-slate-700 mb-2">
                  {t('username')}
                </label>
                <input
                  id="username"
                  name="username"
                  type="text"
                  required
                  className="input-modern"
                  placeholder={t('enterUsername')}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="password" className="block text-sm font-semibold text-slate-700 mb-2">
                  {t('password')}
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  required
                  className="input-modern"
                  placeholder={t('enterPassword')}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            {error && (
              <div className="alert-modern alert-critical-modern">
                <div className="flex items-center">
                  <span className="text-lg mr-2">⚠️</span>
                  <span className="text-sm font-medium">{error}</span>
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-modern w-full flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                  {t('signingIn')}
                </>
              ) : (
                <>
                  <span className="mr-2">🔐</span>
                  {t('signIn')}
                </>
              )}
            </button>
          </form>
        </div>
        {/* Footer */}
        <div className="text-center mt-6">
          <p className="text-sm text-slate-600 mb-2">
            {t('noAccount')}{' '}
            <Link to="/register" className="text-cyan-600 hover:text-cyan-700 font-semibold">{t('createAccount')}</Link>
          </p>
          <p className="text-xs text-slate-500">
            {t('poweredBy')}
          </p>
        </div>
      </div>
    </div>
  )
}

export default Login