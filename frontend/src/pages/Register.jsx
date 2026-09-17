import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { API_BASE } from '../services/apiConfig'
import { useLanguage } from '../context/LanguageContext'
import LanguageToggle from '../components/LanguageToggle'

const Register = () => {
    const [form, setForm] = useState({
        username: '',
        email: '',
        first_name: '',
        last_name: '',
        password: '',
        password2: '',
    })
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)
    const navigate = useNavigate()
    const { t } = useLanguage()

    const handleChange = (e) => {
        setForm({ ...form, [e.target.name]: e.target.value })
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        setLoading(true)
        setError('')

        if (form.password !== form.password2) {
            setError(t('passwordsNoMatch'))
            setLoading(false)
            return
        }

        try {
            const res = await fetch(`${API_BASE.replace(/\/api\/?$/, '')}/api/auth/register/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(form),
            })

            if (!res.ok) {
                const data = await res.json()
                // Flatten DRF validation errors
                const messages = Object.values(data).flat().join(' ')
                throw new Error(messages || 'Registration failed.')
            }

            navigate('/login', { state: { registered: true } })
        } catch (err) {
            setError(err.message || t('registrationFailed'))
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen modern-bg flex items-center justify-center p-4 relative overflow-hidden">
            {/* Language Toggle */}
            <div className="absolute top-4 right-4 z-20">
                <LanguageToggle compact />
            </div>
            {/* Background */}
            <div className="absolute inset-0">
                <div className="absolute inset-0 bg-gradient-to-br from-blue-900/20 via-cyan-900/10 to-teal-900/20"></div>
                <div
                    className="absolute inset-0 bg-cover bg-center opacity-20 animate-float"
                    style={{ backgroundImage: "url('/shrimp_pond_pic/shrimps-pond.jpg')" }}
                ></div>
                <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-transparent"></div>
            </div>

            {/* Floating Elements */}
            <div className="absolute top-20 right-10 w-20 h-20 bg-cyan-400/20 rounded-full blur-xl animate-pulse-glow"></div>
            <div className="absolute bottom-20 left-10 w-32 h-32 bg-blue-400/20 rounded-full blur-xl animate-float" style={{ animationDelay: '2s' }}></div>

            <div className="w-full max-w-md relative z-10">
                <div className="glass-card p-8 animate-float">
                    {/* Logo */}
                    <div className="text-center mb-6">
                        <div className="relative inline-block">
                            <div className="w-16 h-16 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-2xl flex items-center justify-center shadow-2xl animate-pulse-glow mx-auto mb-3">
                                <span className="text-3xl">🦐</span>
                            </div>
                        </div>
                        <h1 className="text-2xl font-bold text-gradient mb-1">{t('createAccount')}</h1>
                        <p className="text-slate-600 text-sm">{t('joinSmart')}</p>
                    </div>

                    {/* Form */}
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label htmlFor="first_name" className="block text-xs font-semibold text-slate-700 mb-1">{t('firstName')}</label>
                                <input id="first_name" name="first_name" type="text" className="input-modern text-sm" placeholder="Juan" value={form.first_name} onChange={handleChange} />
                            </div>
                            <div>
                                <label htmlFor="last_name" className="block text-xs font-semibold text-slate-700 mb-1">{t('lastName')}</label>
                                <input id="last_name" name="last_name" type="text" className="input-modern text-sm" placeholder="Dela Cruz" value={form.last_name} onChange={handleChange} />
                            </div>
                        </div>

                        <div>
                            <label htmlFor="username" className="block text-xs font-semibold text-slate-700 mb-1">{t('username')} *</label>
                            <input id="username" name="username" type="text" required className="input-modern text-sm" placeholder={t('chooseUsername')} value={form.username} onChange={handleChange} />
                        </div>

                        <div>
                            <label htmlFor="email" className="block text-xs font-semibold text-slate-700 mb-1">{t('email')}</label>
                            <input id="email" name="email" type="email" className="input-modern text-sm" placeholder="you@example.com" value={form.email} onChange={handleChange} />
                        </div>

                        <div>
                            <label htmlFor="password" className="block text-xs font-semibold text-slate-700 mb-1">{t('password')} *</label>
                            <input id="password" name="password" type="password" required className="input-modern text-sm" placeholder={t('minChars')} value={form.password} onChange={handleChange} />
                        </div>

                        <div>
                            <label htmlFor="password2" className="block text-xs font-semibold text-slate-700 mb-1">{t('confirmPassword')} *</label>
                            <input id="password2" name="password2" type="password" required className="input-modern text-sm" placeholder={t('repeatPassword')} value={form.password2} onChange={handleChange} />
                        </div>

                        {error && (
                            <div className="alert-modern alert-critical-modern">
                                <div className="flex items-center">
                                    <span className="text-lg mr-2">⚠️</span>
                                    <span className="text-sm font-medium">{error}</span>
                                </div>
                            </div>
                        )}

                        <button type="submit" disabled={loading} className="btn-modern w-full flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed">
                            {loading ? (
                                <>
                                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                                    {t('creatingAccount')}
                                </>
                            ) : (
                                <>
                                    <span className="mr-2">✨</span>
                                    {t('createAccount')}
                                </>
                            )}
                        </button>
                    </form>

                    {/* Link to Login */}
                    <div className="text-center mt-5">
                        <p className="text-sm text-slate-600">
                            {t('alreadyHaveAccount')}{' '}
                            <Link to="/login" className="text-cyan-600 hover:text-cyan-700 font-semibold">{t('signIn')}</Link>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default Register
