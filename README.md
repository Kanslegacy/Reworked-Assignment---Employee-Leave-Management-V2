# Employee Leave Management — v2

A FastAPI + Streamlit + SQLite app for applying, viewing, and approving employee
leave requests, with authentication and authorization.

This is a revised version of the original submission. The table below maps
each piece of grading feedback to the specific fix.

| Feedback | Fix |
|---|---|
| Code formatting is very poor; one-line files | Every file rewritten with normal line breaks, docstrings, and consistent style. |
| Passwords stored as plain text | Passwords are hashed with `bcrypt` before being stored (`auth.py`, see `hash_password` / `verify_password`). The database now stores a `password_hash` column, never the raw password. |
| Pydantic schemas created but not used | Every endpoint now declares a `request body` schema and a `response_model` from `schemas.py` (e.g. `LoginRequest`, `LeaveCreate`, `LeaveOut`, `TokenResponse`). |
| No JWT/session authentication | `/login` issues a signed JWT (`auth.py: create_access_token`). All endpoints except `/` and `/login` require `Authorization: Bearer <token>` via the `get_current_user` dependency. |
| No role-based protection | `require_manager` dependency blocks `/all_leaves` and `/update_leave/{id}` for non-managers (403). `/leave_history/{employee_id}` blocks employees from viewing anyone else's history. `/apply_leave` always uses the logged-in user's own id — it's no longer accepted from the request body. |
| No validation for dates / reason / status / leave id | `LeaveCreate` schema rejects `end_date < start_date` and blank/too-short reasons (422). `status` is restricted to a `LeaveStatus` enum (`Pending`/`Approved`/`Rejected`), so anything else is rejected automatically. Updating a leave id that doesn't exist returns 404 instead of crashing. |
| requirements.txt full of unrelated packages | Trimmed to exactly what the app imports: fastapi, uvicorn, sqlalchemy, pydantic, bcrypt, python-jose, streamlit, requests, pandas, plotly. |

## Project structure

```
employee_leave_management/
├── main.py        # FastAPI app and routes
├── auth.py        # Password hashing + JWT creation/verification + role checks
├── database.py    # SQLAlchemy engine/session
├── models.py       # ORM models: Employee, Leave
├── schemas.py      # Pydantic request/response schemas
├── app.py          # Streamlit frontend
└── requirements.txt
```

## Running it

```bash
cd employee_leave_management
pip install -r requirements.txt

# Terminal 1 — backend
uvicorn main:app --reload --port 8001

# Terminal 2 — frontend
streamlit run app.py
```

The backend creates `leave_management.db` and seeds two demo accounts the
first time it starts:

| Role | Email | Password |
|---|---|---|
| Employee | employee@gmail.com | 1234 |
| Manager | manager@gmail.com | 1234 |

(These are demo credentials only — in a real deployment you'd remove the
seeding step and enforce a strong-password policy.)

## API overview

| Method | Path | Auth required | Notes |
|---|---|---|---|
| GET | `/` | none | health check |
| POST | `/login` | none | returns a JWT + user info |
| POST | `/apply_leave` | any logged-in employee | creates a leave for **yourself**; validates dates and reason |
| GET | `/leave_history/{employee_id}` | logged-in | employees can only request their own id; managers can request any |
| GET | `/all_leaves` | manager only | |
| PUT | `/update_leave/{leave_id}` | manager only | body: `{"status": "Approved"}`; 404 if the leave id doesn't exist |

## What's intentionally still simple

For a Week-1 assignment, a few things are left simple on purpose rather than
gold-plated — happy to extend any of these if you want to push further:

- JWTs are not refreshed or revocable (no refresh-token flow or logout
  blacklist) — they just expire after 60 minutes.
- The `SECRET_KEY` defaults to a hardcoded value if `JWT_SECRET_KEY` isn't
  set in the environment — fine for local grading, not for production.
- There's no leave-balance tracking (e.g. "12 days per year") — it only
  tracks individual requests and their status.
