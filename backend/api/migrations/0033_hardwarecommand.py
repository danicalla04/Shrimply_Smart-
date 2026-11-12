from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0032_activitylog_test_batch'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HardwareCommand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('target', models.CharField(choices=[
                    ('LED1', 'LED1'), ('LED2', 'LED2'), ('LED3', 'LED3'),
                    ('BUZZER', 'BUZZER'), ('ALL', 'ALL'),
                ], max_length=10)),
                ('state', models.BooleanField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('requested_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['id']},
        ),
    ]
