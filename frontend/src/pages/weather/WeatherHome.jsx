import { useMemo } from 'react';
import { useWeather } from './WeatherContext';
import { wmoIcon, wmoLabel } from '../../services/weather/weatherCodes';
import MunicipalitySelector from '../../components/weather/MunicipalitySelector';

function toKm(meters) {
  const m = Number(meters);
  if (!Number.isFinite(m)) return null;
  return m / 1000;
}

function pickTodayIndex(daily) {
  if (!daily?.time || !Array.isArray(daily.time)) return 0;
  return 0;
}

function deriveAlerts(forecast) {
  const daily = forecast?.daily;
  if (!daily) return [];

  const alerts = [];
  const idx = 0;

  const p = daily?.precipitation_probability_max?.[idx];
  const gust = daily?.wind_gusts_10m_max?.[idx];
  const wcode = daily?.weather_code?.[idx];

  if (Number(p) >= 70) {
    alerts.push({
      level: 'warning',
      title: 'High rain chance',
      body: `Precipitation probability is ${Math.round(p)}% today.`,
    });
  }

  if (Number(gust) >= 50) {
    alerts.push({
      level: 'danger',
      title: 'Strong wind gusts',
      body: `Gusts may reach ${Math.round(gust)} today.`,
    });
  }

  if ([95, 96, 99].includes(Number(wcode))) {
    alerts.push({
      level: 'danger',
      title: 'Thunderstorm risk',
      body: 'Thunderstorm conditions are possible today.',
    });
  }

  return alerts.slice(0, 2);
}

