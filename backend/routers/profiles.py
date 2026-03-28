from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session

from database import SessionLocal
from dependencies import get_current_user
from schemas import UserProfileCreate, UserProfileResponse
import crud
from services.file_service import save_file
from models import User, UserProfile

router = APIRouter(prefix="/profiles", tags=["Profiles"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/profile", response_model=UserProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return crud.get_user_profile(db, current_user.id)


@router.patch("/profile", response_model=UserProfileResponse)
def update_my_profile(
    profile_data: UserProfileCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return crud.update_user_profile(db, current_user.id, profile_data)


@router.post("/upload-image")
def upload_profile_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    file_path = save_file(
        file,
        "profile_images",
        ["image/jpeg", "image/png"]
    )

    profile = db.query(UserProfile).filter(
        UserProfile.user_id == current_user.id
    ).first()

    profile.profile_image_url = file_path
    db.commit()

    return {"message": "Profile image uploaded", "file_path": file_path}


@router.post("/upload-document")
def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    file_path = save_file(
        file,
        "documents",
        ["application/pdf"]
    )

    profile = db.query(UserProfile).filter(
        UserProfile.user_id == current_user.id
    ).first()

    profile.document_url = file_path
    db.commit()

    return {"message": "Document uploaded", "file_path": file_path}