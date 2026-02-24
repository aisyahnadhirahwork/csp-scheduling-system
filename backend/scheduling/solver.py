"""Constraint solver helpers for the scheduling app.

This module contains the OR-Tools CP-SAT model and accompanying utility
functions. It's placed in the ``scheduling`` app so it has direct access to the
models (Doctor, PatientPreference, etc.) and can be imported wherever the
solver is needed (views, management commands, tests, etc.).

You could alternatively put the implementation under ``scheduling/utils`` or
create a dedicated management command that imports from here; the important
point is to keep the code inside the Django app (not in the frontend).
"""

from datetime import datetime, time, timedelta
from ortools.sat.python import cp_model

from django.db.models import Q

from .models import Doctor, DoctorBlockedSlot, PatientPreference


def get_doctor_available_slots(doctor, date, session_length=timedelta(hours=1)):
    """(legacy) compute datetime-based slots for the solver.

    The newer ``get_doctor_available_hour_indices`` helper below is
    preferred when you only care about simple hourly indices, but some older
    code in this module still uses the datetime tuples, so we keep it around.
    """
    # fall back to index helper and convert back to datetimes
    indices = get_doctor_available_hour_indices(doctor, date)
    if not indices:
        return []
    result = []
    for idx in indices:
        start = datetime.combine(date, time(9 + idx, 0))
        end = start + session_length
        result.append((start, end))
    return result


def get_doctor_available_hour_indices(doctor, date):
    """Return a list of hour indexes (0 == 09:00–10:00) when the doctor is free.

    - Weeksends return an empty list.
    - Hours outside 09:00‑17:00 are never considered.
    - Any blocked slot overlapping an hour removes that index entirely.

    This function ignores ``session_length``; callers should slice the returned
    indexes if they need contiguous blocks longer than one hour.
    """
    if date.weekday() >= 5:  # Saturday=5, Sunday=6
        return []

    # full range: eight one‑hour slots from 9‑10 up to 16‑17
    indices = list(range(8))
    for blk in DoctorBlockedSlot.objects.filter(doctor=doctor, blocked_date=date):
        # convert block to fractional hours since 9am
        blk_start = blk.start_time.hour + blk.start_time.minute / 60.0
        blk_end = blk.end_time.hour + blk.end_time.minute / 60.0
        # loop over a copy because we may remove elements
        for idx in list(indices):
            slot_start = 9 + idx
            slot_end = slot_start + 1
            # if the one‑hour slot overlaps the blocked interval, drop it
            if not (slot_end <= blk_start or slot_start >= blk_end):
                indices.remove(idx)
    return indices


def solve_preferences(pref: PatientPreference, session_length=timedelta(hours=1), max_search_days=7):
    """Given a PatientPreference instance, return a matching doctor/slot.

    Search begins on ``pref.request_date`` and if no suitable slot exists that
    day it advances one weekday at a time (skipping weekends) up to
    ``max_search_days`` into the future.  The returned slot will always
    respect the requested time window and specialty/gender preferences; only
    the date may shift.

    Other behaviour is unchanged from the previous implementation (hour-idx
    availability, CP-SAT model, penalties).  ``session_length`` is expressed
    as a ``timedelta``.

    Returns ``(doctor, start_datetime, end_datetime)`` or ``None`` if no
    match was found in the search window.
    """

    def _try_date(search_date):
        """Attempt to build and solve a model for a given calendar date."""
        # early reject weekends and past days
        today = datetime.now().date()
        if not search_date or search_date < today or search_date.weekday() >= 5:
            return None

        # build candidate set once per run (specialty/gender unaffected by date)
        if pref.preferred_specialty and pref.preferred_specialty.lower() != "any":
            desired_spec = pref.preferred_specialty
            candidates = Doctor.objects.filter(
                Q(specialisation__iexact=desired_spec)
                | Q(specialisation__iexact="General")
                | Q(specialisation__exact="")
            )
        else:
            candidates = Doctor.objects.all()

        # availability by hour index
        availability = {}
        for doc in candidates:
            availability[doc.doctor_id] = get_doctor_available_hour_indices(doc, search_date)

        # apply time-window filter
        def pref_index_window():
            if not pref.preferred_time_range:
                return None
            if pref.preferred_time_range == "MORNING":
                return (0, 2)
            if pref.preferred_time_range == "MIDDAY":
                return (2, 4)
            if pref.preferred_time_range == "AFTERNOON":
                return (5, 8)
            return None

        window = pref_index_window()
        if window:
            wstart, wend = window
            for doc_id, idxs in list(availability.items()):
                availability[doc_id] = [i for i in idxs if i >= wstart and i < wend]

        # build and solve model (same as previous code)
        model = cp_model.CpModel()
        x = {}
        for doc_id, idxs in availability.items():
            for idx in idxs:
                x[(doc_id, idx)] = model.NewBoolVar(f"x_d{doc_id}_hour{idx}")
        if x:
            model.Add(sum(x.values()) == 1)
        else:
            return None

        if pref.preferred_gender and pref.preferred_gender != "any":
            for doc in candidates:
                if doc.gender != pref.preferred_gender:
                    for key in list(x):
                        if key[0] == doc.doctor_id:
                            model.Add(x[key] == 0)

        # penalties
        penalties = []
        for doc in candidates:
            for idx in availability[doc.doctor_id]:
                var = x[(doc.doctor_id, idx)]
                pen = model.NewIntVar(0, 100, f"pen_{doc.pk}_{idx}")
                components = []

                spec_pen = model.NewIntVar(0, 20, f"spec_pen_{doc.pk}_{idx}")
                if pref.preferred_specialty and pref.preferred_specialty.lower() != "any" and doc.specialisation != pref.preferred_specialty:
                    model.Add(spec_pen == 10).OnlyEnforceIf(var)
                else:
                    model.Add(spec_pen == 0).OnlyEnforceIf(var)
                components.append(spec_pen)

                if pref.preferred_gender and pref.preferred_gender != "any":
                    gen_pen = model.NewIntVar(0, 5, f"gen_pen_{doc.pk}_{idx}")
                    if doc.gender == pref.preferred_gender:
                        model.Add(gen_pen == 0).OnlyEnforceIf(var)
                    else:
                        model.Add(gen_pen == 5).OnlyEnforceIf(var)
                    components.append(gen_pen)

                if pref.preferred_time_range and pref.preferred_time_range != "":
                    time_pen = model.NewIntVar(0, 5, f"time_pen_{doc.pk}_{idx}")
                    if pref.preferred_time_range == "MORNING":
                        time_pen_val = 0 if idx in (0, 1) else 3
                    elif pref.preferred_time_range == "MIDDAY":
                        time_pen_val = 0 if idx in (2, 3) else 3
                    elif pref.preferred_time_range == "AFTERNOON":
                        time_pen_val = 0 if idx in (5, 6, 7) else 3
                    else:
                        time_pen_val = 0
                    model.Add(time_pen == time_pen_val).OnlyEnforceIf(var)
                    components.append(time_pen)

                if components:
                    model.Add(pen == sum(components)).OnlyEnforceIf(var)
                else:
                    model.Add(pen == 0).OnlyEnforceIf(var)
                penalties.append(pen)
        model.Minimize(sum(penalties))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 2
        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for (doc_id, idx), var in x.items():
                if solver.Value(var) == 1:
                    selected_doc = Doctor.objects.get(pk=doc_id)
                    start = datetime.combine(search_date, time(9 + idx, 0))
                    end = start + session_length
                    return selected_doc, (start, end)
        return None

    # main routine: iterate day-by-day starting from requested date
    start_date = pref.request_date or datetime.now().date()
    for offset in range(0, max_search_days + 1):
        candidate_date = start_date + timedelta(days=offset)
        result = _try_date(candidate_date)
        if result:
            return result
    return None


