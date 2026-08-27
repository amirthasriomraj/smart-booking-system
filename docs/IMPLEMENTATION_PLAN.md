# Smart Booking System — V1 Implementation Plan

## Purpose

This document records the approved implementation sequence for Version 1 of the Smart Booking System.

It defines milestone scope and ordering only.

Requirements and architecture come from the frozen PRD and TAS.
Approved post-freeze clarifications come from `IMPLEMENTATION_DECISIONS.md`.
The existing code, migrations, and tests represent the actual implemented state.

Do not move requirements between milestones, expand milestone scope, or change this plan without explicit user approval.

All functionality marked mandatory for V1 in the frozen PRD remains required. The implementation schedule changes sequencing, not frozen V1 scope.

---

## Milestone 1 — Tenant / Identity / Audit Foundation

**Status: COMPLETED**

Delivered:

- Roles and RBAC foundation
- `user_roles`
- `business_members`
- Country
- Business Category
- Business registration
- Business Owner membership creation
- Platform Admin bootstrap
- Platform Admin business approval/rejection
- Minimal append-only AuditLog infrastructure
- Business approval audit trail

Implementation is already merged into `main`.

---

## Milestone 2 — Branch Management

**Status: COMPLETED**

Delivered:

- Branch entity
- Branch approval lifecycle
- Independent operational activation/deactivation
- Branch working hours
- Branch assignment schema/history foundation
- Business Owner branch management APIs
- Platform Admin branch approval APIs
- `/auth/me` role/business context
- Platform Admin approval frontend
- Business Owner branch-management frontend
- Frontend role-gating/session-context corrections
- Branch audit events
- Automated tests and live E2E verification

Implementation is already merged into `main`.

Refer to `IMPLEMENTATION_DECISIONS.md` for approved post-freeze Branch and HR clarifications.

---

## Milestone 3 — Employee / Staff Invitation & Onboarding

**Status: COMPLETED**

Implementation is already merged into `main`.

Purpose:

Provide the missing onboarding mechanism for business-scoped staff roles required by later milestones.

Scope includes:

- Business Owner staff invitation/onboarding
- HR User onboarding
- Branch Manager onboarding
- Required `User` and `business_members` integration
- Appropriate branch assignment for branch-scoped roles
- Invitation lifecycle
- Authentication/account activation implications
- Role-based authorization
- Tenant isolation
- Branch assignment/history integration
- Audit events
- Required backend APIs and schemas
- Required frontend onboarding/invitation UI
- Automated tests and manual verification

Exact behavior must be derived from the frozen PRD/TAS plus `IMPLEMENTATION_DECISIONS.md`.

Do not invent invitation, transfer, role, or permission rules that those sources do not define. Any genuine ambiguity must be presented for explicit user approval before implementation.

This milestone must be completed before relying on Branch Manager scoping or login-linked staff/resource behavior in downstream milestones.

---

## Milestone 4 — Resource Management

**Status: COMPLETED**

Implementation is already merged into `main`.

Refer to `IMPLEMENTATION_DECISIONS.md` for approved post-freeze Resource Management clarifications.

Scope:

- Resource Category
- Generic Resource model
- Branch-scoped resources
- Resource working/configuration requirements defined by V1
- Optional login-linked Resource User where required by frozen V1
- Integration with the staff onboarding mechanism
- Resource create/update audit events
- Required backend/frontend functionality
- Tests

Do not implement future resource-capacity booking functionality.

---

## Milestone 5 — Service Management

**Status: NEXT**

Refer to `IMPLEMENTATION_DECISIONS.md` for approved post-freeze Service Management clarifications (ID-018–ID-027).

Scope:

- Business-level Service Templates
- Branch Service inheritance
- Branch-level overrides
- Business Owner approval workflow for applicable overrides
- Approval audit trail
- Required notifications
- Backend/frontend functionality
- Tests

---

## Milestone 6 — Customer Management & Customer Portal

**Status: PLANNED**

Scope:

- Platform Customer / Business Customer model required by V1
- Customer self-registration
- Staff-created/walk-in customers
- Business-scoped customer management
- Customer profile management
- Customer-facing portal foundation
- Browse/select required business/branch/service information
- Required backend/frontend functionality
- Tests

Customer self-registration and the customer-facing portal are mandatory V1 scope and must not be deferred to V2.

---

## Milestone 7 — Booking Engine & Customer Booking Experience

**Status: PLANNED**

Scope:

- Replace/generalize the legacy booking structure as required by V1
- Business/Branch/Service/Resource/Customer booking relationships
- Correct resource/time uniqueness rules
- Availability validation
- Resource assignment
- Booking creation
- Confirmed / Completed / Cancelled lifecycle
- Rescheduling while preserving history
- Cancellation reasons
- BookingHistory
- Customer self-booking
- Customer appointment history
- Customer cancel/reschedule frontend
- Required audit events
- Tests and end-to-end verification

Branch booking eligibility must respect the approved Branch lifecycle rules recorded in `IMPLEMENTATION_DECISIONS.md`.

---

## Milestone 8 — V1 Notifications, Hardening & Final Integration

**Status: PLANNED**

Complete remaining mandatory V1 cross-cutting functionality, including:

- Remaining required email notifications
- Required soft-delete/status lifecycle corrections
- Remaining V1 audit coverage
- Required search/filter/pagination behavior
- Dashboard foundation required by V1
- Password-policy correction if still outstanding
- Cross-role authorization and tenant-isolation verification
- Full regression testing
- End-to-end V1 workflow verification
- Final frontend/backend integration verification

Engineering polish explicitly classified as future/non-V1 should not delay V1 completion.

---

## Milestone Rules

1. Start each milestone from updated, clean `main` on its own feature branch.
2. Plan the milestone before implementation.
3. Read `CLAUDE.md`, the frozen PRD/TAS, `IMPLEMENTATION_DECISIONS.md`, this implementation plan, and only the existing code relevant to the milestone.
4. Preserve completed milestone behavior.
5. Do not silently resolve conflicts between documentation and implementation.
6. Do not pull later-milestone functionality forward unless technically unavoidable and explicitly approved.
7. Do not defer frozen mandatory V1 functionality without explicit user approval.
8. Record newly approved post-freeze business-rule clarifications in `IMPLEMENTATION_DECISIONS.md`.
9. Do not modify the implementation plan or implementation decisions without explicit user approval.
10. Complete tests and required manual/live verification before declaring a milestone complete.
11. Do not commit or push unless explicitly instructed.