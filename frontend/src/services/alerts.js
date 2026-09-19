import axios from 'axios'
import { authService } from './auth'
import API_BASE from './apiConfig'

export async function fetchAlerts(page = 1, pageSize = 20) {
  try {
    const response = await authService.apiCall(`${API_BASE}/alerts/?page=${page}&page_size=${pageSize}`)
    if (response && typeof response.json === 'function') {
      const data = await response.json()
      if (data && 'results' in data) return data
      return { count: Array.isArray(data) ? data.length : 0, results: Array.isArray(data) ? data : [], next: null, previous: null }
    }
    const data = response?.data || []
    if (data && typeof data === 'object' && 'results' in data) return data
    return { count: Array.isArray(data) ? data.length : 0, results: Array.isArray(data) ? data : [], next: null, previous: null }
  } catch (error) {
    console.error('Failed to fetch alerts:', error)
    return { count: 0, results: [], next: null, previous: null }
  }
}

export async function fetchUnresolvedAlerts() {
  try {
    const response = await authService.apiCall(`${API_BASE}/alerts/unresolved/`)
    if (response && typeof response.json === 'function') {
      return await response.json()
    }
    return response?.data || []
  } catch (error) {
    console.error('Failed to fetch unresolved alerts:', error)
    return []
  }
}

export async function fetchActiveAlerts() {
  try {
    const response = await authService.apiCall(`${API_BASE}/alerts/active/`)
    if (response && typeof response.json === 'function') {
      return await response.json()
    }
    return response?.data || []
  } catch (error) {
    console.error('Failed to fetch active alerts:', error)
    return []
  }
}

export async function fetchAlertSummary() {
  try {
    const response = await authService.apiCall(`${API_BASE}/alerts/summary/`)
    if (response && typeof response.json === 'function') {
      return await response.json()
    }
    return response?.data || { total: 0, critical: 0, warning: 0, low: 0 }
  } catch (error) {
    console.error('Failed to fetch alert summary:', error)
    return { total: 0, critical: 0, warning: 0, low: 0 }
  }
}

export async function fetchAlertsByParameter(parameter, days = 7) {
  try {
    const response = await authService.apiCall(
      `${API_BASE}/alerts/by_parameter/?parameter=${parameter}&days=${days}`
    )
    if (response && typeof response.json === 'function') {
      return await response.json()
    }
    return response?.data || { alerts: [] }
  } catch (error) {
    console.error(`Failed to fetch ${parameter} alerts:`, error)
    return { alerts: [] }
  }
}

export async function deleteAlert(id) {
  try {
    const response = await authService.apiCall(`${API_BASE}/alerts/${id}/`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      throw new Error(`Delete failed (${response.status})`)
    }
    if (response.status !== 204 && typeof response.json === 'function') {
      try { return await response.json() } catch { return {} }
    }
    return {}
  } catch (error) {
    console.error('Failed to delete alert:', error)
    throw error
  }
}

export async function resolveAlert(id) {
  try {
    const response = await authService.apiCall(`${API_BASE}/alerts/${id}/resolve/`, {
      method: 'POST',
    })
    if (response && typeof response.json === 'function') {
      return await response.json()
    }
    return response?.data || {}
  } catch (error) {
    console.error('Failed to resolve alert:', error)
    throw error
  }
}

export async function resolveAllAlerts(parameter = null) {
  try {
    const response = await authService.apiCall(`${API_BASE}/alerts/resolve_all/`, {
      method: 'POST',
      body: JSON.stringify({ parameter })
    })
    if (response && typeof response.json === 'function') {
      return await response.json()
    }
    return response?.data || {}
  } catch (error) {
    console.error('Failed to resolve all alerts:', error)
    throw error
  }
}

export async function checkThresholds() {
  try {
    const response = await authService.apiCall(`${API_BASE}/sensors/check_thresholds/`)
    if (response && typeof response.json === 'function') {
      return await response.json()
    }
    return response?.data || {}
  } catch (error) {
    console.error('Failed to check thresholds:', error)
    return {}
  }
}