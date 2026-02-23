import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import User, Patient, Doctor, DoctorBlockedSlot, PatientPreference
from django.shortcuts import redirect
from django.db.models import Prefetch
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login


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
            login(request, user)  # <-- THIS MAKES request.user AUTHENTICATED
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
    
@csrf_exempt
def create_blocked_slot(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    
    try:
        data = json.loads(request.body)
    except Exception as e:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    
    # Get doctor from authenticated user or from doctor_id
    if request.user.is_authenticated:
        try:
            doctor = Doctor.objects.get(user_id=request.user)
        except Doctor.DoesNotExist:
            return JsonResponse({"error": "User is not a doctor"}, status=403)
    else:
        doctor_id = data.get("doctor_id")
        if not doctor_id:
            return JsonResponse({"error": "No doctor_id provided"}, status=400)
        try:
            doctor = Doctor.objects.get(doctor_id=doctor_id)
        except Doctor.DoesNotExist:
            return JsonResponse({"error": "Doctor not found"}, status=404)
    
    try:
        DoctorBlockedSlot.objects.create(
            doctor=doctor,
            blocked_date=data["date"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            reason=data["reason"],
        )
        return JsonResponse({"message": "Blocked slot created"}, status=201)
    except KeyError as e:
        return JsonResponse({"error": f"Missing field: {str(e)}"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def current_user_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated"}, status=401)
    
    user = request.user
    doctor_id = None
    
    try:
        doctor = Doctor.objects.get(user_id=user)
        doctor_id = doctor.doctor_id
    except Doctor.DoesNotExist:
        pass
    
    return JsonResponse({
        "id": user.user_id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "user_type": user.user_type,
        "doctor_id": doctor_id,
    })


# ---------------------------------------------------------------------------
# patient preference endpoints
# ---------------------------------------------------------------------------

@csrf_exempt
def patient_preferences_api(request):
    """Create/list patient preferences.

    POST: save a new request (used by front‑end form).
    GET: return all preferences for the logged‑in patient (unused for now).
    """
    if not request.user.is_authenticated or request.user.user_type != "patient":
        return JsonResponse({"error": "Authentication required as patient"}, status=401)

    try:
        patient = Patient.objects.get(user_id=request.user)
    except Patient.DoesNotExist:
        return JsonResponse({"error": "Patient record not found"}, status=404)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # pull fields with sensible defaults
        pref_specialty = (data.get("preferred_specialty") or "").strip() or None
        pref_gender = (data.get("preferred_gender") or "any").strip() or "any"
        pref_time = (data.get("preferred_time_range") or "").strip()
        if pref_time == "any":
            pref_time = ""
        req_date = data.get("request_date") or None

        # basic validation: specialty is mandatory
        if not pref_specialty:
            return JsonResponse({"error": "preferred_specialty is required"}, status=400)

        try:
            pref = PatientPreference.objects.create(
                patient=patient,
                request_date=req_date,
                preferred_time_range=pref_time,
                preferred_specialty=pref_specialty,
                preferred_gender=pref_gender,
            )
            return JsonResponse({"message": "Preference saved", "preference_id": pref.preference_id}, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    elif request.method == "GET":
        prefs = PatientPreference.objects.filter(patient=patient).order_by("-created_at")
        out = []
        for p in prefs:
            out.append({
                "id": p.preference_id,
                "request_date": p.request_date.isoformat(),
                "preferred_time_range": p.preferred_time_range,
                "preferred_specialty": p.preferred_specialty,
                "preferred_gender": p.preferred_gender,
                "status": p.status,
                "created_at": p.created_at.isoformat(),
            })
        return JsonResponse(out, safe=False)

    else:
        return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def get_doctor_blocked_slots(request):
    """Get blocked slots for the logged-in doctor"""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated"}, status=401)
    
    try:
        doctor = Doctor.objects.get(user_id=request.user)
    except Doctor.DoesNotExist:
        return JsonResponse({"error": "User is not a doctor"}, status=403)
    
    blocked_slots = DoctorBlockedSlot.objects.filter(
        doctor=doctor
    ).order_by('-blocked_date')
    
    slots_data = []
    for slot in blocked_slots:
        slots_data.append({
            "id": slot.blocked_id,
            "date": slot.blocked_date.isoformat(),
            "start_time": str(slot.start_time),
            "end_time": str(slot.end_time),
            "reason": slot.reason,
        })
    
    return JsonResponse(slots_data, safe=False, status=200)
