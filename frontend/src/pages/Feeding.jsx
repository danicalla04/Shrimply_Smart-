import { useEffect, useRef, useState } from 'react';
import * as XLSX from 'xlsx';
import { useLanguage } from '../context/LanguageContext';
import {
  DEFAULT_FEEDER_STATE,
  hopperPercentFromDistance,
  HOPPER_TEN_PERCENT_CM,
  fetchFeederState,
  updateFeederSettings,
  toggleAutoFeeding,
  feedOnce,
  refillFeeder,
  processAutoFeedTick,
  fetchFeedingHistory,
  fetchMlFeedRecommendation,
  applyMlTodayFeed
} from '../services/feeder';
import { wemosApi } from '../services/wemos';
import { getChannelsWebSocketUrl } from '../services/apiConfig';
import { alertWebSocket } from '../services/alertWebSocket';

function Toggle({ checked, onChange, label }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-8 w-14 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${checked ? 'bg-gradient-to-r from-blue-500 to-blue-600' : 'bg-gray-300'
        }`}
      aria-pressed={checked}
      aria-label={label}
    >
      <span
        className={`inline-block h-6 w-6 transform rounded-full bg-white shadow-lg transition-transform ${checked ? 'translate-x-7' : 'translate-x-1'
          }`}
      />
    </button>
  );
}

function Stat({ label, value, sub, icon }) {
  return (
    <div className="card p-6 relative overflow-hidden">
      {icon && <div className="absolute top-4 right-4 text-3xl opacity-30">{icon}</div>}
      <div className="text-sm font-medium text-cyan-200/70 uppercase tracking-wide">{label}</div>
      <div className="mt-2 text-3xl font-bold text-cyan-100" style={{ fontFamily: 'Orbitron, sans-serif' }}>
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-cyan-200/50">{sub}</div>}
    </div>
  );
}

function useInterval(callback, delay) {
  const savedCallback = useRef();
  useEffect(() => { savedCallback.current = callback; }, [callback]);
  useEffect(() => {
    if (delay == null) return;
    const id = setInterval(() => savedCallback.current && savedCallback.current(), delay);
    return () => clearInterval(id);
  }, [delay]);
}

export default function Feeding() {
  const { t } = useLanguage();
  const [state, setState] = useState(() => DEFAULT_FEEDER_STATE);
  const [now, setNow] = useState(Date.now());
  const [feedingHistory, setFeedingHistory] = useState([]);
  const [activeTab, setActiveTab] = useState('controls');
  const [newDailyTime, setNewDailyTime] = useState('08:00');
  const [servoState, setServoState] = useState('OFF');
  const [ultrasonicDistance, setUltrasonicDistance] = useState('NA');
  const [wemosOnline, setWemosOnline] = useState(false);
  const [lastTelemetryTimestamp, setLastTelemetryTimestamp] = useState(null);
  const [servoLoading, setServoLoading] = useState(false);
  const [servoScheduleOpenTime, setServoScheduleOpenTime] = useState('08:00');
  const [servoScheduleCloseTime, setServoScheduleCloseTime] = useState('18:00');
  const [servoScheduleEnabled, setServoScheduleEnabled] = useState(false);
  const [servoScheduleSaving, setServoScheduleSaving] = useState(false);
  const [toast, setToast] = useState(null);
  const [mlRec, setMlRec] = useState(null);
  const [mlLoading, setMlLoading] = useState(false);
  const [mlError, setMlError] = useState(null);
  const [mlApplying, setMlApplying] = useState(false);
  const [todayPlan, setTodayPlan] = useState(null);
  const [slotEditor, setSlotEditor] = useState(null); // { oldTime, time, kg }
  const lastTelemetryRef = useRef(null);
  const TELEMETRY_STALE_MS = 20000;

  const isTelemetryFresh = (ts = lastTelemetryRef.current) => {
    if (!ts) return false;
    const age = Date.now() - new Date(ts).getTime();
    return Number.isFinite(age) && age >= 0 && age <= TELEMETRY_STALE_MS;
  };

  const flash = (msg, type = 'error') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  // Portion per feed is stored in the backend as whole grams (machine
  // dispenses in grams), but shown to users in kg for easier reading.
  const gramsToKgInput = (g) => Math.round(((Number(g) || 0) / 1000) * 1000) / 1000;
  const kgInputToGrams = (kg) => Math.max(1, Math.round(Number(kg || 0) * 1000));

  const todayISO = () => {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  };

  const openSlotEditor = (timeStr) => {
    const slots = todayPlan?.slots_kg || mlRec?.slots_kg || {};
    const kg = slots[timeStr] != null ? Number(slots[timeStr]) : '';
    setSlotEditor({ oldTime: timeStr, time: timeStr, kg });
  };

  const saveSlotEditor = async () => {
    if (!slotEditor) return;
    const newTime = String(slotEditor.time || '').trim().slice(0, 5);
    if (!/^\d{2}:\d{2}$/.test(newTime)) {
      flash('Enter a valid time (HH:MM)', 'error');
      return;
    }
    const kgNum = slotEditor.kg === '' || slotEditor.kg == null ? null : Number(slotEditor.kg);
    if (kgNum != null && (Number.isNaN(kgNum) || kgNum < 0)) {
      flash('Enter a valid feed amount (kg)', 'error');
      return;
    }

    try {
      const oldTime = slotEditor.oldTime;
      let schedule = [...(state.dailySchedule || [])];
      const idx = schedule.indexOf(oldTime);
      if (idx >= 0) schedule[idx] = newTime;
      else if (!schedule.includes(newTime)) schedule.push(newTime);
      // dedupe + sort
      schedule = [...new Set(schedule.filter(Boolean))].sort();

      let plan = todayPlan ? { ...todayPlan } : (state.todayFeedPlan ? { ...state.todayFeedPlan } : null);
      if (plan) {
        const slots = { ...(plan.slots_kg || {}) };
        const oldKg = slots[oldTime];
        if (oldTime !== newTime) delete slots[oldTime];
        if (kgNum != null) slots[newTime] = Math.round(kgNum * 100) / 100;
        else if (oldKg != null) slots[newTime] = oldKg;
        else if (slots[newTime] == null) slots[newTime] = 0;
        const total = Object.values(slots).reduce((s, v) => s + (Number(v) || 0), 0);
        plan = {
          ...plan,
          date: plan.date || todayISO(),
          slots_kg: slots,
          times: Object.keys(slots).sort(),
          total_kg: Math.round(total * 100) / 100,
        };
      }

      const updatedState = await updateFeederSettings({
        schedule_type: 'daily',
        daily_schedule: schedule,
        ...(plan ? { today_feed_plan: plan } : {}),
      });
      setState(updatedState);
      if (plan) {
        setTodayPlan(plan);
        setMlRec((prev) => prev ? { ...prev, slots_kg: plan.slots_kg, total_kg: plan.total_kg } : prev);
      }
      setSlotEditor(null);
      flash('Feeding time updated', 'success');
    } catch (e) {
      console.error(e);
      flash(e.message || 'Failed to update time', 'error');
    }
  };

  const exportHistoryExcel = async () => {
    try {
      const logs = await fetchFeedingHistory(200);
      if (!logs.length) {
        flash('No feeding history to export', 'error');
        return;
      }
      const rows = [
        ['Smart Shrimp AI — Feeding History'],
        [`Exported: ${new Date().toLocaleString()}`],
        [],
        ['#', 'Date', 'Time', 'Type', 'Portion (g)', 'Capacity Before (g)', 'Capacity After (g)', 'Notes'],
        ...logs.map((f, i) => {
          const ts = new Date(f.timestamp);
          return [
            i + 1,
            ts.toLocaleDateString(),
            ts.toLocaleTimeString(),
            String(f.feed_type || '').replace(/_/g, ' '),
            f.portion_grams ?? '',
            f.capacity_before ?? '',
            f.capacity_after ?? '',
            f.notes || '',
          ];
        }),
      ];
      if (todayPlan?.date === todayISO()) {
        rows.push([]);
        rows.push(["Today's ML Feed Plan"]);
        rows.push(['Date', todayPlan.date]);
        rows.push(['DOC', todayPlan.doc ?? '']);
        rows.push(['Total (kg)', todayPlan.total_kg ?? '']);
        rows.push([]);
        rows.push(['Time', 'Feed (kg)']);
        Object.entries(todayPlan.slots_kg || {}).sort(([a], [b]) => a.localeCompare(b)).forEach(([t, kg]) => {
          rows.push([t, kg]);
        });
      }
      const ws = XLSX.utils.aoa_to_sheet(rows);
      ws['!cols'] = [
        { wch: 5 }, { wch: 14 }, { wch: 12 }, { wch: 18 },
        { wch: 12 }, { wch: 18 }, { wch: 18 }, { wch: 50 },
      ];
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, 'Feeding History');
      XLSX.writeFile(wb, `feeding_history_${todayISO()}.xlsx`);
      flash('Excel downloaded', 'success');
    } catch (e) {
      flash(e.message || 'Excel export failed', 'error');
    }
  };

  const exportHistoryPdf = async () => {
    try {
      const logs = await fetchFeedingHistory(200);
      if (!logs.length && !(todayPlan?.date === todayISO())) {
        flash('No feeding history to print', 'error');
        return;
      }
      const planRows = todayPlan?.date === todayISO()
        ? Object.entries(todayPlan.slots_kg || {}).sort(([a], [b]) => a.localeCompare(b))
            .map(([t, kg]) => `<tr><td>${t}</td><td style="text-align:right">${kg} kg</td></tr>`).join('')
        : '';
      const historyRows = logs.map((f, i) => {
        const ts = new Date(f.timestamp);
        return `<tr>
          <td>${i + 1}</td>
          <td>${ts.toLocaleDateString()}</td>
          <td>${ts.toLocaleTimeString()}</td>
          <td>${String(f.feed_type || '').replace(/_/g, ' ')}</td>
          <td style="text-align:right">${f.portion_grams ?? ''} g</td>
          <td>${(f.notes || '').replace(/</g, '&lt;')}</td>
        </tr>`;
      }).join('');

      const html = `<!DOCTYPE html><html><head><meta charset="utf-8"/>
        <title>Feeding History</title>
        <style>
          body { font-family: Segoe UI, Arial, sans-serif; color: #0f172a; margin: 28px; }
          h1 { margin: 0 0 4px; font-size: 22px; }
          .sub { color: #64748b; margin-bottom: 18px; font-size: 12px; }
          h2 { font-size: 15px; margin: 22px 0 8px; color: #065f46; }
          table { width: 100%; border-collapse: collapse; font-size: 12px; }
          th, td { border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; }
          th { background: #0f766e; color: #fff; }
          tr:nth-child(even) td { background: #f8fafc; }
          .meta { display: flex; gap: 18px; margin-bottom: 8px; font-size: 13px; }
          @media print { body { margin: 12mm; } }
        </style></head><body>
        <h1>Smart Shrimp AI — Feeding History</h1>
        <div class="sub">Exported ${new Date().toLocaleString()}</div>
        ${todayPlan?.date === todayISO() ? `
          <h2>Today's ML Feed Plan</h2>
          <div class="meta">
            <div><strong>Date:</strong> ${todayPlan.date}</div>
            <div><strong>DOC:</strong> ${todayPlan.doc ?? '—'}</div>
            <div><strong>Total:</strong> ${todayPlan.total_kg ?? '—'} kg</div>
          </div>
          <table><thead><tr><th>Time</th><th>Feed amount</th></tr></thead>
          <tbody>${planRows}</tbody></table>` : ''}
        <h2>Feed Events</h2>
        <table>
          <thead><tr><th>#</th><th>Date</th><th>Time</th><th>Type</th><th>Portion</th><th>Notes</th></tr></thead>
          <tbody>${historyRows || '<tr><td colspan="6">No feed events</td></tr>'}</tbody>
        </table>
        <script>window.onload=function(){window.print();}</script>
        </body></html>`;
      const w = window.open('', '_blank', 'width=900,height=700');
      if (!w) {
        flash('Allow pop-ups to print PDF', 'error');
        return;
      }
      w.document.write(html);
      w.document.close();
    } catch (e) {
      flash(e.message || 'PDF print failed', 'error');
    }
  };

  const loadMlRecommendation = async () => {
    setMlLoading(true);
    setMlError(null);
    try {
      const data = await fetchMlFeedRecommendation();
      if (data?.error) {
        setMlError(data.error);
        setMlRec(null);
      } else {
        setMlRec(data);
      }
    } catch (e) {
      setMlError(e.message || 'Failed to load ML recommendation');
      setMlRec(null);
    } finally {
      setMlLoading(false);
    }
  };

  const useAsTodayFeed = async (planOverride) => {
    const planToApply = planOverride || mlRec;
    if (!planToApply?.slots_kg) {
      flash('Get a recommendation first', 'error');
      return;
    }
    setMlApplying(true);
    setMlError(null);
    try {
      const res = await applyMlTodayFeed(planToApply);
      if (res?.error) {
        setMlError(res.error);
        flash(res.error, 'error');
        return;
      }
      const plan = res.today_feed_plan || res.todayFeedPlan;
      setTodayPlan(plan);
      const [feederState, history] = await Promise.all([
        fetchFeederState(),
        fetchFeedingHistory(20),
      ]);
      setState(feederState);
      setFeedingHistory(history);
      flash("Saved as today's feed plan", 'success');
      return plan;
    } catch (e) {
      const msg = e.message || 'Failed to apply today feed plan';
      setMlError(msg);
      flash(msg, 'error');
    } finally {
      setMlApplying(false);
    }
  };

  // Turning Auto Feeding on should immediately pull the freshest ML
  // recommendation and push it into the daily schedule, instead of leaving
  // whatever schedule (or none) was there before.
  const enableAutoFeedingWithMlPlan = async () => {
    setMlLoading(true);
    setMlError(null);
    try {
      const data = await fetchMlFeedRecommendation();
      if (data?.error) {
        setMlError(data.error);
        flash(`Auto feeding is on, but couldn't load today's recommendation: ${data.error}`, 'error');
        return;
      }
      setMlRec(data);
      setMlLoading(false);
      await useAsTodayFeed(data);
    } catch (e) {
      const msg = e.message || 'Failed to load ML recommendation';
      setMlError(msg);
      flash(`Auto feeding is on, but couldn't load today's recommendation: ${msg}`, 'error');
    } finally {
      setMlLoading(false);
    }
  };

  // UI only supports interval + daily scheduling.
  // If backend ever returns another value, default to interval.
  const effectiveScheduleType = state.scheduleType === 'daily' ? 'daily' : 'interval';

  // Fetch schedule once (live telemetry uses WebSocket)
  const fetchWemosData = async () => {
    try {
      const schedule = await wemosApi.getServoSchedule().catch(() => null);

      if (schedule) {
        const open = schedule.open_time || schedule.openTime;
        const close = schedule.close_time || schedule.closeTime;
        if (open) setServoScheduleOpenTime(open);
        if (close) setServoScheduleCloseTime(close);
        setServoScheduleEnabled(Boolean(schedule.enabled));
      }
    } catch (error) {
      console.error('Failed to fetch Wemos data:', error);
    }
  };

  // Fetch initial state from backend
  useEffect(() => {
    const loadData = async () => {
      try {
        const [feederState, history] = await Promise.all([
          fetchFeederState(),
          fetchFeedingHistory(20)
        ]);
        setState(feederState);
        setFeedingHistory(history);
        const plan = feederState.todayFeedPlan;
        if (plan?.date === todayISO()) {
          setTodayPlan(plan);
          setMlRec((prev) => prev || {
            total_kg: plan.total_kg,
            slots_kg: plan.slots_kg,
            doc: plan.doc,
            harvest_scale: plan.harvest_scale,
            weather: plan.weather,
            season: plan.season,
            model_name: plan.model_name,
            note: 'Loaded saved today feed plan',
          });
        } else {
          setTodayPlan(null);
        }
      } catch (error) {
        console.error('Failed to load feeder data:', error);
        // Keep default state
      }
    };
    loadData();

    // One-time schedule fetch
    fetchWemosData();

    // Initial servo state only (distance waits for fresh telemetry)
    (async () => {
      try {
        const servo = await wemosApi.getServoState().catch(() => null);
        if (servo) setServoState(servo);
      } catch {
        // ignore
      }
    })();

    // Live feeder telemetry push (no polling)
    let ws = null;
    let reconnectTimeout = null;
    const WS_URL = getChannelsWebSocketUrl('/ws/feeder/');

    const connectWebSocket = () => {
      try {
        ws = new WebSocket(WS_URL);

        ws.onopen = () => {
          setWemosOnline(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            if (data.timestamp) {
              setLastTelemetryTimestamp(data.timestamp);
            }

            const motor = (data.motor_state ?? data.motorState ?? data.servo_state ?? data.servoState);
            if (motor !== undefined && motor !== null && String(motor).trim() !== '') {
              const normalized = String(motor).trim().toUpperCase();
              setServoState(normalized === 'ON' ? 'ON' : 'OFF');
            }

            if (data.distance_cm !== undefined) {
              if (data.distance_cm === null || data.distance_cm === '') {
                setUltrasonicDistance('NA');
              } else {
                const n = Number(data.distance_cm);
                setUltrasonicDistance(Number.isFinite(n) ? String(Math.round(n * 10) / 10) : 'NA');
              }
            }
          } catch (err) {
            console.warn('[WS_FEEDER] Failed to parse message:', err);
          }
        };

        ws.onclose = () => {
          setWemosOnline(false);
          reconnectTimeout = setTimeout(connectWebSocket, 5000);
        };

        ws.onerror = (err) => {
          console.warn('[WS_FEEDER] Error:', err);
          try {
            ws.close();
          } catch {
            // ignore
          }
        };
      } catch (err) {
        console.warn('[WS_FEEDER] Could not connect:', err);
        setWemosOnline(false);
        reconnectTimeout = setTimeout(connectWebSocket, 5000);
      }
    };

    connectWebSocket();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, []);

  useEffect(() => {
    const seenAlerts = new Set();

    const onAlert = (data) => {
      const alert = data?.alert;
      if (!alert || !alert.id || seenAlerts.has(alert.id)) return;
      seenAlerts.add(alert.id);

      if (alert.parameter === 'feeder_connection' || alert.parameter === 'feeder_capacity' || alert.parameter === 'feeder_level') {
        flash(alert.message || 'Feeder alert received', 'error');
        if ('Notification' in window && Notification.permission === 'granted') {
          new Notification('🚨 Feeder Alert', {
            body: `${alert.parameter}: ${alert.message}`,
            icon: '/alert-icon.png'
          });
        }
      }
    };

    alertWebSocket.connect(onAlert);
    return () => {
      alertWebSocket.disconnect(onAlert);
    };
  }, []);

  // Poll Django feeder telemetry (WeMos → PHP → MySQL). Do not use the
  // device HTTP fallback — that returns the last saved row forever.
  useInterval(async () => {
    try {
      const tel = await wemosApi.getLatestTelemetry().catch(() => null);
      if (tel?.timestamp) {
        const age = Date.now() - new Date(tel.timestamp).getTime();
        if (Number.isFinite(age) && age >= 0 && age <= TELEMETRY_STALE_MS) {
          setLastTelemetryTimestamp(tel.timestamp);
          if (tel.distance_cm != null && tel.distance_cm !== 'NA') {
            setUltrasonicDistance(String(tel.distance_cm));
          }
          // Keep last distance if this row is a servo click with no new reading
        }
      }
      if (!wemosOnline) {
        const servo = await wemosApi.getServoState().catch(() => null);
        if (servo) setServoState(servo);
      }
    } catch {
      // ignore
    }
  }, 3000);

  // Migration: remove legacy 'adaptive' schedule type.
  useEffect(() => {
    if (state.scheduleType !== 'adaptive') return;
    updateFeederSettings({ schedule_type: 'interval' })
      .then((updated) => setState(updated))
      .catch((error) => console.error('Failed to migrate schedule type:', error));
  }, [state.scheduleType]);
  // Tick every 30 seconds: update time and process auto feed events
  useInterval(async () => {
    setNow(Date.now());
    try {
      const updatedState = await processAutoFeedTick();
      if (updatedState && updatedState.id) {
        setState(updatedState);
        // Refresh history every other tick (~60 seconds)
        if (now % 60000 < 30000) {
          const history = await fetchFeedingHistory(20);
          setFeedingHistory(history);
        }
      }
    } catch (error) {
      console.error('Failed to process auto feed:', error);
    }
  }, 30000);

  useInterval(() => {
    setNow(Date.now());
  }, 1000);

  useEffect(() => {
    lastTelemetryRef.current = lastTelemetryTimestamp;
  }, [lastTelemetryTimestamp]);

  const telemetryAgeMs = lastTelemetryTimestamp ? (now - new Date(lastTelemetryTimestamp).getTime()) : Number.POSITIVE_INFINITY;
  const deviceConnected = Number.isFinite(telemetryAgeMs) && telemetryAgeMs >= 0 && telemetryAgeMs <= TELEMETRY_STALE_MS;
  const ultrasonicConnected = deviceConnected && ultrasonicDistance !== 'NA';
  const capPct = ultrasonicConnected ? hopperPercentFromDistance(ultrasonicDistance) : null
  const lowThreshold = 10
  const lowFeed = capPct != null && capPct <= lowThreshold

  const prevDeviceConnected = useRef(null);
  const prevLowFeed = useRef(null);
  const prevUltrasonicOk = useRef(null);
  const prevUltrasonicLow = useRef(null);
  const ULTRASONIC_LOW_CM = HOPPER_TEN_PERCENT_CM;
  const ultrasonicCm = Number(ultrasonicDistance);
  const ultrasonicLow = deviceConnected && Number.isFinite(ultrasonicCm) && ultrasonicCm >= ULTRASONIC_LOW_CM;

  useEffect(() => {
    if (prevDeviceConnected.current === true && deviceConnected === false) {
      flash(t('deviceDisconnected') || 'Device disconnected', 'error');
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('⚠️ Device Disconnected', { body: 'Feeder device is offline.' });
      }
    }
    prevDeviceConnected.current = deviceConnected;
  }, [deviceConnected, t]);

  useEffect(() => {
    if (!deviceConnected) {
      setUltrasonicDistance('NA');
    }
  }, [deviceConnected]);

  // Alert when the ultrasonic sensor becomes disconnected/unavailable.
  useEffect(() => {
    const alertsEnabled = (state.alertsEnabled !== false && state.alerts_enabled !== false);
    if (alertsEnabled && prevUltrasonicOk.current === true && ultrasonicConnected === false) {
      const msg = deviceConnected
        ? (t('ultrasonicDisconnected') || 'Ultrasonic sensor disconnected (no reading)')
        : (t('ultrasonicOffline') || 'Ultrasonic disconnected (device offline)');
      flash(msg, 'error');
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('📡 Ultrasonic Disconnected', { body: msg });
      }
    }
    prevUltrasonicOk.current = ultrasonicConnected;
  }, [ultrasonicConnected, deviceConnected, state.alertsEnabled, state.alerts_enabled, t]);

  useEffect(() => {
    const alertsEnabled = (state.alertsEnabled !== false && state.alerts_enabled !== false);
    const lowFeedEnabled = (state.lowFeedAlert !== false && state.low_feed_alert !== false);

    if (alertsEnabled && lowFeedEnabled) {
      if (prevLowFeed.current === false && lowFeed === true) {
        flash(t('lowFeed') || `Low feed: ${capPct}% remaining`, 'error');
        if ('Notification' in window && Notification.permission === 'granted') {
          new Notification('🍤 Low Feed', { body: `Feeder capacity low (${capPct}%).` });
        }
      }
    }
    prevLowFeed.current = lowFeed;
  }, [lowFeed, capPct, state.alertsEnabled, state.alerts_enabled, state.lowFeedAlert, state.low_feed_alert, t]);

  useEffect(() => {
    const alertsEnabled = (state.alertsEnabled !== false && state.alerts_enabled !== false);
    const lowFeedEnabled = (state.lowFeedAlert !== false && state.low_feed_alert !== false);
    if (alertsEnabled && lowFeedEnabled && prevUltrasonicLow.current === false && ultrasonicLow === true) {
      const msg = `Feeder is low on feeds — please refill (${ultrasonicCm} cm).`;
      flash(msg, 'error');
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('🍤 Feeder Low', { body: msg });
      }
    }
    prevUltrasonicLow.current = ultrasonicLow;
  }, [ultrasonicLow, ultrasonicCm, state.alertsEnabled, state.alerts_enabled, state.lowFeedAlert, state.low_feed_alert]);

  return (
    <div className="p-8">
      <div className="mb-8">
        <div className="pond-kicker">IoT feeder control</div>
        <h1 className="aq-title mb-2">{t('feedingManagement')}</h1>
        <p className="aq-sub">{t('feedingSubtitle')}</p>
      </div>

      {/* Status Overview */}
      <div className="grid-modern mb-8">
        <div className="metric-card-modern">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 rounded-xl bg-gradient-to-r from-green-500 to-teal-500 text-white shadow-lg">
              <span className="text-2xl">⏰</span>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-slate-800">{state.status === 'scheduled' ? t('active') : state.status === 'due' ? t('due') : t('manual')}</div>
              <div className="text-sm text-slate-500">{t('mode')}</div>
            </div>
          </div>
          <h3 className="text-lg font-semibold text-slate-800 mb-1">{t('feedingStatus')}</h3>
          <div className="text-sm text-slate-600">
            {state.nextFeedTime ? `${t('nextFeed')}: ${new Date(state.nextFeedTime).toLocaleString()}` : t('noScheduleSet')}
          </div>
        </div>

        <div className="metric-card-modern">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg">
              <span className="text-2xl">📈</span>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-slate-800">{feedingHistory.length}</div>
              <div className="text-sm text-slate-500">{t('totalFeeds')}</div>
            </div>
          </div>
          <h3 className="text-lg font-semibold text-slate-800 mb-1">{t('feedHistory')}</h3>
          <div className="text-sm text-slate-600">
            {state.lastFedAt ? `${t('lastFeed')}: ${new Date(state.lastFedAt).toLocaleString()}` : t('noFeedsYet')}
          </div>
        </div>
      </div>

      {todayPlan?.date === todayISO() && (
        <div className="card mb-6">
          <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
            <div>
              <h3 className="text-lg font-bold">Today&apos;s feed plan (ML)</h3>
              <p className="text-sm text-cyan-200/70">
                {todayPlan.total_kg} kg total · DOC {todayPlan.doc} · Schedule type: Daily
              </p>
            </div>
            <span className="px-3 py-1 rounded-full bg-emerald-600 text-white text-xs font-semibold">Active today</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {Object.entries(todayPlan.slots_kg || {}).map(([time, kg]) => (
              <button
                key={time}
                type="button"
                onClick={() => openSlotEditor(time)}
                className="rounded-lg border border-cyan-400/15 bg-slate-950/40 p-3 text-center hover:border-cyan-300/40 transition-all"
                title="Click to view/edit this feeding time"
              >
                <div className="text-xs text-cyan-200/70">{time}</div>
                <div className="text-lg font-bold">{kg} kg</div>
                <div className="text-[10px] text-cyan-200/60 mt-1">Edit</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Empty Storage Alert */}
      {(state.capacityCurrent || state.capacity_current) <= 0 && (
        <div className="mb-6 relative overflow-hidden rounded-2xl bg-gradient-to-r from-red-500 to-orange-500 p-6 shadow-lg border-2 border-red-600">
          <div className="absolute inset-0 opacity-10">
            <div className="absolute top-0 right-0 w-40 h-40 bg-white rounded-full -mr-20 -mt-20"></div>
          </div>
          <div className="relative z-10 flex items-center gap-4">
            <div className="text-5xl">⚠️</div>
            <div>
              <h2 className="text-2xl font-bold text-white mb-1">{t('feedStorageEmpty') || 'Feed Storage Empty'}</h2>
              <p className="text-red-50 text-base">{t('feedStorageEmptyMsg') || 'Your feed storage is empty. Please refill the feeder to continue automatic feeding.'}</p>
            </div>
            <button
              onClick={async () => {
                try {
                  const updatedState = await refillFeeder();
                  setState(updatedState);
                } catch (error) {
                  console.error('Failed to refill feeder:', error);
                }
              }}
              className="ml-auto px-6 py-3 bg-white text-red-600 font-bold rounded-xl hover:bg-red-50 transition-all shadow-lg whitespace-nowrap"
            >
              🔄 {t('refillNow') || 'Refill Now'}
            </button>
          </div>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="mb-6">
        <div className="feed-tabs">
          {[
            { id: 'controls', label: t('controls'), icon: '🎛️' },
            { id: 'schedule', label: t('schedule'), icon: '📅' },
            { id: 'settings', label: t('settings'), icon: '⚙️' },
            { id: 'history', label: t('history'), icon: '📋' }
          ].map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`feed-tab ${activeTab === tab.id ? 'is-active' : ''}`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="space-y-6">
        {activeTab === 'controls' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Auto Mode Toggle */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-white via-green-50 to-emerald-50 p-6 shadow-lg border border-green-100">
              <div className="absolute bottom-0 left-0 w-40 h-40 bg-gradient-to-tr from-green-200/20 to-transparent rounded-full -ml-20 -mb-20"></div>
              <h3 className="text-xl font-bold text-slate-800 mb-5 flex items-center">
                <span className="mr-2 text-2xl">⚡</span>
                {t('autoFeedingMode')}
              </h3>
              <div className="space-y-4 relative z-10">
                <div className="flex items-center justify-between p-4 rounded-xl bg-white/60 backdrop-blur-sm border border-slate-200">
                  <span className="text-base font-semibold text-slate-800">{t('autoFeeding')}</span>
                  <Toggle
                    checked={state.autoEnabled !== false && state.auto_enabled !== false}
                    onChange={async (value) => {
                      try {
                        const updatedState = await toggleAutoFeeding(value);
                        setState(updatedState);
                        if (value) {
                          flash("Auto feeding on — applying today's ML recommendation…", 'success');
                          await enableAutoFeedingWithMlPlan();
                        }
                      } catch (error) {
                        console.error('Failed to toggle auto feeding:', error);
                      }
                    }}
                    label="Auto Feeding Toggle"
                  />
                </div>
                {(state.autoEnabled !== false && state.auto_enabled !== false) && (
                  <div className="p-4 bg-gradient-to-r from-green-500 to-emerald-500 rounded-xl shadow-md text-white">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-sm font-semibold opacity-90 mb-1">{t('nextFeed')}</div>
                        <div className="text-lg font-bold">
                          {state.nextFeedTime ? new Date(state.nextFeedTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : t('calculating')}
                        </div>
                      </div>
                      <div className="text-2xl">⏰</div>
                    </div>
                    <div className="mt-2 text-xs bg-white/20 rounded-lg px-3 py-2 backdrop-blur-sm">
                      {t('mode')}: {effectiveScheduleType === 'daily' ? '📅 ' + t('daily') : '⚙️ ' + t('interval')}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Hardware Controls - Servo and Ultrasonic */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-white via-orange-50 to-red-50 p-6 shadow-lg border border-orange-100">
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-orange-200/20 to-transparent rounded-full -mr-16 -mt-16"></div>
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-xl font-bold text-slate-800 flex items-center">
                  <span className="mr-2 text-2xl">⚙️</span>
                  Hardware Controls
                </h3>
              </div>
              <div className="space-y-4">
                {/* Wemos Status */}
                <div className="p-3 rounded-lg bg-white/60 backdrop-blur-sm border border-slate-200">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">Wemos Status:</span>
                    <div className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full animate-pulse ${deviceConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
                      <span className="text-sm font-medium text-slate-700">
                        {deviceConnected ? '🟢 Online' : '🔴 Offline'}
                      </span>
                    </div>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    Telemetry age: {lastTelemetryTimestamp ? `${Math.round(telemetryAgeMs / 1000)}s` : 'No data'}
                  </div>
                </div>

                {/* Ultrasonic Distance */}
                <div className="p-3 rounded-lg bg-white/60 backdrop-blur-sm border border-slate-200">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">Ultrasonic Distance:</span>
                    <span className="text-lg font-bold text-slate-800">
                      {!deviceConnected || ultrasonicDistance === 'NA'
                        ? 'Sensor disconnected'
                        : `📏 ${ultrasonicDistance} cm${capPct != null ? ` (${capPct}%)` : ''}`}
                    </span>
                  </div>
                </div>

                {/* Servo Control Buttons */}
                <div className="grid grid-cols-2 gap-3">
                  <button
                    className="relative overflow-hidden rounded-xl bg-gradient-to-r from-red-600 to-pink-600 text-white font-semibold py-3 px-4 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                    onClick={async () => {
                      if (servoLoading) return;
                      try {
                        setServoLoading(true);
                        await wemosApi.servoOff();
                        setServoState('OFF');
                      } catch (error) {
                        console.error('Failed to turn servo OFF:', error);
                      } finally {
                        setServoLoading(false);
                      }
                    }}
                    disabled={servoLoading}
                  >
                    {servoLoading ? (
                      <>
                        <span className="mr-2 animate-spin">⚙️</span>
                        <span>Loading...</span>
                      </>
                    ) : (
                      <>
                        <span className="mr-2 text-lg">❌</span>
                        <span>Servo OFF</span>
                      </>
                    )}
                  </button>
                  <button
                    className="relative overflow-hidden rounded-xl bg-gradient-to-r from-green-600 to-emerald-600 text-white font-semibold py-3 px-4 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                    onClick={async () => {
                      if (servoLoading) return;
                      try {
                        setServoLoading(true);
                        await wemosApi.servoOn();
                        setServoState('ON');
                      } catch (error) {
                        console.error('Failed to turn servo ON:', error);
                      } finally {
                        setServoLoading(false);
                      }
                    }}
                    disabled={servoLoading}
                  >
                    {servoLoading ? (
                      <>
                        <span className="mr-2 animate-spin">⚙️</span>
                        <span>Loading...</span>
                      </>
                    ) : (
                      <>
                        <span className="mr-2 text-lg">✅</span>
                        <span>Servo ON</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Current Servo State */}
                <div className="p-3 rounded-lg bg-white/60 backdrop-blur-sm border border-slate-200">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">Servo State:</span>
                    <span className={`text-lg font-bold flex items-center gap-2 ${servoState === 'ON' ? 'text-green-600' : 'text-red-600'}`}>
                      <span className="text-xl">{servoState === 'ON' ? '✅' : '❌'}</span>
                      {servoState}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'schedule' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Feeding Schedule */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-white via-blue-50 to-cyan-50 p-6 shadow-lg border border-blue-100">
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-blue-200/20 to-transparent rounded-full -mr-16 -mt-16"></div>
              <h3 className="text-xl font-bold text-slate-800 mb-5 flex items-center relative z-10">
                <span className="mr-2 text-2xl">📅</span>
                {t('schedule')}
              </h3>
              <div className="space-y-4 relative z-10">
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-2">Schedule Type</label>
                  <select
                    className="w-full border-2 border-blue-200 rounded-xl px-4 py-3 text-base font-semibold focus:border-blue-500 focus:ring-4 focus:ring-blue-100 transition-all bg-white"
                    value={effectiveScheduleType}
                    onChange={async (e) => {
                      try {
                        const updatedState = await updateFeederSettings({ schedule_type: e.target.value });
                        setState(updatedState);
                      } catch (error) {
                        console.error('Failed to update schedule type:', error);
                      }
                    }}
                  >
                    <option value="interval">Interval</option>
                    <option value="daily">Daily</option>
                  </select>
                </div>

                {effectiveScheduleType === 'interval' && (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-bold text-slate-700 mb-2">Interval (minutes)</label>
                      <input
                        type="number"
                        className="w-full border-2 border-blue-200 rounded-xl px-4 py-3 text-base font-semibold focus:border-blue-500 focus:ring-4 focus:ring-blue-100 transition-all"
                        value={state.intervalMinutes || 60}
                        onChange={async (e) => {
                          try {
                            const minutes = Math.max(1, Number(e.target.value || 1));
                            const updatedState = await updateFeederSettings({ interval_minutes: minutes });
                            setState(updatedState);
                          } catch (error) {
                            console.error('Failed to update interval:', error);
                          }
                        }}
                        min={1}
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-bold text-slate-700 mb-2">{t('portionPerFeed') || 'Portion per Feed (kg)'}</label>
                      <input
                        type="number"
                        step="0.01"
                        className="w-full border-2 border-blue-200 rounded-xl px-4 py-3 text-base font-semibold focus:border-blue-500 focus:ring-4 focus:ring-blue-100 transition-all"
                        value={gramsToKgInput(state.portionGrams || 50)}
                        onChange={async (e) => {
                          try {
                            const grams = kgInputToGrams(e.target.value);
                            const updatedState = await updateFeederSettings({ portion_grams: grams });
                            setState(updatedState);
                          } catch (error) {
                            console.error('Failed to update portion grams:', error);
                          }
                        }}
                        min={0}
                      />
                    </div>
                  </div>
                )}

                {effectiveScheduleType === 'daily' && (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-bold text-slate-700 mb-2">{t('portionPerFeed') || 'Portion per Feed (kg)'}</label>
                      <input
                        type="number"
                        step="0.01"
                        className="w-full border-2 border-blue-200 rounded-xl px-4 py-3 text-base font-semibold focus:border-blue-500 focus:ring-4 focus:ring-blue-100 transition-all"
                        value={gramsToKgInput(state.portionGrams || 50)}
                        onChange={async (e) => {
                          try {
                            const grams = kgInputToGrams(e.target.value);
                            const updatedState = await updateFeederSettings({ portion_grams: grams });
                            setState(updatedState);
                          } catch (error) {
                            console.error('Failed to update portion grams:', error);
                          }
                        }}
                        min={0}
                      />
                    </div>

                    <div className="text-sm font-bold text-slate-700">Daily Times</div>
                    <p className="text-xs text-slate-500">Click a time to see kg and adjust the clock.</p>
                    <div className="space-y-2">
                      {(state.dailySchedule || []).length === 0 ? (
                        <div className="text-sm text-slate-500">No times set.</div>
                      ) : (
                        (state.dailySchedule || []).map((timeStr) => {
                          const kg = todayPlan?.slots_kg?.[timeStr] ?? mlRec?.slots_kg?.[timeStr];
                          return (
                          <div key={timeStr} className="flex items-center justify-between p-3 bg-white rounded-xl border border-slate-200 gap-2">
                            <button
                              type="button"
                              onClick={() => openSlotEditor(timeStr)}
                              className="flex-1 text-left font-semibold text-slate-800 hover:text-blue-700"
                            >
                              ⏰ {timeStr}
                              {kg != null && (
                                <span className="ml-2 text-sm font-bold text-emerald-700">{kg} kg</span>
                              )}
                              <span className="ml-2 text-xs text-blue-600 font-medium">Edit</span>
                            </button>
                            <button
                              onClick={async () => {
                                try {
                                  const newSchedule = (state.dailySchedule || []).filter(ti => ti !== timeStr);
                                  let plan = todayPlan ? { ...todayPlan, slots_kg: { ...(todayPlan.slots_kg || {}) } } : null;
                                  if (plan?.slots_kg) {
                                    delete plan.slots_kg[timeStr];
                                    plan.times = Object.keys(plan.slots_kg).sort();
                                    plan.total_kg = Math.round(Object.values(plan.slots_kg).reduce((s, v) => s + (Number(v) || 0), 0) * 100) / 100;
                                  }
                                  const updatedState = await updateFeederSettings({
                                    daily_schedule: newSchedule,
                                    ...(plan ? { today_feed_plan: plan } : {}),
                                  });
                                  setState(updatedState);
                                  if (plan) setTodayPlan(plan);
                                } catch (error) {
                                  console.error('Failed to remove time:', error);
                                }
                              }}
                              className="px-3 py-1 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-semibold"
                            >
                              Remove
                            </button>
                          </div>
                          );
                        })
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <input
                        type="time"
                        value={newDailyTime}
                        onChange={(e) => setNewDailyTime(e.target.value)}
                        className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                      />
                      <button
                        onClick={async () => {
                          try {
                            const currentTimes = (state.dailySchedule || []).filter(ti => ti && ti.trim());
                            const next = newDailyTime;
                            if (!next || !next.trim()) return;
                            if (currentTimes.includes(next)) return;
                            const newSchedule = [...currentTimes, next].sort();
                            const updatedState = await updateFeederSettings({ daily_schedule: newSchedule });
                            setState(updatedState);
                          } catch (error) {
                            console.error('Failed to add time:', error);
                          }
                        }}
                        className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold"
                      >
                        Add
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* ML Weather-Adaptive Feed Recommendation */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-white via-green-50 to-emerald-50 p-6 shadow-lg border border-green-100 lg:col-span-2">
              <h3 className="text-xl font-bold text-slate-800 mb-2 flex items-center">
                <span className="mr-2 text-2xl">🤖</span>
                ML Feed Recommendation
              </h3>
              <p className="text-sm text-slate-600 mb-4">
                Weather + DOC model (kg/day). Does not change Feed Once — that still uses your input amount for machine testing.
              </p>
              <div className="flex flex-wrap gap-3 mb-4">
                <button
                  type="button"
                  onClick={loadMlRecommendation}
                  disabled={mlLoading}
                  className="px-4 py-2 rounded-lg bg-emerald-600 text-white font-semibold hover:bg-emerald-700 disabled:opacity-60"
                >
                  {mlLoading ? 'Loading…' : 'Get today\'s recommendation'}
                </button>
                {mlRec?.slots_kg && (
                  <button
                    type="button"
                    onClick={() => useAsTodayFeed()}
                    disabled={mlApplying}
                    className="px-4 py-2 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 disabled:opacity-60"
                  >
                    {mlApplying ? 'Saving…' : "Use as today's feed"}
                  </button>
                )}
              </div>
              {todayPlan?.date === todayISO() && (
                <div className="mb-4 p-3 rounded-xl bg-blue-50 border border-blue-200 text-sm text-blue-900">
                  <strong>Today&apos;s feed plan is active</strong>
                  {' '}({todayPlan.total_kg} kg · DOC {todayPlan.doc} · daily schedule saved).
                  Open Schedule tab to see the times.
                </div>
              )}
              {mlError && (
                <div className="mb-3 p-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-100">{mlError}</div>
              )}
              {mlRec && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="p-3 bg-white rounded-xl border border-emerald-100">
                      <div className="text-xs text-slate-500 uppercase">Total today</div>
                      <div className="text-2xl font-bold text-emerald-700">{mlRec.total_kg} kg</div>
                      {mlRec.base_total_kg != null && (
                        <div className="text-[11px] text-slate-400">base {mlRec.base_total_kg} kg before growth scale</div>
                      )}
                    </div>
                    <div className="p-3 bg-white rounded-xl border border-emerald-100">
                      <div className="text-xs text-slate-500 uppercase">DOC</div>
                      <div className="text-2xl font-bold text-slate-800">{mlRec.doc}</div>
                    </div>
                    <div className="p-3 bg-white rounded-xl border border-emerald-100">
                      <div className="text-xs text-slate-500 uppercase">Growth scale</div>
                      <div className="text-2xl font-bold text-slate-800">{Math.round((mlRec.growth_scale || 1) * 100)}%</div>
                      <div className="text-[11px] text-slate-500">
                        {mlRec.growth?.shrimp_count != null ? `${Number(mlRec.growth.shrimp_count).toLocaleString()} pcs` : '—'}
                        {' · '}
                        {mlRec.growth?.abw_g != null ? `${mlRec.growth.abw_g} g` : '—'}
                      </div>
                    </div>
                    <div className="p-3 bg-white rounded-xl border border-emerald-100">
                      <div className="text-xs text-slate-500 uppercase">Temp / rain</div>
                      <div className="text-lg font-bold text-slate-800">
                        {mlRec.weather?.temp_mean ?? '—'}°C / {mlRec.weather?.rain_sum ?? '—'} mm
                      </div>
                    </div>
                  </div>
                  {(mlRec.season?.from_growth_metric || mlRec.growth) && (
                    <div className="text-xs text-emerald-800 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2">
                      Using Growth Dashboard: count={mlRec.season?.stocks ?? mlRec.growth?.shrimp_count} ·
                      ABW={mlRec.season?.abw_g ?? mlRec.growth?.abw_g} g ·
                      combined scale {Math.round((mlRec.combined_scale || 1) * 100)}%
                      {mlRec.total_grams != null ? ` · ≈ ${mlRec.total_grams.toLocaleString()} g/day` : ''}
                    </div>
                  )}
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                    {Object.entries(mlRec.slots_kg || {}).map(([time, kg]) => (
                      <button
                        key={time}
                        type="button"
                        onClick={() => openSlotEditor(time)}
                        className="p-3 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white text-center hover:brightness-110"
                        title="Click to edit time / kg"
                      >
                        <div className="text-xs opacity-90">{time}</div>
                        <div className="text-xl font-bold">{kg} kg</div>
                      </button>
                    ))}
                  </div>
                  {mlRec.season?.name && (
                    <p className="text-xs text-slate-500">
                      Season: {mlRec.season.name} · model: {mlRec.model_name} · {mlRec.note}
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Basic Settings */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-white via-indigo-50 to-purple-50 p-6 shadow-lg border border-indigo-100">
              <div className="absolute top-0 left-0 w-32 h-32 bg-gradient-to-br from-indigo-200/20 to-transparent rounded-full -ml-16 -mt-16"></div>
              <h3 className="text-xl font-bold text-slate-800 mb-5 flex items-center relative z-10">
                <span className="mr-2 text-2xl">⚙️</span>
                {t('basicSettings')}
              </h3>
              <div className="space-y-4 relative z-10">
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-2">🍤 {t('portionPerFeed')}</label>
                  <input
                    type="number"
                    step="0.01"
                    className="w-full border-2 border-indigo-200 rounded-xl px-4 py-3 text-base font-semibold focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100 transition-all"
                    value={gramsToKgInput(state.portionGrams || state.portion_grams)}
                    onChange={async (e) => {
                      try {
                        const grams = kgInputToGrams(e.target.value);
                        const updatedState = await updateFeederSettings({ portion_grams: grams });
                        setState(updatedState);
                      } catch (error) {
                        console.error('Failed to update portion:', error);
                      }
                    }}
                    min={0}
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Used for manual / interval feeding — the ML daily schedule sets its own kg per slot.
                  </p>
                </div>
              </div>
            </div>

            {/* Alert Settings */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-white via-red-50 to-orange-50 p-6 shadow-lg border border-red-100">
              <div className="absolute bottom-0 right-0 w-40 h-40 bg-gradient-to-tl from-red-200/20 to-transparent rounded-full -mr-20 -mb-20"></div>
              <h3 className="text-xl font-bold text-slate-800 mb-5 flex items-center relative z-10">
                <span className="mr-2 text-2xl">🔔</span>
                {t('alertSettings')}
              </h3>
              <div className="space-y-3 relative z-10">
                {[
                  { key: 'alertsEnabled', label: t('enableAlerts'), field: 'alerts_enabled', icon: '✅' },
                  { key: 'weatherAlert', label: t('weatherChangeAlerts'), field: 'weather_alert', icon: '☁️' }
                ].map(alert => (
                  <label
                    key={alert.key}
                    className="flex items-center p-4 bg-white rounded-xl border-2 border-slate-200 cursor-pointer hover:border-red-300 hover:shadow-md transition-all"
                  >
                    <input
                      type="checkbox"
                      checked={state[alert.key] !== false}
                      onChange={async (e) => {
                        try {
                          const updatedState = await updateFeederSettings({ [alert.field]: e.target.checked });
                          setState(updatedState);
                        } catch (error) {
                          console.error(`Failed to update ${alert.key}:`, error);
                        }
                      }}
                      className="w-5 h-5 mr-3 accent-red-500"
                    />
                    <span className="text-lg mr-3">{alert.icon}</span>
                    <span className="text-base font-semibold text-slate-800">{alert.label}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'history' && (
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-white via-slate-50 to-gray-50 p-6 shadow-lg border border-slate-200">
            <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-bl from-blue-200/10 to-transparent rounded-full -mr-32 -mt-32"></div>
            <div className="flex flex-wrap items-center justify-between gap-3 mb-6 relative z-10">
              <h3 className="text-2xl font-bold text-slate-800 flex items-center">
                <span className="mr-3 text-3xl">📊</span>
                {t('feedingHistory')}
              </h3>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={exportHistoryExcel}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold shadow"
                >
                  Export Excel
                </button>
                <button
                  type="button"
                  onClick={exportHistoryPdf}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-900 text-white text-sm font-semibold shadow"
                >
                  Print / PDF
                </button>
              </div>
            </div>
            <div className="space-y-3 max-h-[600px] overflow-y-auto relative z-10 custom-scrollbar pr-2">
              {feedingHistory.length === 0 ? (
                <div className="text-center py-16">
                  <div className="text-6xl mb-4">📋</div>
                  <div className="text-slate-500 font-medium text-lg">{t('noFeedingHistory')}</div>
                  <div className="text-slate-400 text-sm mt-2">{t('startFeedingToSeeHistory')}</div>
                </div>
              ) : (
                feedingHistory.map((feed, index) => (
                  <div key={index} className="group relative overflow-hidden flex items-center justify-between p-4 bg-white rounded-xl shadow-sm hover:shadow-md border border-slate-200 hover:border-blue-300 transition-all">
                    <div className="absolute inset-0 bg-gradient-to-r from-blue-500/0 to-cyan-500/0 group-hover:from-blue-500/5 group-hover:to-cyan-500/5 transition-all"></div>
                    <div className="flex items-center relative z-10">
                      <div className={`w-12 h-12 rounded-xl mr-4 flex items-center justify-center shadow-md ${feed.feed_type === 'manual' ? 'bg-gradient-to-br from-blue-500 to-blue-600' :
                        feed.feed_type === 'scheduled' ? 'bg-gradient-to-br from-green-500 to-green-600' :
                          feed.feed_type === 'weather_adjusted' ? 'bg-gradient-to-br from-yellow-500 to-amber-600' : 'bg-gradient-to-br from-purple-500 to-purple-600'
                        }`}>
                        <span className="text-white text-xl">
                          {feed.feed_type === 'manual' ? '🕹️' :
                            feed.feed_type === 'scheduled' ? '⏰' :
                              feed.feed_type === 'weather_adjusted' ? '☁️' : '🤖'}
                        </span>
                      </div>
                      <div>
                        <div className="font-bold text-lg text-slate-800">{feed.portion_grams}{t('gFed')}</div>
                        <div className="text-sm text-slate-500 font-medium">
                          {feed.feed_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                        </div>
                        {feed.notes && (
                          <div className="text-xs text-slate-400 mt-1 max-w-md truncate" title={feed.notes}>{feed.notes}</div>
                        )}
                      </div>
                    </div>
                    <div className="text-right relative z-10">
                      <div className="text-sm font-bold text-slate-700">
                        {new Date(feed.timestamp).toLocaleDateString()}
                      </div>
                      <div className="text-xs text-slate-500 font-medium">
                        {new Date(feed.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {slotEditor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl border border-slate-200 p-6">
            <h3 className="text-xl font-bold text-slate-800 mb-1">Edit feeding time</h3>
            <p className="text-sm text-slate-500 mb-4">See how much to feed and change the clock if needed.</p>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Time</label>
                <input
                  type="time"
                  value={slotEditor.time}
                  onChange={(e) => setSlotEditor((s) => ({ ...s, time: e.target.value }))}
                  className="w-full rounded-xl border-2 border-slate-200 px-4 py-3 font-semibold"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Feed amount (kg)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={slotEditor.kg}
                  onChange={(e) => setSlotEditor((s) => ({ ...s, kg: e.target.value }))}
                  className="w-full rounded-xl border-2 border-slate-200 px-4 py-3 font-semibold"
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setSlotEditor(null)}
                className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 font-semibold"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={saveSlotEditor}
                className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
