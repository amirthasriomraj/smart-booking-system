from datetime import date as DateType
from typing import List

from pydantic import BaseModel


class BusinessReportsResponse(BaseModel):
    total_bookings: int
    completed_bookings: int
    cancelled_bookings: int
    active_branches: int
    active_resources: int


class ResourceUtilizationEntry(BaseModel):
    resource_id: int
    resource_name: str
    booking_count: int


class ServicePopularityEntry(BaseModel):
    branch_service_id: int
    service_name: str
    booking_count: int


class BranchDailyReportResponse(BaseModel):
    report_date: DateType
    daily_bookings: int
    resource_utilization: List[ResourceUtilizationEntry]
    service_popularity: List[ServicePopularityEntry]
