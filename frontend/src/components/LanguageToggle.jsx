import React from 'react'
import { useLanguage } from '../context/LanguageContext'

export default function LanguageToggle({ compact = false }) {
    const { language, toggleLanguage } = useLanguage()

    if (compact) {
        return (
            <button
                onClick={toggleLanguage}
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium
                   bg-white/10 hover:bg-white/20 text-white transition-colors"
                title={language === 'en' ? 'Switch to Tagalog' : 'Switch to English'}
            >
                <span>{language === 'en' ? '🇺🇸' : '🇵🇭'}</span>
                <span>{language === 'en' ? '🌐 EN' : '🌐 TL'}</span>
            </button>
        )
    }

    return (
        <button
            onClick={toggleLanguage}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold
                 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600
                 text-white shadow-lg hover:shadow-cyan-500/30 transition-all duration-200
                 border border-cyan-400/30"
            title={language === 'en' ? 'Switch to Tagalog' : 'Switch to English'}
        >
            <span className="text-lg">{language === 'en' ? '🇺🇸' : '🇵🇭'}</span>
            <span>{language === 'en' ? '🌐 English' : '🌐 Tagalog'}</span>
        </button>
    )
}
