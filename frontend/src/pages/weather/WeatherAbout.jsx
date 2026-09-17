export default function WeatherAbout() {
  return (
    <div className="glass-card p-6">
      <h2 className="text-2xl font-bold text-slate-900">About Weather</h2>
      <p className="text-slate-700 mt-3">
        This weather module uses Open‑Meteo for forecast and air‑quality data, Rain Viewer for radar tiles, and NASA APOD for daily astronomy imagery.
      </p>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="metric-card-modern p-5">
          <div className="font-bold text-slate-900">Open‑Meteo</div>
          <div className="text-sm text-slate-600 mt-1">Forecast + geocoding + air quality</div>
          <a className="text-sm text-blue-700 hover:underline" href="https://open-meteo.com/" target="_blank" rel="noreferrer">
            open-meteo.com
          </a>
        </div>
        <div className="metric-card-modern p-5">
          <div className="font-bold text-slate-900">Rain Viewer</div>
          <div className="text-sm text-slate-600 mt-1">Radar map tiles timeline</div>
          <a className="text-sm text-blue-700 hover:underline" href="https://www.rainviewer.com/" target="_blank" rel="noreferrer">
            rainviewer.com
          </a>
        </div>
        <div className="metric-card-modern p-5">
          <div className="font-bold text-slate-900">NASA APOD</div>
          <div className="text-sm text-slate-600 mt-1">Astronomy picture of the day</div>
          <a className="text-sm text-blue-700 hover:underline" href="https://api.nasa.gov/" target="_blank" rel="noreferrer">
            api.nasa.gov
          </a>
        </div>
      </div>

      <div className="mt-6 text-xs text-slate-500">
        Note: Rain Viewer’s public API requires attribution. If you ship this module publicly, make sure the credit remains visible.
      </div>
    </div>
  );
}
