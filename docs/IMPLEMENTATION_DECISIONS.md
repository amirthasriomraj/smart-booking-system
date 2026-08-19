# Implementation Decisions

This document records implementation-time clarifications approved after the Version 1 PRD and TAS were frozen.

It exists only for decisions required where the frozen documents were ambiguous or where an explicit implementation interpretation was required.

The frozen PRD and TAS remain the primary source of truth. This document must not be used to introduce new scope or silently change frozen requirements.

Do not add, remove, or change a decision in this document without explicit user approval.

---

## ID-001 — Branch Approval and Operational State Are Separate

**Decision:**  
A Branch has two independent lifecycle concepts:

- `approval_status` — controlled by the Platform Admin.
- `is_active` — controlled operationally by the Business Owner.

Branch approval statuses are:

- `Pending`
- `Approved`
- `Rejected`

A newly created Branch starts as:

`approval_status = Pending` + `is_active = false`

Platform Admin approval changes the Branch to:

`approval_status = Approved`

Approval does **not** automatically activate the Branch.

Only an `Approved` Branch may be activated.

The Business Owner decides when an approved Branch becomes active or inactive.

Bookings are allowed only when the Branch satisfies the required approval and operational-state rules.

**Reason:**  
Resolved during Milestone 2 because approval and operational activation needed to be represented separately.

---

## ID-002 — Branch Deactivation Is Not Deletion

**Decision:**  
Setting:

`is_active = false`

is an operational deactivation only.

It is **not**:

- soft deletion,
- archival,
- rejection,
- or removal of Platform Admin approval.

Therefore:

`Approved + Active → Approved + Inactive → Approved + Active`

is a valid lifecycle.

An approved Branch that is deactivated may later be reactivated by the Business Owner without requiring Platform Admin approval again.

Branch deletion/archival is a separate lifecycle concern and was not introduced as part of Milestone 2.

**Reason:**  
Resolved explicitly during Milestone 2 planning to prevent operational deactivation from being treated as deletion.

---

## ID-003 — HR Is Business-Scoped

**Decision:**  
HR is primarily a Business-level role rather than inherently belonging to one Branch.

The Business Owner can onboard HR for the Business.

A Business-level/head HR can manage relevant employee/manager workforce operations across the Business's Branches according to the permissions implemented for the role.

The data model should not require every HR user to belong to exactly one Branch merely in order to hold the HR role.

Branch-specific HR assignment may be supported where required, but it must not remove the Business-level HR concept.

**Reason:**  
Resolved during Milestone 2 planning before Employee/Staff Invitation & Onboarding implementation.

---

## ID-004 — Branch Assignment Preserves History

**Decision:**  
Branch assignment is modeled separately from Business membership.

A Business member may have historical Branch assignments, but may have only **one current Branch assignment at a time**.

The database enforces the one-current-assignment invariant for `business_member` using the appropriate PostgreSQL partial unique index/constraint.

Changing a member's Branch should preserve assignment history rather than overwrite the historical assignment.

The BranchAssignment schema was introduced in Milestone 2; assignment/transfer workflows are implemented when the relevant employee/staff onboarding functionality is introduced.

**Reason:**  
Resolved during Milestone 2 planning so Branch assignment history and transfer behavior are not represented as destructive updates.