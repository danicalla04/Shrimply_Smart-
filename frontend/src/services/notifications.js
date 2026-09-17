import { authService } from './auth'
import API_BASE from './apiConfig'

export async function sendHarvestReminder(email = '') {
    const body = email ? { email } : {}
    const res = await authService.apiCall(`${API_BASE}/notify/harvest-reminder/`, {
        method: 'POST',
        body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error((await res.json()).error || 'Failed to send reminder')
    return res.json()
}

export function isReminderSent(seasonId) {
    return localStorage.getItem(`reminder_sent_${seasonId}`) === 'true'
}

export function markReminderSent(seasonId) {
    localStorage.setItem(`reminder_sent_${seasonId}`, 'true')
}
