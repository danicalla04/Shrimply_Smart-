import { useMemo, useState } from 'react';
import { useWeather } from './WeatherContext';
import { getDefaultWeatherSettings, mergeWeatherSettings } from '../../services/weather/settings';

function formatPlace(loc) {
  if (!loc) return '—';
  return [loc.name, loc.admin1, loc.country].filter(Boolean).join(', ');
}

export default function WeatherSettings() {
  const { settings, setSettings, location } = useWeather();
  const [nasaKey, setNasaKey] = useState(settings?.nasaApiKey || '');

  const units = settings?.units || getDefaultWeatherSettings().units;

  const onSave = () => {
    const next = {
      ...settings,
      nasaApiKey: nasaKey,
    };
    mergeWeatherSettings(next);
    setSettings(next);
  };

  const tempUnit = units.temperatureUnit;
  const theme = settings?.theme || 'light';

  const preferred = useMemo(() => formatPlace(location), [location]);

  return (
    <div className="space-y-6">
      <div className="glass-card p-6">
        <h2 className="text-2xl font-bold text-slate-900">Settings</h2>
        <div className="text-slate-600 mt-1">Preferences are saved in localStorage.</div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="metric-card-modern p-5">
            <div className="font-bold text-slate-900 mb-2">Units</div>

            <div className="text-sm font-semibold text-slate-700">Temperature</div>
            <div className="mt-2 flex gap-2">
              <button
                className={`px-4 py-2 rounded-xl border text-sm font-semibold ${
                  tempUnit === 'celsius' ? 'bg-white border-slate-200 shadow-sm' : 'bg-transparent border-slate-200'
                }`}
                onClick={() => setSettings({ ...settings, units: { ...units, temperatureUnit: 'celsius' } })}
              >
                °C
              </button>
              <button
                className={`px-4 py-2 rounded-xl border text-sm font-semibold ${
                  tempUnit === 'fahrenheit' ? 'bg-white border-slate-200 shadow-sm' : 'bg-transparent border-slate-200'
                }`}
                onClick={() => setSettings({ ...settings, units: { ...units, temperatureUnit: 'fahrenheit' } })}
              >
                °F
              </button>
            </div>

            <div className="mt-4 text-sm font-semibold text-slate-700">Wind Speed</div>
            <select
              value={units.windSpeedUnit}
              onChange={(e) => setSettings({ ...settings, units: { ...units, windSpeedUnit: e.target.value } })}
              className="input-modern mt-2"
            >
              <option value="kmh">km/h</option>
              <option value="ms">m/s</option>
              <option value="mph">mph</option>
              <option value="kn">kn</option>
            </select>

            <div className="mt-4 text-sm font-semibold text-slate-700">Precipitation</div>
            <select
              value={units.precipitationUnit}
              onChange={(e) => setSettings({ ...settings, units: { ...units, precipitationUnit: e.target.value } })}
              className="input-modern mt-2"
            >
              <option value="mm">mm</option>
              <option value="inch">inch</option>
            </select>
          </div>

          <div className="metric-card-modern p-5">
            <div className="font-bold text-slate-900 mb-2">Appearance</div>
            <div className="text-sm text-slate-600">Theme</div>
            <div className="mt-2 flex gap-2">
              <button
                className={`px-4 py-2 rounded-xl border text-sm font-semibold ${
                  theme === 'light' ? 'bg-white border-slate-200 shadow-sm' : 'bg-transparent border-slate-200'
                }`}
                onClick={() => setSettings({ ...settings, theme: 'light' })}
              >
                Light
              </button>
              <button
                className={`px-4 py-2 rounded-xl border text-sm font-semibold ${
                  theme === 'dark' ? 'bg-white border-slate-200 shadow-sm' : 'bg-transparent border-slate-200'
                }`}
                onClick={() => setSettings({ ...settings, theme: 'dark' })}
              >
                Dark
              </button>
            </div>

            <div className="mt-6">
              <div className="text-sm text-slate-600">Preferred city</div>
              <div className="mt-1 font-semibold text-slate-900">{preferred}</div>
              <div className="text-xs text-slate-500 mt-1">Use the search box on the Home page to change it.</div>
            </div>
          </div>

          <div className="metric-card-modern p-5 md:col-span-2">
            <div className="font-bold text-slate-900 mb-2">NASA</div>
            <div className="text-sm text-slate-600">
              Optional NASA API key for higher quota. Leave blank to use the demo key.
            </div>
            <input
              value={nasaKey}
              onChange={(e) => setNasaKey(e.target.value)}
              placeholder="NASA API key (optional)"
              className="input-modern mt-3"
            />
            <div className="mt-4 flex gap-2">
              <button onClick={onSave} className="btn-modern">Save</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
