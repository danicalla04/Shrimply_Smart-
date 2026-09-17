import { useEffect, useState } from 'react'
import { fetchCompleteWeather } from '../services/weatherApi'
import API_BASE from '../services/apiConfig'
import { useLanguage } from '../context/LanguageContext'

const iconToEmoji = (code) => {
  if (!code) return '⛅'
  const g = code.slice(0, 2)
  switch (g) {
    case '01': return '☀️'
    case '02':
    case '03':
    case '04': return '☁️'
    case '09':
    case '10': return '🌧️'
    case '11': return '⛈️'
    case '13': return '❄️'
    case '50': return '🌫️'
    default: return '⛅'
  }
}

const Weather = () => {
  const [city, setCity] = useState('Oriental Mindoro')
  const [displayName, setDisplayName] = useState('Oriental Mindoro')
  const [municipalities, setMunicipalities] = useState([])
  const [current, setCurrent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [forecast, setForecast] = useState([])
  const [hourly, setHourly] = useState([])
  const [alerts, setAlerts] = useState([])
  const [impact, setImpact] = useState(null)
  const [activeTab, setActiveTab] = useState('temperature')
  const [lastUpdated, setLastUpdated] = useState(null)
  const { t } = useLanguage()

  // Load municipalities on component mount
  useEffect(() => {
    const loadMunicipalities = async () => {
      try {
        const response = await fetch(`${API_BASE}/weather/municipalities/`)
        const data = await response.json()
        setMunicipalities(data.municipalities || [])
      } catch (e) {
        console.error('Failed to load municipalities:', e)
        setMunicipalities([
          { province: 'Oriental Mindoro', municipality: 'Pinamalayan' },
          { province: 'Oriental Mindoro', municipality: 'Calapan' },
          { province: 'Pangasinan', municipality: 'San Carlos' },
          { province: 'Negros Occidental', municipality: 'Bacolod' }
        ])
      }
    }
    loadMunicipalities()
  }, [])

  const loadWeather = async (targetCity = city) => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchCompleteWeather(targetCity)

      // Set all available data, even if some fields are missing
      if (data.current) {
        setCurrent(data.current)
      }

      if (data.weekly && Array.isArray(data.weekly)) {
        setForecast(data.weekly)
      }

      if (data.hourly && Array.isArray(data.hourly)) {
        setHourly(data.hourly)
      }

      if (data.alerts && Array.isArray(data.alerts)) {
        setAlerts(data.alerts)
      }

      if (data.impact) {
        setImpact(data.impact)
      }

      if (data.last_updated) {
        setLastUpdated(new Date(data.last_updated))
      }

      // If we got current data, the request succeeded - don't show error
      if (data.current) {
        setError('')
      }

    } catch (e) {
      console.error('Weather load error:', e.message)
      // Only show error if we don't have any current data
      if (!current) {
        setError(e.message || 'Failed to load weather')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadWeather()
    // Auto-refresh every 10 minutes
    const interval = setInterval(() => loadWeather(), 600000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleMunicipalityChange = (e) => {
    const selectedValue = e.target.value
    if (selectedValue) {
      const [province, municipality] = selectedValue.split('|')
      const locationName = `${municipality}, ${province}`
      setCity(locationName)
      setDisplayName(`${municipality}, ${province}`)
      loadWeather(locationName)
    }
  }

  const exportToCSV = () => {
    let csv = 'Date,Day,Temperature,Min,Max,Humidity,Wind,Precipitation,Description,Source\n'
    forecast.forEach(day => {
      csv += `${day.date},${day.day},${day.temperature},${day.min},${day.max},${day.humidity},${day.windKmh},${day.precipMm},"${day.description}",${day.source}\n`
    })
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `weather-forecast-${city}-${new Date().toISOString().split('T')[0]}.csv`
    a.click()
  }

  const getConfidenceBadge = (source) => {
    switch (source) {
      case 'openweather_5day':
      case 'openweather_ml_corrected':
        return { label: t('highAccuracy'), color: 'bg-green-500', percent: '95%' }
      case 'ml_ensemble_prediction':
        return { label: 'ML Ensemble', color: 'bg-blue-500', percent: '90%' }
      case 'ml_prediction':
        return { label: 'ML Prediction', color: 'bg-yellow-500', percent: '85%' }
      default:
        return { label: t('estimated'), color: 'bg-gray-500', percent: '60%' }
    }
  }

  const getAlertColor = (severity) => {
    switch (severity) {
      case 'high': return 'bg-red-100 border-red-300 text-red-800'
      case 'medium': return 'bg-orange-100 border-orange-300 text-orange-800'
      case 'low': return 'bg-yellow-100 border-yellow-300 text-yellow-800'
      case 'info': return 'bg-purple-100 border-purple-300 text-purple-800'
      default: return 'bg-blue-100 border-blue-300 text-blue-800'
    }
  }

  return (
    <div className="p-6 bg-gray-200 min-h-screen">
      {/* Header with Location */}
      <div className="max-w-5xl mx-auto mb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-gray-500 text-lg">{t('resultsFor')}</span>
            <span className="text-xl font-bold text-gray-900">{current?.city || displayName}</span>
            <select
              value={city}
              onChange={handleMunicipalityChange}
              className="bg-transparent border border-gray-300 rounded-lg text-sm text-gray-700 focus:outline-none cursor-pointer px-2 py-1"
            >
              <option value="Oriental Mindoro">{t('changeLocation')}</option>
              {municipalities.map((mun, index) => (
                <option key={index} value={`${mun.province}|${mun.municipality}`}>
                  {mun.municipality}, {mun.province}
                </option>
              ))}
            </select>
            <button onClick={() => loadWeather()} className="text-gray-400 hover:text-blue-600 transition-colors text-lg" title="Refresh">
              🔄
            </button>
          </div>
          <button
            onClick={exportToCSV}
            className="bg-blue-600 text-white px-4 py-2 rounded-full hover:bg-blue-700 transition-colors text-sm font-medium"
            title={t('exportForecast')}
          >
            📥 {t('export')}
          </button>
        </div>
      </div>

      {/* Weather Alerts Banner */}
      {alerts && alerts.length > 0 && (
        <div className="max-w-5xl mx-auto mb-4 space-y-2">
          {alerts.slice(0, 3).map((alert, idx) => (
            <div key={idx} className={`rounded-lg border-2 p-3 ${getAlertColor(alert.severity)}`}>
              <div className="flex items-start gap-3">
                <span className="text-2xl">{alert.icon}</span>
                <div>
                  <h3 className="font-bold">{alert.title}</h3>
                  <p className="text-sm mt-1">{alert.message}</p>
                  {alert.recommendations && alert.recommendations.length > 0 && (
                    <ul className="text-xs mt-1 space-y-0.5">
                      {alert.recommendations.slice(0, 2).map((rec, ridx) => (
                        <li key={ridx}>• {rec}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="max-w-5xl mx-auto mb-4 p-3 rounded-lg bg-red-50 text-red-700 border border-red-200">
          {error}
        </div>
      )}

      {loading ? (
        <div className="max-w-5xl mx-auto text-center py-20">
          <div className="text-2xl text-gray-600">{t('loadingWeather')}</div>
        </div>
      ) : (
        <div className="max-w-5xl mx-auto space-y-4">
          {/* Current Weather Card - Google Style */}
          <div className="bg-white rounded-2xl shadow-lg p-6">
            {/* Current weather row */}
            <div className="flex items-center justify-between">
              {/* Left: Icon + Temperature + Stats */}
              <div className="flex items-center gap-6">
                {/* Weather Icon */}
                <div className="text-7xl flex-shrink-0">
                  {current?.iconUrl ? (
                    <img src={current.iconUrl} alt={current.condition} className="w-24 h-24" />
                  ) : '🌧️'}
                </div>
                {/* Temperature */}
                <div className="flex items-start">
                  <span className="text-7xl font-light text-gray-900 leading-none">{Math.round(current?.temperature || 28)}</span>
                  <span className="text-2xl text-gray-500 mt-2">°C</span>
                </div>
                {/* Stats */}
                <div className="text-sm text-gray-600 space-y-1 ml-4 border-l border-gray-200 pl-5">
                  <div>{t('precipitation')}: {current?.precipMm || 0}%</div>
                  <div>{t('humidity')}: {current?.humidity || 89}%</div>
                  <div>{t('wind')}: {current?.windKmh || 8} km/h</div>
                </div>
              </div>
              {/* Right: Day + Condition */}
              <div className="text-right">
                <div className="text-2xl font-semibold text-gray-800">{t('weather')}</div>
                <div className="text-gray-600 mt-1">
                  {new Date().toLocaleDateString('en-US', { weekday: 'long' })}
                </div>
                <div className="text-gray-500 mt-0.5">{current?.description || 'Light rain'}</div>
              </div>
            </div>
          </div>

          {/* Tabs + Chart + Forecast Card */}
          <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
            {/* Tab Navigation */}
            <div className="flex border-b border-gray-200 px-6">
              <button
                onClick={() => setActiveTab('temperature')}
                className={`px-5 py-3 text-sm font-semibold transition-colors ${activeTab === 'temperature'
                  ? 'text-blue-600 border-b-3 border-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
                  }`}
                style={activeTab === 'temperature' ? { borderBottomWidth: '3px' } : {}}
              >
                {t('temperature')}
              </button>
              <button
                onClick={() => setActiveTab('precipitation')}
                className={`px-5 py-3 text-sm font-semibold transition-colors ${activeTab === 'precipitation'
                  ? 'text-blue-600 border-b-3 border-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
                  }`}
                style={activeTab === 'precipitation' ? { borderBottomWidth: '3px' } : {}}
              >
                {t('precipitation')}
              </button>
              <button
                onClick={() => setActiveTab('wind')}
                className={`px-5 py-3 text-sm font-semibold transition-colors ${activeTab === 'wind'
                  ? 'text-blue-600 border-b-3 border-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
                  }`}
                style={activeTab === 'wind' ? { borderBottomWidth: '3px' } : {}}
              >
                {t('wind')}
              </button>
            </div>

            {/* Hourly Chart - Dark Area Chart like Google */}
            <div className="px-6 pt-6 pb-4">
              <div className="rounded-xl overflow-hidden" style={{
                background: activeTab === 'temperature'
                  ? 'linear-gradient(to bottom, #422006, #78350f, #1c1917)'
                  : activeTab === 'precipitation'
                    ? 'linear-gradient(to bottom, #1e3a8a, #1e40af, #1e3a8a)'
                    : 'linear-gradient(to bottom, #065f46, #047857, #064e3b)'
              }}>
                <div className="p-5">
                  <div className="relative" style={{ height: '160px' }}>
                    {hourly && hourly.length > 0 ? (
                      <>
                        <svg className="w-full" style={{ height: '120px' }} viewBox="0 0 800 120" preserveAspectRatio="none">
                          <defs>
                            <linearGradient id="chartFill" x1="0%" y1="0%" x2="0%" y2="100%">
                              <stop offset="0%" stopColor={activeTab === 'temperature' ? '#fbbf24' : activeTab === 'precipitation' ? '#3b82f6' : '#10b981'} stopOpacity="0.5" />
                              <stop offset="100%" stopColor={activeTab === 'temperature' ? '#fbbf24' : activeTab === 'precipitation' ? '#3b82f6' : '#10b981'} stopOpacity="0.05" />
                            </linearGradient>
                          </defs>
                          {(() => {
                            const values = hourly.map(h =>
                              activeTab === 'temperature' ? h.temperature
                                : activeTab === 'precipitation' ? (h.precipitation || 0) * 10
                                  : h.wind_speed
                            )
                            const minVal = Math.min(...values) - 2
                            const maxVal = Math.max(...values) + 2
                            const range = maxVal - minVal || 1

                            const points = hourly.map((h, i) => {
                              const x = (i / (hourly.length - 1)) * 800
                              const val = activeTab === 'temperature' ? h.temperature
                                : activeTab === 'precipitation' ? (h.precipitation || 0) * 10
                                  : h.wind_speed
                              const y = 100 - ((val - minVal) / range) * 80
                              return { x, y, val }
                            })

                            const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x},${p.y}`).join(' ')
                            const areaPath = `${linePath} L 800,120 L 0,120 Z`
                            const color = activeTab === 'temperature' ? '#fbbf24' : activeTab === 'precipitation' ? '#3b82f6' : '#10b981'

                            return (
                              <>
                                <path d={areaPath} fill="url(#chartFill)" />
                                <path d={linePath} fill="none" stroke={color} strokeWidth="2.5" />
                                {points.map((p, i) => (
                                  <text key={i} x={p.x} y={p.y - 8} textAnchor="middle" fill="white" fontSize="11" fontWeight="600">
                                    {Math.round(p.val)}
                                  </text>
                                ))}
                              </>
                            )
                          })()}
                        </svg>
                        <div className="flex justify-between mt-2 px-1">
                          {hourly.map((hour, i) => (
                            <div key={i} className="text-xs text-gray-400 font-medium text-center" style={{ width: `${100 / hourly.length}%` }}>
                              {hour.hour || hour.time}
                            </div>
                          ))}
                        </div>
                      </>
                    ) : (
                      <div className="text-white text-center py-12 text-sm">{t('noHourlyData')}</div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* 7-Day Forecast - Google Row Style with Confidence Intervals */}
            <div className="px-6 pb-6">
              <div className="flex gap-2 overflow-x-auto">
                {forecast.slice(1, 8).map((day, index) => {
                  const confidence = getConfidenceBadge(day.source)
                  // Use confidence intervals if available, otherwise fall back to min/max
                  const tempMax = day.temperature_max !== undefined ? day.temperature_max : (day.max || day.temperature)
                  const tempMin = day.temperature_min !== undefined ? day.temperature_min : (day.min || day.temperature - 3)

                  return (
                    <div key={index} className="flex-1 min-w-[100px] bg-gray-50 rounded-xl p-3 text-center hover:bg-gray-100 transition-all cursor-pointer relative group">
                      {/* Confidence tooltip */}
                      <div className={`absolute -top-1 -right-1 ${confidence.color} text-white text-[9px] w-5 h-5 rounded-full font-bold flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity`} title={confidence.label}>
                        {confidence.percent.replace('%', '')}
                      </div>

                      {/* Detailed tooltip on hover */}
                      <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-max bg-gray-800 text-white text-xs rounded-lg p-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 whitespace-nowrap">
                        <div>Temp: {tempMin.toFixed(1)}°–{tempMax.toFixed(1)}°C</div>
                        {day.humidity_min && day.humidity_max && (
                          <div>Humidity: {day.humidity_min.toFixed(0)}–{day.humidity_max.toFixed(0)}%</div>
                        )}
                        {day.rainfall_min !== undefined && day.rainfall_max !== undefined && (
                          <div>Rain: {day.rainfall_min.toFixed(1)}–{day.rainfall_max.toFixed(1)}mm</div>
                        )}
                      </div>

                      <div className="text-xs font-bold text-gray-700 mb-1">
                        {day.day?.slice(0, 3) || new Date(day.date).toLocaleDateString('en-US', { weekday: 'short' })}
                      </div>
                      <div className="text-2xl my-1.5">
                        {day.iconUrl ? (
                          <img src={day.iconUrl} alt={day.description} className="w-9 h-9 mx-auto" />
                        ) : iconToEmoji(day.icon)}
                      </div>
                      <div className="text-sm font-bold text-gray-900">
                        {Math.round(tempMax)}°
                      </div>
                      <div className="text-xs text-gray-400">
                        {Math.round(tempMin)}°
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Weather Impact Section */}
          {impact && (
            <div className="bg-white rounded-3xl shadow-xl p-8">
              <h2 className="text-2xl font-bold mb-6 text-gray-800">{t('weatherImpact')}</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h3 className="text-lg font-semibold mb-4 text-blue-600">{t('currentConditionsImpact')}</h3>
                  <div className="space-y-3">
                    {impact.temperature_impact === 'high_risk' && (
                      <div className="flex items-center p-3 bg-red-50 rounded-lg border border-red-200">
                        <span className="text-2xl mr-3">🚨</span>
                        <div>
                          <h4 className="font-medium text-red-800">{t('highTempAlert')}</h4>
                          <p className="text-sm text-red-600">Critical: Monitor water quality conditions closely</p>
                        </div>
                      </div>
                    )}
                    {impact.temperature_impact === 'moderate_risk' && (
                      <div className="flex items-center p-3 bg-yellow-50 rounded-lg border border-yellow-200">
                        <span className="text-2xl mr-3">⚠️</span>
                        <div>
                          <h4 className="font-medium text-yellow-800">{t('tempWarning')}</h4>
                          <p className="text-sm text-yellow-600">Ensure adequate water circulation and monitoring</p>
                        </div>
                      </div>
                    )}
                    {impact.temperature_impact === 'optimal' && (
                      <div className="flex items-center p-3 bg-green-50 rounded-lg border border-green-200">
                        <span className="text-2xl mr-3">✅</span>
                        <div>
                          <h4 className="font-medium text-green-800">{t('optimalTemp')}</h4>
                          <p className="text-sm text-green-600">Temperature is within ideal range for shrimp growth</p>
                        </div>
                      </div>
                    )}
                    {impact.rain_impact === 'high_risk' && (
                      <div className="flex items-center p-3 bg-red-50 rounded-lg border border-red-200">
                        <span className="text-2xl mr-3">🌧️</span>
                        <div>
                          <h4 className="font-medium text-red-800">{t('heavyRainAlert')}</h4>
                          <p className="text-sm text-red-600">Monitor salinity and pH levels closely</p>
                        </div>
                      </div>
                    )}
                    {impact.wind_impact === 'optimal' && (
                      <div className="flex items-center p-3 bg-green-50 rounded-lg border border-green-200">
                        <span className="text-2xl mr-3">💨</span>
                        <div>
                          <h4 className="font-medium text-green-800">{t('goodWindConditions')}</h4>
                          <p className="text-sm text-green-600">Favorable for natural aeration</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  <h3 className="text-lg font-semibold mb-4 text-blue-600">{t('recommendations')}</h3>
                  <div className="space-y-3">
                    {impact.recommendations && impact.recommendations.length > 0 ? (
                      impact.recommendations.map((rec, index) => (
                        <div key={index} className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                          <p className="text-sm text-blue-800">{rec}</p>
                        </div>
                      ))
                    ) : (
                      <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                        <h4 className="font-medium text-blue-800 mb-2">{t('generalRecommendations')}</h4>
                        <ul className="text-sm text-blue-600 space-y-1">
                          <li>• {t('monitorWaterTemp')}</li>
                          <li>• {t('ensureAeration')}</li>
                          <li>• {t('checkDORegularly')}</li>
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default Weather
