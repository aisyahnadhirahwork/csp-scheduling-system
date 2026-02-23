from django.test import TestCase
from django.urls import reverse
from .models import User, Patient, PatientPreference
import json


class PatientPreferenceAPITest(TestCase):
    def setUp(self):
        # create a patient user and associated Patient record
        self.email = "patient@example.com"
        self.password = "secret123"
        self.user = User.objects.create_user(
            email=self.email,
            password=self.password,
            first_name="Test",
            last_name="Patient",
            user_type="patient",
        )
        Patient.objects.create(user_id=self.user)

    def test_create_preference_requires_auth(self):
        url = reverse('api_patient_preferences')
        data = {
            "preferred_time_range": "MORNING",
            "request_date": "2026-03-10",
        }
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_create_preference_success(self):
        self.client.login(email=self.email, password=self.password)
        url = reverse('api_patient_preferences')
        data = {
            "preferred_time_range": "AFTERNOON",
            "request_date": "2026-04-01",
            "preferred_specialty": "Cardiology",
            "preferred_gender": "F",
        }
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        pref = PatientPreference.objects.get(patient__user_id=self.user)
        self.assertEqual(pref.preferred_time_range, "AFTERNOON")

    def test_preference_optional_fields(self):
        # specialty only, rest omitted
        self.client.login(email=self.email, password=self.password)
        url = reverse('api_patient_preferences')
        data = {"preferred_specialty": "General"}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        pref = PatientPreference.objects.get(patient__user_id=self.user)
        self.assertEqual(pref.preferred_specialty, "General")
        self.assertEqual(pref.request_date, None)
        self.assertEqual(pref.preferred_time_range, "")

    def test_create_preference_validation(self):
        self.client.login(email=self.email, password=self.password)
        url = reverse('api_patient_preferences')
        # missing specialty should error
        data = {"preferred_time_range": "MORNING", "request_date": "2026-03-10"}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 400)
