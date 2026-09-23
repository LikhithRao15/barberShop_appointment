# Barber Shop Appointment & Visit Management System - Backend

Production-ready backend for the **Barber Shop Appointment & Visit Management System** built with **Python 3.12**, **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.0**, **Alembic**, and **Pydantic v2**.

---

## 1. Architecture & Design Principles

- **Fixed Appointment Principle**: Confirmed appointments are permanently bound to the student at that specific time. Downstream appointments are **never** shifted when earlier slots are cancelled or marked no-show.
- **Deterministic Availability Engine**: Availability is dynamically calculated based on barber working hours, defined breaks, blocked periods, active appointments, and continuous required service duration.
- **Double-Booking & Race Condition Prevention**: Uses database-level row locks (`with_for_update()`) inside atomic transactions to guarantee that only one booking succeeds when multiple users attempt to claim the same slot simultaneously.
- **Separated Visit Tracking**: Decouples appointment reservations (`Appointment`) from the physical in-shop execution (`Visit`), enforcing a strict lifecycle state machine (`BOOKED` -> `ARRIVED` -> `IN_SERVICE` -> `COMPLETED`).
- **Available Now System**: Released slots from cancellations and no-shows become instantly available for fast claiming without disturbing any other bookings.
- **Role-Based Access Control (RBAC)**: Enforced backend security with 3 roles: `STUDENT`, `BARBER`, and `ADMIN`.

---

## 2. Directory Structure

```text
backend/
├── app/
│   ├── main.py                  # FastAPI application entrypoint & lifecycle management
│   ├── config.py                # Environment configuration using pydantic-settings
│   ├── database.py              # SQLAlchemy engine, session maker, Base & get_db dependency
│   ├── models/                  # Declarative SQLAlchemy models
│   │   ├── __init__.py          # Model registry
│   │   ├── user.py              # User authentication & role model
│   │   ├── student.py           # Student profile model
│   │   ├── barber.py            # Barber profile model
│   │   ├── service.py           # Service catalog model (name, duration, price)
│   │   ├── schedule.py          # Working hours, breaks & blocked periods
│   │   ├── appointment.py       # Appointment bookings & state lifecycle
│   │   ├── visit.py             # Physical in-shop visit tracking
│   │   └── notification.py      # Event-driven notification logging
│   ├── schemas/                 # Pydantic request / response validation schemas
│   ├── routers/                 # REST API route handlers
│   │   ├── __init__.py          # Unified API router
│   │   ├── auth.py              # Authentication & user profile endpoints
│   │   ├── students.py          # Student self-service & admin management
│   │   ├── barbers.py           # Barber self-service & catalog
│   │   ├── services.py          # Service catalog management
│   │   ├── schedules.py         # Working hours, breaks & blocked periods
│   │   ├── appointments.py      # Availability calculation, booking, cancel, no-show
│   │   ├── visits.py            # Visit tracking & duration records
│   │   ├── notifications.py     # User notifications & badge counter
│   │   ├── admin.py             # Dashboard metrics, batch import, system rules
│   │   └── health.py            # System & database health checks
│   ├── services/                # Business logic services
│   ├── core/                    # Security, JWT tokens, RBAC dependencies
│   └── utils/                   # Shared utility functions
├── alembic/                     # Database migrations
│   ├── env.py                   # Dynamic migration runner
│   └── versions/                # Versioned migration scripts
├── tests/                       # Pytest automated test suite (37 tests)
│   ├── conftest.py              # Database isolation fixtures
│   ├── test_auth.py             # Authentication & RBAC tests
│   ├── test_phase3.py           # Student, Barber, Service tests
│   ├── test_phase4.py           # Schedules, breaks, blocked periods tests
│   ├── test_phase5.py           # Availability calculation & concurrent booking tests
│   ├── test_phase6.py           # Cancellation, no-show, and Available Now tests
│   ├── test_phase7.py           # Visit tracking & lifecycle progression tests
│   ├── test_phase8.py           # Event-driven notification tests
│   ├── test_phase9.py           # Admin metrics, user status, batch import tests
│   ├── test_e2e_spec_scenarios.py # End-to-end full specification test scenario
│   └── test_health.py           # Health check tests
├── .env                         # Local environment configuration
├── .env.example                 # Configuration template
├── alembic.ini                  # Alembic CLI config
├── requirements.txt             # Locked Python dependencies
└── README.md                    # Documentation
```

---

## 3. Local Setup & Quickstart

### Prerequisites
- Python 3.12+
- PostgreSQL 15+ (Running locally or via Docker)

### Step 1: Create Virtual Environment
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Ensure your `DATABASE_URL` is configured (e.g., `postgresql://username:password@localhost:5432/barber_booking`).

### Step 4: Run Database Migrations
```bash
alembic upgrade head
```

### Step 5: Start the Development Server
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

Default admin credentials seeded on startup:
- **Username / Email**: `admin` / `admin@barberbooking.com`
- **Password**: `Admin@123456`

---

## 4. API Endpoints Reference

### Authentication (`/api/v1/auth`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/auth/login` | Public | Authenticate username/email & password, returns JWT token |
| `GET` | `/auth/me` | Authenticated | Retrieve authenticated user profile |
| `POST` | `/auth/logout` | Authenticated | Stateless session logout |

