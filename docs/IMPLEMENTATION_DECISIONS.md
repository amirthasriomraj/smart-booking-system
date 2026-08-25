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

---

## ID-005 — Invitation Representation and State

**Decision:**  
Staff invitations are represented using the existing `User` and `BusinessMember` entities. No separate `Invitation` entity is introduced; the frozen TAS's Part 3 entity list has no such table.

For a brand-new invitee (no existing `User` for that email), a `User` row and a `BusinessMember` row (`status = Pending`) are created immediately at invite time. Because `business_members.user_id` and `users.username`/`hashed_password` are `NOT NULL`, the new `User` row is created with a randomly generated, never-disclosed placeholder username and an unusable random password hash. These placeholders are overwritten only when the invitation is accepted; they are a mechanical consequence of existing non-null columns, not a business rule.

The invitation token (hash + expiry) is stored on `business_members`, not on `users` — the token belongs to a specific membership, not to the platform identity.

Whether an invitation requires the invitee to set new credentials on acceptance is recorded explicitly at invite time as a `requires_credential_setup` flag on `BusinessMember`. It is never inferred from `User.is_active` at acceptance time, because `User.is_active` is an existing, unrelated, independently-reachable account-lock flag (see ID-008) and is not a reliable signal of invitation state.

**Reason:**  
Resolved during Milestone 3 planning. The frozen PRD/TAS describe invitation only as "record created → invitation email → activation" (see Resource onboarding, PRD §14.5) without specifying the underlying data representation; this decision fixes that representation without adding new entities, and avoids an identity-corruption risk that a naive `User.is_active`-based inference would introduce.

---

## ID-006 — Business Owner Is the Sole Invitation Issuer in Milestone 3

**Decision:**  
Only the Business Owner may invite a Branch Manager or an HR User in Milestone 3. This is the literal reading of PRD §74's acceptance criteria, which name only the Business Owner for both invitations.

HR's PRD §10.4 "Employee onboarding / Employee invitations" responsibility, and the HR dashboard's "Invitations" module (PRD §35), are treated as applying to Resource invitations, which are Milestone 4 scope. HR does not gain any invitation-issuing capability in Milestone 3.

**Reason:**  
Resolved during Milestone 3 planning to remove ambiguity between PRD §10.2/§74 (Business-Owner-only, for Branch Manager/HR) and PRD §10.4 (HR "Employee invitations," unscoped) before implementation.

---

## ID-007 — Duplicate Invitation and Existing-User Reuse

**Decision:**  
A new invitation request is blocked (409) if the invited email already has an **Active or Pending** `BusinessMember` row at any business, per BR-022. An **Inactive** `BusinessMember` row never blocks a new invitation.

If the invited email matches an existing `User` that has no blocking (Active/Pending) membership, the existing `User` row is reused as-is. It is never recreated, and its username/password are never modified. The invitee still receives the normal emailed invitation token; accepting it activates the new `BusinessMember` without touching existing credentials.

Reactivating an **Inactive** `BusinessMember` row *in place* at the **same** business it belonged to is explicitly left unsupported and undecided in Milestone 3. The `(business_id, user_id)` unique constraint on `business_members` makes a second row for the same pair impossible regardless of status, and the frozen documents do not specify what in-place reactivation should do to `joined_at`/history. The invitation endpoint rejects a same-business re-invite with a clear error rather than a raw database constraint failure.

**Reason:**  
Resolved during Milestone 3 planning to make BR-022's business-membership rule concrete, and to avoid silently deciding same-business rehire semantics the frozen documents do not address.

---

## ID-008 — Minimal BusinessMember Deactivation Satisfies BR-022

**Decision:**  
Milestone 3 adds a minimal endpoint to set a `BusinessMember` row to `status = Inactive` (with `left_at` recorded). This exists specifically to satisfy BR-022's precondition — "employees may move to another Business only after their existing Business membership becomes inactive" — which otherwise has no mechanism anywhere in the frozen documents or prior milestones.

Deactivating a `BusinessMember` affects only that membership. It never modifies the associated `User` row's `is_active` flag or credentials. `User.is_active` is a pre-existing, independent platform-account-lock flag (used by the legacy admin `deactivate_user`/`activate_user` endpoints) and is deliberately kept orthogonal to business-membership status.

Once a membership is Inactive, the underlying `User` can be invited to a **different** business through the normal invitation flow (ID-007), reusing the same `User` identity without credential changes. This is BR-022's cross-business movement, implemented end-to-end rather than left half-built.

