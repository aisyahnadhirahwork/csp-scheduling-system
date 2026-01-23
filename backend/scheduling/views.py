from django.shortcuts import render
from django.http import JsonResponse
# from .models import Patient
from .models import DoctorFull, DoctorAvailability

# def appointments_api(request):
#     patients = Patient.objects.all().values("id", "name", "status")
#     return JsonResponse(list(patients), safe=False)

def doctors_api(request):
    doctors = DoctorFull.objects.all()
    data = []

    for d in doctors:
        # get available slots
        slots = DoctorAvailability.objects.filter(doctor=d, status="available")
        slot_times = [s.time.strftime("%H:%M %p") for s in slots]

        data.append({
            "id": d.id,
            "name": d.name,
            "specialty": d.specialty,
            "gender": d.gender,
            "slots": slot_times,
            "status": "available" if slot_times else "unavailable"
        })

    return JsonResponse(data, safe=False)
