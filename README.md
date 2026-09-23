# 💈 Barber Shop Appointment & Visit Management System

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00.svg?style=flat&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Alembic](https://img.shields.io/badge/Alembic-Migrations-8A2BE2.svg?style=flat)](https://alembic.sqlalchemy.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready, high-concurrency backend for the **Barber Shop Appointment & Visit Management System**. Designed for university campuses and modern barbershops, ensuring strict operational invariants, zero cascading schedule delays, and race-condition-proof booking.

---

## 📌 Key Architectural Invariants

1. **Fixed Appointment Principle**: Confirmed appointments are permanently anchored to their scheduled time slots. Downstream appointments are **never** shifted if an earlier customer cancels or is marked a no-show.
2. **"Available Now" System**: Released slots from cancellations and no-shows become instantly claimable on-demand without disturbing other confirmed bookings.
3. **Deterministic Availability Engine**: Dynamic slot calculation verifying working shifts, breaks, blocked periods, active bookings, and continuous service duration.
4. **Double-Booking & Race-Condition Prevention**: Database-level pessimistic row locking (`SELECT ... FOR UPDATE`) inside atomic transactions prevents concurrent double bookings (`409 Conflict`).
5. **Decoupled Booking vs. Physical Visit Lifecycle**: Strict state machine progression:
   $$\text{BOOKED} \longrightarrow \text{ARRIVED} \longrightarrow \text{IN\_SERVICE} \longrightarrow \text{COMPLETED}$$
6. **Role-Based Access Control (RBAC)**: Secure JWT authentication with 3 explicit roles: `STUDENT`, `BARBER`, and `ADMIN`.

---

## 🏛️ System Architecture

```mermaid
graph TD
    A[Student / Customer] -->|1. Browse & Check Availability| B[FastAPI Backend]
    B -->|2. Dynamic Window Calculation| C[(PostgreSQL 16)]
    A -->|3. Atomic Booking with Row Lock| B
    B -->|4. Create Appointment & Visit Record| C
    B -->|5. Trigger Event Notifications| D[Notification Engine]
    E[Barber] -->|6. Manage Shifts & Execute In-Shop Visits| B
    F[Admin] -->|7. Dashboard Metrics & Account Control| B
```

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | Python 3.12, FastAPI (Async ASGI) |
| **Database & ORM** | PostgreSQL 16, SQLAlchemy 2.0 (Mapped Columns) |
| **Migrations** | Alembic |
| **Data Validation** | Pydantic v2 |
| **Authentication & Security** | JWT (HS256), Native Bcrypt Password Hashing, OAuth2 |
| **Testing** | Pytest, Pytest-Asyncio, HTTPX (37 Automated Tests) |

---

## 📂 Project Structure

```text
Barber_booking/
├── .gitignore
├── README.md                           # Main GitHub Documentation
└── backend/
    ├── MANUAL_TESTING_GUIDE.md         # Step-by-step interactive testing guide
    ├── HOW_THE_SYSTEM_WORKS.md         # Visual architecture & deep-dive explanation
    ├── README.md                       # Backend technical manual
    ├── requirements.txt                # Production dependencies
    ├── alembic.ini                     # Migration configuration
    ├── alembic/                        # Versioned DB schema migrations
    │   └── versions/
    ├── app/
    │   ├── main.py                     # FastAPI entrypoint & lifespan
    │   ├── config.py                   # Pydantic environment settings
    │   ├── database.py                 # SQLAlchemy session pooling
    │   ├── core/                       # Security, JWT & RBAC dependencies
    │   ├── models/                     # SQLAlchemy 2.0 data models
    │   ├── schemas/                    # Pydantic v2 validation schemas
    │   ├── routers/                    # REST API endpoints by domain
    │   ├── services/                   # Core business logic & availability engine
    │   └── utils/                      # Helper utilities
    └── tests/                          # 100% passing test suite (37 tests)
```

---

## 🚀 Step-by-Step Setup Instructions (After Cloning)

Follow these instructions to get the project running locally:

### 1. Prerequisites
Ensure you have the following installed on your machine:
- **Python 3.12+** (`python3 --version` or `python --version`)
- **PostgreSQL 16+** (or **Docker**)
- **Git**

---

### 2. Clone Repository & Enter Directory
```bash
git clone https://github.com/LikhithRao15/barberShop_appointment.git
cd barberShop_appointment/backend
```

---

### 3. Create & Activate a Virtual Environment

- **macOS / Linux**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

- **Windows (PowerShell)**:
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  ```

- **Windows (Command Prompt)**:
  ```cmd
  python -m venv .venv
  .venv\Scripts\activate.bat
  ```

---

### 4. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### 5. Start the PostgreSQL Database

#### Option A: Using Docker (Recommended)
Run PostgreSQL in a container with a single command:
```bash
docker run -d \
  --name barber_postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=barber_booking \
  -p 5432:5432 \
  postgres:16-alpine
```

#### Option B: Using Local PostgreSQL (psql)
```bash
psql -U postgres -c "CREATE DATABASE barber_booking;"
```

---

### 6. Configure Environment Variables (`.env`)

Copy the example configuration file to `.env`:
```bash
cp .env.example .env
```

Verify your `.env` settings (update username/password if using custom credentials):
```env
PROJECT_NAME="Barber Shop Appointment & Visit Management System"
API_V1_PREFIX="/api/v1"
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/barber_booking"
SECRET_KEY="your-super-secret-jwt-key"
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Default Seeded Admin Credentials
ADMIN_USERNAME="admin"
ADMIN_EMAIL="admin@barberbooking.com"
ADMIN_PASSWORD="Admin@123456"

# Business Policy Invariants
CANCELLATION_MINUTES_BEFORE=60
NO_SHOW_GRACE_PERIOD_MINUTES=10
```

---

### 7. Run Database Migrations
Apply all versioned Alembic migrations to set up the database tables:
```bash
alembic upgrade head
```

---

### 8. Run Automated Test Suite
Verify that all 37 unit, concurrency, and integration tests pass:
```bash
pytest -v
```

---

### 9. Start the Development Server
Launch the FastAPI server with live reload:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 📖 Interactive API Documentation

Once the server is running, you can test every endpoint directly in your browser:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### How to Log In via Swagger UI:
1. Open [http://localhost:8000/docs](http://localhost:8000/docs).
2. Click the green **Authorize 🔓** button at the top right.
3. Enter:
   - **Username**: `admin`
   - **Password**: `Admin@123456`
4. Click **Authorize** $\rightarrow$ **Close**. All subsequent requests in Swagger UI will now be authenticated!

---

## 📚 Detailed Guides & References

- 📘 **[Manual Testing Guide (backend/MANUAL_TESTING_GUIDE.md)](backend/MANUAL_TESTING_GUIDE.md)**: Interactive step-by-step instructions for testing every feature and edge case.
- 📐 **[How the System Works (backend/HOW_THE_SYSTEM_WORKS.md)](backend/HOW_THE_SYSTEM_WORKS.md)**: Complete guide with Mermaid sequence diagrams, state machines, ER diagrams, and user journeys.
- ⚙️ **[Backend Technical Manual (backend/README.md)](backend/README.md)**: Detailed API specification and architecture guidelines.

---

## 📄 License
This project is open-source and licensed under the [MIT License](LICENSE).
