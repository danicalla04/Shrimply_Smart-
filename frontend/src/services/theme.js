export const THEME_KEY = 'aq-theme'

export function getStoredTheme() {
  try {
    return localStorage.getItem(THEME_KEY) === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

export function applyTheme(mode) {
  const root = document.documentElement
  const light = mode === 'light'
  root.classList.add('aq-root')
  root.classList.toggle('theme-light', light)
  root.classList.toggle('theme-dark', !light)
  root.classList.toggle('dark', !light)
  root.style.colorScheme = light ? 'light' : 'dark'
  root.style.removeProperty('background')
  if (document.body) {
    document.body.style.removeProperty('background')
    document.body.style.removeProperty('color')
  }
  try {
    localStorage.setItem(THEME_KEY, light ? 'light' : 'dark')
  } catch { /* ignore */ }
  window.dispatchEvent(new CustomEvent('aq-theme-changed', { detail: light ? 'light' : 'dark' }))
}
