"""
Management command: Automated evaluation test — 500 patient records, 50 doctors.

Generates all data with Faker, runs the CSP solver, and produces a
comprehensive metrics report suitable for a dissertation evaluation section.

Measured metrics
────────────────
  1. Runtime — total wall-clock, per-request (avg / median / P95 / min / max)
  2. Throughput — requests solved per second
  3. Allocation — success rate, failure rate
  4. Penalty — total, avg, median, max, std dev; breakdown by type
  5. Constraint satisfaction rates — specialty, gender, time-range
  6. Doctor utilisation / load distribution
  7. Slot spread across dates
  8. Breakdowns by specialty, gender preference, time-range preference
  9. CSV export of raw results for external analysis

Usage:
    python manage.py load_test_500
    python manage.py load_test_500 --patients 500 --doctors 50
    python manage.py load_test_500 --cleanup
    python manage.py load_test_500 --csv results.csv
"""

import csv
import math
import os
import statistics
import time as _time
import warnings
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, time

from django.core.management.base import BaseCommand
from django.db import connection, reset_queries
from faker import Faker

from scheduling.models import (
    Appointment,
    Doctor,
    DoctorBlockedSlot,
    Patient,
    PatientPreference,
    User,
)
from scheduling.solver import solve_preferences

fake = Faker()
Faker.seed(42)  # reproducible runs
_run_ts = int(_time.time())  # unique suffix per run

# ── Domain constants (must match solver.py) ──────────────────────────────
SPECIALTIES = ["General", "Cardiology", "Pediatrics", "Dermatology", "Orthopedics"]
DOCTOR_GENDERS = ["M", "F"]
PATIENT_GENDER_PREFS = ["any", "M", "F"]
TIME_RANGES = ["MORNING", "MIDDAY", "AFTERNOON"]
SESSION_LENGTHS = [30, 60]

PENALTY_SPECIALTY = 10
PENALTY_GENDER = 5
PENALTY_TIME = 3


# ── Helpers ──────────────────────────────────────────────────────────────

def _next_n_weekdays(start: date, n: int):
    """Return the next *n* weekdays starting from *start* (inclusive)."""
    days = []
    d = start
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def compute_penalty(pref, doctor, slot_start):
    """Mirror the solver penalty logic and return a detailed breakdown."""
    spec_pen = gen_pen = time_pen = 0
    details = []

    # Specialty
    if pref.preferred_specialty and pref.preferred_specialty.lower() != "any":
        if doctor.specialisation.lower() != pref.preferred_specialty.lower():
            spec_pen = PENALTY_SPECIALTY
            details.append(
                f"specialty(wanted={pref.preferred_specialty}, "
                f"got={doctor.specialisation}): +{PENALTY_SPECIALTY}"
            )
        else:
            details.append("specialty(match): 0")
    else:
        details.append("specialty(any): 0")

    # Gender
    if pref.preferred_gender and pref.preferred_gender != "any":
        if doctor.gender != pref.preferred_gender:
            gen_pen = PENALTY_GENDER
            details.append(
                f"gender(wanted={pref.preferred_gender}, "
                f"got={doctor.gender}): +{PENALTY_GENDER}"
            )
        else:
            details.append("gender(match): 0")
    else:
        details.append("gender(any): 0")

    # Time range
    hour_idx = slot_start.hour - 9
    if pref.preferred_time_range:
        in_window = False
        if pref.preferred_time_range == "MORNING" and hour_idx in (0, 1):
            in_window = True
        elif pref.preferred_time_range == "MIDDAY" and hour_idx in (2, 3):
            in_window = True
        elif pref.preferred_time_range == "AFTERNOON" and hour_idx in (5, 6, 7):
            in_window = True
        if not in_window:
            time_pen = PENALTY_TIME
            details.append(
                f"time(wanted={pref.preferred_time_range}, "
                f"got={slot_start.strftime('%H:%M')}): +{PENALTY_TIME}"
            )
        else:
            details.append("time(in window): 0")
    else:
        details.append("time(any): 0")

    total = spec_pen + gen_pen + time_pen
    return total, spec_pen, gen_pen, time_pen, details


def _percentile(data, p):
    """Simple percentile (nearest-rank) for a sorted list."""
    if not data:
        return 0
    k = int(math.ceil(p / 100.0 * len(data))) - 1
    return data[max(0, min(k, len(data) - 1))]


