import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { usePrivileges } from '../context/PrivilegesContext'
import { authService } from '../services/auth'
import API_BASE from '../services/apiConfig'
import { wemosApi } from '../services/wemos'
import { hopperPercentFromDistance } from '../services/feeder'

const OUTPUTS = [
  { target: 'LED1', label: 'Blue LED', pin: 'D9' },
  { target: 'LED2', label: 'Yellow LED', pin: 'D2' },
  { target: 'LED3', label: 'Red LED', pin: 'D8' },
  { target: 'BUZZER', label: 'Buzzer', pin: 'D10' },
]

const LED_MONITOR = [
  { color: 'BLUE', label: 'Blue', pin: 'D9', lit: 'bg-blue-500 shadow-[0_0_20px_#3b82f6]' },
  { color: 'YELLOW', label: 'Yellow', pin: 'D2', lit: 'bg-yellow-400 shadow-[0_0_20px_#facc15]' },
  { color: 'RED', label: 'Red', pin: 'D8', lit: 'bg-red-500 shadow-[0_0_20px_#ef4444]' },
]

export default function HardwareControls() {
  const { isAdmin, username, loaded } = usePrivileges()
  const [telemetry, setTelemetry] = useState(null)
  const [sensorStatus, setSensorStatus] = useState(null)
  const [outputReport, setOutputReport] = useState(null)
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
      try {
        const response = await authService.apiCall(`${API_BASE}/hardware/status/?format=json`)
        if (active) setSensorStatus(response.ok ? await response.json() : null)
      } catch {
        if (active) setSensorStatus(null)
      }
      try {
        const response = await authService.apiCall(`${API_BASE}/hardware/outputs/`)
        if (active) setOutputReport(response.ok ? await response.json() : null)
      } catch {
        if (active) setOutputReport(null)
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
  const reportAge = outputReport?.reported_at ? now - new Date(outputReport.reported_at).getTime() : Infinity
  const reportLive = Number.isFinite(reportAge) && reportAge >= -5000 && reportAge <= 15000
  const outputMismatch = reportLive && outputReport.mode === 'AUTO' && sensorStatus &&
    (outputReport.color !== sensorStatus.color || outputReport.buzzer !== sensorStatus.buzzer)

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

      <section className="card p-5" aria-live="polite">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <h2 className="text-xl font-semibold">LED and buzzer monitor</h2>
          <span className={`text-sm font-semibold ${reportLive ? 'text-emerald-400' : 'text-slate-400'}`}>{reportLive ? 'WeMos reporting' : 'No recent WeMos report'}</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {LED_MONITOR.map(({ color, label, pin, lit }) => {
            const isOn = reportLive && outputReport.color === color
            return <div key={color} className="rounded-xl border border-slate-500/30 p-4 text-center">
              <span className={`block mx-auto mb-3 h-10 w-10 rounded-full ${isOn ? lit : 'bg-slate-600'}`} aria-hidden="true" />
              <strong>{label} LED</strong>
              <p className="text-sm text-slate-400">{pin} · {reportLive ? isOn ? 'ON' : 'OFF' : 'Unknown'}</p>
            </div>
          })}
          <div className="rounded-xl border border-slate-500/30 p-4 text-center">
            <span className={`block mx-auto mb-3 h-10 w-10 rounded-full ${reportLive && outputReport.buzzer === 'ON' ? 'bg-orange-400 shadow-[0_0_20px_#fb923c]' : 'bg-slate-600'}`} aria-hidden="true" />
            <strong>Buzzer</strong>
            <p className="text-sm text-slate-400">D10 · {reportLive ? outputReport.buzzer : 'Unknown'}</p>
          </div>
        </div>
        <p className="text-xs text-slate-400 mt-4">{reportLive ? `${outputReport.mode === 'MANUAL' ? 'Manual test' : 'Automatic'} · Last report ${new Date(outputReport.reported_at).toLocaleTimeString()}` : 'Upload the updated WeMos sketch to start reporting.'} The WeMos reports its output pin states; this does not detect a broken LED or wire.</p>
        <div className="mt-4 rounded-xl border border-slate-500/30 p-4">
          <h3 className="font-semibold mb-1">Why this color?</h3>
          <p className="mb-2 text-xs text-slate-400">Blue: all four sensors in range. Yellow: one or two out of range, buzzer off. Red: three or four out of range, or a sensor reading is missing or stale; buzzer on.</p>
          {sensorStatus ? (
            <>
              <p className="text-sm text-slate-300">Sensors call for {sensorStatus.color.toLowerCase()} with buzzer {sensorStatus.buzzer.toLowerCase()}: {sensorStatus.reason}</p>
              {sensorStatus.issues?.length > 0 && <ul className="mt-2 list-disc pl-5 text-sm text-slate-400">{sensorStatus.issues.map(issue => <li key={issue}>{issue}</li>)}</ul>}
              {reportLive && outputReport.mode === 'MANUAL' && <p className="mt-2 text-sm text-amber-200">Manual test is active; the reported LED can differ from the sensor status for up to 30 seconds.</p>}
              {!reportLive && <p className="mt-2 text-sm text-amber-200">The WeMos has not reported recently, so its current LED state is unknown.</p>}
            </>
          ) : <p className="text-sm text-slate-400">Sensor status is unavailable.</p>}
        </div>
        {outputMismatch && <p className="mt-3 rounded-lg bg-amber-500/15 p-3 text-sm text-amber-200" role="alert">Sensors call for {sensorStatus.color} with buzzer {sensorStatus.buzzer}, but the WeMos reports {outputReport.color} with buzzer {outputReport.buzzer}. Check the WeMos connection and upload the latest sketch.</p>}
      </section>

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
        <p className="text-sm text-slate-400 mb-5">Manual commands take priority for 30 seconds, then automatic status resumes. The status below is the last request from this page, not device confirmation.</p>
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
          <button type="button" className="btn-secondary" disabled={Boolean(busy)} onClick={() => sendOutput('ALL', false)}>All OFF</button>
        </div>
      </section>
    </div>
  )
}
