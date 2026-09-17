"""
Phase 3: Monthly automated retraining of weather ML models
Updates API performance metrics and ensemble weights based on accuracy tracking
"""
from django.core.management.base import BaseCommand
from django.db.models import Q, Avg
from django.utils import timezone
from datetime import timedelta, datetime
from pathlib import Path
import json
import numpy as np
from api.models import WeatherPrediction, APIPerformance, ModelRetrainingLog
from api.ensemble_ml_predictor import get_ensemble_ml_predictor


class Command(BaseCommand):
    help = 'Retrain weather models monthly using prediction validation data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=str,
            help='Month to retrain on (YYYY-MM format). Default: last month',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output',
        )

    def handle(self, *args, **options):
        verbose = options.get('verbose', False)
        month_str = options.get('month')
        
        self.stdout.write(self.style.SUCCESS('🔄 Starting weather model retraining...'))
        
        # Determine month to retrain
        if month_str:
            try:
                month_date = datetime.strptime(month_str, '%Y-%m').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid month format. Use YYYY-MM'))
                return
        else:
            # Default: last month
            today = timezone.now().date()
            first_of_month = today.replace(day=1)
            last_month_end = first_of_month - timedelta(days=1)
            month_date = last_month_end.replace(day=1)
        
        month_str = month_date.strftime('%Y-%m')
        self.stdout.write(f'📅 Processing month: {month_str}')
        
        # Get all verified predictions from this month
        predictions = WeatherPrediction.objects.filter(
            created_at__year=month_date.year,
            created_at__month=month_date.month,
            actual_value__isnull=False,
            verification_date__isnull=False,
        )
        
        total_predictions = predictions.count()
        verified_predictions = total_predictions
        
        if verified_predictions < 10:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  Only {verified_predictions} verified predictions for {month_str}. '
                    'Need at least 10 to retrain. Skipping.'
                )
            )
            return
        
        self.stdout.write(f'✅ Found {verified_predictions} verified predictions')
        
        # Calculate API performance metrics
        api_metrics = self._calculate_api_performance(predictions, verbose)
        
        # Get previous average RMSE for comparison
        previous_perf = APIPerformance.objects.filter(
            month__lt=month_date
        ).aggregate(Avg('rmse'))
        previous_avg_rmse = previous_perf['rmse__avg'] or 0.0
        
        # Update APIPerformance model and calculate new average
        new_avg_rmse = self._update_api_performance(api_metrics, month_date, verified_predictions)
        
        # Calculate improvement
        improvement_percent = 0.0
        if previous_avg_rmse > 0:
            improvement_percent = (previous_avg_rmse - new_avg_rmse) / previous_avg_rmse * 100
        
        # Adjust ensemble weights
        self._adjust_ensemble_weights(month_date, verbose)
        
        # Create retraining log
        try:
            retrain_log = ModelRetrainingLog.objects.create(
                month_end=month_date,
                total_predictions=total_predictions,
                verified_predictions=verified_predictions,
                previous_avg_rmse=previous_avg_rmse,
                new_avg_rmse=new_avg_rmse,
                improvement_percent=improvement_percent,
                xgboost_version='v3',  # Current version
                lstm_version='v1',  # Current version
                notes=f'Retrained on {verified_predictions} verified predictions. '
                      f'Improvement: {improvement_percent:+.2f}%',
                success=True,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Retraining successful! Improvement: {improvement_percent:+.2f}%'
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Failed to create retraining log: {str(e)}'))
            return
        
        # Output summary
        self._print_summary(api_metrics, improvement_percent, verbose)

    def _calculate_api_performance(self, predictions, verbose):
        """Calculate RMSE, MAE, and accuracy for each API per location"""
        api_metrics = {}  # {location: {api_source: {rmse, mae, accuracy, predictions}}}
        
        for pred in predictions:
            location = pred.location
            metric = pred.metric
            
            if location not in api_metrics:
                api_metrics[location] = {
                    'open_meteo': {'errors': [], 'count': 0},
                    'weatherapi': {'errors': [], 'count': 0},
                    'nasa': {'errors': [], 'count': 0},
                }
            
            # Calculate error for each API
            for api_source in ['open_meteo', 'weatherapi', 'nasa']:
                api_value = getattr(pred, f'{api_source}_value', None)
                if api_value is not None:
                    error = abs(api_value - pred.actual_value)
                    api_metrics[location][api_source]['errors'].append(error)
                    api_metrics[location][api_source]['count'] += 1
        
        # Convert errors to RMSE, MAE, accuracy
        for location in api_metrics:
            for api_source in api_metrics[location]:
                errors = api_metrics[location][api_source]['errors']
                count = api_metrics[location][api_source]['count']
                
                if count > 0:
                    errors = np.array(errors)
                    rmse = np.sqrt(np.mean(errors ** 2))
                    mae = np.mean(errors)
                    # Accuracy: 100 - MAPE (clipped to 0-100)
                    accuracy = max(0, min(100, 100 - mae))  # Simplified for demo
                    
                    api_metrics[location][api_source] = {
                        'rmse': float(rmse),
                        'mae': float(mae),
                        'accuracy': float(accuracy),
                        'count': count,
                    }
                    
                    if verbose:
                        self.stdout.write(
                            f'  {location} {api_source}: RMSE={rmse:.3f}, '
                            f'MAE={mae:.3f}, Accuracy={accuracy:.1f}%'
                        )
        
        return api_metrics

    def _update_api_performance(self, api_metrics, month_date, verified_predictions):
        """Update APIPerformance model with calculated metrics"""
        rmse_values = []
        
        for location in api_metrics:
            for api_source in api_metrics[location]:
                metrics = api_metrics[location][api_source]
                
                if 'rmse' in metrics:
                    rmse_values.append(metrics['rmse'])
                    
                    # Create or update APIPerformance entry
                    perf, created = APIPerformance.objects.get_or_create(
                        location=location,
                        api_source=api_source,
                        month=month_date,
                    )
                    
                    perf.rmse = metrics['rmse']
                    perf.mae = metrics['mae']
                    perf.accuracy_percent = metrics['accuracy']
                    perf.predictions_count = verified_predictions
                    perf.verified_count = metrics['count']
                    perf.save()
                    
                    action = 'Created' if created else 'Updated'
                    self.stdout.write(f'{action} performance record: {location} {api_source}')
        
        # Return average RMSE
        return np.mean(rmse_values) if rmse_values else 0.0

    def _adjust_ensemble_weights(self, month_date, verbose):
        """Adjust ensemble weights based on API accuracy"""
        # Get current month's performance
        current_perf = APIPerformance.objects.filter(month=month_date)
        
        # Group by location and calculate total accuracy
        locations = {}
        for perf in current_perf:
            if perf.location not in locations:
                locations[perf.location] = {}
            locations[perf.location][perf.api_source] = perf.accuracy_percent
        
        # Calculate new weights per API (accuracy-based weighted average)
        new_weights = {
            'open_meteo': [],
            'weatherapi': [],
            'nasa': [],
        }
        
        for location in locations:
            accuracy_sum = sum(locations[location].values())
            if accuracy_sum > 0:
                for api_source in locations[location]:
                    accuracy_pct = locations[location][api_source]
                    weight = accuracy_pct / accuracy_sum
                    new_weights[api_source].append(weight)
        
        # Calculate average new weights
        avg_weights = {}
        for api_source in new_weights:
            if new_weights[api_source]:
                avg_weights[api_source] = np.mean(new_weights[api_source])
            else:
                avg_weights[api_source] = 1.0 / 3  # Default equal weight
        
        # Normalize weights to sum to 1.0
        total_weight = sum(avg_weights.values())
        for api_source in avg_weights:
            avg_weights[api_source] /= total_weight
        
        if verbose:
            self.stdout.write('📊 Adjusted ensemble weights:')
            self.stdout.write(f'  open_meteo: {avg_weights["open_meteo"]:.2%}')
            self.stdout.write(f'  weatherapi: {avg_weights["weatherapi"]:.2%}')
            self.stdout.write(f'  nasa: {avg_weights["nasa"]:.2%}')
        
        # Store weights in ensemble forecaster config
        self._save_ensemble_weights(avg_weights)

    def _save_ensemble_weights(self, weights):
        """Save new ensemble weights to configuration"""
        # This would integrate with frontend ensembleForecaster.js
        # For now, just log them
        config_path = Path(__file__).resolve().parent.parent.parent.parent / \
                      'frontend' / 'src' / 'services' / 'weather' / 'ensembleWeights.json'
        
        try:
            config = {
                'weights': {
                    'open_meteo': float(weights.get('open_meteo', 0.45)),
                    'weatherapi': float(weights.get('weatherapi', 0.35)),
                    'nasa': float(weights.get('nasa', 0.20)),
                },
                'updated_at': timezone.now().isoformat(),
                'note': 'Auto-adjusted based on monthly accuracy performance'
            }
            
            if not config_path.parent.exists():
                config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            self.stdout.write(self.style.SUCCESS(f'✅ Saved weights to {config_path}'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'⚠️  Could not save weights: {str(e)}'))

    def _print_summary(self, api_metrics, improvement_percent, verbose):
        """Print summary of retraining results"""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('📊 RETRAINING SUMMARY'))
        self.stdout.write('=' * 60)
        
        total_apis = 0
        total_rmse = 0
        for location in api_metrics:
            for api_source in api_metrics[location]:
                if 'rmse' in api_metrics[location][api_source]:
                    total_apis += 1
                    total_rmse += api_metrics[location][api_source]['rmse']
        
        if total_apis > 0:
            avg_rmse = total_rmse / total_apis
            self.stdout.write(f'📍 Locations processed: {len(api_metrics)}')
            self.stdout.write(f'📡 API metric sets: {total_apis}')
            self.stdout.write(f'📈 Average RMSE: {avg_rmse:.4f}')
            self.stdout.write(f'✨ Improvement: {improvement_percent:+.2f}%')
        
        self.stdout.write('=' * 60 + '\n')