# ---------------------------------------------------------------------------
# ranking helper for front-end display
# ---------------------------------------------------------------------------

def rank_doctors_for_preference(pref: PatientPreference, limit=None, session_length=timedelta(hours=1), max_search_days=7):
    """Lightweight ranking for UI display.

    Works similarly to ``solve_preferences`` but scores each candidate slot
    rather than solving a CP-SAT model.  If no slots are available on the
    requested date the function will look ahead up to ``max_search_days`` and
    return results on the first future day where something exists.  The
    returned tuples are ``(doctor, (start,end), penalty)`` where ``start`` may
    be ``None`` if no date was specified at all.
    """

    def compute_for_date(search_date):
        # build candidate pool
        if pref.preferred_specialty and pref.preferred_specialty.lower() != "any":
            desired_spec = pref.preferred_specialty
            docs = Doctor.objects.filter(
                Q(specialisation__iexact=desired_spec)
                | Q(specialisation__iexact="General")
                | Q(specialisation__exact="")
            )
        else:
            docs = Doctor.objects.all()
        availability = {}
        for doc in docs:
            availability[doc.doctor_id] = get_doctor_available_hour_indices(doc, search_date) if search_date else []

        def pref_index_window():
            if not pref.preferred_time_range or not search_date:
                return None
            if pref.preferred_time_range == "MORNING":
                return (0, 2)
            if pref.preferred_time_range == "MIDDAY":
                return (2, 4)
            if pref.preferred_time_range == "AFTERNOON":
                return (5, 8)
            return None

        window = pref_index_window()
        if window:
            wstart, wend = window
            for doc_id, idxs in list(availability.items()):
                availability[doc_id] = [i for i in idxs if i >= wstart and i < wend]

        res = []
        for doc in docs:
            for idx in availability[doc.doctor_id]:
                start = datetime.combine(search_date, time(9 + idx, 0)) if search_date else None
                end = start + session_length if start else None
                pen = 0
                if pref.preferred_specialty and pref.preferred_specialty.lower() != "any" and doc.specialisation.lower() != pref.preferred_specialty.lower():
                    pen += 10
                if pref.preferred_gender and pref.preferred_gender != "any" and doc.gender != pref.preferred_gender:
                    pen += 5
                if pref.preferred_time_range and pref.preferred_time_range != "":
                    if pref.preferred_time_range == "MORNING" and idx >= 2:
                        pen += 3
                    elif pref.preferred_time_range == "MIDDAY" and idx not in (2, 3):
                        pen += 3
                    elif pref.preferred_time_range == "AFTERNOON" and idx < 5:
                        pen += 3
                res.append((doc, (start, end), pen))
        return res, docs

    start_date = pref.request_date or datetime.now().date()
    for offset in range(0, max_search_days + 1):
        candidate_date = start_date + timedelta(days=offset)
        # skip weekends
        if candidate_date.weekday() >= 5:
            continue
        results, candidates = compute_for_date(candidate_date)
        if results:
            results.sort(key=lambda trip: trip[2])
            return results[:limit] if limit else results
    return []
