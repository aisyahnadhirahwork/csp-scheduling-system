from django.shortcuts import render
from django.http import JsonResponse
from .models import Patient

def appointments_api(request):
    patients = Patient.objects.all().values("id", "name", "status")
    return JsonResponse(list(patients), safe=False)
