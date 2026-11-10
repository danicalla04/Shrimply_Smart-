from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0030_remove_simulated_activity')]

    operations = [
        migrations.AlterField(
            model_name='activitylog',
            name='action',
            field=models.CharField(max_length=10, choices=[
                ('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'),
                ('visit', 'Visit'),
            ]),
        ),
    ]
