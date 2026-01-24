from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ("patient", "Patient"),
        ("doctor", "Doctor"),
        ("admin", "Admin"),
    )

    user_type = models.CharField(
        max_length=10,
        choices=USER_TYPE_CHOICES
    )

# -----------------------------
# Patient for CSP simulation
# -----------------------------
class PatientFull(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    name = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20,
        choices=[
            ("upcoming", "Upcoming"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        null=True,
        blank=True
    )

    preferred_specialty = models.CharField(max_length=100, null=True, blank=True)
    preferred_gender = models.CharField(max_length=10, null=True, blank=True)
    time_start = models.TimeField(null=True, blank=True)
    time_end = models.TimeField(null=True, blank=True)

# -----------------------------
# Doctor for CSP simulation
# -----------------------------
class DoctorFull(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    name = models.CharField(max_length=100)
    specialty = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, null=True, blank=True)


# -----------------------------
# Doctor Availability Table
# -----------------------------
class DoctorAvailability(models.Model):
    doctor = models.ForeignKey(DoctorFull, on_delete=models.CASCADE)
    time = models.TimeField()
    status = models.CharField(
        max_length=20,
        choices=[
            ("available", "Available"),
            ("unavailable", "Unavailable"),
        ],
        default="available"
    )

    def __str__(self):
        return f"{self.doctor.name} at {self.time}"


# -----------------------------
# Appointment Table
# -----------------------------
class Appointment(models.Model):
    patient = models.ForeignKey(PatientFull, on_delete=models.CASCADE)
    doctor = models.ForeignKey(DoctorFull, on_delete=models.CASCADE)
    time = models.TimeField()
    status = models.CharField(
        max_length=20,
        choices=[
            ("upcoming", "Upcoming"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="upcoming"
    )

    def __str__(self):
        return f"{self.patient.name} → {self.doctor.name} at {self.time}"
