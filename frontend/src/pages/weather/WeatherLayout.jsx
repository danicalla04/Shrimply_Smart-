import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import useDebouncedValue from '../../hooks/useDebouncedValue';
import { fetchForecast, reverseGeocode, searchLocations } from '../../services/weather/openMeteo';
import { getDefaultWeatherSettings, getWeatherSettings, mergeWeatherSettings } from '../../services/weather/settings';
import { fetchMunicipalities, municipalityToLocation } from '../../services/weather/municipalities';
import { WeatherProvider } from './WeatherContext';

function formatPlace(loc) {
  if (!loc) return '';
  const parts = [loc.name, loc.admin1, loc.country].filter(Boolean);
  return parts.join(', ');
}

export default function WeatherLayout() {
  const navigate = useNavigate();
  const routerLoc = useLocation();

  const [settings, setSettings] = useState(() => {
    const defaults = getDefaultWeatherSettings();
    return { ...defaults, ...(getWeatherSettings() || {}) };
  });

  const [location, setLocation] = useState(() => settings.preferredLocation || null);

  const [query, setQuery] = useState('');
  const debouncedQuery = useDebouncedValue(query, 250);
  const [suggestions, setSuggestions] = useState([]);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [geoLoading, setGeoLoading] = useState(false);

  const [municipalities, setMunicipalities] = useState([]);
  const [selectedMunicipality, setSelectedMunicipality] = useState(null);

  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchAbortRef = useRef(null);

  // Autoload geolocation on first entry if no preferred location
  useEffect(() => {
    if (location) return;

    const tryGeolocate = async () => {
      if (!navigator.geolocation) return;

      setGeoLoading(true);
      try {
        const coords = await new Promise((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(
            (pos) => resolve(pos.coords),
            (err) => reject(err),
            { enableHighAccuracy: true, timeout: 8000 }
          );
        });

        const lat = coords.latitude;
        const lon = coords.longitude;

        const controller = new AbortController();
        const rev = await reverseGeocode(lat, lon, { signal: controller.signal });

        const loc =
          rev ||
          ({
            name: 'Current Location',
            latitude: lat,
            longitude: lon,
            country: '',
            admin1: '',
            timezone: 'auto',
          });

        setLocation(loc);
        const merged = mergeWeatherSettings({ preferredLocation: loc });
        setSettings((s) => ({ ...s, ...merged }));
      } catch {
        // ignore denied / timeout
      } finally {
        setGeoLoading(false);
      }
    };

    tryGeolocate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load all 15 Oriental Mindoro municipalities on component mount
  useEffect(() => {
    const loadMunicipalities = async () => {
      try {
        const data = await fetchMunicipalities();
        setMunicipalities(data);
        
        // Auto-select Calapan City (primary) as default if no selection exists
        if (data.length > 0) {
          const calapan = data.find((m) => m.is_primary);
          if (calapan) {
            setSelectedMunicipality(calapan);
          }
        }
      } catch (err) {
        console.error('[WeatherLayout] Failed to load municipalities:', err);
      }
    };

    loadMunicipalities();
  }, []);

  // Fallback default location if geolocation fails and user hasn't selected
  useEffect(() => {
    if (location) return;

    const fallback = {
      name: 'Calapan',
      admin1: 'Oriental Mindoro',
      country: 'Philippines',
      latitude: 13.4117,
      longitude: 121.1803,
      timezone: 'auto',
    };

    setLocation(fallback);
    const merged = mergeWeatherSettings({ preferredLocation: fallback });
    setSettings((s) => ({ ...s, ...merged }));
  }, [location]);

  // Autocomplete
  useEffect(() => {
    if (!debouncedQuery) {
      setSuggestions([]);
      return;
    }

    const controller = new AbortController();
    searchLocations(debouncedQuery, { signal: controller.signal })
      .then((results) => {
        setSuggestions(results);
        setSuggestionsOpen(true);
      })
      .catch(() => {
        setSuggestions([]);
      });

    return () => controller.abort();
  }, [debouncedQuery]);

  const displayLocation = useMemo(() => formatPlace(location), [location]);

  const refresh = async () => {
    if (!location) return;

    setLoading(true);
    setError('');

    if (fetchAbortRef.current) {
      fetchAbortRef.current.abort();
    }

    const controller = new AbortController();
    fetchAbortRef.current = controller;

    try {
      const common = {
        latitude: Number(location.latitude),
        longitude: Number(location.longitude),
        timezone: 'auto',
      };

      const forecastJson = await fetchForecast(
        {
          ...common,
          ...settings.units,
          forecastDays: 7,
        },
        { signal: controller.signal }
      );

      setForecast(forecastJson);
      setLastUpdated(new Date());
    } catch (e) {
      if (e?.name === 'AbortError') return;
      setError(e?.message || 'Failed to load weather data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    location?.latitude,
    location?.longitude,
    settings.units?.temperatureUnit,
    settings.units?.windSpeedUnit,
    settings.units?.precipitationUnit,
  ]);

  // Small UX nicety: close suggestions on route change
  useEffect(() => {
    setSuggestionsOpen(false);
  }, [routerLoc.pathname]);

  const onPickSuggestion = (loc) => {
    setLocation(loc);
    setQuery('');
    setSuggestionsOpen(false);

    const merged = mergeWeatherSettings({ preferredLocation: loc });
    setSettings((s) => ({ ...s, ...merged }));

    // Stay on Home unless user is deep-linked
    if (routerLoc.pathname === '/weather') {
      navigate('/weather');
    }
  };

  const onUseGeolocation = async () => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported in this browser');
      return;
    }

    setGeoLoading(true);
    setError('');

    try {
      const coords = await new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(
          (pos) => resolve(pos.coords),
          (err) => reject(err),
          { enableHighAccuracy: true, timeout: 10000 }
        );
      });

      const lat = coords.latitude;
      const lon = coords.longitude;
      const controller = new AbortController();
      const rev = await reverseGeocode(lat, lon, { signal: controller.signal });

      const loc =
        rev ||
        ({
          name: 'Current Location',
          latitude: lat,
          longitude: lon,
          country: '',
          admin1: '',
          timezone: 'auto',
        });

      setLocation(loc);
      const merged = mergeWeatherSettings({ preferredLocation: loc });
      setSettings((s) => ({ ...s, ...merged }));
    } catch {
      setError('Unable to read your location. Please allow location access.');
    } finally {
      setGeoLoading(false);
    }
  };

  // Handler to switch municipality
  const handleMunicipalityChange = (municipality) => {
    setSelectedMunicipality(municipality);
    
    // Convert municipality object to location format
    const loc = municipalityToLocation(municipality);
    setLocation(loc);
    
    // Save to settings
    const merged = mergeWeatherSettings({ preferredLocation: loc });
    setSettings((s) => ({ ...s, ...merged }));
  };

  const ctx = useMemo(
    () => ({
      settings,
      setSettings: (next) => {
        setSettings(next);
        mergeWeatherSettings(next);
      },
      location,
      setLocation: (next) => {
        setLocation(next);
        const merged = mergeWeatherSettings({ preferredLocation: next });
        setSettings((s) => ({ ...s, ...merged }));
      },
      forecast,
      loading,
      error,
      lastUpdated,
      refresh,
      municipalities,
      selectedMunicipality,
      onMunicipalityChange: handleMunicipalityChange,
    }),
    [settings, location, forecast, loading, error, lastUpdated, municipalities, selectedMunicipality]
  );

  const navLinkClass = ({ isActive }) =>
    `weather-nav-link${isActive ? ' is-on' : ''}`;

  return (
    <WeatherProvider value={ctx}>
      <div className="p-2 min-h-full">
        <div className="mb-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="pond-kicker">Atmospheric intelligence</div>
              <h1 className="aq-title mb-1">Weather</h1>
              <div className="text-slate-600">
                <span className="font-medium">Location:</span> {displayLocation || '—'}
                {lastUpdated && (
                  <span className="ml-3 text-sm text-slate-500">Updated {lastUpdated.toLocaleTimeString()}</span>
                )}
              </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
              <div className="relative">
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onFocus={() => setSuggestionsOpen(true)}
                  placeholder="Search city / place worldwide"
                  className="input-modern w-[320px] max-w-full"
                />

                {suggestionsOpen && suggestions.length > 0 && (
                  <div
                    className="absolute z-50 mt-2 w-full bg-white/95 backdrop-blur-xl border border-slate-200 rounded-2xl shadow-xl overflow-hidden"
                    onMouseDown={(e) => e.preventDefault()}
                  >
                    {suggestions.slice(0, 8).map((sug) => (
                      <button
                        key={`${sug.id || ''}:${sug.latitude}:${sug.longitude}`}
                        onClick={() => onPickSuggestion(sug)}
                        className="w-full text-left px-4 py-3 hover:bg-slate-50 transition-colors"
                      >
                        <div className="font-semibold text-slate-800">{formatPlace(sug)}</div>
                        <div className="text-xs text-slate-500">
                          {sug.latitude.toFixed(2)}, {sug.longitude.toFixed(2)}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <button
                onClick={onUseGeolocation}
                disabled={geoLoading}
                className="btn-secondary-modern"
                title="Auto-detect location"
              >
                {geoLoading ? 'Locating…' : 'Use my location'}
              </button>

              <button onClick={refresh} disabled={loading} className="btn-modern" title="Refresh">
                {loading ? 'Refreshing…' : 'Refresh'}
              </button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <Link to="/weather" className={navLinkClass({ isActive: routerLoc.pathname === '/weather' })}>
              Home
            </Link>
            <Link
              to="/weather/details"
              className={navLinkClass({ isActive: routerLoc.pathname.startsWith('/weather/details') })}
            >
              Forecast Details
            </Link>
            <Link
              to="/weather/analytics"
              className={navLinkClass({ isActive: routerLoc.pathname.startsWith('/weather/analytics') })}
            >
              Analytics
            </Link>
            <Link to="/weather/settings" className={navLinkClass({ isActive: routerLoc.pathname.startsWith('/weather/settings') })}>
              Settings
            </Link>
            <Link to="/weather/about" className={navLinkClass({ isActive: routerLoc.pathname.startsWith('/weather/about') })}>
              About
            </Link>
          </div>

          {error && (
            <div className="mt-4 p-4 rounded-2xl border border-red-200 bg-red-50 text-red-800">
              {error}
            </div>
          )}
        </div>

        <Outlet />

        <div className="mt-10 text-xs text-slate-500">
          Live readings from Open-Meteo for the selected location.
        </div>
      </div>
    </WeatherProvider>
  );
}
