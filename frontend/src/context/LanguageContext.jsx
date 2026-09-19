import React, { createContext, useContext, useCallback } from 'react'
import { translations } from '../services/translations'

const LanguageContext = createContext()

export function LanguageProvider({ children }) {
    const t = useCallback((key) => translations.en?.[key] ?? key, [])

    return (
        <LanguageContext.Provider value={{ language: 'en', t }}>
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
