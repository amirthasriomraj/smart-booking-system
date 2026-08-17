from sqlalchemy.orm import Session
from typing import Optional

from models import AuditLog


def write_audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    performed_by: Optional[int] = None,
    business_id: Optional[int] = None,
    previous_value: Optional[str] = None,
    new_value: Optional[str] = None,
    reason: Optional[str] = None,
    commit: bool = True,
) -> AuditLog:
    """
    Append an immutable audit entry.

    By default this commits independently. Pass commit=False when the audit
    entry must land in the same database transaction as the business change
    it describes (TAS Part 5 §8: audit entries are created before commit,
    not after), then let the caller issue the single db.commit().
    """
    entry = AuditLog(
        business_id=business_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        previous_value=previous_value,
        new_value=new_value,
        performed_by=performed_by,
        reason=reason,
    )

    db.add(entry)

    if commit:
        db.commit()
        db.refresh(entry)

    return entry
