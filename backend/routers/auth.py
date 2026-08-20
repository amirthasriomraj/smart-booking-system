from fastapi import APIRouter, Depends, HTTPException, Cookie, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timedelta

from database import SessionLocal
from schemas import (
    UserCreate,
    UserResponse,
    Token,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserContextResponse,
    BusinessContext,
)
from schemas_staff import AcceptInvitationStatusResponse, AcceptInvitationRequest
import crud
import crud_staff
from auth import create_access_token, generate_csrf_token
from dependencies import get_current_user, user_has_role
from models import RefreshToken, BusinessMember, Business, Role, BranchAssignment, Branch
from services.email_service import send_password_reset_email
from services.rate_limiter import rate_limit

from config import get_settings
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_cookie_settings():
    if settings.DEBUG:
        return {
            "secure": False,
            "samesite": "lax"
        }
    else:
        return {
            "secure": True,
            "samesite": "strict"
        }
    
# -----------------------------
# Register
# -----------------------------

@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    return crud.create_user(db, user.username, user.email, user.password)


# -----------------------------
# Login (Updated with Cookie Refresh Token)
# -----------------------------

@router.post("/login", dependencies=[Depends(rate_limit(5, 60))])
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):

    user = crud.authenticate_user(db, form_data.username, form_data.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(
        {"sub": str(user.id)},
        expires_delta=timedelta(minutes=15)
    )

    refresh_token = crud.create_refresh_token(db, user.id)

    # 🔐 Generate CSRF token (using utility)
    csrf_token = generate_csrf_token()

    response = JSONResponse(
        content={
            "access_token": access_token,
            "token_type": "bearer"
        }
    )

    cookie_settings = get_cookie_settings()

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=cookie_settings["secure"],
        samesite=cookie_settings["samesite"],
        path="/api",
        max_age=60 * 60 * 24 * 7
    )

    # 🔐 CSRF cookie (readable by JS)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=cookie_settings["secure"],
        samesite=cookie_settings["samesite"],
        path="/",
        max_age=60 * 60 * 24 * 7
    )

    return response


# -----------------------------
# Forgot Password
# -----------------------------

@router.post("/forgot-password", dependencies=[Depends(rate_limit(3, 600))])
def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    token = crud.create_password_reset_token(db, request.email)

    # Only send email if user exists
    if token:
        background_tasks.add_task(
            send_password_reset_email,
            request.email,
            token
        )

    return {
        "detail": "If account exists, password reset instructions sent."
    }


# -----------------------------
# Reset Password
# -----------------------------

@router.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    return crud.reset_password(
        db,
        request.token,
        request.new_password
    )


# -----------------------------
# Refresh Token
# -----------------------------

@router.post("/refresh", dependencies=[Depends(rate_limit(10, 60))])
def refresh_token(
    refresh_token: str = Cookie(None),
    csrf_cookie: str = Cookie(None, alias="csrf_token"),
    csrf_header: str = Header(None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db)
):

    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(status_code=403, detail="CSRF validation failed")

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    user_id, new_refresh_token = crud.rotate_refresh_token(db, refresh_token)

    new_access_token = create_access_token(
        {"sub": str(user_id)},
        expires_delta=timedelta(minutes=15)
    )

    response = JSONResponse(
        content={
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    )

    cookie_settings = get_cookie_settings()

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=cookie_settings["secure"],
        samesite=cookie_settings["samesite"],
        path="/api",
        max_age=60 * 60 * 24 * 7
    )

    return response


# -----------------------------
# Logout
# -----------------------------

@router.post("/logout")
def logout(
    refresh_token: str = Cookie(None),
    db: Session = Depends(get_db)
):

    if refresh_token:
        crud.revoke_refresh_token(db, refresh_token)

    response = JSONResponse({"detail": "Logged out successfully"})

    response.delete_cookie("refresh_token")
    response.delete_cookie("csrf_token")

    return response


# -----------------------------
# Logout All
# -----------------------------

@router.post("/logout-all")
def logout_all(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return crud.revoke_all_refresh_tokens(db, current_user.id)


# -----------------------------
# Current user context (Milestone 2 — drives frontend role-gating)
# -----------------------------

@router.get("/me", response_model=UserContextResponse)
def get_current_user_context(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    is_platform_admin = user_has_role(db, current_user.id, "PLATFORM_ADMIN")

    membership = (
        db.query(BusinessMember, Business, Role)
        .join(Business, BusinessMember.business_id == Business.id)
        .join(Role, BusinessMember.role_id == Role.id)
        .filter(BusinessMember.user_id == current_user.id, BusinessMember.status == "Active")
        .first()
    )

    business_context = None
    if membership:
        member, business, role = membership

        branch_id = None
        branch_name = None
        if role.code == "BRANCH_MANAGER":
            assignment = (
                db.query(BranchAssignment, Branch)
                .join(Branch, BranchAssignment.branch_id == Branch.id)
                .filter(BranchAssignment.business_member_id == member.id, BranchAssignment.is_current == True)  # noqa: E712
                .first()
            )
            if assignment:
                _, branch = assignment
                branch_id = branch.id
                branch_name = branch.branch_name

        business_context = BusinessContext(
            id=business.id,
            business_name=business.business_name,
            status=business.status,
            role_code=role.code,
            branch_id=branch_id,
            branch_name=branch_name,
        )

    return UserContextResponse(
        user_id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_platform_admin=is_platform_admin,
        business=business_context,
    )


# -----------------------------
# Staff invitation acceptance (Milestone 3) — public, token-authenticated
# -----------------------------

@router.get("/accept-invitation", response_model=AcceptInvitationStatusResponse)
def get_invitation_status(token: str, db: Session = Depends(get_db)):
    member, business, role, branch = crud_staff.get_invitation_status(db, token)
    return AcceptInvitationStatusResponse(
        requires_credential_setup=member.requires_credential_setup,
        business_name=business.business_name,
        role_code=role.code,
        branch_id=branch.id if branch else None,
        branch_name=branch.branch_name if branch else None,
    )


@router.post("/accept-invitation")
def accept_invitation(payload: AcceptInvitationRequest, db: Session = Depends(get_db)):
    crud_staff.accept_invitation(db, payload)
    return {"detail": "Invitation accepted. You can now log in."}