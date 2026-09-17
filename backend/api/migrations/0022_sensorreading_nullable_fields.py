from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0021_season_initial_shrimp_quantity'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sensorreading',
            name='temperature',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='sensorreading',
            name='ph',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='sensorreading',
            name='turbidity',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='sensorreading',
            name='tds',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
