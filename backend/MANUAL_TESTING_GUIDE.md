# Manual Testing Guide - Barber Shop Management System

This guide walks you step-by-step through manually testing all features of the Barber Shop Appointment & Visit Management System using the interactive **Swagger UI** (`/docs`) or **cURL** / **Postman**.

---

## 1. Prerequisites & Starting the Server

### 1.1 Start Database & Backend

Ensure PostgreSQL is running, then start the FastAPI development server:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 1.2 Open Interactive Swagger UI
Open your browser and navigate to:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

*(Alternatively, Redoc is available at `http://localhost:8000/redoc`)*

---

## 2. Authentication & Test Accounts

### Default Seeded Admin Credentials:
| Field | Value |
|---|---|
| **Username** | `admin` |
| **Email** | `admin@barberbooking.com` |
| **Password** | `Admin@123456` |
| **Role** | `ADMIN` |

### How to Authenticate in Swagger UI:
1. Click the green **Authorize 🔓** button at the top right of the Swagger UI page.
2. Under **OAuth2PasswordBearer (OAuth2, password)**:
   - **username**: `admin` (or your user's username/email)
   - **password**: `Admin@123456`
3. Click **Authorize**, then **Close**. Swagger UI will now automatically attach the `Authorization: Bearer <token>` header to all requests.

---

## 3. Step-by-Step Testing Flow

---

### Step 1: Login & Verify Current User (`/api/v1/auth`)

#### Option A: Using the Green "Authorize 🔓" Button (Recommended)
1. Click **Authorize 🔓** at the top right of the Swagger UI.
2. Enter:
   - `username`: `admin`
   - `password`: `Admin@123456`
3. Click **Authorize** $\rightarrow$ **Close**. All subsequent requests are now authenticated.

#### Option B: Using `POST /api/v1/auth/login` directly
1. Go to `POST /api/v1/auth/login`
2. Click **Try it out** and pass the request body:
   ```json
   {
     "username": "admin",
     "password": "Admin@123456"
   }
   ```
   *(You can also use `"username_or_email": "admin"` or `"admin@barberbooking.com"`)*
3. **Expected Status**: `200 OK`
4. **Expected Response**: Returns `access_token`, `token_type: "bearer"`, and user object.

#### Verify Profile:
1. Go to `GET /api/v1/auth/me` $\rightarrow$ **Try it out** $\rightarrow$ **Execute**
2. **Expected Status**: `200 OK`
3. **Expected Response**: Returns profile showing `username: "admin"`, `role: "ADMIN"`.

---

### Step 2: Create Services (`/api/v1/services`)

*(Logged in as Admin)*

1. Go to `POST /api/v1/services/`
2. Create **Standard Haircut**:
   ```json
   {
     "name": "Standard Haircut",
     "description": "Clean fade and trim",
     "duration_minutes": 30,
     "price": 25.00,
     "is_active": true
   }
   ```
   - **Expected Status**: `201 Created`
   - *Note the returned `id` (e.g. `1`)*.

3. Create **Beard Grooming**:
   ```json
   {
     "name": "Beard Grooming",
     "description": "Precision beard trim & hot towel",
     "duration_minutes": 20,
     "price": 15.00,
     "is_active": true
   }
   ```
   - **Expected Status**: `201 Created`
   - *Note the returned `id` (e.g. `2`)*.

4. List all active services via `GET /api/v1/services/`
   - **Expected Status**: `200 OK` (returns array with 2 services).

---

### Step 3: Register a Barber & a Student

#### 3.1 Register Barber (`/api/v1/barbers/`)
*(Logged in as Admin)*
1. Go to `POST /api/v1/barbers/`
   ```json
   {
     "username": "barber_alex",
     "email": "alex@barberbooking.com",
     "password": "BarberPassword@123",
     "first_name": "Alex",
     "last_name": "Miller",
     "phone_number": "+1234567890",
     "bio": "Master barber with 8 years experience",
     "specialties": ["Fade", "Beard Styling"],
     "is_approved": true
   }
   ```
   - **Expected Status**: `201 Created`
   - *Note the returned `id` (e.g. `1`)*.

#### 3.2 Register Student (`/api/v1/students/`)
1. Go to `POST /api/v1/students/`
   ```json
   {
     "username": "student_john",
     "email": "john.doe@university.edu",
     "password": "StudentPassword@123",
     "first_name": "John",
     "last_name": "Doe",
     "phone_number": "+1987654321",
     "student_id_number": "STU-2026-9999",
     "department": "Computer Science",
     "year_of_study": 3
   }
   ```
   - **Expected Status**: `201 Created`
   - *Note the returned `id` (e.g. `1`)*.

---

### Step 4: Configure Barber Working Hours & Breaks (`/api/v1/schedules`)

*(Log in as Barber `barber_alex` or remain as `admin`)*

1. Go to `POST /api/v1/schedules/`
2. Create recurring schedule for Monday through Friday (e.g. Monday = day `0`):
   ```json
   {
     "barber_id": 1,
     "day_of_week": 0,
     "is_working_day": true,
     "start_time": "09:00:00",
     "end_time": "17:00:00",
     "slot_duration_minutes": 15,
     "breaks": [
       {
         "name": "Lunch Break",
         "start_time": "12:00:00",
         "end_time": "13:00:00"
       },
       {
         "name": "Tea Break",
         "start_time": "15:00:00",
         "end_time": "15:15:00"
       }
     ]
   }
   ```
   - **Expected Status**: `201 Created`.

3. Add a Blocked Period (e.g. Barber training / personal time off):
   - Go to `POST /api/v1/schedules/blocked-periods`
   ```json
   {
     "barber_id": 1,
     "reason": "Equipment Maintenance",
     "start_datetime": "2026-09-28T10:00:00Z",
     "end_datetime": "2026-09-28T10:30:00Z"
   }
   ```
   - **Expected Status**: `201 Created`.

---

### Step 5: Test Availability Calculation Engine (`/api/v1/appointments/availability`)

1. Go to `GET /api/v1/appointments/availability`
   - Query Parameters:
     - `barber_id`: `1`
     - `service_id`: `1` (30 min duration)
     - `date`: `2026-09-28` (Monday)
2. Click **Execute**
   - **Expected Status**: `200 OK`
   - **Verify Invariants**:
     - Slots start at `09:00:00` in 15-minute grid increments (`09:00`, `09:15`, `09:30`, `09:45`...).
     - Slots overlapping the blocked period (`10:00 - 10:30`) will NOT be available for booking.
     - Slots overlapping lunch break (`12:00 - 13:00`) will NOT be available (e.g. `11:45` requires 30 mins ending at `12:15`, so it is excluded).

---

### Step 6: Book an Appointment & Verify Invariants (`/api/v1/appointments`)

#### 6.1 Log in as Student
1. Click **Authorize 🔓** $\rightarrow$ **Logout**.
2. Authorize as `student_john` with password `StudentPassword@123`.

#### 6.2 Book a Slot
1. Go to `POST /api/v1/appointments/`
   ```json
   {
     "barber_id": 1,
     "service_id": 1,
     "scheduled_start": "2026-09-28T09:00:00Z",
     "notes": "First time booking"
   }
   ```
2. **Expected Status**: `201 Created`
   - Check response: `status: "CONFIRMED"`, `scheduled_end: "2026-09-28T09:30:00Z"`.
   - *Note the returned `appointment_id` (e.g. `1`)*.

#### 6.3 Verify Double-Booking Prevention (409 Conflict)
1. Re-send the exact same booking request above.
2. **Expected Status**: `409 Conflict`
   - Error message: *"Selected time slot is no longer available."*

---

### Step 7: Check Notifications (`/api/v1/notifications`)

1. Go to `GET /api/v1/notifications/`
   - **Expected Status**: `200 OK`
   - **Verify**: Student received a `APPOINTMENT_CONFIRMED` notification.
2. Log in as Barber `barber_alex` and check `GET /api/v1/notifications/`
   - **Verify**: Barber received an `APPOINTMENT_BOOKED` notification.
3. Test marking as read: `PATCH /api/v1/notifications/{id}/read`
   - **Expected Status**: `200 OK` (`is_read: true`).

---

### Step 8: Visit Execution Lifecycle (`/api/v1/visits`)

*(Logged in as Barber or Admin)*

1. Look up Visit created automatically from the appointment:
   - `GET /api/v1/visits/by-appointment/1`
   - **Expected Status**: `200 OK` (`status: "BOOKED"`).

2. **Student Arrives at Shop**:
   - `POST /api/v1/visits/1/arrive`
   - **Expected Status**: `200 OK` (`status: "ARRIVED"`, `arrival_time` recorded).

3. **Barber Starts Service**:
   - `POST /api/v1/visits/1/start-service`
   - **Expected Status**: `200 OK` (`status: "IN_SERVICE"`, `service_start_time` recorded).

4. **Barber Completes Service**:
   - `POST /api/v1/visits/1/complete`
   - **Expected Status**: `200 OK` (`status: "COMPLETED"`, `service_end_time`, `actual_duration_minutes` recorded).
   - Associated appointment status transitions to `COMPLETED`.

5. **Test Invalid Transition Prevention**:
   - Try calling `POST /api/v1/visits/1/arrive` again on a completed visit.
   - **Expected Status**: `400 Bad Request` (*"Invalid visit status transition"*).

---

### Step 9: Cancellation, No-Show & "Available Now" Slot Claiming

#### 9.1 Test Cancellation Flow
1. Create a second appointment for `2026-09-28T14:00:00Z` (2:00 PM).
2. Student cancels via `POST /api/v1/appointments/{id}/cancel`:
   ```json
   {
     "reason": "Class schedule conflict"
   }
   ```
   - **Expected Status**: `200 OK` (`status: "CANCELLED"`).
3. Check `GET /api/v1/appointments/available-now`:
   - Returns the freed `14:00 - 14:30` slot as instantly claimable.

#### 9.2 Test No-Show Flow & Fixed Appointment Principle
1. Create a third appointment for `2026-09-28T15:30:00Z`.
2. As Barber, mark student as no-show after grace period:
   - `POST /api/v1/appointments/{id}/no-show`
   ```json
   {
     "reason": "Student did not arrive within 10 minutes"
   }
   ```
   - **Expected Status**: `200 OK` (`status: "NO_SHOW"`).
3. **Verify Fixed Appointment Invariant**:
   - Check any downstream appointments (e.g. at 16:30): **Their start times remain completely unchanged.**

---

### Step 10: Admin Management & Operations (`/api/v1/admin`)

*(Logged in as `admin`)*

1. **Dashboard Overview**:
   - `GET /api/v1/admin/dashboard`
   - **Expected Status**: `200 OK` (returns counts of students, barbers, appointments, completed visits, today's metrics).

2. **Inspect System Invariant Rules**:
   - `GET /api/v1/admin/rules`
   - **Expected Status**: `200 OK` (returns cancellation window, grace periods, locking strategy, fixed appointment rules).

3. **Batch Import Students**:
   - `POST /api/v1/admin/students/batch-import`
   ```json
   {
     "students": [
       {
         "username": "student_batch_1",
         "email": "batch1@university.edu",
         "password": "BatchPassword@123",
         "first_name": "Charlie",
         "last_name": "Brown",
         "student_id_number": "STU-2026-1001",
         "department": "Engineering",
         "year_of_study": 2
       },
       {
         "username": "student_batch_2",
         "email": "batch2@university.edu",
         "password": "BatchPassword@123",
         "first_name": "Diana",
         "last_name": "Prince",
         "student_id_number": "STU-2026-1002",
         "department": "Mathematics",
         "year_of_study": 4
       }
     ]
   }
   ```
   - **Expected Status**: `201 Created` (`imported_count: 2`, `failed_count: 0`).

4. **Toggle User Status (Deactivate / Reactivate)**:
   - `PATCH /api/v1/admin/users/{user_id}/status?is_active=false`
   - **Expected Status**: `200 OK` (`is_active: false`).
   - Try logging in with this user $\rightarrow$ returns `403 Forbidden` (*"Account has been deactivated"*).

---

## 4. Quick Summary Checklist

| # | Feature / Invariant | Method & Path | Expected Result |
|---|---|---|---|
| 1 | Database Ping | `GET /api/v1/health/` | `{"status": "ok", "database": "connected"}` |
| 2 | Admin Login | `POST /api/v1/auth/login` | Returns JWT Bearer Token |
| 3 | Create Service | `POST /api/v1/services/` | `201 Created` with duration & price |
| 4 | Register Barber & Student | `POST /api/v1/barbers/`, `POST /api/v1/students/` | `201 Created` with profiles |
| 5 | Working Hours & Breaks | `POST /api/v1/schedules/` | `201 Created` with break validation |
| 6 | Calculate Slots | `GET /api/v1/appointments/availability` | Clean slot list respecting breaks |
| 7 | Atomic Booking | `POST /api/v1/appointments/` | `201 Created` / `409 Conflict` on duplicate |
| 8 | Visit State Machine | `POST /api/v1/visits/{id}/arrive`, `start-service`, `complete` | `BOOKED` $\rightarrow$ `ARRIVED` $\rightarrow$ `IN_SERVICE` $\rightarrow$ `COMPLETED` |
| 9 | Available Now Query | `GET /api/v1/appointments/available-now` | Lists cancelled/no-show slots |
| 10 | Admin Dashboard & Batch Import | `GET /api/v1/admin/dashboard`, `POST /api/v1/admin/students/batch-import` | Aggregated stats & batch creation |

---

## 5. Troubleshooting & Useful Commands

- **Reset / Truncate Database for Fresh Test**:
  ```bash
  ./.venv/bin/pytest tests/conftest.py
  ```
  *(Or re-run alembic migrations / truncate tables)*.

- **Check FastApi Server Logs**:
  Look at the terminal where `uvicorn` is running for detailed SQL queries and HTTP status codes.
