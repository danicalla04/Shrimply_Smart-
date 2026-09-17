import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Debug mounting instrumentation
console.log('[MAIN] Bundled main.jsx executing');
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
