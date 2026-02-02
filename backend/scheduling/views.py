import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import User, Patient, Doctor


@csrf_exempt
def register_api(request):
    """Register a new user (patient or doctor)"""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Extract form data
    email = payload.get("email", "").strip()
    password = payload.get("password", "").strip()
    first_name = payload.get("first_name", "").strip()
    last_name = payload.get("last_name", "").strip()
    user_type = payload.get("user_type", "").strip()
    gender = payload.get("gender", "").strip()
    specialisation = payload.get("specialisation", "").strip()

    # Validation
    if not email or not password or not user_type:
        return JsonResponse(
            {"error": "email, password, and user_type are required"},
            status=400
        )

    if len(password) < 8:
        return JsonResponse({"error": "Password must be at least 8 characters"}, status=400)

    if user_type not in ("patient", "doctor"):
        return JsonResponse(
            {"error": "user_type must be 'patient' or 'doctor'"},
            status=400
        )

    # Check if email already exists
    if User.objects.filter(email=email).exists():
        return JsonResponse({"error": "Email already registered"}, status=400)

    try:
        # Create user using CustomUserManager
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            user_type=user_type
        )

        # Create role-specific record
        if user_type == "patient":
            Patient.objects.create(user_id=user)
        else:  # doctor
            # Normalize gender
            g = "M"  # default
            if gender and gender.lower() in ("f", "female"):
                g = "F"
            
            Doctor.objects.create(
                user_id=user,
                specialisation=specialisation or "General",
                gender=g
            )

        return JsonResponse({
            "ok": True,
            "message": "Registration successful! Please log in.",
            "user_id": user.user_id,
            "email": user.email,
            "user_type": user.user_type
        }, status=201)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
        if user_type == "patient":
            Patient.objects.create(user_id=user)
        elif user_type == "doctor":
            if not gender or not specialisation:
                return JsonResponse({"error": "Gender and specialisation required for doctor"}, status=400)

            # Map frontend gender to DB choices
            gender_db = "M" if gender.lower() == "male" else "F"
            Doctor.objects.create(user_id=user, gender=gender_db, specialisation=specialisation)

        return JsonResponse({"message": "User registered successfully"}, status=201)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
