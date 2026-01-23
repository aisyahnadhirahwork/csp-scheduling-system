from django.urls import path
from .views import doctors_api

urlpatterns = [
    # path("api/appointments/", appointments_api, name="appointments_api"),
    path("api/doctors/", doctors_api, name="doctors_api"),
]
