import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { usePrivileges } from '../context/PrivilegesContext'
import { authService } from '../services/auth'
import API_BASE from '../services/apiConfig'
import { wemosApi } from '../services/wemos'
import { hopperPercentFromDistance } from '../services/feeder'

const OUTPUTS = [
  { target: 'LED1', label: 'LED 1', pin: 'D9' },
  { target: 'LED2', label: 'LED 2', pin: 'D2' },
  { target: 'LED3', label: 'LED 3', pin: 'D8' },
  { target: 'BUZZER', label: 'Buzzer', pin: 'D10' },
]

export default function HardwareControls() {
  const { isAdmin, username, loaded } = usePrivileges()
  const [telemetry, setTelemetry] = useState(null)
  const [now, setNow] = useState(Date.now())
  const [busy, setBusy] = useState('')
  const [lastRequest, setLastRequest] = useState({})
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isAdmin || username !== 'admin123') return
    let active = true
    const refresh = async () => {
      try {
        const data = await wemosApi.getLatestTelemetry()
        if (active) setTelemetry(data)
      } catch {
        if (active) setTelemetry(null)
      }
      if (active) setNow(Date.now())
    }
    refresh()
    const timer = setInterval(refresh, 5000)
    return () => { active = false; clearInterval(timer) }
  }, [isAdmin, username])

  if (!loaded) return <p className="p-6" role="status">Checking hardware access...</p>
  if (!isAdmin || username !== 'admin123') return <Navigate to="/dashboard" replace />

  const age = telemetry?.timestamp ? now - new Date(telemetry.timestamp).getTime() : Infinity
  const online = Number.isFinite(age) && age >= -5000 && age <= 20000
  const distance = Number(telemetry?.distance_cm)
  const capacity = online && telemetry?.distance_cm != null && Number.isFinite(distance)
    ? hopperPercentFromDistance(distance) : null

  const sendOutput = async (target, state) => {
    setBusy(target)
    setError('')
    setMessage('')
    try {
      const response = await authService.apiCall(`${API_BASE}/hardware/commands/`, {
        method: 'POST',
        body: JSON.stringify({ target, state }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not queue command.')
      setLastRequest(previous => ({ ...previous, [target]: state ? 'ON' : 'OFF' }))
      setMessage(`${target} ${state ? 'ON' : 'OFF'} queued. Watch the Wemos output to confirm it changed.`)
    } catch (err) {
      setError(err.message || 'Could not queue command.')
    } finally {
      setBusy('')
    }
  }

  const sendServo = async (state) => {
    setBusy('SERVO')
    setError('')
    setMessage('')
    try {
      if (state) await wemosApi.servoOn()
      else await wemosApi.servoOff()
      setMessage(`Servo ${state ? 'ON (L45)' : 'OFF (R45)'} queued. Watch the servo to confirm movement.`)
    } catch (err) {
      setError(err.message || 'Could not send servo command.')
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Hardware Controls</h1>
        <p className="text-sm text-slate-400 mt-2">Test the connected WeMos outputs. This page is available only to admin123.</p>
      </div>

      {message && <p className="alert-modern alert-success-modern" role="status">{message}</p>}
      {error && <p className="alert-modern alert-critical-modern" role="alert">{error}</p>}

      <section className="card p-5">
        <h2 className="text-xl font-semibold mb-4">Receiver and feeder</h2>
        <div className="grid gap-4 sm:grid-cols-3 mb-5">
          <div><span className="text-sm text-slate-400">Wemos status</span><p className="font-semibold">{online ? 'Online' : 'Offline or stale telemetry'}</p></div>
          <div><span className="text-sm text-slate-400">Ultrasonic distance</span><p className="font-semibold">{capacity == null ? 'Unavailable' : `${distance.toFixed(1)} cm · ${capacity}%`}</p></div>
          <div><span className="text-sm text-slate-400">Last reported motor state</span><p className="font-semibold">{online ? telemetry?.motor_state || 'Unknown' : 'Unknown'}</p></div>
        </div>
        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn-modern" disabled={Boolean(busy)} onClick={() => sendServo(true)}>Servo ON (L45)</button>
          <button type="button" className="btn-secondary" disabled={Boolean(busy)} onClick={() => sendServo(false)}>Servo OFF (R45)</button>
        </div>
      </section>

      <section className="card p-5">
        <h2 className="text-xl font-semibold mb-2">LEDs and buzzer</h2>
        <p className="text-sm text-slate-400 mb-5">Commands are queued for the WeMos to poll. The status below is the last request from this page, not device confirmation.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          {OUTPUTS.map(({ target, label, pin }) => (
            <div key={target} className="rounded-xl border border-slate-500/30 p-4">
              <div className="flex justify-between items-center mb-3"><strong>{label}</strong><span className="text-xs text-slate-400">{pin} · Last request: {lastRequest[target] || 'None'}</span></div>
              <div className="flex gap-3">
                <button type="button" className="btn-modern" disabled={Boolean(busy)} onClick={() => sendOutput(target, true)}>{label} ON</button>
                <button type="button" className="btn-secondary" disabled={Boolean(busy)} onClick={() => sendOutput(target, false)}>{label} OFF</button>
              </div>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-3 mt-5">
          <button type="button" className="btn-modern" disabled={Boolean(busy)} onClick={() => sendOutput('ALL', true)}>All ON</button>
          <button type="button" className="btn-secondary" disabled={Boolean(busy)} onClick={() => sendOutput('ALL', false)}>All OFF</button>
        </div>
      </section>
    </div>
  )
}