### Students (`/api/v1/students`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/students/me` | STUDENT | View own student profile |
| `PUT` | `/students/me` | STUDENT | Update own contact/room details |
| `GET` | `/students` | ADMIN | List all students |
| `GET` | `/students/{id}` | ADMIN | Get student details |
| `POST` | `/students` | ADMIN | Onboard student account |
| `PUT` | `/students/{id}` | ADMIN | Update student account |

### Barbers (`/api/v1/barbers`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/barbers` | Public | List active barbers |
| `GET` | `/barbers/{id}` | Public | Get barber profile |
| `GET` | `/barbers/me` | BARBER | View own barber profile |
| `PUT` | `/barbers/me` | BARBER | Update own bio and specialties |
| `POST` | `/barbers` | ADMIN | Register new barber |
| `PUT` | `/barbers/{id}` | ADMIN | Update barber chair & profile |

### Services Catalog (`/api/v1/services`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/services` | Public | List active services (with duration & price) |
| `GET` | `/services/{id}` | Public | Get service details |
| `POST` | `/services` | ADMIN | Create service with duration |
| `PUT` | `/services/{id}` | ADMIN | Update service duration / price |
| `DELETE` | `/services/{id}` | ADMIN | Soft-deactivate service |

### Schedules & Blocked Periods (`/api/v1/schedules`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/schedules/barber/{id}` | Public | Get barber recurring/specific schedules |
| `GET` | `/schedules/barber/{id}/effective-date` | Public | Calculate daily shift, breaks & blocked periods |
| `POST` | `/schedules` | BARBER / ADMIN | Create working shift with breaks |
| `PUT` | `/schedules/{id}` | BARBER / ADMIN | Update shift hours or breaks |
| `DELETE` | `/schedules/{id}` | BARBER / ADMIN | Delete shift |
| `POST` | `/schedules/blocked-periods` | BARBER / ADMIN | Block time period (maintenance / leave) |
| `GET` | `/schedules/blocked-periods` | Public | Query active blocked periods |
| `DELETE` | `/schedules/blocked-periods/{id}` | BARBER / ADMIN | Delete blocked period |

### Appointments & Availability (`/api/v1/appointments`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/appointments/availability` | Public | Calculate available slots matching duration |
| `GET` | `/appointments/available-now` | Public | List released slots eligible for Available Now |
| `POST` | `/appointments/available-now/{id}/claim` | STUDENT / ADMIN | Claim an Available Now released slot |
| `POST` | `/appointments` | STUDENT / ADMIN | Book appointment with concurrency lock |
| `GET` | `/appointments/my` | Authenticated | List own appointments |
| `GET` | `/appointments/{id}` | Authenticated | Get appointment details (ownership checked) |
| `POST` | `/appointments/{id}/cancel` | Authenticated | Cancel appointment (releases slot) |
| `POST` | `/appointments/{id}/no-show` | BARBER / ADMIN | Mark no-show after grace period |
| `POST` | `/appointments/{id}/arrive` | BARBER / ADMIN | Mark student arrival (`BOOKED` -> `ARRIVED`) |
| `POST` | `/appointments/{id}/start` | BARBER / ADMIN | Start haircut (`ARRIVED` -> `IN_SERVICE`) |
| `POST` | `/appointments/{id}/complete` | BARBER / ADMIN | Complete service (`IN_SERVICE` -> `COMPLETED`) |
| `GET` | `/appointments` | ADMIN | List all appointments with filters |

### Physical Visit Tracking (`/api/v1/visits`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/visits/appointment/{id}` | Authenticated | Get detailed visit timings for an appointment |
| `GET` | `/visits/{id}` | Authenticated | Get visit record by ID |
| `GET` | `/visits` | ADMIN | List all in-shop visits |

### Notifications (`/api/v1/notifications`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/notifications` | Authenticated | List user notifications (with unread filter) |
| `GET` | `/notifications/unread-count` | Authenticated | Unread notification counter |
| `PUT` | `/notifications/{id}/read` | Authenticated | Mark notification as read |
| `PUT` | `/notifications/read-all` | Authenticated | Mark all notifications read |
| `DELETE` | `/notifications/{id}` | Authenticated | Delete notification |

### Administration (`/api/v1/admin`)
| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/admin/dashboard/stats` | ADMIN | Aggregate counts & daily visit breakdown |
| `GET` | `/admin/system/rules` | ADMIN | Active scheduling and policy parameters |
| `GET` | `/admin/users` | ADMIN | List all users (filter role / is_active) |
| `POST` | `/admin/users` | ADMIN | Create user account |
| `PUT` | `/admin/users/{id}/status` | ADMIN | Activate / deactivate user account |
| `POST` | `/admin/students/import` | ADMIN | Batch import multiple student accounts |
| `PUT` | `/admin/barbers/{id}/approve` | ADMIN | Approve / toggle barber booking availability |

---

## 5. Running Tests

Run the complete test suite:
```bash
pytest
```
Run with detailed verbosity:
```bash
pytest -v
```
All 37 test cases covering concurrency, RBAC, double-booking prevention, the Fixed Appointment Principle, and full visit lifecycles run against PostgreSQL and pass with 100% success.
