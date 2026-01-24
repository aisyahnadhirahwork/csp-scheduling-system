
import json
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
# from .models import Patient
from .models import DoctorFull, DoctorAvailability, PatientFull, User

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

@csrf_exempt
def register_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        data = json.loads(request.body)

        if User.objects.filter(username=data["email"]).exists():
            return JsonResponse(
                {"error": "User already exists"},
                status=400
            )

        user = User.objects.create_user(
            username=data["email"],
            email=data["email"],
            password=data["password"],
            user_type=data["user_type"],
        )

        if user.user_type == "patient":
            PatientFull.objects.create(
                user=user,
                name=data["name"]
            )

        elif user.user_type == "doctor":
            DoctorFull.objects.create(
                user=user,
                name=data["name"],
                specialty=data.get("specialty", ""),
                gender=data.get("gender", "")
            )

        return JsonResponse({"success": True}, status=201)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def login_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        data = json.loads(request.body)

        user = authenticate(
            username=data["email"],
            password=data["password"]
        )

        if user is None:
            return JsonResponse(
                {"error": "Invalid credentials"},
                status=401
            )

        login(request, user)

        return JsonResponse({
            "success": True,
            "user_type": user.user_type
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
