import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

import { applyTheme, getStoredTheme } from './services/theme'

const faviconHref = `/shrimply-logo.jpg?v=4`
document.querySelectorAll("link[rel*='icon']").forEach((el) => el.remove())
const favicon = document.createElement('link')
favicon.rel = 'icon'
favicon.type = 'image/jpeg'
favicon.href = faviconHref
document.head.appendChild(favicon)

applyTheme(getStoredTheme())
window.__APP_MOUNT_TIME = Date.now();

const rootEl = document.getElementById('root');
if (!rootEl) {
  console.error('[MAIN] #root element not found in DOM');
  document.body.innerHTML = '<h2 style="padding:2rem;color:#dc2626;font-family:sans-serif">Root element missing. Check index.html.</h2>';
} else {
  console.log('[MAIN] Mounting React application');
  createRoot(rootEl).render(
    <StrictMode>
      <App />
    </StrictMode>
  );
}
