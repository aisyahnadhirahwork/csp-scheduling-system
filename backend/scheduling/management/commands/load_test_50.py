"""
Management command: Generate 50 fake patients with random preferences,
run the CSP solver for each, create appointments, and print statistics.

Usage:
    python manage.py load_test_50
    python manage.py load_test_50 --patients 100
    python manage.py load_test_50 --cleanup       # remove generated test data afterwards
"""

import time as _time
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from faker import Faker

from scheduling.models import (
    User, Patient, Doctor, PatientPreference, Appointment,
)
from scheduling.solver import solve_preferences

fake = Faker()

# Choices matching the model definitions
SPECIALTIES = ["general", "cardiology", "pediatrics"]
GENDERS = ["any", "M", "F"]
TIME_RANGES = ["MORNING", "MIDDAY", "AFTERNOON"]
SESSION_LENGTHS = [30, 60]


class Command(BaseCommand):
    help = "Generate fake patients with preferences, run solver, and report statistics"

    def add_arguments(self, parser):
        parser.add_argument(
            "--patients", type=int, default=50,
            help="Number of fake patients to generate (default: 50)",
        )
        parser.add_argument(
            "--cleanup", action="store_true",
            help="Delete all generated test data after reporting",
        )

    def handle(self, *args, **options):
        num_patients = options["patients"]
        cleanup = options["cleanup"]

        # ── Pre-flight: check doctors exist ──
        doctor_count = Doctor.objects.count()
        if doctor_count == 0:
            self.stderr.write(self.style.ERROR(
                "No doctors in the database. Please create at least one doctor before running this test."
            ))
            return

        self.stdout.write(
            f"\n{'='*60}\n"
            f"  CSP LOAD TEST\n"
            f"  Patients to generate : {num_patients}\n"
            f"  Doctors available    : {doctor_count}\n"
            f"{'='*60}\n"
        )

        # ── Step 1: Generate fake patients + preferences ──
        self.stdout.write("Creating fake patients and preferences...")

        created_users = []
        created_patients = []
        created_prefs = []

        # Pick dates: next 5 weekdays starting from tomorrow
        base_date = date.today() + timedelta(days=1)
        target_dates = []
        d = base_date
        while len(target_dates) < 5:
            if d.weekday() < 5:  # Mon-Fri
                target_dates.append(d)
            d += timedelta(days=1)

        for i in range(num_patients):
            # Create user
            first = fake.first_name()
            last = fake.last_name()
            email = f"test_{i}_{fake.unique.random_int(min=1000, max=99999)}@loadtest.local"

            user = User.objects.create_user(
                email=email,
                password="TestPass123!",
                first_name=first,
                last_name=last,
                user_type="patient",
            )
            created_users.append(user)

            patient = Patient.objects.create(user_id=user)
            created_patients.append(patient)

            # Create preference with random choices
            pref = PatientPreference.objects.create(
                patient=patient,
                request_date=fake.random_element(target_dates),
                preferred_time_range=fake.random_element(TIME_RANGES),
                preferred_specialty=fake.random_element(SPECIALTIES),
                preferred_gender=fake.random_element(GENDERS),
                session_length_minutes=fake.random_element(SESSION_LENGTHS),
                status="pending",
            )
            created_prefs.append(pref)

        self.stdout.write(self.style.SUCCESS(
            f"  Created {num_patients} patients with preferences.\n"
        ))

        # ── Step 2: Run solver for each preference and measure time ──
        self.stdout.write("Running CSP solver for each preference...\n")

        results = []  # list of dicts
        total_solve_time = 0.0
        solve_times = []

        for idx, pref in enumerate(created_prefs, start=1):
            session_td = timedelta(minutes=pref.session_length_minutes)

            t_start = _time.perf_counter()
            solution = solve_preferences(pref, session_length=session_td)
            t_end = _time.perf_counter()

            elapsed = t_end - t_start
            total_solve_time += elapsed
            solve_times.append(elapsed)

            patient = pref.patient
            p_name = f"{patient.user_id.first_name} {patient.user_id.last_name}"

            if solution:
                doctor, (slot_start, slot_end) = solution
                d_name = f"Dr {doctor.user_id.first_name} {doctor.user_id.last_name}"

                # Create actual appointment
                Appointment.objects.create(
                    patient=patient,
                    doctor=doctor,
                    preference=pref,
                    slot_start=slot_start,
                    slot_end=slot_end,
                    penalty=0,
                    status="Upcoming",
                )
                pref.status = "accepted"
                pref.save()

                results.append({
                    "index": idx,
                    "patient": p_name,
                    "doctor": d_name,
                    "slot": f"{slot_start.strftime('%Y-%m-%d %H:%M')} - {slot_end.strftime('%H:%M')}",
                    "success": True,
                    "time": elapsed,
                })
                status_icon = self.style.SUCCESS("MATCHED")
            else:
                pref.status = "rejected"
                pref.save()

                results.append({
                    "index": idx,
                    "patient": p_name,
                    "doctor": None,
                    "slot": None,
                    "success": False,
                    "time": elapsed,
                })
                status_icon = self.style.ERROR("FAILED ")

            self.stdout.write(
                f"  [{idx:3d}/{num_patients}] {status_icon}  "
                f"{p_name:<25s}  "
                f"{elapsed*1000:7.1f}ms  "
                f"{results[-1].get('slot') or '-- no slot --'}"
            )

        # ── Step 3: Statistics ──
        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]
        success_rate = len(successes) / num_patients * 100 if num_patients else 0
        avg_time = (sum(solve_times) / len(solve_times)) * 1000 if solve_times else 0
        min_time = min(solve_times) * 1000 if solve_times else 0
        max_time = max(solve_times) * 1000 if solve_times else 0

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("  RESULTS SUMMARY")
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"  Total patients tested     : {num_patients}")
        self.stdout.write(self.style.SUCCESS(
            f"  Successfully allocated    : {len(successes)}"
        ))
        self.stdout.write(self.style.ERROR(
            f"  Failed to get appointment : {len(failures)}"
        ))
        self.stdout.write(f"  Allocation success rate   : {success_rate:.1f}%")
        self.stdout.write(f"  {'─'*40}")
        self.stdout.write(f"  Total solver time         : {total_solve_time*1000:.1f}ms")
        self.stdout.write(f"  Avg matching time         : {avg_time:.1f}ms")
        self.stdout.write(f"  Min matching time         : {min_time:.1f}ms")
        self.stdout.write(f"  Max matching time         : {max_time:.1f}ms")
        self.stdout.write(f"  {'─'*40}")
        self.stdout.write(f"  Doctors in system         : {doctor_count}")

        # Breakdown by date
        self.stdout.write(f"\n  Allocation by requested date:")
        for d in target_dates:
            day_prefs = [r for r, p in zip(results, created_prefs) if p.request_date == d]
            day_ok = sum(1 for r in day_prefs if r["success"])
            day_fail = sum(1 for r in day_prefs if not r["success"])
            self.stdout.write(
                f"    {d.strftime('%a %Y-%m-%d')} : "
                f"{day_ok} matched, {day_fail} failed  "
                f"(of {len(day_prefs)} requests)"
            )

        # Breakdown by specialty
        self.stdout.write(f"\n  Allocation by specialty preference:")
        for spec in SPECIALTIES:
            spec_prefs = [r for r, p in zip(results, created_prefs) if p.preferred_specialty == spec]
            spec_ok = sum(1 for r in spec_prefs if r["success"])
            self.stdout.write(
                f"    {spec:<15s}: {spec_ok}/{len(spec_prefs)} matched"
            )

        # Breakdown by time range
        self.stdout.write(f"\n  Allocation by time preference:")
        for tr in TIME_RANGES:
            tr_prefs = [r for r, p in zip(results, created_prefs) if p.preferred_time_range == tr]
            tr_ok = sum(1 for r in tr_prefs if r["success"])
            self.stdout.write(
                f"    {tr:<15s}: {tr_ok}/{len(tr_prefs)} matched"
            )

        self.stdout.write(f"\n{'='*60}\n")

        # ── Step 4: Optional cleanup ──
        if cleanup:
            self.stdout.write("Cleaning up test data...")
            appt_count = Appointment.objects.filter(patient__in=created_patients).delete()[0]
            pref_count = PatientPreference.objects.filter(patient__in=created_patients).delete()[0]
            pat_count = Patient.objects.filter(pk__in=[p.pk for p in created_patients]).delete()[0]
            user_count = User.objects.filter(pk__in=[u.pk for u in created_users]).delete()[0]
            self.stdout.write(self.style.SUCCESS(
                f"  Removed {appt_count} appointments, {pref_count} preferences, "
                f"{pat_count} patients, {user_count} users."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "  Tip: Run with --cleanup to remove test data afterwards.\n"
                "       python manage.py load_test_50 --cleanup"
            ))
