import { useEffect, useState } from 'react';
import { fetchMunicipalities, setActiveMunicipality } from '../../services/weather/municipalities';

/**
 * Municipality Selector Component
 * Displays all 15 Oriental Mindoro municipalities as a dropdown
 * Features:
 * - Calapan City marked as PRIMARY (featured/default)
 * - Grouped by coastal vs inland
 * - Shows model availability status
 * - ML confidence badge for primary location
 */
export default function MunicipalitySelector({ value, onChange, disabled = false }) {
  const [municipalities, setMunicipalities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadMunicipalities = async () => {
      try {
        setLoading(true);
        setError('');
        const data = await fetchMunicipalities();
        setMunicipalities(data);
      } catch (err) {
        setError('Failed to load municipalities');
        console.error('Error loading municipalities:', err);
      } finally {
        setLoading(false);
      }
    };

    loadMunicipalities();
  }, []);

  // Group municipalities by type
  const groupedMunicipalities = municipalities.reduce(
    (acc, m) => {
      if (m.is_primary) {
        acc.primary.push(m);
      } else if (m.is_coastal) {
        acc.coastal.push(m);
      } else {
        acc.inland.push(m);
      }
      return acc;
    },
    { primary: [], coastal: [], inland: [] },
  );

  const handleChange = async (e) => {
    const municipalityKey = e.target.value;
    const selectedMun = municipalities.find((m) => m.key === municipalityKey);

    try {
      // Update active municipality on backend
      await setActiveMunicipality(municipalityKey);
      // Call parent handler
      onChange(selectedMun);
    } catch (err) {
      setError('Failed to switch municipality');
      console.error('Error switching municipality:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2">
        <div className="h-10 bg-gray-200 rounded-lg w-64 animate-pulse" />
      </div>
    );
  }

  return (
    <div className="relative">
      <select
        value={value?.key || 'calapan'}
        onChange={handleChange}
        disabled={disabled || loading}
        className={`w-full px-4 py-2 border border-gray-300 rounded-lg appearance-none cursor-pointer font-medium
          ${
            disabled || loading
              ? 'bg-gray-100 text-gray-500 cursor-not-allowed'
              : 'bg-white text-gray-900 hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500'
          }
        `}
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23333' d='M10.293 3.293L6 7.586 1.707 3.293A1 1 0 00.293 4.707l5 5a1 1 0 001.414 0l5-5a1 1 0 10-1.414-1.414z'/%3E%3C/svg%3E")`,
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'right 0.75rem center',
          backgroundSize: '12px',
          paddingRight: '2.5rem',
        }}
      >
        {/* PRIMARY (Calapan City - Featured) */}
        {groupedMunicipalities.primary.length > 0 && (
          <optgroup label="⭐ PRIMARY - HIGH ACCURACY">
            {groupedMunicipalities.primary.map((m) => (
              <option key={m.key} value={m.key}>
                {m.display_name} (95%+ accuracy)
              </option>
            ))}
          </optgroup>
        )}

        {/* COASTAL MUNICIPALITIES */}
        {groupedMunicipalities.coastal.length > 0 && (
          <optgroup label="🌊 COASTAL MUNICIPALITIES">
            {groupedMunicipalities.coastal.map((m) => (
              <option key={m.key} value={m.key}>
                {m.display_name}
                {m.model_available ? ' ✓' : ''}
              </option>
            ))}
          </optgroup>
        )}

        {/* INLAND MUNICIPALITIES */}
        {groupedMunicipalities.inland.length > 0 && (
          <optgroup label="🏞️ INLAND MUNICIPALITIES">
            {groupedMunicipalities.inland.map((m) => (
              <option key={m.key} value={m.key}>
                {m.display_name}
                {m.model_available ? ' ✓' : ''}
              </option>
            ))}
          </optgroup>
        )}
      </select>

      {/* Badge showing current municipality info */}
      {value && (
        <div className="absolute right-12 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {value.is_primary && (
            <span className="px-2 py-1 bg-amber-100 text-amber-800 text-xs font-bold rounded whitespace-nowrap">
              ⭐ PRIMARY
            </span>
          )}
          {value.model_available && (
            <span className="px-2 py-1 bg-green-100 text-green-800 text-xs font-bold rounded whitespace-nowrap">
              ✓ ML Ready
            </span>
          )}
          {value.is_coastal && !value.is_primary && (
            <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs font-bold rounded whitespace-nowrap">
              🌊 Coastal
            </span>
          )}
        </div>
      )}

      {error && <div className="text-red-500 text-xs mt-1">{error}</div>}

      {/* Info text */}
      <p className="text-xs text-gray-500 mt-1">
        {municipalities.length} municipalities • Calapan City is featured for highest accuracy
      </p>
    </div>
  );
}
