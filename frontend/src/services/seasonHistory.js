import { authService } from './auth'
import API_BASE from './apiConfig'

export async function fetchSeasonHistory() {
    const res = await authService.apiCall(`${API_BASE}/season-history/`)
    return res.json()
}
