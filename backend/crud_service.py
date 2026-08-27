import json
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import (
    User,
    Business,
    BusinessMember,
    Role,
    Branch,
    BranchAssignment,
    ResourceCategory,
    ServiceTemplate,
    ServiceTemplateResourceCategory,
    BranchService,
    BranchServiceResourceCategory,
    ServiceApproval,
)
from audit import write_audit


def _jsonable(value):
    """Renders Decimal-bearing configuration dicts safely into the JSON/JSONB columns."""
    return json.loads(json.dumps(value, default=str))


def _as_audit_string(value) -> str:
    """AuditLog.previous_value/new_value are Text columns — serialize dict snapshots to a string."""
    return json.dumps(_jsonable(value), default=str)


# -------------------------
# LOOKUP HELPERS
# -------------------------

def _get_business_or_404(db: Session, business_id: int) -> Business:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


def _get_branch_or_404(db: Session, branch_id: int) -> Branch:
    # Not imported from crud_branch: crud_branch calls into this module
    # (inherit_templates_to_branch) at branch-creation time, so this module
    # must not import crud_branch back, to avoid a circular import.
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch


def get_service_template_or_404(db: Session, template_id: int) -> ServiceTemplate:
    template = db.query(ServiceTemplate).filter(ServiceTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Service Template not found")
    return template


def get_branch_service_or_404(db: Session, branch_service_id: int) -> BranchService:
    branch_service = db.query(BranchService).filter(BranchService.id == branch_service_id).first()
    if not branch_service:
        raise HTTPException(status_code=404, detail="Branch Service not found")
    return branch_service


def _get_service_approval_or_404(db: Session, approval_id: int) -> ServiceApproval:
    approval = db.query(ServiceApproval).filter(ServiceApproval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Service Approval not found")
    return approval


# -------------------------
# AUTHORIZATION HELPERS (ID-027)
# -------------------------

def _has_active_role(db: Session, business_id: int, user_id: int, role_code: str) -> bool:
    return (
        db.query(BusinessMember)
        .join(Role, BusinessMember.role_id == Role.id)
        .filter(
            BusinessMember.business_id == business_id,
            BusinessMember.user_id == user_id,
            BusinessMember.status == "Active",
            Role.code == role_code,
        )
        .first()
        is not None
    )


def _get_manager_current_branch_id(db: Session, business_id: int, user_id: int) -> Optional[int]:
    member = (
        db.query(BusinessMember)
        .join(Role, BusinessMember.role_id == Role.id)
        .filter(
            BusinessMember.business_id == business_id,
            BusinessMember.user_id == user_id,
            BusinessMember.status == "Active",
            Role.code == "BRANCH_MANAGER",
        )
        .first()
    )
    if not member:
        return None
    assignment = (
        db.query(BranchAssignment)
        .filter(BranchAssignment.business_member_id == member.id, BranchAssignment.is_current == True)  # noqa: E712
        .first()
    )
    return assignment.branch_id if assignment else None


def _require_template_write_access(db: Session, business_id: int, current_user: User) -> Business:
    """Service Template create + Active/Inactive toggle: Business Owner only (ID-019, ID-027)."""
    business = _get_business_or_404(db, business_id)
    if not _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER"):
        raise HTTPException(status_code=403, detail="Business Owner privileges required for this business")
    return business


def _require_template_read_access(db: Session, business_id: int, current_user: User) -> Business:
    """Service Template read: Business Owner or Branch Manager (ID-027)."""
    business = _get_business_or_404(db, business_id)
    if _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER"):
        return business
    if _get_manager_current_branch_id(db, business_id, current_user.id) is not None:
        return business
    raise HTTPException(status_code=403, detail="Not authorized to view Service Templates for this business")


def _require_branch_service_owner_access(db: Session, business_id: int, current_user: User) -> Business:
    """Direct Branch Service edit + approval decisions: Business Owner only (ID-027)."""
    business = _get_business_or_404(db, business_id)
    if not _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER"):
        raise HTTPException(status_code=403, detail="Business Owner privileges required for this business")
    return business


def _require_branch_service_read_access(db: Session, branch: Branch, current_user: User) -> Business:
    """Branch Service read: Business Owner (business-wide) or Branch Manager restricted to their branch (ID-027)."""
    business = _get_business_or_404(db, branch.business_id)
    if _has_active_role(db, business.id, current_user.id, "BUSINESS_OWNER"):
        return business
    if _get_manager_current_branch_id(db, business.id, current_user.id) == branch.id:
        return business
    raise HTTPException(status_code=403, detail="Not authorized to view services for this branch")


def _require_business_wide_branch_service_read_access(db: Session, business_id: int, current_user: User) -> Business:
    """Business-wide Branch Service listing: Business Owner only (ID-027)."""
    business = _get_business_or_404(db, business_id)
    if not _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER"):
        raise HTTPException(status_code=403, detail="Not authorized to view services for this business")
    return business


def _require_branch_service_submit_access(db: Session, branch: Branch, current_user: User) -> Business:
    """Override submission: Branch Manager restricted to their currently assigned branch only (ID-027)."""
    business = _get_business_or_404(db, branch.business_id)
    if _get_manager_current_branch_id(db, business.id, current_user.id) == branch.id:
        return business
    raise HTTPException(
        status_code=403,
        detail="Branch Manager privileges for this branch are required to submit a service override",
    )


# -------------------------
# TENANT ISOLATION ON RESOURCE CATEGORY REFERENCES
# (mechanical enforcement of the platform's existing tenant-isolation
# principle, PRD §27 — not a new Service business rule)
# -------------------------

def _validate_resource_category_ids(db: Session, business_id: int, category_ids: List[int]) -> None:
    if not category_ids:
        return
    unique_ids = set(category_ids)
    matching = (
        db.query(ResourceCategory)
        .filter(ResourceCategory.business_id == business_id, ResourceCategory.id.in_(unique_ids))
        .count()
    )
    if matching != len(unique_ids):
        raise HTTPException(
            status_code=400,
            detail="One or more Resource Category IDs do not belong to this business",
        )


# -------------------------
# RESOURCE CATEGORY ASSIGNMENT HELPERS
# -------------------------

def _get_template_resource_category_ids(db: Session, template_id: int) -> List[int]:
    return [
        row.resource_category_id
        for row in db.query(ServiceTemplateResourceCategory)
        .filter(ServiceTemplateResourceCategory.service_template_id == template_id)
        .all()
    ]


def _get_branch_service_resource_category_ids(db: Session, branch_service_id: int) -> List[int]:
    return [
        row.resource_category_id
        for row in db.query(BranchServiceResourceCategory)
        .filter(BranchServiceResourceCategory.branch_service_id == branch_service_id)
        .all()
    ]


def _set_branch_service_resource_categories(db: Session, branch_service_id: int, category_ids: List[int]) -> None:
    db.query(BranchServiceResourceCategory).filter(
        BranchServiceResourceCategory.branch_service_id == branch_service_id
    ).delete()
    for category_id in category_ids:
        db.add(BranchServiceResourceCategory(branch_service_id=branch_service_id, resource_category_id=category_id))


# -------------------------
# SERVICE TEMPLATE (ID-018, ID-019, ID-024, ID-025)
# -------------------------

def create_service_template(db: Session, business_id: int, payload, current_user: User) -> ServiceTemplate:
    business = _require_template_write_access(db, business_id, current_user)

    if business.status != "Active":
        raise HTTPException(status_code=409, detail="Business must be Active before creating a Service Template")

    _validate_resource_category_ids(db, business.id, payload.default_resource_category_ids)

    template = ServiceTemplate(
        business_id=business.id,
        name=payload.name,
        description=payload.description,
        default_duration=payload.default_duration,
        default_price=payload.default_price,
        default_buffer_minutes=payload.default_buffer_minutes,
        default_working_rules=payload.default_working_rules,
        status="Active",
    )
    db.add(template)
    db.flush()

    for category_id in payload.default_resource_category_ids:
        db.add(ServiceTemplateResourceCategory(service_template_id=template.id, resource_category_id=category_id))

    write_audit(
        db,
        business_id=business.id,
        entity_type="ServiceTemplate",
        entity_id=template.id,
        action="SERVICE_TEMPLATE_CREATED",
        performed_by=current_user.id,
        new_value=f"name={template.name};status=Active",
        commit=False,
    )

    # ID-023(b): propagate immediately to every existing branch of this business.
    _propagate_template_to_all_branches(db, template, current_user.id)

    db.commit()
    db.refresh(template)
    return template


def list_service_templates(db: Session, business_id: int, current_user: User) -> List[ServiceTemplate]:
    _require_template_read_access(db, business_id, current_user)
    return (
        db.query(ServiceTemplate)
        .filter(ServiceTemplate.business_id == business_id)
        .order_by(ServiceTemplate.created_at.desc())
        .all()
    )


def get_service_template(db: Session, template_id: int, current_user: User) -> ServiceTemplate:
    template = get_service_template_or_404(db, template_id)
    _require_template_read_access(db, template.business_id, current_user)
    return template


def set_service_template_status(db: Session, template_id: int, new_status: str, current_user: User) -> ServiceTemplate:
    """ID-019: the only mutation a Service Template supports after creation."""
    template = get_service_template_or_404(db, template_id)
    business = _require_template_write_access(db, template.business_id, current_user)

    if new_status not in ("Active", "Inactive"):
        raise HTTPException(status_code=400, detail="status must be 'Active' or 'Inactive'")

    previous_status = template.status
    template.status = new_status
    # ID-026: no cascade to already-existing Branch Services.

    write_audit(
        db,
        business_id=business.id,
        entity_type="ServiceTemplate",
        entity_id=template.id,
        action="SERVICE_TEMPLATE_STATUS_CHANGED",
        performed_by=current_user.id,
        previous_value=f"status={previous_status}",
        new_value=f"status={new_status}",
        commit=False,
    )

    db.commit()
    db.refresh(template)
    return template


def serialize_service_template(db: Session, template: ServiceTemplate) -> dict:
    return {
        "id": template.id,
        "business_id": template.business_id,
        "name": template.name,
        "description": template.description,
        "default_duration": template.default_duration,
        "default_price": template.default_price,
        "default_buffer_minutes": template.default_buffer_minutes,
        "default_working_rules": template.default_working_rules,
        "default_resource_category_ids": _get_template_resource_category_ids(db, template.id),
        "status": template.status,
        "created_at": template.created_at,
    }


# -------------------------
# SERVICE INHERITANCE (ID-023)
# -------------------------

def _create_branch_service_from_template(
    db: Session, branch: Branch, template: ServiceTemplate, performed_by_user_id: int
) -> BranchService:
    branch_service = BranchService(
        branch_id=branch.id,
        business_id=branch.business_id,
        service_template_id=template.id,
        duration=template.default_duration,
        price=template.default_price,
        status="Approved",
        pending_approval=False,
    )
    db.add(branch_service)
    db.flush()

    for category_id in _get_template_resource_category_ids(db, template.id):
        db.add(BranchServiceResourceCategory(branch_service_id=branch_service.id, resource_category_id=category_id))

    write_audit(
        db,
        business_id=branch.business_id,
        entity_type="BranchService",
        entity_id=branch_service.id,
        action="BRANCH_SERVICE_CREATED",
        performed_by=performed_by_user_id,
        new_value=f"service_template_id={template.id};status=Approved",
        commit=False,
    )

    return branch_service


def inherit_templates_to_branch(db: Session, branch: Branch, performed_by_user_id: int) -> List[BranchService]:
    """ID-023(a): called from crud_branch.create_branch, before its own commit."""
    templates = (
        db.query(ServiceTemplate)
        .filter(ServiceTemplate.business_id == branch.business_id, ServiceTemplate.status == "Active")
        .all()
    )
    return [_create_branch_service_from_template(db, branch, template, performed_by_user_id) for template in templates]


def _propagate_template_to_all_branches(db: Session, template: ServiceTemplate, performed_by_user_id: int) -> List[BranchService]:
    """ID-023(b): called from create_service_template, before its own commit."""
    branches = db.query(Branch).filter(Branch.business_id == template.business_id).all()
    return [_create_branch_service_from_template(db, branch, template, performed_by_user_id) for branch in branches]


# -------------------------
# BRANCH SERVICE (ID-018, ID-020, ID-024, ID-027)
# -------------------------

def list_branch_services_for_branch(db: Session, branch_id: int, current_user: User) -> List[BranchService]:
    branch = _get_branch_or_404(db, branch_id)
    _require_branch_service_read_access(db, branch, current_user)
    return (
        db.query(BranchService)
        .filter(BranchService.branch_id == branch_id)
        .order_by(BranchService.created_at.desc())
        .all()
    )


def list_branch_services_for_business(db: Session, business_id: int, current_user: User) -> List[BranchService]:
    _require_business_wide_branch_service_read_access(db, business_id, current_user)
    return (
        db.query(BranchService)
        .filter(BranchService.business_id == business_id)
        .order_by(BranchService.created_at.desc())
        .all()
    )


def get_branch_service(db: Session, branch_service_id: int, current_user: User) -> BranchService:
    branch_service = get_branch_service_or_404(db, branch_service_id)
    branch = _get_branch_or_404(db, branch_service.branch_id)
    _require_branch_service_read_access(db, branch, current_user)
    return branch_service


def serialize_branch_service(db: Session, branch_service: BranchService) -> dict:
    return {
        "id": branch_service.id,
        "branch_id": branch_service.branch_id,
        "business_id": branch_service.business_id,
        "service_template_id": branch_service.service_template_id,
        "duration": branch_service.duration,
        "price": branch_service.price,
        "resource_category_ids": _get_branch_service_resource_category_ids(db, branch_service.id),
        "status": branch_service.status,
        "pending_approval": branch_service.pending_approval,
        "created_at": branch_service.created_at,
    }


def _current_configuration(db: Session, branch_service: BranchService) -> dict:
    return {
        "duration": branch_service.duration,
        "price": branch_service.price,
        "resource_category_ids": _get_branch_service_resource_category_ids(db, branch_service.id),
    }


def update_branch_service_direct(db: Session, branch_service_id: int, payload, current_user: User) -> BranchService:
    """
    Business Owner direct edit (ID-027): immediate effect, no approval step,
    since the Business Owner is themself the approver for Branch-Manager
    overrides (ID-022 established Price/Duration/Resource Category as the
    only customizable fields; this schema exposes exactly those three —
    business_id/branch_id/service_template_id/pending_approval/status are
    never accepted here).
    """
    branch_service = get_branch_service_or_404(db, branch_service_id)
    business = _require_branch_service_owner_access(db, branch_service.business_id, current_user)

    updates = payload.model_dump(exclude_unset=True)
    previous_configuration = _current_configuration(db, branch_service)

    if "resource_category_ids" in updates and updates["resource_category_ids"] is not None:
        _validate_resource_category_ids(db, business.id, updates["resource_category_ids"])
        _set_branch_service_resource_categories(db, branch_service.id, updates["resource_category_ids"])

    if "duration" in updates and updates["duration"] is not None:
        branch_service.duration = updates["duration"]
    if "price" in updates and updates["price"] is not None:
        branch_service.price = updates["price"]

    write_audit(
        db,
        business_id=business.id,
        entity_type="BranchService",
        entity_id=branch_service.id,
        action="BRANCH_SERVICE_UPDATED",
        performed_by=current_user.id,
        previous_value=_as_audit_string(previous_configuration),
        new_value=_as_audit_string(_current_configuration(db, branch_service)),
        commit=False,
    )

    db.commit()
    db.refresh(branch_service)
    return branch_service


# -------------------------
# SERVICE APPROVAL (ID-021, ID-022, ID-027)
# -------------------------

def submit_branch_service_override(
    db: Session, branch_service_id: int, payload, current_user: User
) -> Tuple[ServiceApproval, str, str, str, str]:
    """
    Branch Manager submits an override proposal. Returns
    (approval, business_owner_email, business_name, branch_name, service_name)
    so the router can schedule the submission-notification email.
    """
    branch_service = get_branch_service_or_404(db, branch_service_id)
    branch = _get_branch_or_404(db, branch_service.branch_id)
    business = _require_branch_service_submit_access(db, branch, current_user)

    if branch_service.pending_approval:
        raise HTTPException(status_code=409, detail="An override for this service is already pending approval")

    updates = payload.model_dump(exclude_unset=True)
    if "resource_category_ids" in updates and updates["resource_category_ids"] is not None:
        _validate_resource_category_ids(db, business.id, updates["resource_category_ids"])

    previous_configuration = _current_configuration(db, branch_service)
    proposed_configuration = {
        "duration": updates.get("duration", previous_configuration["duration"]),
        "price": updates.get("price", previous_configuration["price"]),
        "resource_category_ids": updates.get("resource_category_ids", previous_configuration["resource_category_ids"]),
    }

    approval = ServiceApproval(
        branch_service_id=branch_service.id,
        requested_by=current_user.id,
        decision="Pending",
        previous_configuration=_jsonable(previous_configuration),
        proposed_configuration=_jsonable(proposed_configuration),
    )
    db.add(approval)

    branch_service.pending_approval = True

    db.flush()

    write_audit(
        db,
        business_id=business.id,
        entity_type="ServiceApproval",
        entity_id=approval.id,
        action="SERVICE_OVERRIDE_SUBMITTED",
        performed_by=current_user.id,
        new_value=_as_audit_string(proposed_configuration),
        commit=False,
    )

    db.commit()
    db.refresh(approval)

    owner_member = (
        db.query(BusinessMember)
        .join(Role, BusinessMember.role_id == Role.id)
        .filter(
            BusinessMember.business_id == business.id,
            BusinessMember.status == "Active",
            Role.code == "BUSINESS_OWNER",
        )
        .first()
    )
    owner_user = db.query(User).filter(User.id == owner_member.user_id).first()
    template = get_service_template_or_404(db, branch_service.service_template_id)

    return approval, owner_user.email, business.business_name, branch.branch_name, template.name


def decide_service_approval(
    db: Session, approval_id: int, payload, current_user: User
) -> Tuple[ServiceApproval, str, str, str, str]:
    """
    Business Owner approves or rejects a pending override. Returns
    (approval, submitter_email, business_name, branch_name, service_name)
    so the router can schedule the decision-notification email.
    """
    approval = _get_service_approval_or_404(db, approval_id)
    branch_service = get_branch_service_or_404(db, approval.branch_service_id)
    branch = _get_branch_or_404(db, branch_service.branch_id)
    business = _require_branch_service_owner_access(db, branch_service.business_id, current_user)

    if approval.decision != "Pending":
        raise HTTPException(status_code=409, detail="This approval has already been decided")

    if payload.decision == "Approved":
        # ID-021: apply the proposed snapshot onto the live configuration.
        proposed = approval.proposed_configuration
        branch_service.duration = proposed["duration"]
        branch_service.price = Decimal(str(proposed["price"]))
        _set_branch_service_resource_categories(db, branch_service.id, proposed["resource_category_ids"])
        audit_action = "SERVICE_OVERRIDE_APPROVED"
    else:
        # ID-021: rejection leaves the live configuration untouched.
        audit_action = "SERVICE_OVERRIDE_REJECTED"

    branch_service.pending_approval = False
    approval.decision = payload.decision
    approval.approved_by = current_user.id
    approval.comments = payload.comments
    approval.decided_at = datetime.utcnow()

    write_audit(
        db,
        business_id=business.id,
        entity_type="ServiceApproval",
        entity_id=approval.id,
        action=audit_action,
        performed_by=current_user.id,
        previous_value=_as_audit_string(approval.previous_configuration),
        new_value=_as_audit_string(
            approval.proposed_configuration if payload.decision == "Approved" else approval.previous_configuration
        ),
        reason=payload.comments,
        commit=False,
    )

    db.commit()
    db.refresh(approval)

    submitter = db.query(User).filter(User.id == approval.requested_by).first()
    template = get_service_template_or_404(db, branch_service.service_template_id)

    return approval, submitter.email, business.business_name, branch.branch_name, template.name


def serialize_service_approval(db: Session, approval: ServiceApproval) -> dict:
    """
    Enriches the raw ServiceApproval columns with the Branch/Service Template
    identity and requester/approver emails the review UI needs to identify
    what is being approved and by whom — none of this is a new business
    rule; it is already reachable via existing FKs (branch_service_id ->
    BranchService.branch_id/service_template_id, requested_by/approved_by ->
    User.email) and was simply not being surfaced in the API response.
    """
    branch_service = get_branch_service_or_404(db, approval.branch_service_id)
    requester = db.query(User).filter(User.id == approval.requested_by).first()
    approver = db.query(User).filter(User.id == approval.approved_by).first() if approval.approved_by else None

    return {
        "id": approval.id,
        "branch_service_id": approval.branch_service_id,
        "branch_id": branch_service.branch_id,
        "service_template_id": branch_service.service_template_id,
        "requested_by": approval.requested_by,
        "requested_by_email": requester.email,
        "approved_by": approval.approved_by,
        "approved_by_email": approver.email if approver else None,
        "decision": approval.decision,
        "previous_configuration": approval.previous_configuration,
        "proposed_configuration": approval.proposed_configuration,
        "comments": approval.comments,
        "decided_at": approval.decided_at,
        "created_at": approval.created_at,
    }


def list_service_approvals(db: Session, business_id: int, current_user: User) -> List[ServiceApproval]:
    business = _get_business_or_404(db, business_id)

    is_owner = _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER")
    manager_branch_id = None
    if not is_owner:
        manager_branch_id = _get_manager_current_branch_id(db, business_id, current_user.id)
        if manager_branch_id is None:
            raise HTTPException(status_code=403, detail="Not authorized to view Service Approvals for this business")

    query = (
        db.query(ServiceApproval)
        .join(BranchService, ServiceApproval.branch_service_id == BranchService.id)
        .filter(BranchService.business_id == business.id)
    )
    if manager_branch_id is not None:
        query = query.filter(BranchService.branch_id == manager_branch_id)

    return query.order_by(ServiceApproval.created_at.desc()).all()
