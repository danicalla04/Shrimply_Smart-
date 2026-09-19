export default function GaugeRing({ value, min = 0, max = 100, unit = '', tone = 'offline' }) {
  const n = Number(value)
  const usable = Number.isFinite(n)
  const span = max - min || 1
  const pct = usable ? Math.min(100, Math.max(0, ((n - min) / span) * 100)) : 0
  const colors = {
    normal: '#34d399',
    warning: '#fbbf24',
    critical: '#fb7185',
    offline: '#94a3b8',
  }
  const color = colors[tone] || colors.offline
  const r = 42
  const c = 2 * Math.PI * r
  const dash = (pct / 100) * c

  return (
    <div className="relative mx-auto" style={{ width: 120, height: 120 }}>
      <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
        <circle cx="60" cy="60" r={r} fill="none" stroke="rgba(148,163,184,0.18)" strokeWidth="10" />
        <circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c}`}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <div className="text-xl font-bold" style={{ color, fontFamily: 'Orbitron, sans-serif' }}>
            {usable ? (Math.abs(n) >= 100 ? Math.round(n) : n.toFixed(1)) : '—'}
          </div>
          <div className="text-[10px] uppercase tracking-widest text-slate-400">{unit}</div>
        </div>
      </div>
    </div>
  )
}
