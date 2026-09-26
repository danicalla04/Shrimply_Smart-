import { useEffect, useMemo, useState } from 'react';
import { MapContainer, Marker, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { buildRadarTileUrl, fetchRainviewerTimeline } from '../../services/weather/rainviewer';

// Fix default marker icons in Leaflet + bundlers
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

const PLACE_ZOOM = 9;

function FocusPlace({ center }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, PLACE_ZOOM);
  }, [center, map]);
  return null;
}

export default function WeatherMap({ location }) {
  const [radarFrame, setRadarFrame] = useState(null);
  const [radarOn, setRadarOn] = useState(true);
  const [radarError, setRadarError] = useState('');

  const center = useMemo(() => {
    const lat = Number(location?.latitude);
    const lon = Number(location?.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return [13.41, 121.18];
    return [lat, lon];
  }, [location?.latitude, location?.longitude]);

  useEffect(() => {
    const controller = new AbortController();
    setRadarError('');

    fetchRainviewerTimeline({ signal: controller.signal })
      .then((timeline) => {
        const latest = timeline.frames[timeline.frames.length - 1];
        if (!latest) throw new Error('No radar frames available');
        setRadarFrame({ host: timeline.host, ...latest });
      })
      .catch((e) => {
        if (e?.name === 'AbortError') return;
        setRadarError(e?.message || 'Radar unavailable');
        setRadarFrame(null);
      });

    return () => controller.abort();
  }, []);

  const radarUrl = useMemo(() => {
    if (!radarFrame) return null;
    return buildRadarTileUrl({ host: radarFrame.host, path: radarFrame.path, size: 256, color: 6, smooth: 1, snow: 1 });
  }, [radarFrame]);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="text-sm text-slate-600">
          {radarFrame?.time ? `Radar frame: ${new Date(radarFrame.time * 1000).toLocaleTimeString()}` : 'Radar frame: —'}
          {radarError ? <span className="ml-2 text-red-700">({radarError})</span> : null}
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-secondary-modern" onClick={() => setRadarOn((v) => !v)}>
            {radarOn ? 'Hide radar' : 'Show radar'}
          </button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-3 text-sm" style={{ color: '#e6f7ff' }}>
        <span className="font-semibold">What to look at:</span>
        <span>the pin is your selected place.</span>
        <span className="inline-flex items-center gap-1"><span className="inline-block h-3 w-6 rounded" style={{ background: '#38bdf8' }} /> light rain</span>
        <span className="inline-flex items-center gap-1"><span className="inline-block h-3 w-6 rounded" style={{ background: '#facc15' }} /> moderate</span>
        <span className="inline-flex items-center gap-1"><span className="inline-block h-3 w-6 rounded" style={{ background: '#ef4444' }} /> heavy</span>
        <span>A clear area means no rain is over it in this radar frame.</span>
      </div>

      <div className="h-[420px] rounded-2xl overflow-hidden border border-sky-400/40 shadow-sm">
        <MapContainer center={center} zoom={PLACE_ZOOM} scrollWheelZoom style={{ height: '100%', width: '100%' }}>
          <FocusPlace center={center} />
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {radarOn && radarUrl && (
            <TileLayer
              attribution='Weather data by Rain Viewer'
              url={radarUrl}
              opacity={0.85}
              zIndex={10}
              maxNativeZoom={7}
              maxZoom={12}
            />
          )}

          <Marker position={center} />
        </MapContainer>
      </div>

      <div className="mt-2 text-xs text-slate-500">
        Colored patches are live rain radar. Zoom with the mouse or the + / − buttons. Weather data by Rain Viewer. Map base by OpenStreetMap.
      </div>
    </div>
  );
}
