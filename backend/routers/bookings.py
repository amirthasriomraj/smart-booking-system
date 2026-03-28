from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal
from schemas import BookingCreate, BookingUpdate, BookingResponse, PaginatedBookings
from dependencies import get_current_user, get_current_admin
import crud

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=BookingResponse)
def create_booking(
        booking: BookingCreate,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    return crud.create_booking(db, booking, current_user)


@router.get("/", response_model=PaginatedBookings)
def get_bookings(
        limit: int = Query(10, le=100),
        offset: int = Query(0, ge=0),
        sort: str = "date",
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    return crud.get_all_bookings(
        db=db,
        current_user=current_user,
        limit=limit,
        offset=offset,
        sort=sort
    )

@router.patch("/{booking_id}", response_model=BookingResponse)
def update_booking(
        booking_id: int,
        booking: BookingUpdate,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    return crud.update_booking(db, booking_id, booking, current_user)


@router.delete("/{booking_id}")
def delete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_admin)
):
    return crud.delete_booking(db, booking_id)