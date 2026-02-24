from django.test import TestCase
from django.urls import reverse
from .models import User, Patient, PatientPreference, Doctor
import json
from datetime import timedelta

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
            "session_length": 30,
        }
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        pref = PatientPreference.objects.get(patient__user_id=self.user)
        self.assertEqual(pref.preferred_time_range, "AFTERNOON")

    def test_preference_api_returns_matches(self):
        """When doctors exist the POST response should include at least one match."""
        # create a sample doctor free on given day
        d = User.objects.create_user(email="doc3@example.com", password="pass", first_name="Doc", last_name="Three", user_type="doctor")
        Doctor.objects.create(user_id=d, specialisation="General", gender="M")

        self.client.login(email=self.email, password=self.password)
        url = reverse('api_patient_preferences')
        data = {
            "preferred_time_range": "AFTERNOON",
            "request_date": "2026-02-25",
            "preferred_specialty": "General",
            "preferred_gender": "any",
            "session_length": 60,
        }
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertIn('matches', payload)
        # at least one match should exist since we just added a doctor with no blocks
        self.assertTrue(len(payload['matches']) >= 1)
        # slot should be populated
        self.assertIsNotNone(payload['matches'][0]['slot']['start'])

    def test_preference_optional_fields(self):
        # specialty only, rest omitted
        self.client.login(email=self.email, password=self.password)
        url = reverse('api_patient_preferences')
        data = {"preferred_specialty": "General", "session_length": 60}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        pref = PatientPreference.objects.get(patient__user_id=self.user)
        self.assertEqual(pref.preferred_specialty, "General")
        self.assertEqual(pref.request_date, None)
        self.assertEqual(pref.preferred_time_range, "")
        self.assertEqual(pref.session_length_minutes, 60)

    def test_create_preference_validation(self):
        self.client.login(email=self.email, password=self.password)
        url = reverse('api_patient_preferences')
        # missing specialty should error
        data = {"preferred_time_range": "MORNING", "request_date": "2026-03-10"}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 400)


