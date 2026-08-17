"""
Bootstrap the initial Platform Administrator account.

This is a standalone, manually-run script — it is never invoked
automatically by `alembic upgrade` or application startup. Alembic
migrations stay schema/structure-only (TAS AP-002).

Credentials are never hard-coded. They are read from environment
variables (PLATFORM_ADMIN_EMAIL / PLATFORM_ADMIN_USERNAME /
PLATFORM_ADMIN_PASSWORD); any that are missing are collected via a
secure interactive prompt instead. The raw password is never logged,
printed, or persisted anywhere — only its bcrypt hash is stored.

Safe to run more than once: if a Platform Administrator already exists,
the script reports that and exits without creating a duplicate account
or mutating the existing one.

Usage:
    PLATFORM_ADMIN_EMAIL=admin@example.com \\
    PLATFORM_ADMIN_USERNAME=platform_admin \\
    PLATFORM_ADMIN_PASSWORD='...' \\
        python scripts/bootstrap_platform_admin.py

    # or, omitting any/all of the above, to be prompted securely:
    python scripts/bootstrap_platform_admin.py
"""
import os
import sys
import getpass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException  # noqa: E402

from database import SessionLocal  # noqa: E402
from models import User, UserProfile, Role, UserRole  # noqa: E402
from auth import hash_password, validate_password  # noqa: E402

PLATFORM_ADMIN_ROLE_CODE = "PLATFORM_ADMIN"


def _read_credentials():
    email = os.environ.get("PLATFORM_ADMIN_EMAIL") or input("Platform Admin email: ").strip()
    username = os.environ.get("PLATFORM_ADMIN_USERNAME") or input("Platform Admin username: ").strip()
    password = os.environ.get("PLATFORM_ADMIN_PASSWORD") or getpass.getpass("Platform Admin password: ")
    return email, username, password


def bootstrap_platform_admin() -> int:
    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.code == PLATFORM_ADMIN_ROLE_CODE).first()
        if role is None:
            print("PLATFORM_ADMIN role is not seeded yet. Run database migrations first.")
            return 1

        existing_admin = db.query(UserRole).filter(UserRole.role_id == role.id).first()
        if existing_admin is not None:
            print("A Platform Administrator already exists. No action taken.")
            return 0

        email, username, password = _read_credentials()

        duplicate = db.query(User).filter(
            (User.email == email) | (User.username == username)
        ).first()
        if duplicate is not None:
            print("A user with that email or username already exists. Aborting.")
            return 1

        try:
            validate_password(password)
        except HTTPException as exc:
            print(f"Password does not meet policy requirements: {exc.detail}")
            return 1

        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role="admin",  # keeps continuity with the existing legacy admin dependency
        )
        db.add(user)
        db.flush()

        db.add(UserProfile(user_id=user.id))
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()

        print(f"Platform Administrator created: {username} <{email}>")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(bootstrap_platform_admin())
