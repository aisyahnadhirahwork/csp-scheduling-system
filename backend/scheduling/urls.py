from django.urls import path
from . import views

urlpatterns = [
    path('', lambda request: __import__('django.http', fromlist=['HttpResponse']).JsonResponse({'message': 'CSP Scheduling API'})),
    path('api/register/', views.register_api, name='api_register'),
    path('api/login/', views.signin_api, name='api_login'),
    path('api/doctors/', views.get_doctors_api, name='api_doctors'),
]
