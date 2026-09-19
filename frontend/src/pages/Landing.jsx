import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import { applyTheme, getStoredTheme } from '../services/theme'

const slideImages = [
    '/landing/aquaculture-pond.jpeg',
    '/landing/shrimps-pond.jpg',
    '/landing/vannamei-shrimp-Pacific-white-shrimp.avif',
    '/landing/pile-fresh-shrimps-background_62193-612.avif',
    '/landing/raw-shrimps-on-hand-washing-shrimp-on-bowl-shrimps-background-fresh-shrimp-prawns-for-cooking-seafood-food-in-the-kitchen-free-photo.jpg',
]

const slideKeys = [
    { titleKey: 'landingSlide1Title', subKey: 'landingSlide1Sub' },
    { titleKey: 'landingSlide2Title', subKey: 'landingSlide2Sub' },
    { titleKey: 'landingSlide3Title', subKey: 'landingSlide3Sub' },
    { titleKey: 'landingSlide4Title', subKey: 'landingSlide4Sub' },
    { titleKey: 'landingSlide5Title', subKey: 'landingSlide5Sub' },
]

const features = [
    { icon: '🌡️', labelKey: 'temperature' },
    { icon: '💧', labelKey: 'phLevel' },
    { icon: '🫧', labelKey: 'turbidity' },
    { icon: '📊', labelKey: 'tdsEc' },
    { icon: '🤖', labelKey: 'aiPredictions' },
]

const Landing = () => {
    const navigate = useNavigate()
    const { t } = useLanguage()
    const [current, setCurrent] = useState(0)
    const [isTransitioning, setIsTransitioning] = useState(false)
    const [theme, setTheme] = useState(() => getStoredTheme())
    const [touchX, setTouchX] = useState(null)

    useEffect(() => {
        applyTheme(theme)
    }, [theme])

    const goToSlide = useCallback((index) => {
        if (isTransitioning) return
        setIsTransitioning(true)
        setCurrent(index)
        setTimeout(() => setIsTransitioning(false), 700)
    }, [isTransitioning])

    const next = useCallback(() => {
        goToSlide((current + 1) % slideImages.length)
    }, [current, goToSlide])

    const prev = useCallback(() => {
        goToSlide((current - 1 + slideImages.length) % slideImages.length)
    }, [current, goToSlide])

    useEffect(() => {
        const timer = setInterval(next, 5000)
        return () => clearInterval(timer)
    }, [next])

    const toggleTheme = () => {
        setTheme((currentTheme) => (currentTheme === 'light' ? 'dark' : 'light'))
    }

    return (
        <div
            className="landing-stage aq-root-bg"
            onTouchStart={(e) => setTouchX(e.changedTouches[0].clientX)}
            onTouchEnd={(e) => {
                if (touchX == null) return
                const delta = e.changedTouches[0].clientX - touchX
                if (Math.abs(delta) > 40) {
                    if (delta < 0) next()
                    else prev()
                }
                setTouchX(null)
            }}
        >
            <div className="absolute inset-0">
                <div
                    className="login-photo"
                    style={{ backgroundImage: "url('/shrimp_pond_pic/shrimps-pond.jpg')" }}
                />
                <div className="login-veil" />
            </div>
            <div className="login-orbs" aria-hidden="true">
                <span /><span /><span />
            </div>
            <div className="login-bubbles" aria-hidden="true">
                <span /><span /><span /><span /><span /><span /><span /><span />
            </div>

            <header className="landing-top">
                <div className="landing-brand">
                    <div className="aq-logo">
                        <img src="/shrimply-logo.jpg" alt="" />
                    </div>
                    <div>
                        <div className="pond-kicker">Aqua command</div>
                        <strong>Shrimply Smart</strong>
                    </div>
                </div>
                <div className="landing-actions">
                    <button
                        type="button"
                        className="aq-theme-toggle"
                        onClick={toggleTheme}
                        aria-label={theme === 'light' ? 'Switch to night mode' : 'Switch to light mode'}
                    >
                        <span className={theme === 'light' ? 'is-on' : ''} aria-hidden="true">☀️</span>
                        <span className={theme === 'dark' ? 'is-on' : ''} aria-hidden="true">🌙</span>
                    </button>
                    <button type="button" className="btn-secondary" onClick={() => navigate('/login')}>
                        {t('signIn')}
                    </button>
                </div>
            </header>

            <main className="landing-mid">
                <div className="landing-copy-stack">
                    {slideKeys.map((sk, index) => (
                        <div
                            key={sk.titleKey}
                            className="landing-copy"
                            style={{
                                opacity: index === current ? 1 : 0,
                                transform: index === current ? 'translateY(0)' : 'translateY(18px)',
                                pointerEvents: index === current ? 'auto' : 'none',
                            }}
                        >
                            <div className="pond-kicker">Smart aquaculture platform</div>
                            <h1 className="landing-title">{t(sk.titleKey)}</h1>
                            <p className="landing-sub">{t(sk.subKey)}</p>
                        </div>
                    ))}
                </div>
                <button type="button" className="btn-modern landing-cta" onClick={() => navigate('/login')}>
                    {t('getStarted')}
                </button>
            </main>

            <div className="landing-pills">
                {features.map((feature) => (
                    <div key={feature.labelKey} className="landing-pill">
                        <span aria-hidden="true">{feature.icon}</span>
                        <span>{t(feature.labelKey)}</span>
                    </div>
                ))}
            </div>

            <div className="landing-dots">
                {slideImages.map((_, index) => (
                    <button
                        key={slideImages[index]}
                        type="button"
                        className={index === current ? 'is-on' : ''}
                        onClick={() => goToSlide(index)}
                        aria-label={`Go to slide ${index + 1}`}
                    />
                ))}
            </div>

            <button type="button" className="landing-arrow is-prev" onClick={prev} aria-label="Previous slide">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
            </button>
            <button type="button" className="landing-arrow is-next" onClick={next} aria-label="Next slide">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
            </button>
        </div>
    )
}

export default Landing
