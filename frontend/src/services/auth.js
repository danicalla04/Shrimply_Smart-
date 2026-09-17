// Authentication service for JWT tokens
import API_BASE from './apiConfig'

export const authService = {
  async login(username, password) {
    const url = `${API_BASE}/auth/token/`
    let response
    try {
      response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      })
    } catch (e) {
      // Browser network/CORS errors surface as a rejected fetch with a generic message.
      throw new Error(`Failed to reach backend (${url}). Is Django running on port 8000?`)
    }

    if (!response.ok) {
      // Try to surface server-provided details (e.g., invalid credentials).
      let detail = ''
      try {
        const ct = response.headers.get('content-type') || ''
        if (ct.includes('application/json')) {
          const body = await response.json()
          detail = body?.detail || body?.message || ''
        } else {
          detail = (await response.text()).slice(0, 200)
        }
      } catch {
        // ignore
      }

      const msg = detail ? `Login failed: ${detail}` : `Login failed (HTTP ${response.status})`
      throw new Error(msg)
    }

    const data = await response.json()
    localStorage.setItem('access_token', data.access)
    localStorage.setItem('refresh_token', data.refresh)
    return data
  },

  logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  },

  getToken() {
    return localStorage.getItem('access_token')
  },

  isAuthenticated() {
    return !!this.getToken()
  },

  async refreshToken() {
    const refresh = localStorage.getItem('refresh_token')
    if (!refresh) {
      throw new Error('No refresh token')
    }

    const response = await fetch(`${API_BASE}/auth/token/refresh/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh }),
    })

    if (response.ok) {
      const data = await response.json()
      localStorage.setItem('access_token', data.access)
      return data.access
    } else {
      this.logout()
      throw new Error('Token refresh failed')
    }
  },

  async apiCall(url, options = {}) {
    const token = this.getToken()
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    }

    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch(url, {
      ...options,
      headers,
    })

    if (response.status === 401) {
      // Try to refresh token
      try {
        await this.refreshToken()
        const newToken = this.getToken()
        headers.Authorization = `Bearer ${newToken}`
        return fetch(url, {
          ...options,
          headers,
        })
      } catch (error) {
        this.logout()
        window.location.href = '/login'
        throw error
      }
    }

    return response
  },
}

export default authService