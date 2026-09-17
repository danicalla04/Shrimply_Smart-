import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import LanguageToggle from '../components/LanguageToggle'

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

const Landing = () => {
    const navigate = useNavigate()
    const { t } = useLanguage()
    const [current, setCurrent] = useState(0)
    const [isTransitioning, setIsTransitioning] = useState(false)

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

    // Auto-advance every 5 seconds
    useEffect(() => {
        const timer = setInterval(next, 5000)
        return () => clearInterval(timer)
    }, [next])

    return (
        <div className="relative w-full h-screen overflow-hidden bg-black">
            {/* Slideshow Images */}
            {slideImages.map((image, index) => (
                <div
                    key={index}
                    className="absolute inset-0 transition-opacity duration-700 ease-in-out"
                    style={{ opacity: index === current ? 1 : 0, zIndex: index === current ? 1 : 0 }}
                >
                    <img
                        src={image}
                        alt={t(slideKeys[index].titleKey)}
                        className="w-full h-full object-cover"
                    />
                    {/* Dark overlay */}
                    <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-black/30 to-black/70" />
                </div>
            ))}

            {/* Top Navigation Bar */}
            <div className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-8 py-5">
                <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 bg-white/20 backdrop-blur-md rounded-xl flex items-center justify-center border border-white/30">
                        <span className="text-xl">🦐</span>
                    </div>
                    <span className="text-white text-xl font-bold tracking-wide">ShrimplySmart</span>
                </div>
                <div className="flex items-center space-x-3">
                    <LanguageToggle compact />
                    <button
                        onClick={() => navigate('/login')}
                        className="px-6 py-2.5 bg-white/15 backdrop-blur-md text-white border border-white/30 rounded-full font-medium hover:bg-white/25 transition-all duration-300"
                    >
                        {t('signIn')}
                    </button>
                </div>
            </div>

            {/* Center Content */}
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center text-center px-6">
                {slideKeys.map((sk, index) => (
                    <div
                        key={index}
                        className="absolute transition-all duration-700 ease-in-out max-w-3xl"
                        style={{
                            opacity: index === current ? 1 : 0,
                            transform: index === current ? 'translateY(0)' : 'translateY(30px)',
                            pointerEvents: index === current ? 'auto' : 'none',
                        }}
                    >
                        <h1 className="text-5xl md:text-6xl lg:text-7xl font-extrabold text-white mb-6 leading-tight drop-shadow-lg">
                            {t(sk.titleKey)}
                        </h1>
                        <p className="text-lg md:text-xl text-white/85 mb-10 max-w-2xl mx-auto leading-relaxed drop-shadow">
                            {t(sk.subKey)}
                        </p>
                    </div>
                ))}

                {/* CTA Button */}
                <div className="mt-64 z-20">
                    <button
                        onClick={() => navigate('/login')}
                        className="px-10 py-4 bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-lg font-semibold rounded-full shadow-2xl hover:shadow-cyan-500/30 hover:scale-105 transition-all duration-300 border border-white/20"
                    >
                        {t('getStarted')}
                    </button>
                </div>
            </div>

            {/* Arrow Navigation */}
            <button
                onClick={prev}
                className="absolute left-6 top-1/2 -translate-y-1/2 z-20 w-12 h-12 flex items-center justify-center rounded-full bg-white/10 backdrop-blur-md border border-white/20 text-white hover:bg-white/25 transition-all duration-300"
                aria-label="Previous slide"
            >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
            </button>
            <button
                onClick={next}
                className="absolute right-6 top-1/2 -translate-y-1/2 z-20 w-12 h-12 flex items-center justify-center rounded-full bg-white/10 backdrop-blur-md border border-white/20 text-white hover:bg-white/25 transition-all duration-300"
                aria-label="Next slide"
            >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
            </button>

            {/* Dot Indicators */}
            <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-20 flex items-center space-x-3">
                {slideImages.map((_, index) => (
                    <button
                        key={index}
                        onClick={() => goToSlide(index)}
                        className={`transition-all duration-300 rounded-full ${index === current
                            ? 'w-10 h-3 bg-white'
                            : 'w-3 h-3 bg-white/40 hover:bg-white/60'
                            }`}
                        aria-label={`Go to slide ${index + 1}`}
                    />
                ))}
            </div>

            {/* Bottom Feature Pills */}
            <div className="absolute bottom-24 left-1/2 -translate-x-1/2 z-20 flex items-center space-x-4">
                {[
                    { icon: '🌡️', labelKey: 'temperature' },
                    { icon: '💧', labelKey: 'phLevel' },
                    { icon: '🫧', labelKey: 'turbidity' },
                    { icon: '📊', labelKey: 'tdsEc' },
                    { icon: '🤖', labelKey: 'aiPredictions' },
                ].map((feature, i) => (
                    <div
                        key={i}
                        className="flex items-center space-x-2 px-4 py-2 bg-white/10 backdrop-blur-md rounded-full border border-white/20 text-white/90 text-sm"
                    >
                        <span>{feature.icon}</span>
                        <span>{t(feature.labelKey)}</span>
                    </div>
                ))}
            </div>
        </div>
    )
}

export default Landing
