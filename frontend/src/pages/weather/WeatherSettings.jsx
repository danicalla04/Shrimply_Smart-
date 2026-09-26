import { useWeather } from './WeatherContext';
import { getDefaultWeatherSettings } from '../../services/weather/settings';

export default function WeatherSettings() {
  const { settings, setSettings } = useWeather();

  const units = settings?.units || getDefaultWeatherSettings().units;
  const tempUnit = units.temperatureUnit;

  return (
    <div className="space-y-6">
      <div className="glass-card p-6">
        <h2 className="text-2xl font-bold text-slate-900">Settings</h2>
        <div className="text-slate-600 mt-1">Preferences are saved in localStorage.</div>

        <div className="mt-6 metric-card-modern p-5">
          <div className="font-bold text-slate-900 mb-2">Units</div>

          <div className="text-sm font-semibold text-slate-700">Temperature</div>
          <div className="mt-2 flex gap-2">
            <button
              className="px-4 py-2 rounded-xl border text-sm font-semibold"
              style={{
                color: '#ffffff',
                background: tempUnit === 'celsius' ? '#1d4ed8' : '#123a5c',
                borderColor: '#7dd3fc',
              }}
              onClick={() => setSettings({ ...settings, units: { ...units, temperatureUnit: 'celsius' } })}
            >
              °C
            </button>
            <button
              className="px-4 py-2 rounded-xl border text-sm font-semibold"
              style={{
                color: '#ffffff',
                background: tempUnit === 'fahrenheit' ? '#1d4ed8' : '#123a5c',
                borderColor: '#7dd3fc',
              }}
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
      </div>
    </div>
  );
}
