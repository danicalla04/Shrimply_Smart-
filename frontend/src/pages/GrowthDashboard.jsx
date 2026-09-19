import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import authService from '../services/auth';
import { EFFECTIVE_API_BASE } from '../services/apiConfig';
import ShrimpQuantityForm from './ShrimpQuantityForm';
import GrowthAnalytics from './GrowthAnalytics';
import PageLoader from '../components/PageLoader';

export default function GrowthDashboard() {
  const { seasonId: paramSeasonId } = useParams();
  const [seasons, setSeasons] = useState([]);
  const [selectedSeasonId, setSelectedSeasonId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  useEffect(() => {
    const fetchSeasons = async () => {
      try {
        setLoading(true);
        const res = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/`);
        const seasonsJson = await res.json();
        const seasonsList = seasonsJson?.results || seasonsJson || [];
        setSeasons(seasonsList);

        // Set initial season
        if (paramSeasonId) {
          setSelectedSeasonId(parseInt(paramSeasonId));
        } else {
          const activeSeason = seasonsList.find(s => s.is_active);
          if (activeSeason) {
            setSelectedSeasonId(activeSeason.id);
          } else if (seasonsList.length > 0) {
            setSelectedSeasonId(seasonsList[0].id);
          }
        }
      } catch (err) {
        console.error('Error fetching seasons:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchSeasons();
  }, [paramSeasonId]);

  if (loading) {
    return <PageLoader />;
  }

  if (seasons.length === 0) {
    return (
      <div className="p-8">
        <div className="max-w-4xl mx-auto">
          <div className="glass-card p-8 text-center">
            <p className="text-slate-500 mb-4">No seasons found. Create a new season to start tracking growth.</p>
          </div>
        </div>
      </div>
    );
  }

  const activeSeason = seasons.find(s => s.id === selectedSeasonId);

  return (
    <div className="p-8">
      {/* Hero Header */}
      <div className="mb-8 relative">
        <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 to-blue-500/10 rounded-2xl"></div>
        <div className="relative z-10 p-6">
          <h1 className="text-4xl font-bold text-gradient mb-2">🚀 Growth Prediction &amp; Analytics</h1>
          <p className="text-slate-600 text-lg">Track shrimp growth, predict harvest dates, and optimize feeding</p>
        </div>
      </div>

      {/* Season Selector */}
      <div className="mb-6 flex gap-2 flex-wrap items-center">
        <span className="text-slate-600 font-medium mr-1">Select Season:</span>
        {seasons.map(season => (
          <button
            key={season.id}
            onClick={() => setSelectedSeasonId(season.id)}
            className={`aq-choice${selectedSeasonId === season.id ? ' is-on' : ''}`}
          >
            {season.name}
            {season.is_active && ' 🟢'}
          </button>
        ))}
      </div>

      {/* Main Content */}
      {activeSeason && (
        <div className="space-y-6">
          {/* Season Info */}
          <div className="glass-card p-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <p className="text-slate-500 text-sm">Season Name</p>
                <p className="text-slate-800 text-lg font-semibold">{activeSeason.name}</p>
              </div>
              <div>
                <p className="text-slate-500 text-sm">Started</p>
                <p className="text-slate-800 text-lg font-semibold">
                  {new Date(activeSeason.start_date).toLocaleDateString()}
                </p>
              </div>
              <div>
                <p className="text-slate-500 text-sm">Days Active</p>
                <p className="text-slate-800 text-lg font-semibold">
                  {activeSeason.days_active != null ? activeSeason.days_active : 'N/A'}
                </p>
              </div>
              <div>
                <p className="text-slate-500 text-sm">Status</p>
                <p className={`text-lg font-semibold ${
                  activeSeason.is_active ? 'text-emerald-600' : 'text-rose-500'
                }`}>
                  {activeSeason.is_active ? '🟢 Active' : '🔴 Completed'}
                </p>
              </div>
            </div>
          </div>

          {/* Two Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left: Input Form */}
            <div className="lg:col-span-1">
              <ShrimpQuantityForm
                seasonId={selectedSeasonId}
                onUpdate={() => setRefreshTrigger(prev => prev + 1)}
              />
            </div>

            {/* Right: Analytics */}
            <div className="lg:col-span-2">
              <GrowthAnalytics
                seasonId={selectedSeasonId}
                key={refreshTrigger}
              />
            </div>
          </div>

          {/* Quick Stats */}
          <div className="glass-card p-6">
            <h3 className="text-slate-800 font-bold text-lg mb-4">📈 Quick Stats</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                <p className="text-slate-500 text-sm">Current Count</p>
                <p className="text-slate-800 text-2xl font-bold">
                  {activeSeason.current_shrimp_quantity?.toLocaleString() || '—'}
                </p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                <p className="text-slate-500 text-sm">Avg Weight</p>
                <p className="text-slate-800 text-2xl font-bold">
                  {activeSeason.average_shrimp_weight_grams?.toFixed(2) || '—'}
                  <span className="text-sm ml-1">g</span>
                </p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                <p className="text-slate-500 text-sm">Total Biomass</p>
                <p className="text-slate-800 text-2xl font-bold">
                  {activeSeason.current_shrimp_quantity && activeSeason.average_shrimp_weight_grams
                    ? `${(activeSeason.current_shrimp_quantity * activeSeason.average_shrimp_weight_grams / 1000).toFixed(1)}kg`
                    : '—'
                  }
                </p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                <p className="text-slate-500 text-sm">Initial Stock</p>
                <p className="text-slate-800 text-2xl font-bold">
                  {activeSeason.initial_shrimp_quantity
                    ? activeSeason.initial_shrimp_quantity.toLocaleString()
                    : '—'}
                </p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                <p className="text-slate-500 text-sm">Stocking Density</p>
                <p className="text-slate-800 text-2xl font-bold">
                  {activeSeason.stocking_density || '—'}
                  <span className="text-sm ml-1">/m²</span>
                </p>
              </div>
            </div>
          </div>

          {/* Information Panel */}
          <div className="card p-6">
            <h3 className="font-bold text-lg mb-3">💡 How to Use</h3>
            <ul className="space-y-2 text-sm text-cyan-100/80">
              <li>✅ <strong>Input Data:</strong> Use the form on the left to enter daily metrics for your shrimp pond</li>
              <li>✅ <strong>Track Growth:</strong> Log shrimp count, average weight, and water quality parameters</li>
              <li>✅ <strong>Get Predictions:</strong> The ML model predicts growth trends and harvest dates</li>
              <li>✅ <strong>View Analytics:</strong> Charts show weight progression, feeding patterns, and recommendations</li>
              <li>✅ <strong>Smart Feeding:</strong> Adjust feed based on shrimp size in Feeding Management</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
