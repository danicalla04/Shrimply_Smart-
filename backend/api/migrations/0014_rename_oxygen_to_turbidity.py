# Generated migration to rename oxygen field to turbidity in SensorReading model
# and update Threshold model choices for water quality parameter

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0013_add_stocking_density'),
    ]

    operations = [
        migrations.RenameField(
            model_name='sensorreading',
            old_name='oxygen',
            new_name='turbidity',
        ),
        migrations.AlterField(
            model_name='threshold',
            name='parameter',
            field=models.CharField(
                choices=[
                    ('temperature', 'Temperature'),
                    ('ph', 'pH'),
                    ('turbidity', 'Turbidity'),
                    ('tds', 'TDS'),
                ],
                default='temperature',
                max_length=20,
            ),
        ),
    ]
