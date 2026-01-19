from django.db import models

# Create your models here.
class Doctor(models.Model):
    name = models.CharField(max_length=50)
    specialty = models.CharField(max_length=50)

class Patient(models.Model):
    name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)

class Timeslot(models.Model):
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

class Appointment(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    timeslot = models.ForeignKey(Timeslot, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default='scheduled')