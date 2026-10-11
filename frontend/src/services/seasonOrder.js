// Numeric comparison keeps S1, S2, ... S10 in chronological season-name order.
export function sortSeasons(seasons) {
  return [...seasons].sort((a, b) =>
    String(a.name || '').trim().localeCompare(String(b.name || '').trim(), 'en', { numeric: true, sensitivity: 'base' })
    || String(a.start_date || '').localeCompare(String(b.start_date || ''))
    || Number(a.id || 0) - Number(b.id || 0)
  )
}
