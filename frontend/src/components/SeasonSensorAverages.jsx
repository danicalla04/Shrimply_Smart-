import { useEffect, useState } from 'react'
import { getActiveSeason, getSensorAverages } from '../services/seasonBackend'

const AVG_RANGES = [
    { id: 'week', title: 'Week', subtitle: 'Last 7 days' },
    { id: 'month', title: 'Month', subtitle: 'Last 30 days' },
    { id: 'season', title: 'Whole season', subtitle: 'Every reading this season' },
]

const AVG_SPLITS = [
    { id: 'day', title: 'Day', subtitle: '8:00 AM – 8:00 PM' },
    { id: 'night', title: 'Night', subtitle: '8:00 PM – 8:00 AM' },
    { id: 'all', title: 'All hours', subtitle: 'Day and night combined' },
]

const fmt = (value, digits) => {
    if (value == null || value === '') return '—'
    return Number(value).toFixed(digits)
}

export default function SeasonSensorAverages({ averages: averagesProp, className = 'card mb-5' }) {
    const [localAvgs, setLocalAvgs] = useState(null)
    const [avgRange, setAvgRange] = useState('season')
    const [avgSplit, setAvgSplit] = useState('all')
    const averages = averagesProp === undefined ? localAvgs : averagesProp

    useEffect(() => {
        if (averagesProp !== undefined) return undefined
        let alive = true
        const load = async () => {
            const season = await getActiveSeason().catch(() => null)
            if (!season?.id) {
                if (alive) setLocalAvgs(null)
                return
            }
            const avgs = await getSensorAverages(season.id).catch(() => null)
            if (alive) setLocalAvgs(avgs)
        }
        load()
        const id = setInterval(load, 20000)
        return () => {
            alive = false
            clearInterval(id)
        }
    }, [averagesProp])

    if (!averages) return null
    const range = AVG_RANGES.find((row) => row.id === avgRange) || AVG_RANGES[2]
    const split = AVG_SPLITS.find((row) => row.id === avgSplit) || AVG_SPLITS[2]
    const rangeData = averages[range.id] || averages.season || averages
    const data = rangeData?.[split.id] || (split.id === 'all' ? (rangeData?.hours24 || rangeData) : null) || {}

    return (
        <div className={className}>
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                <div>
                    <div className="pond-kicker mb-1">This season</div>
                    <h2 className="font-semibold">Sensor averages</h2>
                </div>
                <div className="aq-range" role="group" aria-label="Sensor average filters">
                    {AVG_RANGES.map((row) => (
                        <button
                            key={row.id}
                            type="button"
                            aria-pressed={avgRange === row.id}
                            className={avgRange === row.id ? 'is-on' : ''}
                            onClick={() => setAvgRange(row.id)}
                        >
                            {row.title}
                        </button>
                    ))}
                    <span className="aq-range-split" aria-hidden="true" />
                    {AVG_SPLITS.map((row) => (
                        <button
                            key={row.id}
                            type="button"
                            aria-pressed={avgSplit === row.id}
                            className={avgSplit === row.id ? 'is-on' : ''}
                            onClick={() => setAvgSplit(row.id)}
                        >
                            {row.title}
                        </button>
                    ))}
                </div>
            </div>
            <p className="text-sm text-cyan-200/70 mb-3">{range.title} · {split.title} · {split.subtitle}</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-xl border border-cyan-400/15 bg-slate-950/40 p-3 text-center">
                    <div className="text-xs text-cyan-200/70">Avg Temp</div>
                    <div className="text-lg font-bold mt-1">{fmt(data.temperature, 1)}<span className="text-xs ml-1">°C</span></div>
                </div>
                <div className="rounded-xl border border-cyan-400/15 bg-slate-950/40 p-3 text-center">
                    <div className="text-xs text-cyan-200/70">Avg pH</div>
                    <div className="text-lg font-bold mt-1">{fmt(data.ph, 2)}</div>
                </div>
                <div className="rounded-xl border border-cyan-400/15 bg-slate-950/40 p-3 text-center">
                    <div className="text-xs text-cyan-200/70">Avg Turbidity</div>
                    <div className="text-lg font-bold mt-1">{fmt(data.turbidity, 1)}<span className="text-xs ml-1">NTU</span></div>
                </div>
                <div className="rounded-xl border border-cyan-400/15 bg-slate-950/40 p-3 text-center">
                    <div className="text-xs text-cyan-200/70">Avg TDS</div>
                    <div className="text-lg font-bold mt-1">{fmt(data.tds, 0)}<span className="text-xs ml-1">ppm</span></div>
                </div>
            </div>
            <div className="text-xs text-cyan-200/60 mt-3 text-center">{data.reading_count ?? 0} readings</div>
        </div>
    )
}
