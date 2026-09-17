const MetricCard = ({ title, value, unit, icon, color = 'primary', trend = null }) => {
  const colorClasses = {
    primary: 'from-blue-500 to-blue-600',
    success: 'from-green-500 to-green-600',
    warning: 'from-yellow-500 to-yellow-600',
    danger: 'from-red-500 to-red-600',
    info: 'from-cyan-500 to-cyan-600'
  }

  return (
    <div className="metric-card card-shrimp group">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-3 rounded-lg bg-gradient-to-r ${colorClasses[color]} text-white`}>
          <span className="text-2xl">{icon}</span>
        </div>
        {trend && (
          <div className={`text-sm font-medium ${
            trend > 0 ? 'text-green-600' : trend < 0 ? 'text-red-600' : 'text-gray-600'
          }`}>
            {trend > 0 ? '↗' : trend < 0 ? '↘' : '→'} {Math.abs(trend)}%
          </div>
        )}
      </div>
      
      <div>
        <h3 className="text-sm font-medium text-gray-600 mb-1">{title}</h3>
        <div className="flex items-baseline">
          <span className="text-3xl font-bold text-gray-900">{value}</span>
          <span className="text-lg text-gray-500 ml-1">{unit}</span>
        </div>
      </div>
    </div>
  )
}

export default MetricCard