export default function WeatherHome() {
  const { forecast, loading, settings, selectedMunicipality, onMunicipalityChange } = useWeather();

  const unitSymbol = settings?.units?.temperatureUnit === 'fahrenheit' ? '°F' : '°C';

  const current = forecast?.current;
  const daily = forecast?.daily;
  const hourly = forecast?.hourly;

  const todayIdx = useMemo(() => pickTodayIndex(daily), [daily]);
  const sunrise = daily?.sunrise?.[todayIdx];
  const sunset = daily?.sunset?.[todayIdx];
  const uvMax = daily?.uv_index_max?.[todayIdx];

  const alerts = useMemo(() => deriveAlerts(forecast), [forecast]);

  if (loading && !forecast) {
    return (
      <div className="grid grid-cols-1 gap-6">
        <div className="h-40 bg-gray-200 rounded-2xl animate-pulse" />
        <div className="h-64 bg-gray-200 rounded-2xl animate-pulse" />
        <div className="h-64 bg-gray-200 rounded-2xl animate-pulse" />
      </div>
    );
  }

  const currentIcon = wmoIcon(current?.weather_code, current?.is_day === 1);
  const condition = wmoLabel(current?.weather_code);
  const visibilityKm = toKm(current?.visibility);

  return (
    <div className="space-y-6">
      {/* MUNICIPALITY SELECTOR SECTION */}
      <div className="bg-gradient-to-r from-blue-50 to-cyan-50 p-6 rounded-2xl border border-blue-200 shadow-sm">
        <h3 className="text-lg font-bold text-gray-900 mb-3">📍 Oriental Mindoro Municipality</h3>
        <MunicipalitySelector
          value={selectedMunicipality}
          onChange={onMunicipalityChange}
          disabled={loading}
        />
      </div>

      {/* PRIMARY FOCUS BADGE */}
      {selectedMunicipality?.is_primary && (
        <div className="bg-gradient-to-r from-amber-50 to-yellow-50 border border-amber-300 rounded-2xl p-4 flex items-center gap-3 shadow-sm">
          <span className="text-3xl">⭐</span>
          <div>
            <div className="font-bold text-amber-900">High-Accuracy Weather Forecast</div>
            <div className="text-sm text-amber-700">
              Calapan City is optimized for 95%+ forecast accuracy with specialized ML models
            </div>
          </div>
        </div>
      )}

      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((a, idx) => (
            <div
              key={idx}
              className={`p-4 rounded-2xl border shadow-sm ${
                a.level === 'danger'
                  ? 'bg-red-50 border-red-200 text-red-900'
                  : 'bg-orange-50 border-orange-200 text-orange-900'
              }`}
            >
              <div className="font-bold">{a.title}</div>
              <div className="text-sm mt-1">{a.body}</div>
            </div>
          ))}
        </div>
      )}

      {/* CURRENT WEATHER */}
      <div className="glass-card p-6">
        <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-5">
            <div className="text-6xl">{currentIcon}</div>
            <div>
              <div className="flex items-start gap-2">
                <div className="text-6xl font-light text-slate-900 leading-none">
                  {Number.isFinite(current?.temperature_2m) ? Math.round(current.temperature_2m) : '—'}
                </div>
                <div className="text-2xl text-slate-600 mt-2">{unitSymbol}</div>
              </div>
              <div className="text-slate-700 font-semibold mt-1">{condition}</div>
              <div className="text-slate-600 text-sm">
                Feels like{' '}
                {Number.isFinite(current?.apparent_temperature) ? Math.round(current.apparent_temperature) : '—'}
                {unitSymbol}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
            <div className="metric-card-modern p-4">
              <div className="text-slate-500">Humidity</div>
              <div className="text-xl font-bold text-slate-800">
                {Number.isFinite(current?.relative_humidity_2m) ? Math.round(current.relative_humidity_2m) : '—'}%
              </div>
            </div>
            <div className="metric-card-modern p-4">
              <div className="text-slate-500">Wind</div>
              <div className="text-xl font-bold text-slate-800">
                {Number.isFinite(current?.wind_speed_10m) ? Math.round(current.wind_speed_10m) : '—'}
              </div>
            </div>
            <div className="metric-card-modern p-4">
              <div className="text-slate-500">UV (max)</div>
              <div className="text-xl font-bold text-slate-800">{Number.isFinite(uvMax) ? uvMax.toFixed(1) : '—'}</div>
            </div>
            <div className="metric-card-modern p-4">
              <div className="text-slate-500">Pressure</div>
              <div className="text-xl font-bold text-slate-800">
                {Number.isFinite(current?.pressure_msl) ? Math.round(current.pressure_msl) : '—'} hPa
              </div>
            </div>
            <div className="metric-card-modern p-4">
              <div className="text-slate-500">Visibility</div>
              <div className="text-xl font-bold text-slate-800">
                {Number.isFinite(visibilityKm) ? visibilityKm.toFixed(1) : '—'} km
              </div>
            </div>
            <div className="metric-card-modern p-4">
              <div className="text-slate-500">Sun</div>
              <div className="text-sm font-semibold text-slate-800">
                <div>↑ {sunrise ? new Date(sunrise).toLocaleTimeString() : '—'}</div>
                <div>↓ {sunset ? new Date(sunset).toLocaleTimeString() : '—'}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 7-DAY */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-slate-900">7‑Day Forecast</h2>
        </div>

        {!daily?.time ? (
          <div className="text-slate-600">No forecast available.</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {daily.time.slice(0, 7).map((t, idx) => {
              const w = daily.weather_code?.[idx];
              const maxT = daily.temperature_2m_max?.[idx];
              const minT = daily.temperature_2m_min?.[idx];
              const rainP = daily.precipitation_probability_max?.[idx];
              const wind = daily.wind_speed_10m_max?.[idx];

              return (
                <div key={t} className="metric-card-modern p-4">
                  <div className="text-sm text-slate-600">{new Date(t).toLocaleDateString(undefined, { weekday: 'short' })}</div>
                  <div className="text-3xl mt-2">{wmoIcon(w, true)}</div>
                  <div className="text-slate-800 font-semibold mt-2">{wmoLabel(w)}</div>
                  <div className="mt-2 text-sm text-slate-700">
                    <div>
                      <span className="font-semibold">{Number.isFinite(maxT) ? Math.round(maxT) : '—'}</span>
                      {unitSymbol} / {Number.isFinite(minT) ? Math.round(minT) : '—'}
                      {unitSymbol}
                    </div>
                    <div>Rain: {Number.isFinite(rainP) ? Math.round(rainP) : '—'}%</div>
                    <div>Wind: {Number.isFinite(wind) ? Math.round(wind) : '—'}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* HOURLY */}
      <div className="glass-card p-6">
        <h2 className="text-xl font-bold text-slate-900 mb-4">Hourly Forecast</h2>

        {!hourly?.time ? (
          <div className="text-slate-600">No hourly data available.</div>
        ) : (
          <div className="flex gap-4 overflow-x-auto pb-2">
            {hourly.time.slice(0, 24).map((t, idx) => {
              const temp = hourly.temperature_2m?.[idx];
              const rainP = hourly.precipitation_probability?.[idx];
              const w = hourly.weather_code?.[idx];
              const wind = hourly.wind_speed_10m?.[idx];
              const rh = hourly.relative_humidity_2m?.[idx];

              return (
                <div key={t} className="min-w-[160px] metric-card-modern p-4">
                  <div className="text-sm text-slate-600">{new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                  <div className="text-3xl mt-2">{wmoIcon(w, true)}</div>
                  <div className="text-2xl font-bold text-slate-800 mt-2">
                    {Number.isFinite(temp) ? Math.round(temp) : '—'}
                    {unitSymbol}
                  </div>
                  <div className="text-sm text-slate-700 mt-2 space-y-0.5">
                    <div>Rain: {Number.isFinite(rainP) ? Math.round(rainP) : '—'}%</div>
                    <div>Humidity: {Number.isFinite(rh) ? Math.round(rh) : '—'}%</div>
                    <div>Wind: {Number.isFinite(wind) ? Math.round(wind) : '—'}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
