import { createContext, useContext } from 'react';

const WeatherContext = createContext(null);

export function WeatherProvider({ value, children }) {
  return (
    <WeatherContext.Provider
      value={{
        ...value,
        municipalities: value.municipalities || [],
        selectedMunicipality: value.selectedMunicipality || null,
        onMunicipalityChange: value.onMunicipalityChange || (() => {}),
      }}
    >
      {children}
    </WeatherContext.Provider>
  );
}

export function useWeather() {
  const ctx = useContext(WeatherContext);
  if (!ctx) {
    throw new Error('useWeather must be used within WeatherProvider');
  }
  return ctx;
}