# ── Command ──────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Generate 50 doctors + 500 fake patients with preferences, "
        "run the CSP solver, and output a full evaluation metrics report."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--patients", type=int, default=500,
            help="Number of fake patients (default 500)",
        )
        parser.add_argument(
            "--doctors", type=int, default=50,
            help="Number of fake doctors to create (default 50)",
        )
        parser.add_argument(
            "--cleanup", action="store_true",
            help="Delete generated test data after the report",
        )
        parser.add_argument(
            "--csv", type=str, default="",
            help="Path to export raw per-request results as CSV",
        )

    # ------------------------------------------------------------------ #
    def handle(self, *args, **options):
        warnings.filterwarnings(
            "ignore", category=RuntimeWarning, module="django.db.models.fields"
        )

        num_patients = options["patients"]
        num_doctors = options["doctors"]
        cleanup = options["cleanup"]
        csv_path = options["csv"]

        # ── 1. Create doctors ────────────────────────────────────────
        created_doc_users = []
        created_doctors = []

        for i in range(num_doctors):
            first = fake.first_name()
            last = fake.last_name()
            email = f"doc_{i}_{_run_ts}_{fake.unique.random_int(1000, 99999)}@loadtest.local"
            gender = fake.random_element(DOCTOR_GENDERS)
            spec = fake.random_element(SPECIALTIES)

            user = User.objects.create_user(
                email=email,
                password="TestPass123!",
                first_name=first,
                last_name=last,
                user_type="doctor",
            )
            created_doc_users.append(user)

            doc = Doctor.objects.create(
                user_id=user,
                specialisation=spec,
                gender=gender,
            )
            created_doctors.append(doc)

        # Add some random blocked slots for realism (≈20 % of doctor-days)
        target_dates = _next_n_weekdays(date.today() + timedelta(days=1), 10)
        blocked_count = 0
        for doc in created_doctors:
            for dt in target_dates:
                if fake.random_int(1, 100) <= 20:
                    start_hour = fake.random_int(9, 14)
                    end_hour = min(start_hour + fake.random_int(1, 2), 17)
                    DoctorBlockedSlot.objects.create(
                        doctor=doc,
                        blocked_date=dt,
                        start_time=time(start_hour, 0),
                        end_time=time(end_hour, 0),
                        reason=fake.random_element(["unavailable", "off_duty"]),
                    )
                    blocked_count += 1

        # ── Header (same template as load_test_50) ───────────────────
        self.stdout.write(
            f"\n{'='*70}\n"
            f"  CSP SCHEDULING LOAD TEST\n"
            f"  Patients to generate : {num_patients}\n"
            f"  Doctors available    : {num_doctors}\n"
            f"{'='*70}"
        )

        # Show doctor roster
        self.stdout.write("\n  Doctor Roster:")
        for doc in created_doctors:
            self.stdout.write(
                f"    - Dr {doc.user_id.first_name} {doc.user_id.last_name}"
                f"  | {doc.specialisation or 'General'}"
                f"  | Gender: {doc.gender}"
            )

        # ── 2. Create patients + preferences ─────────────────────────
        self.stdout.write(f"\n{'-'*70}")
        self.stdout.write("  STEP 1: Creating fake patients and preferences...\n")

        created_pat_users = []
        created_patients = []
        created_prefs = []

        for i in range(num_patients):
            first = fake.first_name()
            last = fake.last_name()
            email = f"pat_{i}_{_run_ts}_{fake.unique.random_int(1000, 99999)}@loadtest.local"

            user = User.objects.create_user(
                email=email,
                password="TestPass123!",
                first_name=first,
                last_name=last,
                user_type="patient",
            )
            created_pat_users.append(user)

            patient = Patient.objects.create(user_id=user)
            created_patients.append(patient)

            pref = PatientPreference.objects.create(
                patient=patient,
                request_date=fake.random_element(target_dates),
                preferred_time_range=fake.random_element(TIME_RANGES),
                preferred_specialty=fake.random_element(SPECIALTIES),
                preferred_gender=fake.random_element(PATIENT_GENDER_PREFS),
                session_length_minutes=fake.random_element(SESSION_LENGTHS),
                status="pending",
            )
            created_prefs.append(pref)

        self.stdout.write(self.style.SUCCESS(
            f"  Created {num_patients} patients with preferences."
        ))

        # ── 3. Run solver ────────────────────────────────────────────
        self.stdout.write(f"\n{'-'*70}")
        self.stdout.write("  STEP 2: Running CSP solver with penalty calculation...\n")

        results = []
        solve_times = []
        db_query_counts = []

        overall_start = _time.perf_counter()

        for idx, pref in enumerate(created_prefs, start=1):
            session_td = timedelta(minutes=pref.session_length_minutes)

            # Track DB queries per solve
            reset_queries()
            t0 = _time.perf_counter()
            solution = solve_preferences(pref, session_length=session_td)
            t1 = _time.perf_counter()
            db_query_counts.append(len(connection.queries))

            elapsed = t1 - t0
            solve_times.append(elapsed)

            patient = pref.patient
            p_name = f"{patient.user_id.first_name} {patient.user_id.last_name}"

            if solution:
                doctor, (slot_start, slot_end) = solution
                d_name = (
                    f"Dr {doctor.user_id.first_name} {doctor.user_id.last_name}"
                )
                total_pen, spec_pen, gen_pen, time_pen, pen_details = compute_penalty(
                    pref, doctor, slot_start
                )

                Appointment.objects.create(
                    patient=patient,
                    doctor=doctor,
                    preference=pref,
                    slot_start=slot_start,
                    slot_end=slot_end,
                    penalty=total_pen,
                    status="Upcoming",
                )
                pref.status = "accepted"
                pref.save()

                # Constraint satisfaction flags
                spec_satisfied = (
                    not pref.preferred_specialty
                    or pref.preferred_specialty.lower() == "any"
                    or doctor.specialisation.lower() == pref.preferred_specialty.lower()
                )
                gender_satisfied = (
                    not pref.preferred_gender
                    or pref.preferred_gender == "any"
                    or doctor.gender == pref.preferred_gender
                )
                hour_idx = slot_start.hour - 9
                time_satisfied = True
                if pref.preferred_time_range:
                    if pref.preferred_time_range == "MORNING":
                        time_satisfied = hour_idx in (0, 1)
                    elif pref.preferred_time_range == "MIDDAY":
                        time_satisfied = hour_idx in (2, 3)
                    elif pref.preferred_time_range == "AFTERNOON":
                        time_satisfied = hour_idx in (5, 6, 7)

                results.append({
                    "index": idx,
                    "patient": p_name,
                    "doctor": d_name,
                    "doctor_id": doctor.doctor_id,
                    "slot_start": slot_start.strftime("%Y-%m-%d %H:%M"),
                    "slot_end": slot_end.strftime("%Y-%m-%d %H:%M"),
                    "success": True,
                    "time_s": elapsed,
                    "penalty": total_pen,
                    "spec_pen": spec_pen,
                    "gen_pen": gen_pen,
                    "time_pen": time_pen,
                    "pen_details": " | ".join(pen_details),
                    "pref_specialty": pref.preferred_specialty,
                    "pref_gender": pref.preferred_gender,
                    "pref_time": pref.preferred_time_range,
                    "pref_date": str(pref.request_date),
                    "spec_satisfied": spec_satisfied,
                    "gender_satisfied": gender_satisfied,
                    "time_satisfied": time_satisfied,
                    "date_shifted": str(pref.request_date) != slot_start.strftime("%Y-%m-%d"),
                    "db_queries": db_query_counts[-1],
                })
                tag = self.style.SUCCESS("MATCHED")
            else:
                pref.status = "rejected"
                pref.save()

                results.append({
                    "index": idx,
                    "patient": p_name,
                    "doctor": None,
                    "doctor_id": None,
                    "slot_start": None,
                    "slot_end": None,
                    "success": False,
                    "time_s": elapsed,
                    "penalty": None,
                    "spec_pen": 0,
                    "gen_pen": 0,
                    "time_pen": 0,
                    "pen_details": "",
                    "pref_specialty": pref.preferred_specialty,
                    "pref_gender": pref.preferred_gender,
                    "pref_time": pref.preferred_time_range,
                    "pref_date": str(pref.request_date),
                    "spec_satisfied": False,
                    "gender_satisfied": False,
                    "time_satisfied": False,
                    "date_shifted": False,
                    "db_queries": db_query_counts[-1],
                })
                tag = self.style.ERROR("FAILED ")

            # Print every patient line (same format as load_test_50)
            r = results[-1]
            if r["success"]:
                pen_val = r["penalty"]
                pen_str = f"penalty={pen_val:2d}" if pen_val > 0 else self.style.SUCCESS("penalty= 0")
                slot_str = f"{r['slot_start'].split(' ')[0]} {r['slot_start'].split(' ')[1]} - {r['slot_end'].split(' ')[1]}" if r['slot_start'] else "-- no slot --"
            else:
                pen_str = "penalty= -"
                slot_str = "-- no slot --"

            self.stdout.write(
                f"  [{idx:3d}/{num_patients}] {tag}  "
                f"{p_name:<22s}  {pen_str}  "
                f"{elapsed*1000:7.1f}ms  "
                f"{slot_str}"
            )

        overall_end = _time.perf_counter()
        total_wall_time = overall_end - overall_start

        # ── 4. Metrics (load_test_50 template) ──────────────────────
        matched = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        penalties = [r["penalty"] for r in matched]
        total_solve_time = sum(solve_times)

        # -- Penalty Detail Table --
        self.stdout.write(f"\n{'='*70}")
        self.stdout.write("  PENALTY CALCULATION BREAKDOWN")
        self.stdout.write(f"{'='*70}")
        self.stdout.write(
            f"  {'#':<4s} {'Patient':<20s} {'Doctor':<22s} "
            f"{'Spec':>4s} {'Gen':>4s} {'Time':>4s} {'Total':>5s}  Details"
        )
        self.stdout.write(f"  {'-'*100}")

        for r in matched:
            detail_str = r["pen_details"]
            total_pen = r["penalty"]
            if total_pen == 0:
                pen_display = self.style.SUCCESS(f"{total_pen:5d}")
            elif total_pen <= 5:
                pen_display = self.style.WARNING(f"{total_pen:5d}")
            else:
                pen_display = self.style.ERROR(f"{total_pen:5d}")
            self.stdout.write(
                f"  {r['index']:<4d} {r['patient']:<20s} {r['doctor']:<22s} "
                f"{r['spec_pen']:4d} {r['gen_pen']:4d} {r['time_pen']:4d} {pen_display}  {detail_str}"
            )

        if failed:
            self.stdout.write(f"\n  Failed allocations:")
            for r in failed:
                self.stdout.write(self.style.ERROR(
                    f"  {r['index']:<4d} {r['patient']:<20s} "
                    f"Wanted: {r['pref_specialty']}, {r['pref_gender']}, {r['pref_time']}"
                ))

        # -- Results Summary --
        success_rate = len(matched) / num_patients * 100 if num_patients else 0
        avg_time = (total_solve_time / len(solve_times)) * 1000 if solve_times else 0
        min_time = min(solve_times) * 1000 if solve_times else 0
        max_time = max(solve_times) * 1000 if solve_times else 0

        avg_penalty = sum(penalties) / len(penalties) if penalties else 0
        zero_pen = sum(1 for p in penalties if p == 0)
        nonzero_pen = sum(1 for p in penalties if p > 0)
        total_spec_pen = sum(r["spec_pen"] for r in matched)
        total_gen_pen = sum(r["gen_pen"] for r in matched)
        total_time_pen = sum(r["time_pen"] for r in matched)

        self.stdout.write(f"\n{'='*70}")
        self.stdout.write("  RESULTS SUMMARY")
        self.stdout.write(f"{'='*70}")
        self.stdout.write(f"  Total patients tested     : {num_patients}")
        self.stdout.write(self.style.SUCCESS(
            f"  Successfully allocated    : {len(matched)}"
        ))
        self.stdout.write(self.style.ERROR(
            f"  Failed to get appointment : {len(failed)}"
        ))
        self.stdout.write(f"  Allocation success rate   : {success_rate:.1f}%")

        self.stdout.write(f"\n  {'-'*50}")
        self.stdout.write("  PENALTY STATISTICS")
        self.stdout.write(f"  {'-'*50}")
        self.stdout.write(f"  Perfect matches (pen=0)   : {zero_pen}")
        self.stdout.write(f"  Imperfect matches (pen>0) : {nonzero_pen}")
        self.stdout.write(f"  Avg penalty per match     : {avg_penalty:.2f}")
        self.stdout.write(f"  Max penalty               : {max(penalties) if penalties else 0}")
        self.stdout.write(f"  Total penalty (all)       : {sum(penalties)}")
        self.stdout.write(f"    - Specialty mismatches  : {total_spec_pen}  ({sum(1 for r in matched if r['spec_pen'] > 0)} patients)")
        self.stdout.write(f"    - Gender mismatches     : {total_gen_pen}  ({sum(1 for r in matched if r['gen_pen'] > 0)} patients)")
        self.stdout.write(f"    - Time-range mismatches : {total_time_pen}  ({sum(1 for r in matched if r['time_pen'] > 0)} patients)")

        self.stdout.write(f"\n  {'-'*50}")
        self.stdout.write("  SOLVER PERFORMANCE")
        self.stdout.write(f"  {'-'*50}")
        self.stdout.write(f"  Total solver time         : {total_solve_time*1000:.1f}ms")
        self.stdout.write(f"  Avg matching time         : {avg_time:.1f}ms")
        self.stdout.write(f"  Min matching time         : {min_time:.1f}ms")
        self.stdout.write(f"  Max matching time         : {max_time:.1f}ms")
        self.stdout.write(f"  Doctors in system         : {num_doctors}")

        # Breakdown by date
        self.stdout.write(f"\n  {'-'*50}")
        self.stdout.write("  BREAKDOWN BY DATE")
        self.stdout.write(f"  {'-'*50}")
        for dt in target_dates:
            day_results = [r for r, p in zip(results, created_prefs) if p.request_date == dt]
            day_ok = sum(1 for r in day_results if r["success"])
            day_fail = sum(1 for r in day_results if not r["success"])
            day_pens = [r["penalty"] for r in day_results if r["success"]]
            day_avg = sum(day_pens) / len(day_pens) if day_pens else 0
            self.stdout.write(
                f"    {dt.strftime('%a %Y-%m-%d')} : "
                f"{day_ok} matched, {day_fail} failed  "
                f"(of {len(day_results)})  avg_penalty={day_avg:.1f}"
            )

        # Breakdown by specialty
        self.stdout.write(f"\n  {'-'*50}")
        self.stdout.write("  BREAKDOWN BY SPECIALTY")
        self.stdout.write(f"  {'-'*50}")
        for spec in SPECIALTIES:
            spec_results = [r for r, p in zip(results, created_prefs) if p.preferred_specialty == spec]
            spec_ok = sum(1 for r in spec_results if r["success"])
            spec_pens = [r["penalty"] for r in spec_results if r["success"]]
            spec_avg = sum(spec_pens) / len(spec_pens) if spec_pens else 0
            self.stdout.write(
                f"    {spec:<15s}: {spec_ok}/{len(spec_results)} matched  avg_penalty={spec_avg:.1f}"
            )

        # Breakdown by time range
        self.stdout.write(f"\n  {'-'*50}")
        self.stdout.write("  BREAKDOWN BY TIME PREFERENCE")
        self.stdout.write(f"  {'-'*50}")
        for tr in TIME_RANGES:
            tr_results = [r for r, p in zip(results, created_prefs) if p.preferred_time_range == tr]
            tr_ok = sum(1 for r in tr_results if r["success"])
            tr_pens = [r["penalty"] for r in tr_results if r["success"]]
            tr_avg = sum(tr_pens) / len(tr_pens) if tr_pens else 0
            self.stdout.write(
                f"    {tr:<15s}: {tr_ok}/{len(tr_results)} matched  avg_penalty={tr_avg:.1f}"
            )

        self.stdout.write(f"\n{'='*70}")
        self.stdout.write(
            "  Tip: Run with --cleanup to remove test data afterwards.\n"
            "       python manage.py load_test_500 --cleanup"
        )

        # ── 5. CSV export ────────────────────────────────────────────
        if csv_path:
            fieldnames = [
                "index", "patient", "doctor", "doctor_id",
                "slot_start", "slot_end", "success",
                "time_s", "penalty", "spec_pen", "gen_pen", "time_pen",
                "pen_details",
                "pref_specialty", "pref_gender", "pref_time", "pref_date",
                "spec_satisfied", "gender_satisfied", "time_satisfied",
                "date_shifted", "db_queries",
            ]
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)
            self.stdout.write(self.style.SUCCESS(f"  Exported {len(results)} rows → {csv_path}"))

        # ── 6. Cleanup ───────────────────────────────────────────────
        if cleanup:
            # Delete appointments created during the test
            Appointment.objects.filter(
                patient__in=created_patients
            ).delete()
            PatientPreference.objects.filter(
                patient__in=created_patients
            ).delete()
            Patient.objects.filter(
                pk__in=[p.pk for p in created_patients]
            ).delete()
            DoctorBlockedSlot.objects.filter(
                doctor__in=created_doctors
            ).delete()
            Doctor.objects.filter(
                pk__in=[d.pk for d in created_doctors]
            ).delete()
            User.objects.filter(
                pk__in=[u.pk for u in created_doc_users + created_pat_users]
            ).delete()
            self.stdout.write(self.style.SUCCESS("  All test data removed."))

