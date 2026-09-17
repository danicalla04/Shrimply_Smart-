import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Line, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { useWeather } from './WeatherContext';
import { fetchApod } from '../../services/weather/nasa';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend);

const WeatherMap = lazy(() => import('./WeatherMap'));

function buildHourlySeries(forecast, key, count = 24) {
  const hourly = forecast?.hourly;
  if (!hourly?.time || !hourly?.[key]) return null;
  const times = hourly.time.slice(0, count);
  const values = hourly[key].slice(0, count);
  return { times, values };
}

function num(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export default function WeatherDetails() {
  const { forecast, air, settings, location } = useWeather();
  const [apod, setApod] = useState(null);
  const [apodError, setApodError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setApodError('');

    fetchApod({ apiKey: settings?.nasaApiKey || 'DEMO_KEY', signal: controller.signal })
      .then(setApod)
      .catch((e) => {
        if (e?.name === 'AbortError') return;
        setApodError(e?.message || 'Failed to load NASA APOD');
      });

    return () => controller.abort();
  }, [settings?.nasaApiKey]);

  const tempSeries = useMemo(() => buildHourlySeries(forecast, 'temperature_2m', 48), [forecast]);
  const rainSeries = useMemo(() => buildHourlySeries(forecast, 'precipitation_probability', 48), [forecast]);
  const windSeries = useMemo(() => buildHourlySeries(forecast, 'wind_speed_10m', 48), [forecast]);

  const unitSymbol = settings?.units?.temperatureUnit === 'fahrenheit' ? '°F' : '°C';

  const tempChart = tempSeries
    ? {
        labels: tempSeries.times.map((t) => new Date(t).toLocaleTimeString([], { hour: '2-digit' })),
        datasets: [
          {
            label: `Temperature (${unitSymbol})`,
            data: tempSeries.values.map((v) => num(v)),
            borderColor: '#0ea5e9',
            backgroundColor: 'rgba(14,165,233,0.15)',
            tension: 0.35,
          },
        ],
      }
    : null;

  const rainChart = rainSeries
    ? {
        labels: rainSeries.times.map((t) => new Date(t).toLocaleTimeString([], { hour: '2-digit' })),
        datasets: [
          {
            label: 'Rain probability (%)',
            data: rainSeries.values.map((v) => num(v)),
            backgroundColor: 'rgba(20,184,166,0.25)',
            borderColor: '#14b8a6',
            borderWidth: 1,
          },
        ],
      }
    : null;

  const windChart = windSeries
    ? {
        labels: windSeries.times.map((t) => new Date(t).toLocaleTimeString([], { hour: '2-digit' })),
        datasets: [
          {
            label: 'Wind',
            data: windSeries.values.map((v) => num(v)),
            borderColor: '#f97316',
            backgroundColor: 'rgba(249,115,22,0.20)',
            tension: 0.35,
          },
        ],
      }
    : null;

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: { display: true },
    },
    scales: {
      x: { grid: { display: false } },
    },
  };

  const airCurrent = air?.current || null;

  return (
    <div className="space-y-6">
      {/* Charts */}
      <div className="glass-card p-6">
        <h2 className="text-2xl font-bold text-slate-900">Charts</h2>
        <div className="text-slate-600 mt-1">48-hour trends for temperature, rain probability, and wind.</div>

        <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="metric-card-modern p-4">
            <div className="font-bold text-slate-900 mb-2">Temperature</div>
            {tempChart ? <Line data={tempChart} options={chartOptions} /> : <div className="text-slate-600">No data.</div>}
          </div>

          <div className="metric-card-modern p-4">
            <div className="font-bold text-slate-900 mb-2">Rain probability</div>
            {rainChart ? <Bar data={rainChart} options={chartOptions} /> : <div className="text-slate-600">No data.</div>}
          </div>

          <div className="metric-card-modern p-4">
            <div className="font-bold text-slate-900 mb-2">Wind</div>
            {windChart ? <Line data={windChart} options={chartOptions} /> : <div className="text-slate-600">No data.</div>}
          </div>
        </div>
      </div>

      {/* Map */}
      <div className="glass-card p-6">
        <h2 className="text-2xl font-bold text-slate-900">Weather Map</h2>
        <div className="text-slate-600 mt-1">Radar overlay + marker for your selected location.</div>

        <div className="mt-4">
          <Suspense fallback={<div className="h-[420px] bg-gray-200 rounded-2xl animate-pulse" />}>
            <WeatherMap location={location} />
          </Suspense>
        </div>
      </div>

      {/* Air Quality */}
      <div className="glass-card p-6">
        <h2 className="text-2xl font-bold text-slate-900">Air Quality</h2>
        {!airCurrent ? (
          <div className="text-slate-600 mt-2">No air quality data available.</div>
        ) : (
          <div className="mt-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div className="metric-card-modern p-4">
              <div className="text-slate-500 text-sm">US AQI</div>
              <div className="text-2xl font-bold text-slate-800">{Number.isFinite(airCurrent.us_aqi) ? Math.round(airCurrent.us_aqi) : '—'}</div>
            </div>
            <div className="metric-card-modern p-4">
              <div className="text-slate-500 text-sm">EU AQI</div>
              <div className="text-2xl font-bold text-slate-800">{Number.isFinite(airCurrent.european_aqi) ? Math.round(airCurrent.european_aqi) : '—'}</div>
            </div>
            <div className="metric-card-modern p-4">
              <div className="text-slate-500 text-sm">PM2.5</div>
              <div className="text-2xl font-bold text-slate-800">{Number.isFinite(airCurrent.pm2_5) ? airCurrent.pm2_5.toFixed(1) : '—'}</div>
            </div>
            <div className="metric-card-modern p-4">
              <div className="text-slate-500 text-sm">PM10</div>
              <div className="text-2xl font-bold text-slate-800">{Number.isFinite(airCurrent.pm10) ? airCurrent.pm10.toFixed(1) : '—'}</div>
            </div>
            <div className="metric-card-modern p-4">
              <div className="text-slate-500 text-sm">CO</div>
              <div className="text-2xl font-bold text-slate-800">{Number.isFinite(airCurrent.carbon_monoxide) ? airCurrent.carbon_monoxide.toFixed(0) : '—'}</div>
            </div>
            <div className="metric-card-modern p-4">
              <div className="text-slate-500 text-sm">Ozone</div>
              <div className="text-2xl font-bold text-slate-800">{Number.isFinite(airCurrent.ozone) ? airCurrent.ozone.toFixed(0) : '—'}</div>
            </div>
          </div>
        )}
      </div>

      {/* NASA */}
      <div className="glass-card p-6">
        <h2 className="text-2xl font-bold text-slate-900">NASA Imagery</h2>
        <div className="text-slate-600 mt-1">Astronomy Picture of the Day (APOD)</div>

        {apodError && <div className="mt-4 p-4 rounded-2xl bg-red-50 border border-red-200 text-red-800">{apodError}</div>}

        {!apod ? (
          <div className="mt-4 h-56 bg-gray-200 rounded-2xl animate-pulse" />
        ) : (
          <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="metric-card-modern p-4">
              {apod.media_type === 'image' ? (
                <img
                  src={apod.url}
                  alt={apod.title}
                  loading="lazy"
                  className="w-full h-[320px] object-cover rounded-xl"
                />
              ) : (
                <a className="text-blue-700 hover:underline" href={apod.url} target="_blank" rel="noreferrer">
                  Open APOD media
                </a>
              )}
            </div>
            <div className="metric-card-modern p-5">
              <div className="text-sm text-slate-500">{apod.date}</div>
              <div className="text-xl font-bold text-slate-900 mt-1">{apod.title}</div>
              <div className="text-slate-700 text-sm mt-3 leading-relaxed">{apod.explanation}</div>
            </div>
          </div>
        )}
      </div>

      <div className="text-xs text-slate-500">
        Radar tiles use Rain Viewer’s public Weather Maps API (attribution required). Selected location: {location?.latitude?.toFixed(3)}, {location?.longitude?.toFixed(3)}
      </div>
    </div>
  );
}
