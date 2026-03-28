from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal
from dependencies import get_current_admin
from schemas import UserResponse
import crud

router = APIRouter(prefix="/users", tags=["User Management (Admin)"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 🔹 Get all users (Admin only)
@router.get("/", response_model=List[UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin)
):
    return crud.get_all_users(db)


# 🔹 Deactivate user (Admin only)
@router.patch("/deactivate/{user_id}", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin)
):
    return crud.deactivate_user(db, user_id)


# 🔹 Activate user (Admin only)
@router.patch("/activate/{user_id}", response_model=UserResponse)
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin)
):
    return crud.activate_user(db, user_id)


# 🔹 Delete user (Admin only)
@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin)
):
    return crud.delete_user(db, user_id)