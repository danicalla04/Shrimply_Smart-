import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import * as seasonApi from '../services/seasonBackend'
import { fetchHistorySettings, updateHistorySettings } from '../services/historySettings'
import { sendHarvestReminder, isReminderSent, markReminderSent } from '../services/notifications'
import SeasonSensorAverages from '../components/SeasonSensorAverages'
import PageLoader from '../components/PageLoader'
import './history-overview.css'

// Helper to format numbers with unit
const formatAmount = (kg) => {
    if (kg == null) return '—'
    if (kg >= 1000) return `${(kg / 1000).toFixed(2)} t`
    return `${Number(kg).toFixed(0)} kg`
}

const formatPcs = (n) => {
    if (n == null || n === '' || Number(n) <= 0) return '—'
    return Number(n).toLocaleString()
}

const formatAbw = (g) => {
    if (g == null || g === '' || Number(g) <= 0) return '—'
    return `${Number(g).toFixed(2)} g`
}

const seasonInitialStock = (season) =>
    Number(season?.initial_shrimp_quantity || 0) || Number(season?.stocking_density > 1000 ? season.stocking_density : 0) || 0

const seasonSurvivalPct = (season) => {
    const initial = seasonInitialStock(season)
    const current = Number(season?.current_shrimp_quantity || 0)
    if (!initial || !current) return null
    return Math.round((current / initial) * 100)
}

// Color palette for charts
const CHART_COLORS = ['#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#3b82f6', '#14b8a6']



