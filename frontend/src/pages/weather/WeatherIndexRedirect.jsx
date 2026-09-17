import { Navigate } from 'react-router-dom';

export default function WeatherIndexRedirect() {
  return <Navigate to="/weather" replace />;
}
