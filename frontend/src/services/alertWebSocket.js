/**
 * Alert WebSocket Service
 * Connects to Django Channels /ws/alerts/ for real-time alert notifications
 */

import { getChannelsWebSocketUrl } from './apiConfig'

export class AlertWebSocketService {
  constructor() {
    this.ws = null
    this.url = null
    this.listeners = []
    this.connected = false
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 8
    this.reconnectDelay = 3000
    this._intentionalClose = false
  }

  /**
   * Ensure a shared connection exists. Optional callback is registered as a listener.
   */
  connect(onAlert) {
    if (typeof onAlert === 'function') {
      this.addListener(onAlert)
    }

    this.url = getChannelsWebSocketUrl('/ws/alerts/')

    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return
    }

    this._intentionalClose = false
    console.log('[ALERT_WS] Connecting to', this.url)

    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        console.log('[ALERT_WS] ✅ Connected to alert stream')
        this.connected = true
        this.reconnectAttempts = 0
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('[ALERT_WS] Received:', data)
          const payload = data?.data || data
          this.listeners.forEach((listener) => {
            try {
              listener(payload)
            } catch (err) {
              console.warn('[ALERT_WS] Listener error:', err)
            }
          })
        } catch (err) {
          console.warn('[ALERT_WS] Failed to parse message:', err)
        }
      }

      this.ws.onerror = (error) => {
        console.error('[ALERT_WS] WebSocket error:', error)
      }

      this.ws.onclose = () => {
        console.warn('[ALERT_WS] Disconnected.')
        this.connected = false
        this.ws = null
        if (!this._intentionalClose) {
          this.attemptReconnect()
        }
      }
    } catch (err) {
      console.error('[ALERT_WS] Failed to connect:', err)
      this.attemptReconnect()
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[ALERT_WS] Max reconnection attempts reached.')
      return
    }
    if (this.listeners.length === 0) return

    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
    console.log(
      `[ALERT_WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`
    )
    setTimeout(() => this.connect(), delay)
  }

  addListener(listener) {
    if (typeof listener !== 'function') return
    if (!this.listeners.includes(listener)) {
      this.listeners.push(listener)
    }
  }

  removeListener(listener) {
    this.listeners = this.listeners.filter((l) => l !== listener)
  }

  /**
   * Drop one listener. Closes the socket only when no listeners remain.
   */
  disconnect(onAlert) {
    if (typeof onAlert === 'function') {
      this.removeListener(onAlert)
    }
    if (this.listeners.length > 0) return

    this._intentionalClose = true
    if (this.ws) {
      console.log('[ALERT_WS] Disconnecting (no listeners left)...')
      this.ws.close()
      this.ws = null
      this.connected = false
    }
  }

  isConnected() {
    return this.connected
  }
}

export const alertWebSocket = new AlertWebSocketService()
