from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0025_feedertelemetry_run_times'),
    ]

    operations = [
        migrations.CreateModel(
            name='SensorCalibration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('parameter', models.CharField(choices=[('temperature', 'Temperature'), ('ph', 'pH'), ('turbidity', 'Turbidity'), ('tds', 'TDS')], max_length=20, unique=True)),
                ('scale', models.FloatField(default=1.0)),
                ('offset', models.FloatField(default=0.0)),
                ('unit', models.CharField(blank=True, max_length=10)),
            ],
        ),
    ]
