from django.db import migrations, models


OLD_RATE = 40.14
NEW_RATE = 1207.5


def recalibrate_existing_feeders(apps, schema_editor):
    Feeder = apps.get_model('api', 'Feeder')
    Feeder.objects.using(schema_editor.connection.alias).filter(feed_rate_grams_per_minute=OLD_RATE).update(feed_rate_grams_per_minute=NEW_RATE)

    # The optional servo queue is managed with raw SQL. Cancel jobs calculated
    # using the old rate so the poller can recreate them with the new rate.
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        columns = {column.name for column in connection.introspection.get_table_description(cursor, 'api_feedertelemetry')}
        if {'schedule_status', 'calibration_grams_30s'}.issubset(columns):
            cursor.execute(
                '''UPDATE api_feedertelemetry
                   SET schedule_status = %s
                   WHERE schedule_status = %s
                     AND calibration_grams_30s BETWEEN %s AND %s''',
                ['cancelled', 'scheduled', OLD_RATE / 2 - 0.0001, OLD_RATE / 2 + 0.0001],
            )


class Migration(migrations.Migration):
    dependencies = [('api', '0037_feeder_rate_and_daily_portions')]

    operations = [
        migrations.AlterField(
            model_name='feeder',
            name='feed_rate_grams_per_minute',
            field=models.FloatField(default=NEW_RATE),
        ),
        migrations.RunPython(recalibrate_existing_feeders, migrations.RunPython.noop),
    ]
