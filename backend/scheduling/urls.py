from django.urls import path
from .views import doctors_api, register_api, login_api, patient_api, current_user_api

urlpatterns = [
    path("api/doctors/", doctors_api, name="doctors_api"),       # list of doctors
    path("api/register/", register_api, name="register_api"),    # signup
    path("api/login/", login_api, name="login_api"),             # login
    path("api/patient/", patient_api, name="patient_api"),       # list of patients
    path("api/me/", current_user_api, name="current_user_api"),  # current logged-in user info
]
