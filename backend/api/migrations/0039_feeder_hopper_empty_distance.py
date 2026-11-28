from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0038_feeder_rate_recalibration'),
    ]

    operations = [
        migrations.AddField(
            model_name='feeder',
            name='hopper_empty_distance_cm',
            field=models.FloatField(default=43.5),
        ),
    ]
