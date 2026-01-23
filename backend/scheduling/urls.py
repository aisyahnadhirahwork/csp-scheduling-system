from django.urls import path
from .views import appointments_api

urlpatterns = [
    path("api/appointments/", appointments_api, name="appointments_api"),
]
