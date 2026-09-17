// Centralized API configuration
// All service files should import API_BASE from here

export const API_BASE = import.meta.env.VITE_BACKEND_URL
    ? `${import.meta.env.VITE_BACKEND_URL.replace(/\/$/, '')}/api`
    : 'http://127.0.0.1:8000/api'

// In local development (`npm run dev`), prefer same-origin calls via the Vite proxy.
// This avoids CORS/preflight and hostname resolution quirks (localhost vs 127.0.0.1).
export const DEV_API_BASE = '/api'

export const EFFECTIVE_API_BASE = import.meta.env.DEV ? DEV_API_BASE : API_BASE

/**
 * Django Channels WebSocket origin (no path).
 * VITE_WS_URL overrides (e.g. ws://127.0.0.1:8000 or wss://api.example.com).
 * Else derived from VITE_BACKEND_URL (same host/port as REST).
 * Dev fallback: ws://<hostname>:8000 — Vite does not proxy WebSockets to Django.
 */
export function getChannelsWebSocketBase() {
  // In dev, prefer the same hostname the UI is loaded from when it's local.
  // This prevents stale env values (e.g. a LAN IP) from breaking WS on localhost.
  if (import.meta.env.DEV && typeof window !== 'undefined') {
    const h = window.location.hostname
    if (h === 'localhost' || h === '127.0.0.1') {
      return `ws://${h}:8000`
    }
  }

  const explicit = import.meta.env.VITE_WS_URL
  if (explicit) {
    return String(explicit).replace(/\/$/, '')
  }
  const backend = import.meta.env.VITE_BACKEND_URL
  if (backend) {
    try {
      const u = new URL(backend)
      const wsProto = u.protocol === 'https:' ? 'wss:' : 'ws:'
      return `${wsProto}//${u.host}`
    } catch {
      /* fall through */
    }
  }
  if (import.meta.env.DEV) {
    const h = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1'
    return `ws://${h}:8000`
  }
  if (typeof window !== 'undefined') {
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${wsProto}//${window.location.host}`
  }
  return 'ws://127.0.0.1:8000'
}

/** @param {string} path e.g. '/ws/feeder/' */
export function getChannelsWebSocketUrl(path) {
  const p = path.startsWith('/') ? path : `/${path}`
  return getChannelsWebSocketBase() + p
}

export default EFFECTIVE_API_BASE