**Reason:**  
Resolved during Milestone 3 planning because the plumbing this sits on (`BusinessMember.status`, `BranchAssignment` closure) is already being built this milestone, and BR-022 would otherwise remain permanently unsatisfiable.

---

## ID-009 — Invitation Token Expiry and Resend

**Decision:**  
Invitation tokens expire 7 days after issuance. This duration is not specified anywhere in the frozen PRD/TAS (only password-reset expiry is mentioned); it was chosen explicitly during Milestone 3 planning.

A dedicated resend endpoint is provided for a `BusinessMember` row still in `Pending` status: it regenerates the invitation token and expiry and invalidates the previous token. This exists because neither the frozen documents nor any other decision here provide a way to recover a lost invitation email, and the duplicate-invitation rule (ID-007) would otherwise leave a Pending invitation permanently unrecoverable.

**Reason:**  
Resolved during Milestone 3 planning; both the expiry duration and the existence of resend were confirmed as genuine gaps in the frozen documents requiring an explicit decision rather than an assumed default.

---

## ID-010 — Branch Manager Assignment Timing

**Decision:**  
A Branch Manager invitation's target branch must have `approval_status = Approved` at invite time; `is_active` does not affect eligibility (PRD §10.3: "administers a single approved branch"). This eligibility is re-checked when the invitation is accepted, since a Pending invitation may remain outstanding for up to 7 days (ID-009).

The `BranchAssignment` row for an invited Branch Manager is created only when the invitation is **successfully accepted**, not at invitation time. Until then, `BusinessMember` records the intended branch in a temporary `invited_branch_id` field (`NULL` for HR User invitations, which never receive a Branch Manager assignment — see ID-003). `invited_branch_id` is not itself a `BranchAssignment`; it is cleared once the real `BranchAssignment` row (`is_current = true`, `assigned_from` = acceptance time) is created.

**Reason:**  
Resolved during Milestone 3 planning. Neither the PRD, the TAS, nor ID-004 specifies when in the lifecycle a `BranchAssignment` row must exist; they describe an actual, currently-serving Branch Manager, not an unaccepted invitee. Creating `is_current = true` at invite time would misrepresent an unaccepted invitation as a real, in-effect assignment and leave a permanently "current" row if the invitation is never accepted — the same kind of status-conflation ID-001 was written to avoid for Branch approval versus operational activation.

---

## ID-011 — Branch Manager Transfer Is Milestone 3 Scope

**Decision:**  
Branch Manager transfer (moving an Active Branch Manager from one Approved Branch to another while preserving assignment history) is implemented as part of Milestone 3, not deferred.

**Reason:**  
This is not a new decision but a scheduling confirmation of ID-004, which already states that "assignment/transfer workflows are implemented when the relevant employee/staff onboarding functionality is introduced" — i.e., this milestone. Recorded here explicitly during Milestone 3 planning so milestone scope is not re-derived from the ID-004 cross-reference alone.

---

## ID-012 — Resource Tenant Ownership (`business_id`)

**Decision:**  
`Resource` includes an explicit `business_id` column, denormalized from `branch.business_id` at creation, in addition to `branch_id`. `business_id` is set once at creation from the owning branch and is not independently mutable.

This resolves an internal inconsistency in the frozen TAS: §7's `Resources` column list omits `business_id`, while the TAS's "Entities requiring business_id" list explicitly names `Resource` and `Resource Category` as tenant-owned entities requiring it.

**Reason:**  
Resolved during Milestone 4 planning to make Resource conform to the platform's tenant-isolation architecture (PRD §28, TAS business_id-isolation rule) and to allow efficient business-wide Resource queries (e.g. Business Owner "manage all resources") without requiring a join through `branches` on every request — consistent with how `Branch` and `AuditLog` already carry `business_id`.

---

## ID-013 — Resource Scheduling/Configuration Attributes: Stored in Milestone 4, Enforced in Milestone 7

**Decision:**  
Milestone 4 adds storage for the V1-mandatory Resource scheduling/configuration attributes that the frozen TAS's `ResourceWorkingHours` table has no columns for: `Resource.max_bookings_per_day`, `Resource.booking_buffer_minutes`, and `ResourceWorkingHours.break_start_time` / `break_end_time` (one break window per weekday row).

These columns are configuration/storage only in Milestone 4. Enforcing them against actual bookings (validating buffer time, break conflicts, or daily booking caps) is Booking Engine scope (Milestone 7) and is not implemented here.

**Reason:**  
Resolved during Milestone 4 planning because PRD §14.3 mandates these as required Resource attributes for V1, but the frozen TAS's Resource Working Hours schema does not define columns for them. Per CLAUDE.md, mandatory V1 requirements are not silently deferred, so the fields are added now even though their enforcement logic belongs to a later milestone.

