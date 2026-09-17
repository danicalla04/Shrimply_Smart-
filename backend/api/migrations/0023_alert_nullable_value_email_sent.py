from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0022_sensorreading_nullable_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='alert',
            name='value',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='alert',
            name='threshold_min',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='alert',
            name='threshold_max',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
        migrations.AddField(
            model_name='alert',
            name='email_sent',
            field=models.BooleanField(default=False),
        ),
    ]
