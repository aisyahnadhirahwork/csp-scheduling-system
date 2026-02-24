from django.urls import path
from . import views

urlpatterns = [
    path('', lambda request: __import__('django.http', fromlist=['HttpResponse']).JsonResponse({'message': 'CSP Scheduling API'})),
    path('api/register/', views.register_api, name='api_register'),
    path('api/login/', views.signin_api, name='api_login'),
    path('api/doctors/', views.get_doctors_api, name='api_doctors'),
    path('api/doctor/blocked-slots/', views.create_blocked_slot, name='create_blocked_slot'),
    path('api/doctor/blocked-slots/list/', views.get_doctor_blocked_slots, name='get_doctor_blocked_slots'),
    path('api/appointments/', views.appointments_api, name='api_appointments'),
    path('api/current-user/', views.current_user_api, name='api_current_user'),
    path('api/patient/preferences/', views.patient_preferences_api, name='api_patient_preferences'),
]
