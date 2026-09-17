const CACHE = new Map();

function cacheGet(key, ttlMs) {
  const hit = CACHE.get(key);
  if (!hit) return null;
  if (Date.now() - hit.time > ttlMs) return null;
  return hit.data;
}

function cacheSet(key, data) {
  CACHE.set(key, { time: Date.now(), data });
}

export async function fetchRainviewerTimeline({ signal } = {}) {
  const cacheKey = 'rainviewer.timeline';
  const cached = cacheGet(cacheKey, 2 * 60 * 1000);
  if (cached) return cached;

  const res = await fetch('https://api.rainviewer.com/public/weather-maps.json', { signal });
  if (!res.ok) {
    throw new Error(`RainViewer request failed (${res.status})`);
  }
  const json = await res.json();

  const host = json?.host;
  const past = Array.isArray(json?.radar?.past) ? json.radar.past : [];
  const nowcast = Array.isArray(json?.radar?.nowcast) ? json.radar.nowcast : [];

  const frames = [...past, ...nowcast]
    .map((f) => ({ time: f.time, path: f.path }))
    .filter((f) => typeof f.time === 'number' && typeof f.path === 'string');

  const timeline = {
    host: typeof host === 'string' ? host : 'https://tilecache.rainviewer.com',
    frames,
  };

  cacheSet(cacheKey, timeline);
  return timeline;
}

export function buildRadarTileUrl({ host, path, size = 256, color = 2, smooth = 1, snow = 1 }) {
  // Template for Leaflet: host + path + /{size}/{z}/{x}/{y}/{color}/{smooth}_{snow}.png
  return `${host}${path}/${size}/{z}/{x}/{y}/${color}/${smooth}_${snow}.png`;
}