const HistoryOverview = () => {
    const [seasons, setSeasons] = useState([])
    const [activeSeason, setActiveSeason] = useState(null)
    const [selectedSeasonId, setSelectedSeasonId] = useState(null)
    const [selectedEntries, setSelectedEntries] = useState([])
    const [settings, setSettings] = useState({ harvest_lead_days: 90, harvest_time: '08:00', notification_email: '' })

    const [dateISO, setDateISO] = useState(() => new Date().toISOString().slice(0, 10))
    const [timeHM, setTimeHM] = useState('09:30')
    const [amount, setAmount] = useState('')
    const [unit, setUnit] = useState('kg')
    const [note, setNote] = useState('')
    const [loading, setLoading] = useState(true)
    const [toast, setToast] = useState(null)
    const [actionLoading, setActionLoading] = useState(false)

    const [dayDraft, setDayDraft] = useState('')
    const [cycleDraft, setCycleDraft] = useState('')
    const [sensorAvgs, setSensorAvgs] = useState(null)
    const [expandedSeasonId, setExpandedSeasonId] = useState(null)
    const [pendingDeleteEntry, setPendingDeleteEntry] = useState(null)
    const overviewRef = useRef(null)


    const flash = (msg, type = 'success') => {
        setToast({ msg, type })
        setTimeout(() => setToast(null), 4000)
    }

    const loadAll = useCallback(async () => {
        try {
            const [allSeasons, active, sets] = await Promise.all([
                seasonApi.listSeasons().catch(() => []),
                seasonApi.getActiveSeason().catch(() => null),
                fetchHistorySettings().catch(() => ({ harvest_lead_days: 90, harvest_time: '08:00', notification_email: '' })),
            ])
            const seasonList = Array.isArray(allSeasons) ? allSeasons : []
            setSeasons(seasonList)
            setActiveSeason(active)

            const s = Array.isArray(sets) ? sets[0] || { harvest_lead_days: 90 } : sets
            setSettings(s)

            // Load sensor averages for the active season
            if (active?.id) {
                const avgs = await seasonApi.getSensorAverages(active.id).catch(() => null)
                setSensorAvgs(avgs)
            } else {
                setSensorAvgs(null)
            }
        } catch (e) {
            console.error('Failed to load history data:', e)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { loadAll() }, [loadAll])

    // ── computed values ────────────────────────────────────────────
    const totals = useMemo(() => ({
        active: activeSeason?.total_harvest_kg || 0,
        activeHarvests: activeSeason?.harvest_count || 0,
        all: seasons.reduce((sum, s) => sum + (s.total_harvest_kg || 0), 0),
    }), [seasons, activeSeason])

    const harvestDays = settings.harvest_lead_days || 90

    const expected = useMemo(() => {
        if (!activeSeason) return null
        try {
            const start = new Date(activeSeason.start_date)
            const est = new Date(start)
            est.setDate(est.getDate() + harvestDays)
            const today = new Date()
            const daysLeft = Math.max(0, Math.ceil((est - today) / (1000 * 60 * 60 * 24)))
            const daysSinceStart = Math.floor((today - start) / (1000 * 60 * 60 * 24))
            const dayNumber = Math.max(1, daysSinceStart + 1)
            return { date: est, daysLeft, dayNumber, totalDays: harvestDays }
        } catch {
            return null
        }
    }, [activeSeason, harvestDays])

    useEffect(() => {
        if (!expected) return
        setDayDraft(String(expected.dayNumber))
        setCycleDraft(String(expected.totalDays))
    }, [expected])





    // Auto-send reminder when within lead days
    useEffect(() => {
        const run = async () => {
            if (!activeSeason || !expected) return
            const email = settings.notification_email
            const notifyBefore = settings.days_before_notification ?? 2
            if (expected.daysLeft <= notifyBefore && email) {
                if (!isReminderSent(activeSeason.id)) {
                    try {
                        await sendHarvestReminder(email)
                        markReminderSent(activeSeason.id)
                    } catch (e) {
                        console.error('Failed to send reminder:', e)
                    }
                }
            }
        }
        run()
    }, [activeSeason, expected, settings])

    // ── actions ────────────────────────────────────────────────────
    const localISODate = (date) => {
        const y = date.getFullYear()
        const m = String(date.getMonth() + 1).padStart(2, '0')
        const d = String(date.getDate()).padStart(2, '0')
        return `${y}-${m}-${d}`
    }

    const saveCultureDay = async () => {
        if (!activeSeason || !expected) return
        const day = parseInt(dayDraft, 10)
        if (!Number.isFinite(day) || day < 1 || day > 365) {
            setDayDraft(String(expected.dayNumber))
            return flash('Culture day must be between 1 and 365', 'error')
        }
        if (day === expected.dayNumber) return
        const start = new Date()
        start.setHours(12, 0, 0, 0)
        start.setDate(start.getDate() - (day - 1))
        setActionLoading(true)
        try {
            await seasonApi.updateSeason(activeSeason.id, { start_date: localISODate(start) })
            flash(`Culture day set to ${day}`)
            await loadAll()
        } catch (e) {
            setDayDraft(String(expected.dayNumber))
            flash(e.message || 'Could not update culture day', 'error')
        } finally {
            setActionLoading(false)
        }
    }

    const saveCycleDays = async () => {
        if (!expected) return
        const days = parseInt(cycleDraft, 10)
        if (!Number.isFinite(days) || days < 1 || days > 365) {
            setCycleDraft(String(expected.totalDays))
            return flash('Cycle length must be between 1 and 365 days', 'error')
        }
        if (days === expected.totalDays) return
        setActionLoading(true)
        try {
            const saved = await updateHistorySettings({ harvest_lead_days: days })
            setSettings((prev) => ({ ...prev, ...saved, harvest_lead_days: days }))
            flash(`Cycle length set to ${days} days`)
        } catch (e) {
            setCycleDraft(String(expected.totalDays))
            flash(e.message || 'Could not update cycle length', 'error')
        } finally {
            setActionLoading(false)
        }
    }

    const addHarvest = async (isAll = false) => {
        if (!dateISO) return flash('Please select a date', 'error')
        if (!activeSeason) return flash('No active season', 'error')

        const amtNum = amount === '' ? null : Number(amount)
        if (amtNum == null || isNaN(amtNum) || amtNum <= 0) {
            return flash('Please enter a harvest amount greater than 0', 'error')
        }

        // Note is optional for harvest / harvest-all
        const amountKg = unit === 'kg' ? amtNum : amtNum * 1000

        setActionLoading(true)
        try {
            await seasonApi.addEntryToActive(activeSeason.id, dateISO, amountKg, 'kg', (note || '').trim(), isAll)
            flash(isAll ? 'Season ended — harvested all' : 'Harvest entry added')
            setAmount('')
            setNote('')
            await loadAll()
        } catch (e) {
            flash(e.message, 'error')
        } finally {
            setActionLoading(false)
        }
    }

    // ── Export Season Report as CSV ────────────────────────────────
    const exportSeasonCSV = async (season) => {
        try {
            const entries = await seasonApi.getSeasonEntries(season.id).catch(() => [])
            const avgs = await seasonApi.getSensorAverages(season.id).catch(() => null)
            const lines = [
                `Season Report: ${season.name}`,
                `Start Date,${season.start_date}`,
                `End Date,${season.end_date || 'Active'}`,
                `Total Harvest (kg),${season.total_harvest_kg || 0}`,
                `Harvest Count,${season.harvest_count || 0}`,
                `Initial Stock (pcs),${season.initial_shrimp_quantity || 0}`,
                `Current/Final Quantity (pcs),${season.current_shrimp_quantity || 0}`,
                `Average Weight (g),${season.average_shrimp_weight_grams || 0}`,
                `Survival Rate (%),${seasonSurvivalPct(season) ?? 'N/A'}`,
                `Stocking Density,${season.stocking_density || 'N/A'}`,
                `Days Active,${season.days_active || 0}`,
                '',
                'Sensor Averages',
                `Avg Temperature,${avgs?.temperature != null ? Number(avgs.temperature).toFixed(2) : 'N/A'}`,
                `Avg pH,${avgs?.ph != null ? Number(avgs.ph).toFixed(2) : 'N/A'}`,
                `Avg Turbidity (NTU),${avgs?.turbidity != null ? Number(avgs.turbidity).toFixed(2) : 'N/A'}`,
                `Avg TDS (ppm),${avgs?.tds != null ? Number(avgs.tds).toFixed(0) : 'N/A'}`,
                `Total Readings,${avgs?.reading_count || 0}`,
                '',
                'Harvest Entries',
                'Date,Amount (kg),Note,Is All',
                ...(Array.isArray(entries) ? entries : []).map(e =>
                    `${e.date},${e.amount},${(e.note || '').replace(/,/g, ';')},${e.is_all ? 'Yes' : 'No'}`
                )
            ]
            const blob = new Blob([lines.join('\n')], { type: 'application/vnd.ms-excel' })
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `${season.name.replace(/[^a-zA-Z0-9]/g, '_')}_report.xls`
            a.click()
            URL.revokeObjectURL(url)
            flash('Report exported!')
        } catch (e) {
            flash('Export failed: ' + e.message, 'error')
        }
    }

    const handleDeleteEntry = async () => {
        const entryId = pendingDeleteEntry?.id
        if (!entryId) return
        setActionLoading(true)
        try {
            await seasonApi.deleteEntry(entryId)
            flash('Entry deleted')
            setPendingDeleteEntry(null)
            await loadAll()
            if (selectedSeasonId) {
                const ents = await seasonApi.getSeasonEntries(selectedSeasonId).catch(() => [])
                setSelectedEntries(Array.isArray(ents) ? ents : [])
            }
        } catch (e) {
            flash(e.message, 'error')
        } finally {
            setActionLoading(false)
        }
    }

    const handleStartSeason = async () => {
        const raw = prompt('Season name (required, must be unique):')
        if (raw == null) return // cancelled
        const name = raw.trim()
        if (!name) return flash('Season name is required', 'error')
        if (seasons.some(s => (s.name || '').toLowerCase() === name.toLowerCase())) {
            return flash(`Season name "${name}" already exists. Choose a different name.`, 'error')
        }

        const startDate = new Date().toISOString().slice(0, 10)
        setActionLoading(true)
        try {
            await seasonApi.startNewSeason(name, startDate)
            flash('Season started!')
            await loadAll()
        } catch (e) {
            flash(e.message, 'error')
        } finally {
            setActionLoading(false)
        }
    }

    const handleViewOverview = async (seasonId) => {
        setSelectedSeasonId(seasonId)
        try {
            const ents = await seasonApi.getSeasonEntries(seasonId).catch(() => [])
            setSelectedEntries(Array.isArray(ents) ? ents : [])
        } catch {
            setSelectedEntries([])
        }
    }

    const selectedSeason = useMemo(() => {
        return seasons.find(s => s.id === selectedSeasonId) || null
    }, [selectedSeasonId, seasons])

    useEffect(() => {
        if (!selectedSeasonId) return
        overviewRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, [selectedSeasonId])

    // ── render ─────────────────────────────────────────────────────
    if (loading) {
        return <PageLoader />
    }

    return (
        <div className="history-overview p-6">
            {/* Toast */}
            {toast && (
                <div className={`fixed top-6 right-6 z-50 px-5 py-3 rounded-xl shadow-lg text-white text-sm font-medium transition-all
          ${toast.type === 'error' ? 'bg-red-500' : 'bg-emerald-500'}`}>
                    {toast.msg}
                </div>
            )}

            {/* ── Summary Cards ─────────────────────────────────────────── */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                <div className="glass-card rounded-2xl p-4">
                    <div className="text-slate-400">Active Season Total</div>
                    <div className="text-2xl font-semibold">{formatAmount(totals.active)}</div>
                </div>
                <div className="glass-card rounded-2xl p-4">
                    <div className="text-slate-400">Total (all time)</div>
                    <div className="text-2xl font-semibold">{formatAmount(totals.all)}</div>
                </div>
                <div className="glass-card rounded-2xl p-4">
                    <div className="text-slate-400">Harvests (active season)</div>
                    <div className="text-2xl font-semibold">{totals.activeHarvests}</div>
                </div>
                <div className="glass-card rounded-2xl p-4">
                    <div className="text-slate-400">Seasons</div>
                    <div className="text-2xl font-semibold">{seasons.length}</div>
                </div>
            </div>



            {/* ── Shrimp Population & Growth ─────────────────────────────── */}
            {activeSeason && (
                <div className="glass-card rounded-2xl p-6 mb-6">
                    <h2 className="text-xl font-bold mb-4">🦐 Shrimp Population & Growth</h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="glass-card rounded-2xl p-4 text-center">
                            <div className="text-slate-400 text-sm">🦐 Current Count</div>
                            <div className="text-2xl font-bold mt-1">{formatPcs(activeSeason.current_shrimp_quantity)}</div>
                            <div className="text-xs text-slate-500 mt-1">
                                Initial: {formatPcs(seasonInitialStock(activeSeason))}
                                {activeSeason.stocking_density > 0 && activeSeason.stocking_density <= 1000
                                    ? ` · Density: ${activeSeason.stocking_density}/m²`
                                    : ''}
                            </div>
                        </div>
                        <div className="glass-card rounded-2xl p-4 text-center">
                            <div className="text-slate-400 text-sm">⚖️ Avg Weight</div>
                            <div className="text-2xl font-bold mt-1">{formatAbw(activeSeason.average_shrimp_weight_grams)}</div>
                            <div className="text-xs text-slate-500 mt-1">Per shrimp</div>
                        </div>
                        <div className="glass-card rounded-2xl p-4 text-center">
                            <div className="text-slate-400 text-sm">📈 Survival Rate</div>
                            <div className="text-2xl font-bold mt-1">
                                {seasonSurvivalPct(activeSeason) != null ? `${seasonSurvivalPct(activeSeason)}%` : '—'}
                            </div>
                            <div className="text-xs text-slate-500 mt-1">vs initial stocking</div>
                        </div>
                        <div className="glass-card rounded-2xl p-4 text-center">
                            <div className="text-slate-400 text-sm">💼 Total Biomass</div>
                            <div className="text-2xl font-bold mt-1">
                                {activeSeason.current_shrimp_quantity && activeSeason.average_shrimp_weight_grams
                                    ? `${(activeSeason.current_shrimp_quantity * activeSeason.average_shrimp_weight_grams / 1000).toFixed(1)}kg`
                                    : '—'
                                }
                            </div>
                            <div className="text-xs text-slate-500 mt-1">Current standing stock</div>
                        </div>
                    </div>
                </div>
            )}

            {/* ── Sensor Averages Per Season ─────────────────────────────── */}
            {activeSeason && (
                <SeasonSensorAverages averages={sensorAvgs} className="glass-card rounded-2xl p-6 mb-6" />
            )}



            {/* ── Active Season ─────────────────────────────────────────── */}
            <div className="glass-card rounded-2xl p-6 mb-6">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-bold">Active Season</h2>
                    {!activeSeason && (
                        <button onClick={handleStartSeason} disabled={actionLoading}
                            className="px-4 py-2 rounded-xl bg-emerald-600 text-white hover:bg-emerald-500">
                            Start New Season
                        </button>
                    )}
                </div>
                {activeSeason ? (
                    <div className="mb-4 text-slate-600">
                        <div>Season: <span className="font-semibold">{activeSeason.name}</span></div>
                        <div>Started: {new Date(activeSeason.start_date).toLocaleDateString()}</div>
                        {expected && (
                            <div className="mt-1">
                                Expected Harvest: <span className="font-semibold">{expected.date.toLocaleDateString()}</span>
                                <span className="history-day-badge ml-3 inline-flex items-center gap-1 px-2 py-1 rounded bg-slate-700 text-white text-xs">
                                    Day
                                    <input
                                        type="number"
                                        min="1"
                                        max="365"
                                        value={dayDraft}
                                        disabled={actionLoading}
                                        aria-label="Current culture day"
                                        className="history-day-input"
                                        onChange={(e) => setDayDraft(e.target.value)}
                                        onBlur={saveCultureDay}
                                        onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }}
                                    />
                                    /
                                    <input
                                        type="number"
                                        min="1"
                                        max="365"
                                        value={cycleDraft}
                                        disabled={actionLoading}
                                        aria-label="Cycle length in days"
                                        className="history-day-input"
                                        onChange={(e) => setCycleDraft(e.target.value)}
                                        onBlur={saveCycleDays}
                                        onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }}
                                    />
                                </span>
                                {expected.daysLeft > 0 ? (
                                    <span className="ml-2 px-2 py-1 rounded bg-amber-600/30 text-amber-800">{expected.daysLeft} days left</span>
                                ) : (
                                    <span className="ml-2 px-2 py-1 rounded bg-green-600/30 text-green-800">Ready</span>
                                )}
                            </div>
                        )}
                    </div>
                ) : (
                    <p className="text-slate-400">No active season. Start a new one to record harvests.</p>
                )}

                {/* Add Harvest form — inside the Active Season card */}
                {activeSeason && (
                    <>
                        <h3 className="text-lg font-semibold mt-2 mb-2">Add Harvest</h3>
                        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
                            <div>
                                <label className="text-sm text-slate-400">Date</label>
                                <div className="harvest-picker mt-1">
                                    <input type="date" value={dateISO} onChange={e => setDateISO(e.target.value)}
                                        className="w-full rounded-lg bg-white/10 border border-white/20 px-3 py-2" />
                                    <button type="button" className="harvest-picker-btn" title="Select date"
                                        onClick={(e) => e.currentTarget.previousElementSibling?.showPicker?.()}>📅</button>
                                </div>
                            </div>
                            <div>
                                <label className="text-sm text-slate-400">Time</label>
                                <div className="harvest-picker mt-1">
                                    <input type="time" value={timeHM} onChange={e => setTimeHM(e.target.value)}
                                        className="w-full rounded-lg bg-white/10 border border-white/20 px-3 py-2" />
                                    <button type="button" className="harvest-picker-btn" title="Select time"
                                        onClick={(e) => e.currentTarget.previousElementSibling?.showPicker?.()}>🕒</button>
                                </div>
                            </div>
                            <div>
                                <label className="text-sm text-slate-400">Amount</label>
                                <input type="number" min="0" placeholder="e.g., 800" value={amount}
                                    onChange={e => setAmount(e.target.value)}
                                    className="w-full mt-1 rounded-lg bg-white/10 border border-white/20 px-3 py-2" />
                            </div>
                            <div>
                                <label className="text-sm text-slate-400">Unit</label>
                                <select value={unit} onChange={e => setUnit(e.target.value)}
                                    className="w-full mt-1 rounded-lg bg-white/10 border border-white/20 px-3 py-2">
                                    <option value="kg">kg</option>
                                    <option value="t">ton (t)</option>
                                </select>
                            </div>
                        </div>
                        <div className="mt-3">
                            <label className="text-sm text-slate-400">Note (optional)</label>
                            <input type="text" placeholder="e.g., Morning harvest"
                                value={note} onChange={e => setNote(e.target.value)}
                                className="w-full mt-1 rounded-lg bg-white/10 border border-white/20 px-3 py-2" />
                        </div>
                        <div className="flex flex-wrap gap-3 mt-4">
                            <button type="button" onClick={() => addHarvest(false)} disabled={actionLoading}
                                className="harvest-action-btn">Add Harvest</button>
                            <button type="button" onClick={() => addHarvest(true)} disabled={actionLoading}
                                className="harvest-action-btn is-all">Harvest All (end season)</button>
                        </div>
                        <p className="text-xs text-slate-400 mt-2">Tip: Harvest needs an amount (&gt; 0). Note is optional.</p>
                    </>
                )}
            </div>

            {/* ── Harvest Yield Bar Chart ───────────────────────────────── */}
            {seasons.length > 0 && (
                <div className="glass-card rounded-2xl p-6 mb-6">
                    <h2 className="text-xl font-bold mb-4">📈 Harvest Yield Comparison</h2>
                    {(() => {
                        const maxKg = Math.max(...seasons.map(s => s.total_harvest_kg || 0), 1)
                        const barWidth = Math.min(60, Math.max(30, 350 / seasons.length))
                        const chartWidth = Math.max(400, seasons.length * (barWidth + 20) + 80)
                        return (
                            <div className="overflow-x-auto">
                                <svg viewBox={`0 0 ${chartWidth} 200`} className="w-full" style={{ minHeight: 200 }} preserveAspectRatio="xMidYMid meet">
                                    {/* Y grid lines */}
                                    {[0, 0.25, 0.5, 0.75, 1].map(frac => (
                                        <g key={frac}>
                                            <line x1="60" y1={160 - frac * 140} x2={chartWidth - 20} y2={160 - frac * 140}
                                                stroke="rgba(148,163,184,0.2)" strokeWidth="0.5" />
                                            <text x="55" y={164 - frac * 140} fill="#94a3b8" fontSize="8" textAnchor="end">
                                                {(maxKg * frac).toFixed(0)}
                                            </text>
                                        </g>
                                    ))}
                                    {/* bars */}
                                    {seasons.map((s, i) => {
                                        const val = s.total_harvest_kg || 0
                                        const h = (val / maxKg) * 140
                                        const x = 70 + i * (barWidth + 20)
                                        return (
                                            <g key={s.id}>
                                                <rect
                                                    x={x} y={160 - h} width={barWidth} height={h}
                                                    rx="4" fill={CHART_COLORS[i % CHART_COLORS.length]}
                                                    opacity="0.85"
                                                />
                                                <text x={x + barWidth / 2} y={155 - h} textAnchor="middle" fill="#000" fontSize="8" fontWeight="bold">
                                                    {val > 0 ? `${val.toFixed(0)}kg` : ''}
                                                </text>
                                                <text x={x + barWidth / 2} y="175" textAnchor="middle" fill="#94a3b8" fontSize="7">
                                                    {s.name?.length > 10 ? s.name.slice(0, 10) + '…' : s.name}
                                                </text>
                                            </g>
                                        )
                                    })}
                                    {/* Y-axis label */}
                                    <text x="10" y="90" fill="#94a3b8" fontSize="8" transform="rotate(-90 10 90)">Harvest (kg)</text>
                                </svg>
                            </div>
                        )
                    })()}
                </div>
            )}

            {/* ── Seasons History Cards ─────────────────────────────────── */}
            <div className="glass-card rounded-2xl p-6">
                <h2 className="text-xl font-bold mb-4">Seasons History</h2>
                {seasons.length === 0 ? (
                    <p className="text-slate-400">No history yet.</p>
                ) : (
                    <div className="season-card-grid">
                        {seasons.map(season => {
                            const survival = seasonSurvivalPct(season)
                            const isOpen = expandedSeasonId === season.id
                            const startLabel = new Date(season.start_date).toLocaleDateString()
                            const endLabel = season.end_date
                                ? new Date(season.end_date).toLocaleDateString()
                                : null
                            return (
                                <article key={season.id} className={`season-card${isOpen ? ' is-open' : ''}`}>
                                    <button
                                        type="button"
                                        className="season-card-head"
                                        aria-expanded={isOpen}
                                        onClick={() => setExpandedSeasonId(isOpen ? null : season.id)}
                                    >
                                        <div className="season-card-titleblock">
                                            <div className="season-card-name">{season.name}</div>
                                            <div className="season-card-dates">
                                                {startLabel}
                                                {endLabel ? ` → ${endLabel}` : ''}
                                            </div>
                                        </div>
                                        <div className="season-card-meta">
                                            {endLabel
                                                ? <span className="season-chip">{formatAmount(season.total_harvest_kg)}</span>
                                                : <span className="px-2 py-1 rounded bg-emerald-600/30 text-emerald-700">Active</span>
                                            }
                                            <span className={`season-caret${isOpen ? ' is-open' : ''}`} aria-hidden>▾</span>
                                        </div>
                                    </button>
                                    {isOpen && (
                                        <div className="season-card-body">
                                            <div className="season-stat-grid">
                                                <div className="season-stat">
                                                    <div className="season-stat-label">Start</div>
                                                    <div className="season-stat-value">{startLabel}</div>
                                                </div>
                                                <div className="season-stat">
                                                    <div className="season-stat-label">End</div>
                                                    <div className="season-stat-value">
                                                        {endLabel || <span className="px-2 py-1 rounded bg-emerald-600/30 text-emerald-700">Active</span>}
                                                    </div>
                                                </div>
                                                <div className="season-stat">
                                                    <div className="season-stat-label">Initial Stock</div>
                                                    <div className="season-stat-value">{formatPcs(seasonInitialStock(season))}</div>
                                                </div>
                                                <div className="season-stat">
                                                    <div className="season-stat-label">Current / Final Qty</div>
                                                    <div className="season-stat-value">{formatPcs(season.current_shrimp_quantity)}</div>
                                                </div>
                                                <div className="season-stat">
                                                    <div className="season-stat-label">ABW</div>
                                                    <div className="season-stat-value">{formatAbw(season.average_shrimp_weight_grams)}</div>
                                                </div>
                                                <div className="season-stat">
                                                    <div className="season-stat-label">Survival</div>
                                                    <div className="season-stat-value">{survival != null ? `${survival}%` : '—'}</div>
                                                </div>
                                                <div className="season-stat">
                                                    <div className="season-stat-label">Total</div>
                                                    <div className="season-stat-value">{formatAmount(season.total_harvest_kg)}</div>
                                                </div>
                                                <div className="season-stat">
                                                    <div className="season-stat-label">Harvests</div>
                                                    <div className="season-stat-value">{season.harvest_count || 0}</div>
                                                </div>
                                            </div>
                                            <div className="season-card-actions">
                                                <button type="button" onClick={() => handleViewOverview(season.id)}
                                                    className="season-action-btn">View Overview</button>
                                                <button type="button" onClick={() => exportSeasonCSV(season)}
                                                    className="season-action-btn is-export">Export Excel</button>
                                            </div>
                                        </div>
                                    )}
                                </article>
                            )
                        })}
                    </div>
                )}
            </div>

            {selectedSeason && (
                <div ref={overviewRef} className="glass-card rounded-2xl p-6 mt-6">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-xl font-bold">Season Overview</h2>
                        <div className="flex gap-2">
                            <button type="button" onClick={() => exportSeasonCSV(selectedSeason)}
                                className="season-action-btn is-export">Export Excel</button>
                            <button type="button" onClick={() => { setSelectedSeasonId(null); setSelectedEntries([]) }}
                                className="season-action-btn is-close">Close</button>
                        </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                        <div className="glass-card rounded-2xl p-4">
                            <div className="text-slate-400">Season</div>
                            <div className="text-lg font-semibold">{selectedSeason.name}</div>
                        </div>
                        <div className="glass-card rounded-2xl p-4">
                            <div className="text-slate-400">Start</div>
                            <div className="text-lg font-semibold">{new Date(selectedSeason.start_date).toLocaleDateString()}</div>
                        </div>
                        <div className="glass-card rounded-2xl p-4">
                            <div className="text-slate-400">End</div>
                            <div className="text-lg font-semibold">{selectedSeason.end_date ? new Date(selectedSeason.end_date).toLocaleDateString() : '— (Active)'}</div>
                        </div>
                        <div className="glass-card rounded-2xl p-4">
                            <div className="text-slate-400">Total</div>
                            <div className="text-lg font-semibold">{formatAmount(selectedSeason.total_harvest_kg)}</div>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        <div className="glass-card rounded-2xl p-4">
                            <div className="text-slate-400">Initial Stock</div>
                            <div className="text-lg font-semibold">{formatPcs(seasonInitialStock(selectedSeason))}</div>
                        </div>
                        <div className="glass-card rounded-2xl p-4">
                            <div className="text-slate-400">Current / Final Qty</div>
                            <div className="text-lg font-semibold">{formatPcs(selectedSeason.current_shrimp_quantity)}</div>
                        </div>
                        <div className="glass-card rounded-2xl p-4">
                            <div className="text-slate-400">ABW</div>
                            <div className="text-lg font-semibold">{formatAbw(selectedSeason.average_shrimp_weight_grams)}</div>
                        </div>
                        <div className="glass-card rounded-2xl p-4">
                            <div className="text-slate-400">Survival</div>
                            <div className="text-lg font-semibold">
                                {seasonSurvivalPct(selectedSeason) != null ? `${seasonSurvivalPct(selectedSeason)}%` : '—'}
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                        <div className="glass-card rounded-2xl p-4">
                            <div className="text-slate-400">Harvests</div>
                            <div className="text-lg font-semibold">{selectedSeason.harvest_count}</div>
                        </div>
                        <div className="glass-card rounded-2xl p-4">
                            <div className="text-slate-400">Avg per Harvest</div>
                            <div className="text-lg font-semibold">{formatAmount(selectedSeason.harvest_count > 0 ? selectedSeason.total_harvest_kg / selectedSeason.harvest_count : 0)}</div>
                        </div>
                        <div className="glass-card rounded-2xl p-4">
                            <div className="text-slate-400">Days Active</div>
                            <div className="text-lg font-semibold">{selectedSeason.days_active}</div>
                        </div>
                    </div>

                    <h3 className="text-lg font-semibold mb-2">Entries</h3>
                    <div className="space-y-2">
                        {selectedEntries.length === 0 && <div className="text-slate-400">No entries</div>}
                        {selectedEntries.map(e => {
                            let dayBadge = null
                            try {
                                const start = new Date(selectedSeason.start_date)
                                const d = new Date(e.date)
                                const daysSince = Math.floor((d - start) / (1000 * 60 * 60 * 24))
                                dayBadge = `Day ${Math.max(1, daysSince + 1)}`
                            } catch { dayBadge = null }
                            return (
                                <div key={e.id} className="flex items-center gap-2">
                                    <span className="text-slate-600">{new Date(e.date).toLocaleDateString()}</span>
                                    {dayBadge && <span className="text-xs px-2 py-1 rounded bg-slate-700 text-white">{dayBadge}</span>}
                                    <span>{formatAmount(e.amount)}</span>
                                    <span>{e.is_all ? <span className="px-2 py-1 rounded bg-blue-600/30 text-blue-700">All</span> : 'Partial'}</span>
                                    <span className="text-slate-400">{e.note || '—'}</span>
                                    <button type="button" onClick={() => setPendingDeleteEntry(e)}
                                        className="season-action-btn is-danger ml-auto">Delete</button>
                                </div>
                            )
                        })}
                    </div>
                </div>
            )}

            {/* ── Multi-Season Comparison Table ─────────────────────────── */}
            {seasons.length >= 2 && (
                <div className="glass-card rounded-2xl p-6 mt-6">
                    <h2 className="text-xl font-bold mb-4">📊 Multi-Season Comparison</h2>
                    <div className="overflow-x-auto">
                        <table className="min-w-full text-sm">
                            <thead>
                                <tr className="text-left text-slate-400">
                                    <th className="py-2 pr-4">Metric</th>
                                    {seasons.map(s => (
                                        <th key={s.id} className="py-2 pr-4 text-center">{s.name}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                <tr className="border-t border-white/10">
                                    <td className="py-2 pr-4 font-medium">Duration (days)</td>
                                    {seasons.map(s => (
                                        <td key={s.id} className="py-2 pr-4 text-center">{s.days_active || '—'}</td>
                                    ))}
                                </tr>
                                <tr className="border-t border-white/10">
                                    <td className="py-2 pr-4 font-medium">Initial Stock (pcs)</td>
                                    {seasons.map(s => (
                                        <td key={s.id} className="py-2 pr-4 text-center font-semibold">{formatPcs(seasonInitialStock(s))}</td>
                                    ))}
                                </tr>
                                <tr className="border-t border-white/10">
                                    <td className="py-2 pr-4 font-medium">Current / Final Qty (pcs)</td>
                                    {seasons.map(s => (
                                        <td key={s.id} className="py-2 pr-4 text-center font-semibold">{formatPcs(s.current_shrimp_quantity)}</td>
                                    ))}
                                </tr>
                                <tr className="border-t border-white/10">
                                    <td className="py-2 pr-4 font-medium">Avg Weight / ABW (g)</td>
                                    {seasons.map(s => (
                                        <td key={s.id} className="py-2 pr-4 text-center">{formatAbw(s.average_shrimp_weight_grams)}</td>
                                    ))}
                                </tr>
                                <tr className="border-t border-white/10">
                                    <td className="py-2 pr-4 font-medium">Survival Rate</td>
                                    {seasons.map(s => {
                                        const survival = seasonSurvivalPct(s)
                                        return (
                                            <td key={s.id} className="py-2 pr-4 text-center">
                                                {survival != null ? `${survival}%` : '—'}
                                            </td>
                                        )
                                    })}
                                </tr>
                                <tr className="border-t border-white/10">
                                    <td className="py-2 pr-4 font-medium">Biomass (kg)</td>
                                    {seasons.map(s => {
                                        const bio = s.current_shrimp_quantity && s.average_shrimp_weight_grams
                                            ? (s.current_shrimp_quantity * s.average_shrimp_weight_grams / 1000)
                                            : 0
                                        return (
                                            <td key={s.id} className="py-2 pr-4 text-center">
                                                {bio > 0 ? bio.toFixed(1) : '—'}
                                            </td>
                                        )
                                    })}
                                </tr>
                                <tr className="border-t border-white/10">
                                    <td className="py-2 pr-4 font-medium">Total Harvest (kg)</td>
                                    {seasons.map(s => (
                                        <td key={s.id} className="py-2 pr-4 text-center font-semibold">{(s.total_harvest_kg || 0).toFixed(1)}</td>
                                    ))}
                                </tr>
                                <tr className="border-t border-white/10">
                                    <td className="py-2 pr-4 font-medium">Harvest Count</td>
                                    {seasons.map(s => (
                                        <td key={s.id} className="py-2 pr-4 text-center">{s.harvest_count || 0}</td>
                                    ))}
                                </tr>
                                <tr className="border-t border-white/10">
                                    <td className="py-2 pr-4 font-medium">Avg per Harvest (kg)</td>
                                    {seasons.map(s => {
                                        const avg = s.harvest_count > 0 ? (s.total_harvest_kg || 0) / s.harvest_count : 0
                                        return <td key={s.id} className="py-2 pr-4 text-center">{avg > 0 ? avg.toFixed(1) : '—'}</td>
                                    })}
                                </tr>
                                <tr className="border-t border-white/10">
                                    <td className="py-2 pr-4 font-medium">Yield per Day (kg/day)</td>
                                    {seasons.map(s => {
                                        const yieldPerDay = s.days_active > 0 ? (s.total_harvest_kg || 0) / s.days_active : 0
                                        return <td key={s.id} className="py-2 pr-4 text-center">{yieldPerDay > 0 ? yieldPerDay.toFixed(2) : '—'}</td>
                                    })}
                                </tr>
                                <tr className="border-t border-white/10">
                                    <td className="py-2 pr-4 font-medium">Stocking Density</td>
                                    {seasons.map(s => (
                                        <td key={s.id} className="py-2 pr-4 text-center">{s.stocking_density > 0 ? s.stocking_density.toLocaleString() : '—'}</td>
                                    ))}
                                </tr>
                                <tr className="border-t border-white/10">
                                    <td className="py-2 pr-4 font-medium">Status</td>
                                    {seasons.map(s => (
                                        <td key={s.id} className="py-2 pr-4 text-center">
                                            {!s.end_date
                                                ? <span className="season-status-active">Active</span>
                                                : <span className="season-status-completed">✓ Completed</span>
                                            }
                                        </td>
                                    ))}
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {pendingDeleteEntry ? (
                <div className="aq-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="delete-entry-title">
                    <div className="card aq-modal">
                        <h3 id="delete-entry-title" className="text-lg font-semibold mb-2">Delete harvest entry</h3>
                        <p className="text-sm text-cyan-100/80 mb-4">
                            Delete this harvest entry? This cannot be undone.
                        </p>
                        <p className="text-xs text-cyan-200/60 mb-5">
                            {pendingDeleteEntry.date ? new Date(pendingDeleteEntry.date).toLocaleDateString() : ''}
                            {pendingDeleteEntry.amount != null ? ` · ${formatAmount(pendingDeleteEntry.amount)}` : ''}
                            {pendingDeleteEntry.note ? ` · ${pendingDeleteEntry.note}` : ''}
                        </p>
                        <div className="flex justify-end gap-2">
                            <button type="button" className="season-action-btn is-close" onClick={() => setPendingDeleteEntry(null)} disabled={actionLoading}>
                                Cancel
                            </button>
                            <button type="button" className="season-action-btn is-danger" onClick={handleDeleteEntry} disabled={actionLoading}>
                                {actionLoading ? 'Deleting...' : 'Delete'}
                            </button>
                        </div>
                    </div>
                </div>
            ) : null}
        </div>
    )
}

export default HistoryOverview
