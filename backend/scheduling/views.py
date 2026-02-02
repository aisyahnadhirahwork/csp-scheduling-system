import json
from django.shortcuts import render
from django.contrib.auth import authenticate, login
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import DoctorFull, DoctorAvailability, PatientFull, User

# ==========================
# DOCTORS API
# ==========================
def doctors_api(request):
    doctors = DoctorFull.objects.all()
    data = []

    for d in doctors:
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


# ==========================
# PATIENT API
# ==========================
def patient_api(request):
    patients = PatientFull.objects.all().values(
        "id", "name", "status", "preferred_specialty"
    )
    return JsonResponse(list(patients), safe=False)


# ==========================
# REGISTER API
# ==========================
@csrf_exempt
def register_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        data = json.loads(request.body)

        # Check if email already exists
        if User.objects.filter(username=data["email"]).exists():
            return JsonResponse({"error": "User already exists"}, status=400)

        # Create User
        user = User.objects.create_user(
            username=data["email"],
            email=data["email"],
            password=data["password"],
            user_type=data["user_type"],
            first_name=data.get("first_name", data["name"])
        )

        # Create linked profile
        if user.user_type == "patient":
            PatientFull.objects.create(
                user=user,
                name=data["name"],
                preferred_specialty=data.get("preferred_specialty", "")
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

# ==========================
# LOGIN API
# ==========================
@csrf_exempt
def login_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        data = json.loads(request.body)
        user = authenticate(username=data["email"], password=data["password"])

        if user is None:
            return JsonResponse({"error": "Invalid credentials"}, status=401)

        # Login the user (session)
        login(request, user)

        # Pull name from linked profile
        first_name = ""
        if user.user_type == "patient" and hasattr(user, "patientfull"):
            first_name = user.patientfull.name
        elif user.user_type == "doctor" and hasattr(user, "doctorfull"):
            first_name = user.doctorfull.name

        return JsonResponse({
            "success": True,
            "user_type": user.user_type,
            "username": user.username,   # email
            "email": user.email,
            "first_name": first_name
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ==========================
# CURRENT USER / SESSION API
# ==========================
@login_required
def current_user_api(request):
    user = request.user
    first_name = ""
    if user.user_type == "patient" and hasattr(user, "patientfull"):
        first_name = user.patientfull.name
    elif user.user_type == "doctor" and hasattr(user, "doctorfull"):
        first_name = user.doctorfull.name

    return JsonResponse({
        "username": user.username,
        "email": user.email,
        "user_type": user.user_type,
        "first_name": first_name
    })
