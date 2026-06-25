"""Password hashing and JWT authentication helpers.

This module fixes three issues from the original submission:
  1. Passwords are hashed with bcrypt instead of stored as plain text.
  2. Every protected endpoint requires a valid JWT (no more open APIs).
  3. A `require_manager` dependency enforces role-based access control.
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
from models import Employee

# In production, set JWT_SECRET_KEY as an environment variable rather than
# relying on this default value.
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret-key-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password for storage using bcrypt."""
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a plain-text password against its stored bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(employee_id: int, role: str) -> str:
    """Create a signed JWT that encodes the employee's id and role."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(employee_id), "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Employee:
    """Decode the JWT from the Authorization header and load the employee.

    Any endpoint that depends on this function is no longer callable
    without a valid token.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        employee_id = payload.get("sub")
        if employee_id is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = db.query(Employee).filter(Employee.id == int(employee_id)).first()
    if user is None:
        raise credentials_error

    return user


def require_manager(current_user: Employee = Depends(get_current_user)) -> Employee:
    """Dependency that only allows users with the 'manager' role through."""
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires manager privileges.",
        )
    return current_user
