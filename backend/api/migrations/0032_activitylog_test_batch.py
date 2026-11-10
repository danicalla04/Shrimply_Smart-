from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0031_real_page_visits')]

    operations = [
        migrations.AlterField(
            model_name='activitylog',
            name='action',
            field=models.CharField(max_length=10, choices=[
                ('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'),
                ('visit', 'Visit'), ('read', 'Read'),
            ]),
        ),
        migrations.AddField(
            model_name='activitylog',
            name='test_batch',
            field=models.CharField(max_length=64, blank=True, default='', db_index=True),
        ),
    ]
