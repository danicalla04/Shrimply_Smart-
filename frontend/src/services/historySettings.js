import { authService } from './auth'
import API_BASE from './apiConfig'

export async function fetchHistorySettings() {
    const res = await authService.apiCall(`${API_BASE}/history-settings/`)
    return res.json()
}

export async function updateHistorySettings(data) {
    const res = await authService.apiCall(`${API_BASE}/history-settings/`, {
        method: 'POST',
        body: JSON.stringify(data),
    })
    if (!res.ok) throw new Error('Failed to update settings')
    return res.json()
}
