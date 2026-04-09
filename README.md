# Constraint-Based Medical Appointment Scheduling System

A final-year dissertation project for **BSc (Hons) Computer Science** at Heriot-Watt University, supervised by Dr. Muhammad Najib.

This is a web-based appointment scheduling system that treats doctor–patient booking as a **Constraint Satisfaction Problem (CSP)**. Instead of assigning patients to the first available slot, the system uses Google OR-Tools' **CP-SAT solver** to find the best possible match — respecting hard constraints like doctor availability and specialty, while optimising soft preferences like preferred gender, time of day, and date.

---

## What It Does

- Patients submit their preferences (specialty, gender, time window, session length, preferred date)
- The solver finds the top-matching doctors and time slots, ranked by how closely they fit
- Appointments are confirmed, and the schedule updates in real time
- Doctors can block out time periods, and overlapping bookings get cancelled automatically
- Patients can cancel or reschedule (once per appointment), with conflict checking built in

The system handles edge cases too — if no slots are available on the requested date, it slides forward up to 7 weekdays to find the nearest match. If no specialist is available, a General practitioner is offered as a fallback (with a penalty score so the patient knows it's not a perfect fit).

---

## How It Works

The scheduling engine has two modes:

1. **Ranking helper** — a lightweight loop that scores every available doctor-slot combination and returns the top 5 options for the patient to browse. Fast enough for real-time previews.
2. **CP-SAT solver** — the full constraint model, used when the patient confirms a booking. It builds a set of yes/no decision variables (one per doctor-slot pair), enforces hard constraints, minimises a penalty objective, and returns the optimal assignment.

### Penalty system

Not every preference can always be met. Rather than rejecting imperfect matches, the solver assigns penalties:

| Factor              | Condition                                          | Penalty |
|---------------------|----------------------------------------------------|---------|
| Specialty mismatch  | Wanted a specialist but matched with General       | +10     |
| Gender mismatch     | Doctor's gender differs from preference             | +5      |
| Time mismatch       | Slot falls outside preferred time window            | +3      |

A penalty of 0 means a perfect match. The solver always picks the assignment with the lowest total penalty.

---

## Tech Stack

### Backend
- **Python 3.10** + **Django 5.2** + **Django REST Framework**
- **Google OR-Tools** (CP-SAT solver) for constraint-based scheduling
- **PostgreSQL** via psycopg2
- **Faker** for synthetic test data generation

### Frontend
- **Alpine.js** for interactivity (lightweight, no build-step framework)
- **Tailwind CSS** for styling (utility-first, responsive)
- **Webpack 5** for bundling and dev server
- Admin template based on [TailAdmin](https://github.com/cruip/tailwind-dashboard-template) (GPL licensed)

---

## Project Structure

```
csp-scheduling-system/
├── backend/
│   ├── csp_scheduler/          # Django project settings
│   ├── scheduling/
│   │   ├── models.py           # User, Patient, Doctor, Appointment, etc.
│   │   ├── solver.py           # CP-SAT solver + ranking helper
│   │   ├── views.py            # REST API endpoints
│   │   ├── urls.py             # API routing
│   │   └── management/commands/
│   │       ├── seed_csp.py     # Seed database with test data
│   │       ├── load_test_50.py # 50-patient load test
│   │       └── load_test_500.py# 500-patient load test
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── index.html          # Patient dashboard
│   │   ├── doctor-schedule.html# Doctor schedule management
│   │   ├── auth.html           # Login / Registration
│   │   ├── js/
│   │   │   └── appointment.js  # Booking logic (Alpine.js)
│   │   ├── css/style.css
│   │   └── partials/           # Reusable HTML components
│   ├── package.json
│   └── webpack.config.js
├── data/                       # Data files
├── docs/                       # Documentation
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL

### 1. Clone the repository

```bash
git clone https://github.com/your-username/csp-scheduling-system.git
cd csp-scheduling-system
```

### 2. Set up the backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # On Windows
# source venv/bin/activate   # On macOS/Linux

pip install -r requirements.txt
```

Create a PostgreSQL database and update `csp_scheduler/settings.py` with your database credentials, then run:

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 3. Seed test data (optional)

```bash
python manage.py seed_csp
```

This generates synthetic doctors and patients using Faker.

### 4. Start the backend server

```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000`.

### 5. Set up the frontend

```bash
cd ../frontend
npm install
npm start
```

The frontend will open at `http://localhost:3000` and proxy API requests to the backend.

---

## API Endpoints

| Endpoint | Method | What it does |
|----------|--------|-------------|
| `/api/register` | POST | Create a new patient or doctor account |
| `/api/login` | POST | Log in and start a session |
| `/api/current-user` | GET | Get the logged-in user's profile |
| `/api/doctors/` | GET | List all registered doctors |
| `/api/doctor/blocked-slots/` | POST | Block out a time period (auto-cancels conflicts) |
| `/api/doctor/blocked-slots/list/` | GET | View blocked slots |
| `/api/patient/preferences/` | POST | Submit preferences and get top 5 matches |
| `/api/patient/preferences/` | GET | View preference history |
| `/api/appointments/` | GET | View appointments (role-filtered) |
| `/api/appointments/` | POST | Confirm a booking |
| `/api/appointments/<id>/cancel/` | POST | Cancel an appointment |
| `/api/appointments/<id>/status/` | PATCH | Mark as completed or cancelled (doctor) |
| `/api/appointments/<id>/reschedule/search/` | GET | Find alternative slots |
| `/api/appointments/<id>/reschedule/confirm/` | POST | Confirm a reschedule |

---

## Running the Load Tests

The project includes management commands to benchmark the solver:

```bash
# 50 patients, 5 doctors
python manage.py load_test_50

# 500 patients, 50 doctors
python manage.py load_test_500
```

Results from the 500-patient test:
- **100% allocation rate** — every patient got an appointment
- **93.4% perfect matches** (penalty = 0)
- **84.9 ms** average solve time per patient
- All 33 imperfect matches were specialty fallbacks (Pediatrics → General)

---

## Database Models

| Model | Purpose |
|-------|---------|
| `User` | Email-based auth with role (patient/doctor) |
| `Patient` | Links to User; patient identity in the system |
| `Doctor` | Links to User; stores specialty and gender |
| `PatientPreference` | Stores what the patient is looking for |
| `Appointment` | Confirmed booking with doctor, time slot, penalty score |
| `DoctorBlockedSlot` | Time periods when a doctor is unavailable |

Double-booking is prevented at both the application level (solver checks) and the database level (unique constraint). Blocked slots with invalid time ranges (end before start) are also rejected by the database.

---

## Acknowledgements

- **Supervisor:** Dr. Muhammad Najib, Heriot-Watt University
- **Admin template:** [TailAdmin](https://github.com/cruip/tailwind-dashboard-template) — used under GPL licence for the dashboard UI
- **OR-Tools:** [Google OR-Tools](https://developers.google.com/optimization) — open-source optimisation library

---

## Licence

This project was developed as part of a university dissertation and is intended for academic purposes. The frontend admin template is licensed under GPL — see the [frontend/LICENSE](frontend/LICENSE) file for details.
