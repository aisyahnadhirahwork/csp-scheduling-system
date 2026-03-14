from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0007_add_session_length_to_preference'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='reschedule_count',
            field=models.IntegerField(default=0, help_text='Number of times this appointment has been rescheduled'),
        ),
        migrations.AddField(
            model_name='appointment',
            name='preference',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='scheduling.patientpreference',
            ),
        ),
    ]
