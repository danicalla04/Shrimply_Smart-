from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0036_remove_hardwareteststate')]

    operations = [
        migrations.AddField(model_name='feeder', name='feed_rate_grams_per_minute', field=models.FloatField(default=40.14)),
        migrations.AddField(model_name='feeder', name='daily_portions_grams', field=models.JSONField(blank=True, default=dict)),
    ]
