from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class PlatformFeeOverrideResponse(BaseModel):
    business_id: int
    business_name: str
    fee_percentage: Decimal
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlatformFeeSettingsResponse(BaseModel):
    default_fee_percentage: Decimal
    default_updated_at: Optional[datetime] = None
    overrides: List[PlatformFeeOverrideResponse] = []


class SetDefaultFeeRequest(BaseModel):
    fee_percentage: Decimal
    reason: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class SetBusinessFeeOverrideRequest(BaseModel):
    fee_percentage: Decimal
    reason: str  # ID-051: mandatory whenever business_id is not NULL

    model_config = ConfigDict(extra="forbid")


class RemoveBusinessFeeOverrideRequest(BaseModel):
    reason: str

    model_config = ConfigDict(extra="forbid")
