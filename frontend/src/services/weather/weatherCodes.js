// WMO weather interpretation codes (WW)
// Source: Open‑Meteo docs; mapped here for display.

export function wmoLabel(code) {
  const c = Number(code);
  if (!Number.isFinite(c)) return 'Unknown';

  if (c === 0) return 'Clear sky';
  if ([1, 2, 3].includes(c)) return 'Partly cloudy';
  if (c === 45 || c === 48) return 'Fog';

  if ([51, 53, 55].includes(c)) return 'Drizzle';
  if (c === 56 || c === 57) return 'Freezing drizzle';

  if ([61, 63, 65].includes(c)) return 'Rain';
  if (c === 66 || c === 67) return 'Freezing rain';

  if ([71, 73, 75].includes(c)) return 'Snow';
  if (c === 77) return 'Snow grains';

  if ([80, 81, 82].includes(c)) return 'Rain showers';
  if (c === 85 || c === 86) return 'Snow showers';

  if (c === 95) return 'Thunderstorm';
  if (c === 96 || c === 99) return 'Thunderstorm with hail';

  return 'Mixed conditions';
}

export function wmoIcon(code, isDay = true) {
  const c = Number(code);
  const day = !!isDay;
  if (!Number.isFinite(c)) return day ? '⛅' : '🌙';

  if (c === 0) return day ? '☀️' : '🌙';
  if ([1, 2].includes(c)) return day ? '🌤️' : '🌙';
  if (c === 3) return '☁️';
  if (c === 45 || c === 48) return '🌫️';

  if ([51, 53, 55, 56, 57].includes(c)) return '🌦️';
  if ([61, 63, 65, 80, 81, 82].includes(c)) return '🌧️';
  if (c === 66 || c === 67) return '🌧️';

  if ([71, 73, 75, 77, 85, 86].includes(c)) return '❄️';

  if ([95, 96, 99].includes(c)) return '⛈️';

  return '⛅';
}
