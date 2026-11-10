from django.db import migrations, models


def remove_simulated_activity(apps, schema_editor):
    ActivityLog = apps.get_model('api', 'ActivityLog')
    ActivityLog.objects.using(schema_editor.connection.alias).filter(is_simulated=True).delete()


class Migration(migrations.Migration):
    dependencies = [('api', '0029_activitylog_simulated_events')]

    operations = [
        migrations.RunPython(remove_simulated_activity, migrations.RunPython.noop),
        migrations.RemoveField(model_name='activitylog', name='is_simulated'),
        migrations.AlterField(
            model_name='activitylog',
            name='action',
            field=models.CharField(max_length=10, choices=[
                ('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'),
            ]),
        ),
    ]
