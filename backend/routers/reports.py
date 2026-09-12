from datetime import date as DateType
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from database import SessionLocal
from schemas_reports import BusinessReportsResponse, BranchDailyReportResponse
import crud_reports
from dependencies import get_current_user

router = APIRouter(tags=["Reports"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# Business Owner Reports (M9 Phase 6, PRD §36)
# -----------------------------

@router.get("/businesses/{business_id}/reports", response_model=BusinessReportsResponse)
def get_business_reports(
    business_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_reports.get_business_reports(db, business_id, current_user)


# -----------------------------
# Branch Manager Daily Reports (M9 Phase 6, PRD §36)
# -----------------------------

@router.get("/branches/{branch_id}/reports/daily", response_model=BranchDailyReportResponse)
def get_branch_daily_report(
    branch_id: int,
    report_date: Optional[DateType] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_reports.get_branch_daily_report(db, branch_id, current_user, report_date)
