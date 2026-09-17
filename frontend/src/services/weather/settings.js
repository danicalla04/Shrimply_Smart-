const STORAGE_KEY = 'weather.settings.v1';

export function getWeatherSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

export function saveWeatherSettings(next) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // ignore
  }
}

export function mergeWeatherSettings(partial) {
  const current = getWeatherSettings() || {};
  const merged = { ...current, ...partial };
  saveWeatherSettings(merged);
  return merged;
}

export function getDefaultWeatherSettings() {
  return {
    units: {
      temperatureUnit: 'celsius', // 'celsius' | 'fahrenheit'
      windSpeedUnit: 'kmh', // 'kmh' | 'ms' | 'mph' | 'kn'
      precipitationUnit: 'mm', // 'mm' | 'inch'
    },
    theme: 'light', // 'light' | 'dark'
    preferredLocation: null, // { name, latitude, longitude, country, admin1, timezone }
    nasaApiKey: '',
  };
}
