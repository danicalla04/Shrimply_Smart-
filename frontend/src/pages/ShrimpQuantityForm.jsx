import React, { useState, useEffect } from 'react';
import authService from '../services/auth';
import { EFFECTIVE_API_BASE } from '../services/apiConfig';
import { format } from 'date-fns';

const TODAY_STR = () => format(new Date(), 'yyyy-MM-dd');

export default function ShrimpQuantityForm({ seasonId, onUpdate }) {
  const [formData, setFormData] = useState({
    current_shrimp_quantity: '',
    average_shrimp_weight_grams: '',
    date: TODAY_STR(),
    daily_weight_gain_grams: '',
    daily_mortality_percent: '',
    feed_amount_grams: '',
    water_temperature: '',
    water_ph: '',
    turbidity: '',
    tds: '',
    weather_condition: 'clear',
    notes: '',
  });

  const [loading, setLoading] = useState(false);
  const [avgLoading, setAvgLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [season, setSeason] = useState(null);
  const [hasGrowthTracking, setHasGrowthTracking] = useState(false);
  const [dayAvgInfo, setDayAvgInfo] = useState(null);

  useEffect(() => {
    const fetchSeason = async () => {
      try {
        const res = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/${seasonId}/`);
        const data = await res.json();
        setSeason(data);

        // Only prefill quantity/weight once this season actually has growth
        // tracking entries — otherwise stale/imported season fields (e.g. from
        // a completed real-pond import) would show up as if they were live.
        let started = false;
        try {
          const metricsRes = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/${seasonId}/growth_metrics/`);
          if (metricsRes.ok) {
            const metricsJson = await metricsRes.json();
            const metricsData = Array.isArray(metricsJson) ? metricsJson : (metricsJson.results || []);
            started = metricsData.length > 0;
          }
        } catch {
          started = false;
        }
        setHasGrowthTracking(started);

        if (started && data.current_shrimp_quantity) {
          setFormData(prev => ({
            ...prev,
            current_shrimp_quantity: data.current_shrimp_quantity,
            average_shrimp_weight_grams: data.average_shrimp_weight_grams || '',
          }));
        } else {
          setFormData(prev => ({
            ...prev,
            current_shrimp_quantity: '',
            average_shrimp_weight_grams: '',
          }));
        }
      } catch (err) {
        console.error('Error fetching season:', err);
      }
    };

    if (seasonId) {
      fetchSeason();
    }
  }, [seasonId]);

  // Keep the date locked to "today" — if the tab stays open past midnight,
  // roll it forward automatically instead of letting a stale date linger.
  useEffect(() => {
    const syncToday = () => {
      const today = TODAY_STR();
      setFormData(prev => (prev.date === today ? prev : { ...prev, date: today }));
    };
    syncToday();
    const interval = setInterval(syncToday, 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
  };

  /** Fill feed / temp / pH / TDS from DB noon→noon averages for the form date */
  const fillFromDayAverages = async () => {
    if (!seasonId || !formData.date) return;
    setAvgLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await authService.apiCall(
        `${EFFECTIVE_API_BASE}/seasons/${seasonId}/day_averages/?date=${encodeURIComponent(formData.date)}`
      );
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.error || `Failed to load day averages (${res.status})`);
      }
      const data = await res.json();
      setDayAvgInfo(data);
      setFormData((prev) => ({
        ...prev,
        feed_amount_grams:
          data.feed_amount_grams != null ? String(data.feed_amount_grams) : prev.feed_amount_grams,
        water_temperature:
          data.water_temperature != null ? String(data.water_temperature) : prev.water_temperature,
        water_ph: data.water_ph != null ? String(data.water_ph) : prev.water_ph,
        turbidity: data.turbidity != null ? String(data.turbidity) : prev.turbidity,
        tds: data.tds != null ? String(data.tds) : prev.tds,
      }));
      const parts = [];
      if (data.feed_amount_grams != null) parts.push(`feed ${data.feed_amount_grams}g (${data.feed_events} events)`);
      if (data.water_temperature != null) parts.push(`temp ${data.water_temperature}°C`);
      if (data.water_ph != null) parts.push(`pH ${data.water_ph}`);
      if (data.tds != null) parts.push(`TDS ${data.tds}`);
      if (data.turbidity != null) parts.push(`turbidity ${data.turbidity} NTU`);
      if (!parts.length) {
        setSuccess('No sensor/feed readings in the 12:00–12:00 window for this date.');
      } else {
        setSuccess(`Filled 12:00–12:00 averages: ${parts.join(' · ')}.`);
      }
    } catch (err) {
      setError(err?.message || 'Failed to load day averages');
    } finally {
      setAvgLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (season && season.is_active === false) {
      setError('This season has ended — there is nowhere for new daily data to go. Use Growth Settings to correct a past entry instead.');
      return;
    }

    if (!formData.current_shrimp_quantity || !formData.average_shrimp_weight_grams) {
      setError('Enter both Shrimp Quantity and Average Weight before saving.');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // Update shrimp quantity on season
      const updateRes = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/${seasonId}/update_shrimp_quantity/`, {
        method: 'PATCH',
        body: JSON.stringify({
          current_shrimp_quantity: parseInt(formData.current_shrimp_quantity),
          average_shrimp_weight_grams: parseFloat(formData.average_shrimp_weight_grams),
        }),
      });
      if (!updateRes.ok) throw new Error('Failed to update quantity');

      // Add daily growth metric
      if (formData.date) {
        const metricPayload = {
          date: formData.date,
          shrimp_count: parseInt(formData.current_shrimp_quantity),
          avg_weight_grams: parseFloat(formData.average_shrimp_weight_grams),
          daily_weight_gain_grams: parseFloat(formData.daily_weight_gain_grams) || 0,
          daily_mortality_percent: parseFloat(formData.daily_mortality_percent) || 0,
          feed_amount_grams: parseFloat(formData.feed_amount_grams) || 0,
          water_temperature: parseFloat(formData.water_temperature) || null,
          water_ph: parseFloat(formData.water_ph) || null,
          turbidity: parseFloat(formData.turbidity) || null,
          tds: parseFloat(formData.tds) || null,
          weather_condition: formData.weather_condition,
          notes: formData.notes,
        };

        // Remove null values
        Object.keys(metricPayload).forEach(
          key => metricPayload[key] === null && delete metricPayload[key]
        );

        const metricRes = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/${seasonId}/add_growth_metric/`, {
          method: 'POST',
          body: JSON.stringify(metricPayload),
        });
        if (!metricRes.ok) {
          const errBody = await metricRes.json().catch(() => ({}));
          throw new Error(errBody.error || errBody.detail || 'Failed to add metric');
        }      }

      setSuccess('Data updated successfully! Growth predictions will be generated next run.');
      
      if (onUpdate) {
        onUpdate();
      }

      // Clear all form fields after successful save (date stays locked to today)
      setFormData({
        current_shrimp_quantity: '',
        average_shrimp_weight_grams: '',
        date: TODAY_STR(),
        daily_weight_gain_grams: '',
        daily_mortality_percent: '',
        feed_amount_grams: '',
        water_temperature: '',
        water_ph: '',
        turbidity: '',
        tds: '',
        weather_condition: '',
        notes: '',
      });
    } catch (err) {
      console.error('Error updating data:', err);
      setError(err?.message || 'Failed to update data');
    } finally {
      setLoading(false);
    }
  };

  const weatherOptions = ['clear', 'rainy', 'cloudy', 'hot', 'cold', 'windy'];

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <h2 className="text-xl font-bold mb-6">📊 Shrimp Quantity & Growth Metrics</h2>

      {error && (
        <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 p-3 bg-green-100 border border-green-400 text-green-700 rounded">
          {success}
        </div>
      )}

      {season && season.is_active === false ? (
        <div className="p-4 bg-rose-50 border border-rose-300 text-rose-800 rounded-lg text-sm">
          <p className="font-semibold mb-1">This season has ended — nothing to save here.</p>
          <p>
            {season.name} finished on {season.end_date ? format(new Date(season.end_date), 'MMM dd, yyyy') : 'an earlier date'},
            so there&apos;s no live pond to record today&apos;s data for. Select an active season above to log daily
            metrics, or go to <strong>Growth Settings</strong> if you need to correct one of its past entries.
          </p>
        </div>
      ) : (
        <>
          {season && !hasGrowthTracking && (
            <div className="mb-4 p-3 bg-amber-50 border border-amber-300 text-amber-800 rounded text-sm">
              Growth tracking hasn&apos;t started for this season yet, so quantity/weight are blank
              (any imported harvest data is ignored here). Enter today&apos;s numbers below to start tracking.
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
        {/* Core Quantity Data */}
        <div>
          <h3 className="font-semibold text-slate-700 mb-4">Current Pond Status</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Shrimp Quantity (count)
              </label>
              <input
                type="number"
                name="current_shrimp_quantity"
                value={formData.current_shrimp_quantity}
                onChange={handleChange}
                placeholder="e.g., 50000"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-slate-500 mt-1">Total shrimp in the pond now</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Average Weight (grams)
              </label>
              <input
                type="number"
                step="0.01"
                name="average_shrimp_weight_grams"
                value={formData.average_shrimp_weight_grams}
                onChange={handleChange}
                placeholder="e.g., 5.5"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-slate-500 mt-1">Average weight per shrimp</p>
            </div>
          </div>
        </div>

        {/* Daily Metrics */}
        <div>
          <h3 className="font-semibold text-slate-700 mb-4">Daily Metrics</h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Date
              </label>
              <input
                type="date"
                name="date"
                value={formData.date}
                readOnly
                disabled
                min={formData.date}
                max={formData.date}
                title="Locked to today so updates always reflect the current day"
                className="w-full px-3 py-2 border border-slate-300 rounded-md bg-slate-100 text-slate-600 cursor-not-allowed focus:outline-none"
              />
              <p className="text-xs text-slate-500 mt-1">Automatically set to today</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Daily Weight Gain (g)
              </label>
              <input
                type="number"
                step="0.01"
                name="daily_weight_gain_grams"
                value={formData.daily_weight_gain_grams}
                onChange={handleChange}
                placeholder="0.25"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Daily Mortality (%)
              </label>
              <input
                type="number"
                step="0.01"
                name="daily_mortality_percent"
                value={formData.daily_mortality_percent}
                onChange={handleChange}
                placeholder="0.5"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="md:col-span-2">
              <button
                type="button"
                onClick={fillFromDayAverages}
                disabled={avgLoading || !formData.date}
                className="w-full px-3 py-2 text-sm font-medium rounded-md border border-cyan-300 bg-cyan-50 text-cyan-900 hover:bg-cyan-100 disabled:opacity-50"
              >
                {avgLoading
                  ? 'Loading 12:00–12:00 averages…'
                  : '📥 Fill feed / temp / pH / TDS / turbidity from DB (12:00–12:00)'}
              </button>
              <p className="text-[11px] text-slate-500 mt-1">
                Averages SensorReading (temp, pH, TDS, turbidity) + FeedingLog for this date noon→noon.
                {dayAvgInfo?.counts ? (
                  <> · readings: temp {dayAvgInfo.counts.temperature}, pH {dayAvgInfo.counts.ph}, TDS {dayAvgInfo.counts.tds}, turb {dayAvgInfo.counts.turbidity}, feed events {dayAvgInfo.counts.feed_events}</>
                ) : null}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Feed Amount (g)
              </label>
              <input
                type="number"
                step="0.1"
                name="feed_amount_grams"
                value={formData.feed_amount_grams}
                onChange={handleChange}
                placeholder="1000"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Water Temp (°C)
              </label>
              <input
                type="number"
                step="0.1"
                name="water_temperature"
                value={formData.water_temperature}
                onChange={handleChange}
                placeholder="28"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                pH Level
              </label>
              <input
                type="number"
                step="0.1"
                name="water_ph"
                value={formData.water_ph}
                onChange={handleChange}
                placeholder="7.5"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Turbidity (NTU)
              </label>
              <input
                type="number"
                step="0.1"
                name="turbidity"
                value={formData.turbidity}
                onChange={handleChange}
                placeholder="20"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                TDS (ppm)
              </label>
              <input
                type="number"
                step="1"
                name="tds"
                value={formData.tds}
                onChange={handleChange}
                placeholder="800"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Weather
              </label>
              <select
                name="weather_condition"
                value={formData.weather_condition}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select weather</option>
                {weatherOptions.map(opt => (
                  <option key={opt} value={opt}>
                    {opt.charAt(0).toUpperCase() + opt.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-medium text-slate-600 mb-1">
            Notes (optional)
          </label>
          <textarea
            name="notes"
            value={formData.notes}
            onChange={handleChange}
            placeholder="Any observations or special conditions..."
            rows="3"
            className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Submit Button */}
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 disabled:bg-slate-400"
          >
            {loading ? '💾 Saving...' : '💾 Save Data & Update Quantity'}
          </button>
        </div>

        {season && (
          <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded text-sm text-slate-700">
            <p><strong>Last Updated:</strong> {season.updated_at ? format(new Date(season.updated_at), 'MMM dd, yyyy HH:mm') : 'Never'}</p>
          </div>
        )}
          </form>
        </>
      )}
    </div>
  );
}
