"""
Management command: Generate fake patients with random preferences,
run the CSP solver for each, create appointments, and print statistics
including detailed penalty calculations.

Usage:
    python manage.py load_test_50
    python manage.py load_test_50 --patients 100
    python manage.py load_test_50 --cleanup       # remove generated test data afterwards
"""

import time as _time
import warnings
from datetime import date, datetime, timedelta

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

# Penalty weights (must match solver.py)
PENALTY_SPECIALTY = 10
PENALTY_GENDER = 5
PENALTY_TIME = 3


def compute_penalty(pref, doctor, slot_start):
    """Calculate the penalty breakdown for a matched appointment.

    Returns (total, specialty_pen, gender_pen, time_pen, details_list).
    """
    spec_pen = 0
    gen_pen = 0
    time_pen = 0
    details = []

    # Specialty penalty
    if pref.preferred_specialty and pref.preferred_specialty.lower() != "any":
        if doctor.specialisation.lower() != pref.preferred_specialty.lower():
            spec_pen = PENALTY_SPECIALTY
            details.append(f"specialty(wanted={pref.preferred_specialty}, got={doctor.specialisation}): +{PENALTY_SPECIALTY}")
        else:
            details.append(f"specialty(exact match): 0")
    else:
        details.append("specialty(any): 0")

    # Gender penalty
    if pref.preferred_gender and pref.preferred_gender != "any":
        if doctor.gender != pref.preferred_gender:
            gen_pen = PENALTY_GENDER
            details.append(f"gender(wanted={pref.preferred_gender}, got={doctor.gender}): +{PENALTY_GENDER}")
        else:
            details.append(f"gender(exact match): 0")
    else:
        details.append("gender(any): 0")

    # Time-range penalty
    hour_idx = slot_start.hour - 9  # 0-based index (9am = 0)
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
            actual_hr = slot_start.strftime("%H:%M")
            details.append(f"time(wanted={pref.preferred_time_range}, got={actual_hr}): +{PENALTY_TIME}")
        else:
            details.append(f"time(in window): 0")
    else:
        details.append("time(any): 0")

    total = spec_pen + gen_pen + time_pen
    return total, spec_pen, gen_pen, time_pen, details


class Command(BaseCommand):
    help = "Generate fake patients with preferences, run solver, and report statistics with penalty calculations"

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
        # Suppress naive-datetime warnings from Django (solver returns naive datetimes)
        warnings.filterwarnings("ignore", category=RuntimeWarning, module="django.db.models.fields")

        num_patients = options["patients"]
        cleanup = options["cleanup"]

        # -- Pre-flight: check doctors exist --
        doctors = list(Doctor.objects.select_related("user_id").all())
        doctor_count = len(doctors)
        if doctor_count == 0:
            self.stderr.write(self.style.ERROR(
                "No doctors in the database. Please create at least one doctor before running this test."
            ))
            return

        self.stdout.write(
            f"\n{'='*70}\n"
            f"  CSP SCHEDULING LOAD TEST\n"
            f"  Patients to generate : {num_patients}\n"
            f"  Doctors available    : {doctor_count}\n"
            f"{'='*70}"
        )

        # Show doctor roster
        self.stdout.write("\n  Doctor Roster:")
        for doc in doctors:
            self.stdout.write(
                f"    - Dr {doc.user_id.first_name} {doc.user_id.last_name}"
                f"  | {doc.specialisation or 'General'}"
                f"  | Gender: {doc.gender}"
            )

        # -- Step 1: Generate fake patients + preferences --
        self.stdout.write(f"\n{'-'*70}")
        self.stdout.write("  STEP 1: Creating fake patients and preferences...\n")

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
            f"  Created {num_patients} patients with preferences."
        ))

        # -- Step 2: Run solver + compute penalties --
        self.stdout.write(f"\n{'-'*70}")
        self.stdout.write("  STEP 2: Running CSP solver with penalty calculation...\n")

        results = []
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

                # Compute penalty breakdown
                total_pen, spec_pen, gen_pen, time_pen, pen_details = compute_penalty(pref, doctor, slot_start)

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

                results.append({
                    "index": idx,
                    "patient": p_name,
                    "doctor": d_name,
                    "slot": f"{slot_start.strftime('%Y-%m-%d %H:%M')} - {slot_end.strftime('%H:%M')}",
                    "success": True,
                    "time": elapsed,
                    "penalty": total_pen,
                    "spec_pen": spec_pen,
                    "gen_pen": gen_pen,
                    "time_pen": time_pen,
                    "pen_details": pen_details,
                    "pref_specialty": pref.preferred_specialty,
                    "pref_gender": pref.preferred_gender,
                    "pref_time": pref.preferred_time_range,
                })
                status_icon = self.style.SUCCESS("MATCHED")
                pen_str = f"penalty={total_pen:2d}" if total_pen > 0 else self.style.SUCCESS("penalty= 0")
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
                    "penalty": None,
                    "spec_pen": 0,
                    "gen_pen": 0,
                    "time_pen": 0,
                    "pen_details": [],
                    "pref_specialty": pref.preferred_specialty,
                    "pref_gender": pref.preferred_gender,
                    "pref_time": pref.preferred_time_range,
                })
                status_icon = self.style.ERROR("FAILED ")
                pen_str = "penalty= -"

            self.stdout.write(
                f"  [{idx:3d}/{num_patients}] {status_icon}  "
                f"{p_name:<22s}  {pen_str}  "
                f"{elapsed*1000:7.1f}ms  "
                f"{results[-1].get('slot') or '-- no slot --'}"
            )

        # -- Step 3: Penalty Detail Table --
        matched = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        self.stdout.write(f"\n{'='*70}")
        self.stdout.write("  PENALTY CALCULATION BREAKDOWN")
        self.stdout.write(f"{'='*70}")
        self.stdout.write(
            f"  {'#':<4s} {'Patient':<20s} {'Doctor':<22s} "
            f"{'Spec':>4s} {'Gen':>4s} {'Time':>4s} {'Total':>5s}  Details"
        )
        self.stdout.write(f"  {'-'*100}")

        for r in matched:
            detail_str = " | ".join(r["pen_details"])
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

        # -- Step 4: Statistics --
        success_rate = len(matched) / num_patients * 100 if num_patients else 0
        avg_time = (sum(solve_times) / len(solve_times)) * 1000 if solve_times else 0
        min_time = min(solve_times) * 1000 if solve_times else 0
        max_time = max(solve_times) * 1000 if solve_times else 0

        penalties = [r["penalty"] for r in matched]
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
        self.stdout.write(f"  Doctors in system         : {doctor_count}")

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

        self.stdout.write(f"\n{'='*70}\n")

        # -- Step 5: Optional cleanup --
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
