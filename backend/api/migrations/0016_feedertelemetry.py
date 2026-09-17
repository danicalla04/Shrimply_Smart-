from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0015_alter_threshold_parameter'),
    ]

    operations = [
        migrations.CreateModel(
            name='FeederTelemetry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('motor_state', models.CharField(blank=True, default='', max_length=10)),
                ('distance_cm', models.FloatField(blank=True, null=True)),
                ('device_id', models.CharField(blank=True, default='', max_length=64)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
    ]
