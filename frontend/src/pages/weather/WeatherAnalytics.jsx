import { useWeather } from './WeatherContext.jsx';

function num(value, digits = 0) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return digits > 0 ? n.toFixed(digits) : String(Math.round(n));
}

export default function WeatherAnalytics() {
  const { forecast, loading, lastUpdated, location, selectedMunicipality } = useWeather();
  const current = forecast?.current;
  const daily = forecast?.daily;
  const place = selectedMunicipality?.display_name || location?.name || 'this place';
  const live = Number.isFinite(Number(current?.temperature_2m));

  const cards = [
    { label: 'Temperature now', value: `${num(current?.temperature_2m)}°C`, note: `High ${num(daily?.temperature_2m_max?.[0])}° / low ${num(daily?.temperature_2m_min?.[0])}°` },
    { label: 'Humidity now', value: `${num(current?.relative_humidity_2m)}%`, note: 'From the live Open-Meteo reading' },
    { label: 'Wind now', value: `${num(current?.wind_speed_10m)} km/h`, note: `Gusts today up to ${num(daily?.wind_gusts_10m_max?.[0])} km/h` },
    { label: 'Rain chance today', value: `${num(daily?.precipitation_probability_max?.[0])}%`, note: `Rain so far ${num(daily?.precipitation_sum?.[0], 1)} mm` },
  ];

  if (loading && !forecast) {
    return (
      <div className="p-6 text-slate-300">Loading the live reading…</div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold mb-2">Analytics</h2>
          <p className="text-gray-300">Live Open-Meteo reading for {place}. These are the forecast values, not a scored model accuracy.</p>
        </div>
        <div className="text-right">
          <p className="text-sm text-gray-400">Last updated</p>
          <p className="text-lg font-semibold">{lastUpdated ? lastUpdated.toLocaleTimeString() : '—'}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-2xl p-6 bg-gradient-to-br from-blue-600 to-blue-800">
          <p className="text-blue-100 text-sm font-semibold mb-1">DATA SOURCE</p>
          <div className="text-3xl font-bold text-white">Open-Meteo</div>
          <p className="text-blue-100 text-sm mt-3">{live ? 'Active — this is the reading on the Weather home page.' : 'Waiting for a reading. Use Refresh.'}</p>
        </div>
        <div className="rounded-2xl p-6 bg-gradient-to-br from-emerald-600 to-emerald-800">
          <p className="text-emerald-100 text-sm font-semibold mb-1">CONDITION NOW</p>
          <div className="text-3xl font-bold text-white">{num(current?.temperature_2m)}°C</div>
          <p className="text-emerald-100 text-sm mt-3">
            Feels like {num(current?.apparent_temperature)}°C
            {Number(current?.precipitation) > 0 ? ` · rain ${num(current.precipitation, 1)} mm` : ' · no rain falling'}
          </p>
        </div>
        <div className="rounded-2xl p-6 bg-gradient-to-br from-purple-600 to-purple-800">
          <p className="text-purple-100 text-sm font-semibold mb-1">PRESSURE</p>
          <div className="text-3xl font-bold text-white">{num(current?.pressure_msl)} hPa</div>
          <p className="text-purple-100 text-sm mt-3">Same live packet as temperature and humidity.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((card) => (
          <div key={card.label} className="rounded-xl p-5 border border-sky-400/30 bg-slate-950/40">
            <p className="text-sm text-sky-100">{card.label}</p>
            <p className="text-3xl font-bold text-white mt-2">{card.value}</p>
            <p className="text-xs text-slate-300 mt-2">{card.note}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
