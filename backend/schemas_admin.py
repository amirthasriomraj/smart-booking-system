from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: int
    business_id: Optional[int] = None
    entity_type: str
    entity_id: int
    action: str
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    performed_by: Optional[int] = None
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedAuditLogs(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AuditLogFilterOptionsResponse(BaseModel):
    entity_types: List[str]
    actions: List[str]


class NotificationResponse(BaseModel):
    id: int
    business_id: Optional[int] = None
    recipient_user_id: int
    notification_type: str
    channel: str
    status: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    created_at: datetime
    sent_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedNotifications(BaseModel):
    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PlatformAnalyticsResponse(BaseModel):
    total_businesses: int
    pending_business_approvals: int
    active_businesses: int
    active_branches: int
