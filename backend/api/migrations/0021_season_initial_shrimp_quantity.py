from django.db import migrations, models


def backfill_initial_shrimp_quantity(apps, schema_editor):
    Season = apps.get_model('api', 'Season')
    DailyGrowthMetric = apps.get_model('api', 'DailyGrowthMetric')

    for season in Season.objects.all().iterator():
        initial = 0
        first_metric = (
            DailyGrowthMetric.objects.filter(season_id=season.id)
            .order_by('date', 'id')
            .first()
        )
        if first_metric and first_metric.shrimp_count:
            initial = int(first_metric.shrimp_count)
        elif season.current_shrimp_quantity:
            # Harvest imports historically stored stocking pcs in current_shrimp_quantity
            initial = int(season.current_shrimp_quantity)
        elif season.stocking_density and season.stocking_density > 1000:
            # Older rows sometimes stored piece counts in stocking_density
            initial = int(season.stocking_density)

        if initial and season.initial_shrimp_quantity != initial:
            season.initial_shrimp_quantity = initial
            season.save(update_fields=['initial_shrimp_quantity'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0020_feeder_today_feed_plan'),
    ]

    operations = [
        migrations.AddField(
            model_name='season',
            name='initial_shrimp_quantity',
            field=models.IntegerField(
                default=0,
                help_text='Shrimp pieces stocked at the start of the season',
            ),
        ),
        migrations.AlterField(
            model_name='season',
            name='stocking_density',
            field=models.IntegerField(
                default=0,
                help_text='Stocking density (shrimp per m²)',
            ),
        ),
        migrations.AddField(
            model_name='seasonhistory',
            name='average_shrimp_weight_grams',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='seasonhistory',
            name='current_shrimp_quantity',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='seasonhistory',
            name='initial_shrimp_quantity',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='seasonhistory',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.RunPython(backfill_initial_shrimp_quantity, noop_reverse),
    ]
