from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0034_hardwareteststate')]

    operations = [
        migrations.CreateModel(
            name='HardwareOutputState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('color', models.CharField(default='NONE', max_length=6)),
                ('buzzer_on', models.BooleanField(default=False)),
                ('mode', models.CharField(default='AUTO', max_length=6)),
                ('reported_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
