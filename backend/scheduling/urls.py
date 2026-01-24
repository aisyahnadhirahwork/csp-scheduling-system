from django.urls import path
from .views import doctors_api, register_api, login_api

urlpatterns = [
    # path("api/appointments/", appointments_api, name="appointments_api"),
    path("api/doctors/", doctors_api, name="doctors_api"),
    path("api/register/", register_api),
    path("api/login/", login_api),
]
