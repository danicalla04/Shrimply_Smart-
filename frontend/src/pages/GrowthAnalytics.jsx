import React, { useState, useEffect } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { format, parseISO } from 'date-fns';
import authService from '../services/auth';
import { EFFECTIVE_API_BASE } from '../services/apiConfig';
import { fetchMlFeedRecommendation } from '../services/feeder';

export default function GrowthAnalytics({ seasonId }) {
  const [growthMetrics, setGrowthMetrics] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('metrics');
  const [feedRec, setFeedRec] = useState(null);
  const [feedRecLoading, setFeedRecLoading] = useState(false);
  const [regenLoading, setRegenLoading] = useState(false);

  const loadPredictions = async () => {
    const predictionsRes = await authService.apiCall(
      `${EFFECTIVE_API_BASE}/seasons/${seasonId}/growth_predictions/`
    );
    if (!predictionsRes.ok) {
      setPredictions([]);
      return;
    }
    const predictionsJson = await predictionsRes.json();
    const predictionsData = Array.isArray(predictionsJson)
      ? predictionsJson
      : (predictionsJson.results || []);
    // API returns ascending by forecast_date
    setPredictions(predictionsData);
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Metrics are required for the dashboard
        const metricsRes = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/${seasonId}/growth_metrics/`);
        if (!metricsRes.ok) {
          throw new Error(`Failed to load growth metrics (${metricsRes.status})`);
        }
        const metricsJson = await metricsRes.json();
        const metricsData = Array.isArray(metricsJson)
          ? metricsJson
          : (metricsJson.results || []);
        // oldest → newest for charts
        setGrowthMetrics([...metricsData].reverse());

        try {
          await loadPredictions();
        } catch {
          setPredictions([]);
        }
      } catch (err) {
        console.error('Error fetching data:', err);
        setError(err.message || 'Failed to load growth analytics');
      } finally {
        setLoading(false);
      }
    };

    if (seasonId) {
      fetchData();
    }
  }, [seasonId]);

  const regeneratePredictions = async () => {
    if (!seasonId) return;
    setRegenLoading(true);
    try {
      const res = await authService.apiCall(
        `${EFFECTIVE_API_BASE}/seasons/${seasonId}/regenerate_growth_predictions/`,
        { method: 'POST' }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `Regenerate failed (${res.status})`);
      }
      await loadPredictions();
      setActiveTab('predictions');
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to regenerate predictions');
    } finally {
      setRegenLoading(false);
    }
  };

  useEffect(() => {
    const loadFeed = async () => {
      if (!seasonId || activeTab !== 'recommendations') return;
      setFeedRecLoading(true);
      try {
        const data = await fetchMlFeedRecommendation(seasonId);
        setFeedRec(data?.error ? null : data);
      } catch {
        setFeedRec(null);
      } finally {
        setFeedRecLoading(false);
      }
    };
    loadFeed();
  }, [seasonId, activeTab, growthMetrics.length]);

  if (loading) {
    return <div className="p-6 text-center">Loading growth analytics...</div>;
  }

  if (error) {
    return <div className="p-6 text-red-500">{error}</div>;
  }

  if (!growthMetrics.length) {
    return (
      <div className="p-6 bg-slate-50 border border-slate-200 rounded-lg text-slate-500">
        No growth metrics yet for this season. Save data on the left to see analytics.
      </div>
    );
  }

  // Prepare chart data
  const metricsChartData = growthMetrics.map(m => ({
    date: format(parseISO(m.date), 'MMM dd'),
    weight: m.avg_weight_grams,
    count: m.shrimp_count,
    mortality: m.daily_mortality_percent,
    feed: m.feed_amount_grams,
  }));

  const parseRec = (p) => {
    if (p?.recommendation_parsed) return p.recommendation_parsed;
    if (typeof p?.recommendation === 'string' && p.recommendation.trim().startsWith('{')) {
      try { return JSON.parse(p.recommendation); } catch { return null; }
    }
    return null;
  };

  const predictionsChartData = predictions.slice(0, 30).map(p => {
    const rec = parseRec(p);
    return {
      date: format(parseISO(p.forecast_date), 'MMM dd'),
      predicted_weight: p.predicted_avg_weight_grams,
      base_weight: p.predicted_avg_weight_base_grams ?? rec?.base_abw ?? null,
      adjusted_weight: p.predicted_avg_weight_grams,
      confidence: p.confidence_score,
    };
  });

  // Combine actual history + forecast for one chart on Predictions tab
  const actualVsPredicted = [
    ...growthMetrics.map(m => ({
      date: format(parseISO(m.date), 'MMM dd'),
      actual_weight: m.avg_weight_grams,
      predicted_weight: null,
      base_weight: null,
      adjusted_weight: null,
    })),
    ...predictions.slice(0, 30).map(p => {
      const rec = parseRec(p);
      return {
        date: format(parseISO(p.forecast_date), 'MMM dd'),
        actual_weight: null,
        predicted_weight: p.predicted_avg_weight_grams,
        base_weight: p.predicted_avg_weight_base_grams ?? rec?.base_abw ?? null,
        adjusted_weight: p.predicted_avg_weight_grams,
      };
    }),
  ];

  const latestMetric = growthMetrics[growthMetrics.length - 1];
  const nearestPrediction = predictions[0];
  const modelVersion = nearestPrediction?.model_version || null;
  const nearestRec = parseRec(nearestPrediction);
  const recCards = nearestRec?.cards || null;
  const envModifier = nearestRec?.adg_modifier;
  const envNotes = nearestRec?.env_notes || [];

  const buildLiveRecCards = (metric, feed) => {
    const temp = metric?.water_temperature;
    const ph = metric?.water_ph;
    const turb = metric?.turbidity;
    const tds = metric?.tds;
    const wqActions = [];
    let wqType = 'info';
    let wqTitle = 'Water looks manageable';
    let wqMsg = 'Based on the latest saved daily metrics (regenerate for full ML advice).';

    const push = (ok, warnMsg, okMsg) => {
      if (!ok) {
        wqType = wqType === 'critical' ? 'critical' : 'warning';
        wqTitle = 'Check water quality';
        wqMsg = 'One or more readings need attention before you raise feed.';
        wqActions.push(warnMsg);
      } else if (okMsg) {
        wqActions.push(okMsg);
      }
    };

    if (temp == null && ph == null && turb == null && tds == null) {
      wqType = 'warning';
      wqTitle = 'No water data saved yet';
      wqMsg = 'Fill temp / pH / TDS / turbidity from the database, save, then update advice.';
      wqActions.push('Click “Fill feed / temp / pH / TDS / turbidity from DB”, then Save.');
    } else {
      if (temp != null) {
        push(
          temp >= 26 && temp <= 32,
          `Temp ${temp}°C is outside ideal 26–32°C — keep aeration steady; avoid big feed hikes.`,
          `Temperature ${temp}°C is in the good range.`
        );
      }
      if (ph != null) {
        const ok = ph >= 7 && ph <= 8.5;
        if (ph < 6.5 || ph > 9) wqType = 'critical';
        push(
          ok,
          ph < 6.5
            ? `pH is low (${ph}). Add lime/dolomite; do not raise feed.`
            : ph > 9
              ? `pH is high (${ph}). Do a 20–30% water exchange.`
              : `pH ${ph} is slightly off ideal 7.0–8.5 — monitor today.`,
          `pH ${ph} is acceptable.`
        );
      }
      if (turb != null) {
        push(
          turb <= 40,
          turb > 100
            ? `Turbidity high (${turb} NTU). Partial water change; cut feed until clearer.`
            : `Turbidity elevated (${turb} NTU). Check leftover feed / algae.`,
          `Turbidity ${turb} NTU looks fine.`
        );
      }
      if (tds != null) {
        push(
          tds >= 5 && tds <= 2000,
          `TDS ${tds} ppm looks unusual — verify the probe.`,
          `TDS ${tds} ppm is within a usable range.`
        );
      }
    }

    const feedKg = feed?.total_kg;
    const feedActions = [
      feedKg != null
        ? `Today’s suggested total is ${feedKg} kg — see times in the green box.`
        : 'Wait for the feed plan to load, or check shrimp count / average weight.',
      'Open Feeding → Use as today’s feed to apply to the auto-feeder.',
      'Check trays 1–2 hours after feeding for leftovers before changing ration.',
    ];

    const gain = metric?.daily_weight_gain_grams;
    const growthActions = [
      `Current average weight: ${metric?.avg_weight_grams ?? '—'} g · count: ${Number(metric?.shrimp_count || 0).toLocaleString()}.`,
      gain != null
        ? `Last recorded daily gain: ${gain} g. Compare after you update the ML forecast.`
        : 'Save daily weight gain when you sample, then update the ML forecast.',
      'Click “Update advice from latest data” for harvest timing and environment-adjusted growth.',
    ];

    return {
      water_quality: { type: wqType, title: wqTitle, message: wqMsg, actions: wqActions },
      feed: {
        type: 'info',
        title: 'Follow today’s ML feed plan',
        message: 'Feed from shrimp count, average weight, culture day, and weather.',
        actions: feedActions,
      },
      growth: {
        type: 'info',
        title: 'Growth snapshot',
        message: 'Full growth advice appears after you update the ML forecast.',
        actions: growthActions,
      },
    };
  };

  const liveFallback = buildLiveRecCards(latestMetric, feedRec);
  const normalizeCard = (card, fallback, defaultTitle) => {
    if (!card) return fallback;
    const actions = Array.isArray(card.actions) && card.actions.length
      ? card.actions
      : (card.message ? [card.message] : (fallback?.actions || []));
    return {
      type: card.type || fallback?.type || 'info',
      title: card.title || defaultTitle,
      message: card.title ? (card.message || '') : (fallback?.message || card.message || ''),
      actions,
    };
  };
  const displayRecCards = {
    water_quality: normalizeCard(recCards?.water_quality, liveFallback.water_quality, 'Water quality'),
    feed: normalizeCard(recCards?.feed, liveFallback.feed, 'Feed'),
    growth: normalizeCard(recCards?.growth, liveFallback.growth, 'Growth'),
  };

  const cardStyle = (type) => {
    if (type === 'critical') return 'border-red-200 bg-red-50 text-red-900';
    if (type === 'warning') return 'border-amber-200 bg-amber-50 text-amber-950';
    return 'border-slate-200 bg-slate-50 text-slate-800';
  };

  return (
    <div className="space-y-6 p-6 bg-gradient-to-b from-slate-50 to-slate-100 rounded-lg">
      {/* Header Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-lg shadow">
          <p className="text-sm text-slate-600">Current Weight</p>
          <p className="text-2xl font-bold text-blue-600">
            {typeof latestMetric?.avg_weight_grams === 'number'
              ? `${latestMetric.avg_weight_grams.toFixed(2)}g`
              : 'N/A'}
          </p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <p className="text-sm text-slate-600">Shrimp Count</p>
          <p className="text-2xl font-bold text-green-600">
            {typeof latestMetric?.shrimp_count === 'number'
              ? latestMetric.shrimp_count.toLocaleString()
              : 'N/A'}
          </p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <p className="text-sm text-slate-600">Daily Gain</p>
          <p className="text-2xl font-bold text-purple-600">
            {typeof latestMetric?.daily_weight_gain_grams === 'number'
              ? `${latestMetric.daily_weight_gain_grams.toFixed(2)}g`
              : 'N/A'}
          </p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <p className="text-sm text-slate-600">Harvest Ready</p>
          <p className="text-2xl font-bold text-orange-600">
            {nearestPrediction?.estimated_harvest_date 
              ? format(parseISO(nearestPrediction.estimated_harvest_date), 'MMM dd')
              : 'N/A'
            }
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 mb-3">
        <button
          type="button"
          onClick={() => setActiveTab('metrics')}
          className={`aq-choice${activeTab === 'metrics' ? ' is-on' : ''}`}
        >
          📊 Growth Metrics
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('predictions')}
          className={`aq-choice${activeTab === 'predictions' ? ' is-on' : ''}`}
        >
          🔮 Predictions
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('recommendations')}
          className={`aq-choice${activeTab === 'recommendations' ? ' is-on' : ''}`}
        >
          💡 Recommendations
        </button>
      </div>

      {/* Growth Metrics Tab */}
      {activeTab === 'metrics' && (
        <div className="space-y-4">
          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="font-semibold mb-4">Weight Progression</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={metricsChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="weight" stroke="#3b82f6" name="Avg Weight (g)" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="font-semibold mb-4">Feed & Mortality</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={metricsChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="feed" fill="#10b981" name="Feed (g)" />
                <Bar dataKey="mortality" fill="#ef4444" name="Mortality (%)" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="font-semibold mb-2">Shrimp Population Trend</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={metricsChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="#8b5cf6" name="Count" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Predictions Tab */}
      {activeTab === 'predictions' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-4 rounded-lg shadow">
            <div>
              <h3 className="font-semibold">Growth Predictions (30 days)</h3>
              <p className="text-xs text-slate-500 mt-1">
                Model: {modelVersion || 'none yet'}
                {envModifier != null ? ` · env modifier ${Number(envModifier).toFixed(2)}` : ''}
                {' · '}Save a growth entry or click regenerate to refresh
              </p>
              {nearestRec && (
                <p className="text-xs text-slate-500 mt-1">
                  Base ADG {nearestRec.adg_base} → adjusted {nearestRec.adg_adjusted} g/day
                  {nearestRec.wq_class ? ` · WQ ML: ${nearestRec.wq_class}` : ''}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={regeneratePredictions}
              disabled={regenLoading}
              className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 disabled:opacity-60 text-white text-sm font-medium"
            >
              {regenLoading ? 'Regenerating…' : 'Regenerate ML forecast'}
            </button>
          </div>

          {envNotes.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-900 space-y-1">
              <p className="font-semibold">Environment factors applied</p>
              {envNotes.map((n, i) => <p key={i}>• {n}</p>)}
            </div>
          )}

          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="font-semibold mb-1">Actual vs Predicted ABW</h3>
            <p className="text-xs text-slate-500 mb-4">
              Yellow dashed = environment-adjusted · Gray = base model (no WQ/weather stress)
            </p>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={actualVsPredicted}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="actual_weight" stroke="#3b82f6" name="Actual (g)" connectNulls={false} />
                <Line type="monotone" dataKey="base_weight" stroke="#94a3b8" name="Base predicted (g)" connectNulls={false} strokeDasharray="2 4" />
                <Line type="monotone" dataKey="adjusted_weight" stroke="#f59e0b" name="Env-adjusted (g)" connectNulls={false} strokeDasharray="4 4" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="font-semibold mb-4">Forecast: base vs environment-adjusted</h3>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={predictionsChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="base_weight" stroke="#94a3b8" name="Base ABW (g)" strokeDasharray="2 4" />
                <Line type="monotone" dataKey="adjusted_weight" stroke="#f59e0b" name="Env-adjusted ABW (g)" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {predictions.length === 0 && (
            <div className="text-center p-4 text-slate-500 text-sm bg-white rounded-lg border">
              No predictions yet. Click &quot;Regenerate ML forecast&quot; after entering growth data.
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            {predictions.slice(0, 6).map((pred, idx) => {
              const rec = parseRec(pred);
              return (
                <div key={idx} className="bg-blue-50 p-3 rounded border border-blue-200">
                  <p className="text-sm font-medium text-slate-700">
                    {format(parseISO(pred.forecast_date), 'MMM dd, yyyy')}
                  </p>
                  <p className="text-lg font-bold text-blue-600 mt-1">
                    {Number(pred.predicted_avg_weight_grams).toFixed(2)}g
                    <span className="text-xs font-normal text-slate-500 ml-1">adjusted</span>
                  </p>
                  {rec?.base_abw != null && (
                    <p className="text-xs text-slate-500">Base: {Number(rec.base_abw).toFixed(2)}g</p>
                  )}
                  <p className="text-xs text-slate-500 mt-1">
                    Confidence: {pred.confidence_score}% · {pred.model_version}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recommendations Tab */}
      {activeTab === 'recommendations' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-950">
            <p className="font-semibold mb-1">What should I do today?</p>
            <ol className="list-decimal ml-5 space-y-1 text-blue-900/90">
              <li>Read the three cards below (Water → Feed → Growth). Priority issues are yellow/red.</li>
              <li>Apply the green feed plan (kg + times), then open <strong>Feeding</strong> → Use as today&apos;s feed.</li>
              <li>
                After you save new water / count / weight on the left, click{' '}
                <button
                  type="button"
                  onClick={regeneratePredictions}
                  disabled={regenLoading}
                  className="underline font-semibold disabled:opacity-50"
                >
                  {regenLoading ? 'Updating…' : 'Update advice from latest data'}
                </button>
                .
              </li>
            </ol>
            {!recCards && (
              <p className="mt-2 text-xs text-blue-800">
                Tip: you already have feed advice below. For full water + growth actions, use the update button once.
              </p>
            )}
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            {[
              { key: 'water_quality', label: '1. Water quality', card: displayRecCards.water_quality },
              { key: 'feed', label: '2. Feed', card: displayRecCards.feed },
              { key: 'growth', label: '3. Growth', card: displayRecCards.growth },
            ].map(({ key, label, card }) => (
              <div key={key} className={`rounded-xl border p-4 ${cardStyle(card?.type || 'info')}`}>
                <p className="text-xs font-bold uppercase tracking-wide mb-1">{label}</p>
                <p className="text-sm font-semibold mb-1">{card?.title || 'Advice'}</p>
                <p className="text-sm leading-relaxed mb-3 opacity-90">{card?.message}</p>
                {(card?.actions || []).length > 0 && (
                  <ul className="space-y-1.5 text-sm">
                    {card.actions.map((a, i) => (
                      <li key={i} className="flex gap-2 leading-snug">
                        <span className="shrink-0 mt-0.5">•</span>
                        <span>{a}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>

          <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
            <p className="text-sm font-semibold text-emerald-900 mb-1">Today&apos;s feed plan (ready to apply)</p>
            <p className="text-xs text-emerald-800 mb-3">
              Based on shrimp count, average weight (ABW), days of culture, and weather.
              Next step: go to <strong>Feeding</strong> and click <strong>Use as today&apos;s feed</strong>.
            </p>
            {feedRecLoading && <p className="text-sm text-slate-500">Loading feed recommendation…</p>}
            {!feedRecLoading && feedRec && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <div className="bg-white rounded-lg border border-emerald-100 p-3">
                    <div className="text-[10px] uppercase text-slate-500">Feed today</div>
                    <div className="text-xl font-bold text-emerald-700">{feedRec.total_kg} kg</div>
                    <div className="text-[11px] text-slate-400">≈ {(feedRec.total_grams || 0).toLocaleString()} g total</div>
                  </div>
                  <div className="bg-white rounded-lg border border-emerald-100 p-3">
                    <div className="text-[10px] uppercase text-slate-500">Adjusted for growth stage</div>
                    <div className="text-xl font-bold text-slate-800">{Math.round((feedRec.growth_scale || 1) * 100)}%</div>
                    <div className="text-[11px] text-slate-400">of full adult ration</div>
                  </div>
                  <div className="bg-white rounded-lg border border-emerald-100 p-3">
                    <div className="text-[10px] uppercase text-slate-500">Your stock</div>
                    <div className="text-sm font-semibold text-slate-800">
                      {Number(feedRec.growth?.shrimp_count || 0).toLocaleString()} shrimp · {feedRec.growth?.abw_g}g avg
                    </div>
                  </div>
                  <div className="bg-white rounded-lg border border-emerald-100 p-3">
                    <div className="text-[10px] uppercase text-slate-500">Unscaled estimate</div>
                    <div className="text-sm font-semibold text-slate-800">{feedRec.base_total_kg} kg</div>
                    <div className="text-[11px] text-slate-400">before growth-stage scale</div>
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold text-emerald-900 mb-1.5">Feeding times</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(feedRec.slots_kg || {}).map(([time, kg]) => (
                      <span key={time} className="text-xs bg-white border border-emerald-100 rounded-md px-2 py-1 text-slate-700">
                        {time}: <strong>{kg}</strong> kg
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
            {!feedRecLoading && !feedRec && (
              <p className="text-sm text-slate-500">Could not load ML feed recommendation. Check season count and average weight.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
