from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0028_preserve_shared_records_on_account_delete')]

    operations = [
        migrations.AlterField(
            model_name='activitylog',
            name='action',
            field=models.CharField(max_length=10, choices=[
                ('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'),
                ('visit', 'Visit'), ('read', 'Read'), ('auto_feed', 'Auto feed'),
            ]),
        ),
        migrations.AddField(
            model_name='activitylog',
            name='is_simulated',
            field=models.BooleanField(default=False),
        ),
    ]
