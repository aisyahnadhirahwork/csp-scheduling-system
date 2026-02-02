import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import User, Patient, Doctor
from django.db.models import Prefetch


@csrf_exempt
def register_api(request):
    """Register a new user (patient or doctor)"""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Extract form data - handle None values properly
    email = (payload.get("email") or "").strip()
    password = (payload.get("password") or "").strip()
    first_name = (payload.get("first_name") or "").strip()
    last_name = (payload.get("last_name") or "").strip()
    user_type = (payload.get("user_type") or "").strip()
    gender = (payload.get("gender") or "").strip()
    specialisation = (payload.get("specialisation") or "").strip()

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


@csrf_exempt
def signin_api(request):
    """Authenticate user and return user_type"""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Extract form data
    email = payload.get("email", "").strip()
    password = payload.get("password", "").strip()

    # Validation
    if not email or not password:
        return JsonResponse(
            {"error": "email and password are required"},
            status=400
        )

    try:
        # Find user by email
        user = User.objects.get(email=email)
        
        # Verify password
        if user.check_password(password):
            return JsonResponse({
                "success": True,
                "user_id": user.user_id,
                "email": user.email,
                "user_type": user.user_type,
                "first_name": user.first_name,
                "last_name": user.last_name
            }, status=200)
        else:
            return JsonResponse({
                "success": False,
                "error": "Invalid email or password"
            }, status=401)
    
    except User.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "Invalid email or password"
        }, status=401)
    
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def get_doctors_api(request):
    """Get all doctors with their details"""
    if request.method != "GET":
        return JsonResponse({"error": "GET only"}, status=405)

    try:
        # Fetch all doctors with related user data
        doctors = Doctor.objects.select_related('user_id').all()
        
        doctors_data = []
        for doctor in doctors:
            user = doctor.user_id
            doctors_data.append({
                "id": doctor.doctor_id,
                "name": f"{user.first_name} {user.last_name}",
                "specialty": doctor.specialisation,
                "gender": doctor.gender,
                "email": user.email,
                "status": "available",  # You can add logic to determine availability later
                "slots": []  # Add appointment slots if needed
            })
        
        return JsonResponse(doctors_data, safe=False, status=200)
    
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
