from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('api', '0035_hardwareoutputstate')]

    operations = [migrations.DeleteModel(name='HardwareTestState')]
