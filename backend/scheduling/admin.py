from django.contrib import admin
# from .models import Patient
from scheduling.models import DoctorFull, DoctorAvailability


# Register your models here.
# admin.site.register(Patient)
admin.site.register(DoctorFull)
admin.site.register(DoctorAvailability)