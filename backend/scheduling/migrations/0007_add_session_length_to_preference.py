from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0006_add_penalty_to_appointment'),
    ]

    operations = [
        migrations.AddField(
            model_name='patientpreference',
            name='session_length_minutes',
            field=models.IntegerField(default=60, help_text='Length of desired session in minutes'),
        ),
    ]