---

## ID-014 — Resource User Invitation and Linking Lifecycle

**Decision:**  
Resource User invitations reuse the Milestone 3 `BusinessMember` invitation mechanism (token hash/expiry, `requires_credential_setup`, `/auth/accept-invitation`), with `RESOURCE_USER` added to `INVITABLE_ROLE_CODES`.

A nullable `BusinessMember.linked_resource_id` (FK → `resources`) stages which `Resource` row an in-flight Resource User invitation belongs to, mirroring the `invited_branch_id` staging pattern introduced for Branch Manager invitations in ID-010. On successful acceptance, `Resource.linked_user_id` is set to the accepted `User`'s id and `BusinessMember.linked_resource_id` is cleared.

A Resource with `requires_login = true` cannot transition to `status = Active` until this linkage has completed (i.e. `linked_user_id` is populated). A Resource with `requires_login = false` may be activated without ever having a linked User.

Later deactivating the linked `BusinessMember` (revoking Resource User login) does not automatically change `Resource.status` — Resource schedulability and Resource User login access are tracked independently, the same way ID-008 keeps `User.is_active` independent of `BusinessMember.status`.

**Reason:**  
Resolved during Milestone 4 planning. Neither the PRD nor TAS specifies how an accepted invitation maps back to a specific Resource record, nor whether a login-required Resource may be activated before its invitation is accepted. This decision fixes both gaps: it follows PRD §14.4's Resource Lifecycle diagram, which places "(Optional) Invite Login" before "Activate," and it preserves the status-orthogonality principle ID-008 established for staff invitations.

---

## ID-015 — Resource Category Ownership and Lifecycle Scope

**Decision:**  
Resource Category create/update is Business Owner-only. Branch Manager and HR User have read-only access to Resource Categories, limited to what their authorized Resource workflows require (e.g. populating a category picker); they cannot create or modify categories.

Milestone 4 implements Resource Category create/list/update only. No delete, archive, or status field/behavior is introduced for Resource Category.

**Reason:**  
Resolved during Milestone 4 planning. PRD §14.2 states only that "each Business defines its own Resource Categories," without naming which role performs that action; this decision resolves it by analogy to Service Templates, another business-level entity that PRD §10.2 makes Business-Owner-only. The frozen TAS schema for Resource Category has no status/archive column, so no delete/archive behavior is invented for it.

---

## ID-016 — Resource Management Authorization Matrix

**Decision:**  
Resource management authority in Milestone 4 is:

- Business Owner: business-wide Resource record CRUD/configuration/status across every branch in their business, Resource Category create/update, and Resource User invite/resend/deactivate for any resource in their business.
- Branch Manager: the same Resource record CRUD/configuration/status and Resource User invite/resend/deactivate operations, restricted to their currently assigned branch only; read-only on Resource Categories.
- HR User: business-wide Resource User account administration (invite/resend/deactivate) plus the read access necessary for that workflow; no Resource record, Resource Category, or configuration CRUD.
- Platform Administrator: no tenant Resource-management operations, consistent with PRD §10.1's restriction against participating in tenant day-to-day operations.

**Reason:**  
Resolved during Milestone 4 planning. PRD §10.2/§10.3 grant Business Owner and Branch Manager overlapping but not identically-worded Resource permissions ("Manage all resources" vs. "Invite Resources with login access" / "Create Resources without login"), and PRD §10.4's Human Resource "Resource login management" responsibility is unscoped as to whether it extends to full Resource CRUD. This decision makes the split explicit and final, extending ID-006's reading (HR's invitation-issuing authority applies to Resource invitations from Milestone 4 onward) to a complete authorization matrix.

---

## ID-017 — Resource.requires_login Is Immutable After Creation

**Decision:**  
`Resource.requires_login` is set once at creation and cannot be changed afterward; `ResourceUpdateRequest` (the Resource configuration PATCH) does not accept it as a field.

**Reason:**  
Resolved during Milestone 4 review. Neither the frozen PRD nor TAS explicitly states whether `requires_login` may change after creation. PRD §14.5 ("Resource Creation") describes the login-credentials choice as made "if the creator chooses" at creation time, which supports immutability, while PRD §14.4's lifecycle (Create → Configure → (Optional) Invite Login → Activate) leaves room to read it as still adjustable during "Configure." Presented to the user as three options — immutable after creation, mutable only while Pending, or freely mutable — because any mutable option requires inventing undefined behavior for what happens to an in-flight invitation or an already-linked Resource User when the flag changes. The user chose immutable after creation, avoiding that invented behavior entirely.