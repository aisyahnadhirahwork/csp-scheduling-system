
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0003_patientpreference'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patientpreference',
            name='request_date',
            field=models.DateField(null=True, blank=True),
        ),
    ]
