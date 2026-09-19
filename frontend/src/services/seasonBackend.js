import { authService } from './auth'
import API_BASE from './apiConfig'

async function parseJsonSafe(res) {
    const text = await res.text()
    if (!text) return { data: null, text: '' }
    try {
        return { data: JSON.parse(text), text }
    } catch {
        return { data: null, text }
    }
}

export async function listSeasons() {
    const res = await authService.apiCall(`${API_BASE}/seasons/`)
    return res.json()
}

export async function getActiveSeason() {
    const res = await authService.apiCall(`${API_BASE}/seasons/current/`)
    if (res.status === 404) return null
    return res.json()
}

export async function startNewSeason(name, startDate, notes = '') {
    const res = await authService.apiCall(`${API_BASE}/seasons/start/`, {
        method: 'POST',
        body: JSON.stringify({ name, start_date: startDate, notes }),
    })

    const { data, text } = await parseJsonSafe(res)
    if (!res.ok) {
        throw new Error(data?.error || data?.detail || text || 'Failed to start season')
    }
    // Some servers may respond with 201 + empty body; treat as success.
    return data || {}
}

export async function endActiveSeason(seasonId) {
    const res = await authService.apiCall(`${API_BASE}/seasons/${seasonId}/end/`, {
        method: 'POST',
        body: JSON.stringify({ end_date: new Date().toISOString().split('T')[0] }),
    })

    const { data, text } = await parseJsonSafe(res)
    if (!res.ok) {
        throw new Error(data?.error || data?.detail || text || 'Failed to end season')
    }
    return data || {}
}

export async function addEntryToActive(seasonId, date, amount, unit, note, isAll) {
    const res = await authService.apiCall(`${API_BASE}/seasons/${seasonId}/add_entry/`, {
        method: 'POST',
        body: JSON.stringify({ date, amount: parseFloat(amount), unit, note, is_all: isAll }),
    })

    const { data, text } = await parseJsonSafe(res)
    if (!res.ok) {
        throw new Error(data?.error || data?.detail || text || 'Failed to add entry')
    }
    return data || {}
}

export async function getSeasonEntries(seasonId) {
    const res = await authService.apiCall(`${API_BASE}/seasons/${seasonId}/entries/`)
    return res.json()
}

export async function deleteEntry(entryId) {
    const res = await authService.apiCall(`${API_BASE}/harvest-entries/${entryId}/`, {
        method: 'DELETE',
    })
    if (!res.ok) throw new Error('Failed to delete entry')
}

export async function deleteSeason(seasonId) {
    const res = await authService.apiCall(`${API_BASE}/seasons/${seasonId}/`, {
        method: 'DELETE',
    })
    if (!res.ok) throw new Error('Failed to delete season')
}

export async function seasonTotals(seasonId) {
    const res = await authService.apiCall(`${API_BASE}/seasons/${seasonId}/`)
    return res.json()
}

function packSensorAvgBlock(block) {
    if (!block || typeof block !== 'object') {
        return { temperature: null, ph: null, turbidity: null, tds: null, reading_count: 0 }
    }
    return {
        temperature: block.temperature ?? block.avg_temp ?? null,
        ph: block.ph ?? block.avg_ph ?? null,
        turbidity: block.turbidity ?? block.avg_do ?? block.avg_turbidity ?? null,
        tds: block.tds ?? block.avg_tds ?? null,
        reading_count: block.reading_count ?? block.count ?? 0,
    }
}

function packSensorAvgSplit(block) {
    if (!block || typeof block !== 'object') {
        return {
            day: packSensorAvgBlock(null),
            night: packSensorAvgBlock(null),
            all: packSensorAvgBlock(null),
        }
    }
    if (block.day || block.night || block.all) {
        return {
            day: packSensorAvgBlock(block.day),
            night: packSensorAvgBlock(block.night),
            all: packSensorAvgBlock(block.all || block.hours24),
        }
    }
    const all = packSensorAvgBlock(block)
    return { day: packSensorAvgBlock(null), night: packSensorAvgBlock(null), all }
}

export async function getSensorAverages(seasonId) {
    const res = await authService.apiCall(`${API_BASE}/seasons/${seasonId}/sensor_averages/`)
    if (!res.ok) return null
    const raw = await res.json()
    if (!raw || typeof raw !== 'object') return null
    const season = packSensorAvgSplit(raw.season || {
        day: raw.day,
        night: raw.night,
        all: raw.hours24 || raw,
    })
    const hours24 = season.all
    return {
        week: packSensorAvgSplit(raw.week),
        month: packSensorAvgSplit(raw.month),
        season,
        day: season.day,
        night: season.night,
        hours24,
        ...hours24,
    }
}

export async function updateStockingDensity(seasonId, stockingDensity) {
    const res = await authService.apiCall(`${API_BASE}/seasons/${seasonId}/update_stocking/`, {
        method: 'PATCH',
        body: JSON.stringify({ stocking_density: stockingDensity }),
    })

    const { data, text } = await parseJsonSafe(res)
    if (!res.ok) {
        throw new Error(data?.error || data?.detail || text || 'Failed to update stocking density')
    }
    return data || {}
}

export async function updateSeasonNotes(seasonId, notes) {
    const res = await authService.apiCall(`${API_BASE}/seasons/${seasonId}/`, {
        method: 'PATCH',
        body: JSON.stringify({ notes }),
    })
    if (!res.ok) throw new Error('Failed to update notes')
    return res.json()
}
