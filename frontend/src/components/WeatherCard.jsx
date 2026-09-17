const WeatherCard = ({ day, condition, temperature, humidity, windSpeed, icon, high, low }) => {
  const getConditionColor = (condition) => {
    switch (condition.toLowerCase()) {
      case 'sunny':
        return 'from-yellow-400 to-orange-500'
      case 'rainy':
        return 'from-blue-400 to-blue-600'
      case 'cloudy':
        return 'from-gray-400 to-gray-600'
      case 'partly cloudy':
        return 'from-gray-300 to-blue-400'
      default:
        return 'from-gray-400 to-gray-600'
    }
  }

  return (
    <div className="card-gradient hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1">
      <div className="text-center">
        <h3 className="text-lg font-semibold text-gray-800 mb-2">{day}</h3>
        <div className={`w-16 h-16 mx-auto rounded-full bg-gradient-to-r ${getConditionColor(condition)} flex items-center justify-center mb-4`}>
          <span className="text-3xl">{icon}</span>
        </div>
        <h4 className="text-xl font-bold text-gray-900 mb-2">{condition}</h4>
        {high != null && low != null ? (
          <div className="text-2xl font-bold text-primary-600 mb-4">{high} / {low}°C</div>
        ) : (
          <div className="text-3xl font-bold text-primary-600 mb-4">{temperature}°C</div>
        )}
        
        <div className="space-y-2 text-sm text-gray-600">
          <div className="flex justify-between">
            <span>Humidity:</span>
            <span className="font-medium">{humidity}%</span>
          </div>
          <div className="flex justify-between">
            <span>Wind:</span>
            <span className="font-medium">{windSpeed} km/h</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default WeatherCard