class SolverLogicTest(TestCase):
    def setUp(self):
        # create patient and a couple of doctors for ranking
        self.user = User.objects.create_user(
            email="solverpatient@example.com",
            password="secret123",
            first_name="Solver",
            last_name="Patient",
            user_type="patient",
        )
        self.patient = Patient.objects.create(user_id=self.user)
        d1 = User.objects.create_user(email="d1@example.com", password="pass", first_name="Doc", last_name="One", user_type="doctor")
        self.doc1 = Doctor.objects.create(user_id=d1, specialisation="Cardiology", gender="F")
        d2 = User.objects.create_user(email="d2@example.com", password="pass", first_name="Doc", last_name="Two", user_type="doctor")
        self.doc2 = Doctor.objects.create(user_id=d2, specialisation="General", gender="M")

    def test_rank_doctors_by_specialty_and_time(self):
        """Preference should return doctors matching specialty/gender and time.

        With the new hour‑index logic we still expect the ranking helper to
        return a datetime tuple for the slot, so the front‑end can display it.
        """
        from .solver import rank_doctors_for_preference

        from datetime import date
        pref = PatientPreference.objects.create(
            patient=self.patient,
            preferred_specialty="Cardiology",
            preferred_gender="F",
            preferred_time_range="MORNING",
            request_date=date.today(),
            session_length_minutes=60,
        )
        results = rank_doctors_for_preference(pref, limit=5, session_length=timedelta(hours=1))
        self.assertTrue(results)
        doc, slot, pen = results[0]
        self.assertEqual(doc.specialisation, "Cardiology")
        self.assertIsNotNone(slot[0])
        # slot should correspond to a working hour (>=9am)
        self.assertGreaterEqual(slot[0].hour, 9)
        self.assertLess(slot[0].hour, 17)

    def test_hour_index_computation_excludes_blocked(self):
        """When a doctor has a blocked slot their corresponding hour indices are
        removed from availability."""
        from datetime import date, time
        from .solver import get_doctor_available_hour_indices

        block_date = date(2026, 3, 2)
        # block 10‑12 on doc1
        from .models import DoctorBlockedSlot
        DoctorBlockedSlot.objects.create(
            doctor=self.doc1,
            blocked_date=block_date,
            start_time=time(10, 0),
            end_time=time(12, 0),
            reason="blocked",
        )
        idxs = get_doctor_available_hour_indices(self.doc1, block_date)
        # should include 0 (9‑10) but not 1 or 2
        self.assertIn(0, idxs)
        self.assertNotIn(1, idxs)
        self.assertNotIn(2, idxs)
        # other hours remain (3..7)
        for h in range(3, 8):
            self.assertIn(h, idxs)

    def test_slot_window_applies_after_block(self):
        """If a doctor is blocked during preferred window, filtered correctly."""
        from datetime import date, time, timedelta
        from .models import DoctorBlockedSlot
        from .solver import rank_doctors_for_preference

        block_date = date(2026, 3, 2)
        DoctorBlockedSlot.objects.create(
            doctor=self.doc2,
            blocked_date=block_date,
            start_time=time(10, 0),
            end_time=time(12, 0),
            reason="unavailable",
        )
        pref = PatientPreference.objects.create(
            patient=self.patient,
            preferred_specialty="General",
            preferred_gender="any",
            preferred_time_range="MIDDAY",
            request_date=block_date,
            session_length_minutes=60,
        )
        matches = rank_doctors_for_preference(pref, limit=5, session_length=timedelta(hours=1))
        self.assertTrue(matches)
        # ensure first available slot starts at 12 or later
        self.assertGreaterEqual(matches[0][1][0].hour, 12)

    def test_solve_preferences_uses_hour_index(self):
        """The CP-SAT solver should also return a real slot converted from an index."""
        from .solver import solve_preferences
        from datetime import date

        pref = PatientPreference.objects.create(
            patient=self.patient,
            preferred_specialty="Cardiology",
            request_date=date.today(),
            session_length_minutes=60,
        )
        result = solve_preferences(pref, session_length=timedelta(hours=1))
        # if any cardiologist exists we should get a tuple back
        if result is not None:
            doc, slot = result
            self.assertIsInstance(slot[0], datetime)
            self.assertGreaterEqual(slot[0].hour, 9)
            self.assertLess(slot[0].hour, 17)

    def test_past_or_weekend_date_returns_none(self):
        """Preferences on a past date or a weekend should yield no matches."""
        from datetime import date, timedelta
        from .solver import solve_preferences, rank_doctors_for_preference

        yesterday = date.today() - timedelta(days=1)
        pref1 = PatientPreference.objects.create(
            patient=self.patient,
            preferred_specialty="Cardiology",
            request_date=yesterday,
            session_length_minutes=60,
        )
        self.assertIsNone(solve_preferences(pref1))
        self.assertEqual(rank_doctors_for_preference(pref1, limit=10), [])

        # pick a coming Saturday
        saturday = date.today()
        # advance until weekday()==5
        while saturday.weekday() != 5:
            saturday += timedelta(days=1)
        pref2 = PatientPreference.objects.create(
            patient=self.patient,
            preferred_specialty="General",
            request_date=saturday,
            session_length_minutes=60,
        )
        self.assertIsNone(solve_preferences(pref2))
        self.assertEqual(rank_doctors_for_preference(pref2, limit=10), [])

    def test_any_specialty_matches_everyone(self):
        """Selecting "any" should not filter out doctors by field."""
        from datetime import date
        from .solver import rank_doctors_for_preference

        pref = PatientPreference.objects.create(
            patient=self.patient,
            preferred_specialty="any",
            request_date=date.today(),
            session_length_minutes=60,
        )
        results = rank_doctors_for_preference(pref, limit=10, session_length=timedelta(hours=1))
        ob_ids = {r[0].pk for r in results}
        self.assertIn(self.doc1.pk, ob_ids)
        self.assertIn(self.doc2.pk, ob_ids)
