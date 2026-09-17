import React, { createContext, useContext, useState, useCallback } from 'react'
import { translations } from '../services/translations'

const LanguageContext = createContext()

export function LanguageProvider({ children }) {
    const [language, setLanguage] = useState(() => {
        return localStorage.getItem('app_language') || 'en'
    })

    const toggleLanguage = useCallback(() => {
        setLanguage((prev) => {
            const next = prev === 'en' ? 'tl' : 'en'
            localStorage.setItem('app_language', next)
            return next
        })
    }, [])

    const setLang = useCallback((lang) => {
        localStorage.setItem('app_language', lang)
        setLanguage(lang)
    }, [])

    // t(key) → returns the translated string, or the key itself as fallback
    const t = useCallback(
        (key) => {
            return translations[language]?.[key] ?? translations['en']?.[key] ?? key
        },
        [language]
    )

    return (
        <LanguageContext.Provider value={{ language, toggleLanguage, setLang, t }}>
            {children}
        </LanguageContext.Provider>
    )
}

export function useLanguage() {
    const ctx = useContext(LanguageContext)
    if (!ctx) throw new Error('useLanguage must be used inside <LanguageProvider>')
    return ctx
}

export default LanguageContext
