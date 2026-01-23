from django.core.management.base import BaseCommand
from scheduling.models import PatientFull, DoctorFull, DoctorAvailability

class Command(BaseCommand):
    help = 'Seed initial CSP data for development'

    def handle(self, *args, **kwargs):
        # Doctors
        d1 = DoctorFull.objects.create(name="Dr Aisyah", specialty="Cardiology", gender="Female")
        d2 = DoctorFull.objects.create(name="Dr Amir", specialty="Neurology", gender="Male")

        # Patients
        p1 = PatientFull.objects.create(
            name="Patient 1",
            preferred_specialty="Cardiology",
            preferred_gender="Female",
            time_start="09:00",
            time_end="11:00"
        )
        p2 = PatientFull.objects.create(
            name="Patient 2",
            preferred_specialty="Neurology",
            preferred_gender="Male",
            time_start="10:00",
            time_end="12:00"
        )

        # Doctor Availability
        DoctorAvailability.objects.create(doctor=d1, time="09:00", status="available")
        DoctorAvailability.objects.create(doctor=d2, time="10:00", status="available")

        self.stdout.write(self.style.SUCCESS('CSP seed data created successfully'))
