"""FastAPI application for the Employee Leave Management System.

Compared to the original version, this file:
  - Uses the Pydantic schemas for every request body and response
    (instead of accepting raw `dict` and returning ad-hoc dicts).
  - Requires a valid JWT for every endpoint except `/` and `/login`.
  - Enforces role-based access: only managers can view all leave
    requests or approve/reject them; employees can only see their
    own history and can only apply leave for themselves.
  - Validates leave data (dates, reason, status, leave id) and
    returns proper 4xx errors instead of crashing or staying silent.
"""

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_manager,
    verify_password,
)
from database import Base, SessionLocal, engine, get_db
from models import Employee, Leave
from schemas import (
    LeaveCreate,
    LeaveOut,
    LeaveStatusUpdate,
    LoginRequest,
    TokenResponse,
)

app = FastAPI(title="Employee Leave Management API")

Base.metadata.create_all(bind=engine)


def seed_demo_users(db: Session) -> None:
    """Create two demo accounts on first run so the app is usable out of the box.

    Passwords are hashed before being stored, unlike the original version
    which stored them as plain text (e.g. "1234").
    """
    if db.query(Employee).count() > 0:
        return

    db.add_all(
        [
            Employee(
                name="John",
                email="employee@gmail.com",
                password_hash=hash_password("1234"),
                role="employee",
            ),
            Employee(
                name="Manager",
                email="manager@gmail.com",
                password_hash=hash_password("1234"),
                role="manager",
            ),
        ]
    )
    db.commit()


@app.on_event("startup")
def on_startup() -> None:
    db = SessionLocal()
    try:
        seed_demo_users(db)
    finally:
        db.close()


@app.get("/")
def home():
    return {"message": "Leave Management API"}


@app.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate an employee and issue a JWT access token."""
    user = db.query(Employee).filter(Employee.email == credentials.email).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        # Same error for "no such user" and "wrong password" so callers
        # cannot use this endpoint to discover which emails are registered.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(employee_id=user.id, role=user.role)
    return TokenResponse(
        access_token=token, id=user.id, name=user.name, role=user.role
    )


@app.post(
    "/apply_leave",
    response_model=LeaveOut,
    status_code=status.HTTP_201_CREATED,
)
def apply_leave(
    leave_data: LeaveCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Apply for leave.

    `employee_id` is taken from the authenticated user's token, not from
    the request body, so one employee can never apply leave on behalf
    of another. Date order and a non-empty reason are validated by the
    `LeaveCreate` schema before this code even runs.
    """
    leave = Leave(
        employee_id=current_user.id,
        start_date=leave_data.start_date,
        end_date=leave_data.end_date,
        reason=leave_data.reason,
        status="Pending",
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave


@app.get("/leave_history/{employee_id}", response_model=list[LeaveOut])
def leave_history(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """View leave history.

    Employees may only view their own history. Managers may look up
    any employee's history.
    """
    if current_user.role == "employee" and current_user.id != employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employees can only view their own leave history.",
        )

    return db.query(Leave).filter(Leave.employee_id == employee_id).all()


@app.get("/all_leaves", response_model=list[LeaveOut])
def all_leaves(
    db: Session = Depends(get_db),
    _: Employee = Depends(require_manager),
):
    """Manager-only: view every leave request in the system."""
    return db.query(Leave).all()


@app.put("/update_leave/{leave_id}", response_model=LeaveOut)
def update_leave(
    leave_id: int,
    update: LeaveStatusUpdate,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_manager),
):
    """Manager-only: approve or reject a leave request.

    `update.status` is restricted by the `LeaveStatus` enum, so values
    other than Pending/Approved/Rejected are rejected automatically.
    A missing leave id now returns 404 instead of crashing the server.
    """
    leave = db.query(Leave).filter(Leave.id == leave_id).first()

    if leave is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Leave request with id {leave_id} was not found.",
        )

    leave.status = update.status.value
    db.commit()
    db.refresh(leave)
    return leave
