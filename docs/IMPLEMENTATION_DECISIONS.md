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

---

## ID-018 — No Template-less Branch Services

**Decision:**  
Every `BranchService` always references a `ServiceTemplate` (`service_template_id` is `NOT NULL`). There is no path to create a Branch Service that does not originate from a Business-level Service Template.

PRD §10.3's "Create branch-specific services" and §25.2's "New Branch Services" (as a category requiring Business-Level Approval) are read as the Branch Manager's *first-time customization* of an already-inherited service, not creation of a service from scratch.

**Reason:**  
Resolved during Milestone 5 planning. PRD §15.2 states "Branch Services maintain a reference to their originating template," which is incompatible with a template-less Branch Service. The alternative reading (a nullable `service_template_id` with the Branch Manager manually supplying name/duration/price) would require inventing fields, validation, and an approval shape the frozen documents never define for that case. The user chose to keep every Branch Service template-derived.

---

## ID-019 — Service Template Is Create-Once; No Field-Level Edit After Creation

**Decision:**  
`ServiceTemplate` supports Create, Read, and an Active/Inactive status toggle only. There is no general update endpoint for name, description, duration, price, default resource categories, default buffer time, or default working rules after creation. To change a template's definition, the Business Owner creates a new template; the old one can be set Inactive.

**Reason:**  
Resolved during Milestone 5 planning. TAS Part 4 §5 (Service Inheritance Engine) states "Templates remain immutable" as its own unqualified design principle, separate from the neighboring "Branch overrides do not modify the original template" bullet — treated as the general rule, not a restatement scoped only to branch-override protection. No PRD passage anywhere uses "edit," "update," or "archive" in connection with a template. PRD §10.2's Responsibilities list names only "Create business-level service templates" for the Business Owner; the separate, generic "Edit services. Archive services." Permissions bullet never says "templates" and is read as applying to Branch Services, which the Business Owner already controls business-wide. The user confirmed this reading over the alternative of a general Template PATCH, which would also have reopened an undefined question of whether such edits sync to already-inherited Branch Services.

---

## ID-020 — Branch Service Status Has No Separate "Active" State

**Decision:**  
`BranchService.status` is a 5-value enum: `Draft`, `Pending Approval`, `Approved`, `Suspended`, `Archived`. `Approved` is itself the live/bookable state — there is no separate `Active` value and no action that transitions a Branch Service from `Approved` to some further `Active` state. `pending_approval` (TAS §8) remains a separate boolean, independent of `status`.

No Milestone 5 action is wired to reach `Suspended` (no rule names an actor who may suspend a Branch Service) or `Archived` (PRD §15.5 itself marks this "(Future)"). Both values exist in the column only for naming-fidelity with §15.5's lifecycle diagram. `Draft` is likewise never produced by any Milestone 5 workflow, since inheritance always creates an `Approved` row (ID-023) and ID-018 rules out from-scratch creation.

**Reason:**  
Resolved during Milestone 5 planning. Every booking-validation checklist in the frozen PRD tests Service against exactly one gate — "Service is Active" (§16.3, §16.5) or "Service is Approved" (§15.5, §24, BR-033, BR-043) — never both together in the same list, unlike Branch, where §24/§16 explicitly list "Branch is Approved" **and** "Branch is Active" as two separate checks. No rule names any actor or action for a manual Approved→Active transition for Branch Service, unlike Resource (explicit `activate`/`suspend` actions) or Branch (Business-Owner-controlled `is_active`). Treating Approved and Active as independently meaningful, separately-controlled states was considered and rejected as an unsupported analogy to Branch's ID-001 split.

---

## ID-021 — Pending Override Storage: Structured JSONB Snapshots on ServiceApproval

**Decision:**  
`BranchService` holds only the current effective configuration (`duration`, `price`, and its live Resource Category assignments). `ServiceApproval` holds `previous_configuration` and `proposed_configuration` as structured JSONB snapshots (each containing `duration`, `price`, `resource_category_ids`), in addition to its TAS-defined columns (`branch_service_id`, `requested_by`, `approved_by`, `decision`, `comments`, `decided_at`).

Submitting an override creates a `ServiceApproval` row (`decision = Pending`) with `previous_configuration` set to the Branch Service's current live values and `proposed_configuration` set to the requested values, and sets `BranchService.pending_approval = true`. Live columns are untouched at submission time.

On approval: `proposed_configuration` is copied onto the live `BranchService` columns, `pending_approval` is cleared, and the `ServiceApproval` row (with both snapshots) is retained as history.

On rejection: live columns are left untouched, `pending_approval` is cleared, and the `ServiceApproval` row is retained as history.

The JSONB columns use `JSONB().with_variant(JSON(), "sqlite")` for test-database compatibility, consistent with the existing dual-dialect pattern used for `BranchAssignment`'s partial unique index.

**Reason:**  
Resolved during Milestone 5 planning. TAS §8's `service_approvals` column list has no field for the proposed values, yet PRD §15.4/BR-034 require the existing approved configuration to keep operating, untouched, until a decision is made — which is only possible if the proposed values are held separately from the live configuration. A shadow-columns-on-`BranchService` alternative was considered; the user chose a structured JSONB snapshot on `ServiceApproval` instead, so the approval record remains a complete, self-contained historical account after the decision, and `BranchService` continues to hold only ever the currently effective configuration.

---

## ID-022 — "Service Availability Changes" Is Out of Milestone 5 Scope

**Decision:**  
Of PRD §15.4's four "Examples requiring approval," only three are implemented as overridable, approval-gated fields in Milestone 5: **Price, Duration, and Resource Category assignment.** "Service availability changes" is not implemented as a Branch Service field, and no Suspend/Reinstate-via-approval workflow is built for Branch Service in Milestone 5.

**Reason:**  
Resolved during Milestone 5 planning. Every other occurrence of "availability" tied to Service in the frozen documents is a booking-time/runtime concept (PRD §19.2 Reschedule Rules; TAS Part 4 §3 Availability Engine, "Determines whether a requested booking slot is available... never creates bookings") — explicitly Milestone 7 scope per `IMPLEMENTATION_PLAN.md`'s own Milestone 5 guardrail against pulling booking/availability behavior forward. No rule defines a Suspend/Reinstate action for Branch Service, names who could trigger one, or resolves how it would coexist with §15.4's "existing approved configuration continues to operate until approval" (a pending suspend request would otherwise have to remain bookable, which is incoherent). The user confirmed treating the fourth bullet as forward-referencing the Booking Engine's runtime concept rather than inventing an undocumented status-change workflow.

---

## ID-023 — Service Inheritance Covers Both Creation Orders

**Decision:**  
A `BranchService` (status `Approved`, uncustomized, copied from the template's current defaults) is created in both directions:

(a) When a Branch is created, for every current Active Service Template of the business.
(b) When a Service Template is created (and set Active), for every existing Branch of the business.

Both directions apply regardless of the Branch's own `approval_status`/`is_active` state. Neither direction requires Business Owner approval, since an unmodified inherited copy is not a "customization."

**Reason:**  
Resolved during Milestone 5 planning. Direction (a) is explicit — PRD §15.2 ("When a Branch is created: It automatically inherits every Service Template from the Business") and BR-030. Direction (b) is not stated as directly, but is supported by TAS Part 4 §5's Service Inheritance Engine being named a "synchronization" responsibility ("Maintains synchronization between Business Service Templates and Branch Services") with a workflow diagram sequenced "Business Owner creates Service Template → Branch inherits template." Applying regardless of Branch approval/active state follows from PRD §25.4, which explicitly permits "Services can be configured" while a Branch is Pending Approval, mirroring the Milestone 4 Resource-creation precedent. The user confirmed implementing direction (b) despite it resting on inference rather than a literal rule, given the Engine's own stated "synchronization" responsibility.

---

## ID-024 — `business_id` Denormalization on Service Template and Branch Service

**Decision:**  
`service_templates.business_id` (direct owner) and `branch_services.business_id` (denormalized from `branch.business_id` at creation, immutable thereafter) are added as columns, matching the pattern already established for `Resource` in ID-012.

**Reason:**  
Resolved during Milestone 5 planning. TAS's "Entities requiring business_id" list explicitly names both Service Template and Branch Service, but the TAS §8 column lists for both omit it — the same internal inconsistency ID-012 already resolved for Resource. Needed for tenant isolation and business-wide queries without a join through `branches` on every request.

---

## ID-025 — Service Template's Undefined Mandatory Fields Are Storage-Only

**Decision:**  
`ServiceTemplate.default_buffer_minutes` is a plain nullable integer. `ServiceTemplate.default_working_rules` is a nullable JSONB column with no defined internal structure, no enforcement, and no booking/availability logic built on it in Milestone 5. Both are exposed as opaque values through the Service Template create/read APIs. No `ServiceWorkingHours`-style table is introduced.

**Reason:**  
Resolved during Milestone 5 planning, mirroring ID-013's precedent for Resource. PRD §15.1 mandates "Default Buffer Time" and "Default Working Rules" as required Service Template fields, but TAS §8's Service Template column list has neither. Buffer Time is unambiguous (a number, enforcement is Milestone 7 scope like `Resource.booking_buffer_minutes`). Working Rules has no defined structure anywhere in either frozen document, unlike Default Resource Categories (clearly a category link) — so it is stored opaquely rather than inventing a schedule structure the documents never describe.

---

## ID-026 — Service Template Deactivation Does Not Cascade

**Decision:**  
Setting `ServiceTemplate.status = Inactive` only stops it from propagating/syncing to branches going forward (per ID-023). Branch Services already created from it are completely unaffected and keep their own independent status until a Business Owner or Branch Manager acts on them directly.

**Reason:**  
Resolved during Milestone 5 planning. No rule anywhere addresses what happens to already-inherited Branch Services when their source Template is later deactivated. Resolved consistently with the platform's established non-cascading precedent across independent lifecycle flags: ID-002 (Branch `approval_status`/`is_active`), ID-008 (`BusinessMember.status`/`User.is_active`), and ID-014 (`Resource.status`/linked `BusinessMember.status`).

---

## ID-027 — Service Management Authorization Matrix

**Decision:**  
Service Management authority in Milestone 5 is:

- Business Owner: Service Template create + Active/Inactive toggle, business-wide; direct edit (`price`, `duration`, Resource Category assignment) of any Branch Service in their business, taking effect immediately with no approval step; decide (approve/reject) pending Branch Service overrides.
- Branch Manager: submit Branch Service override proposals (`price`, `duration`, Resource Category assignment), restricted to their currently assigned branch only; cannot approve their own submissions.
- HR User: no Service Management access of any kind.
- Platform Administrator: no tenant Service-management operations.

**Reason:**  
Resolved during Milestone 5 planning, following the ID-016 format established for Resource Management. Business Owner authority follows PRD §10.2 ("Create business-level service templates," "Approve branch service overrides," full administrative control over every branch). Branch Manager scoping follows PRD §10.3 and §26.3 ("cannot... Modify another branch's services"); the inability to approve one's own submission is structural, since only the Business Owner path can decide (§10.3: "cannot approve their own service modifications"). HR exclusion follows from PRD §10.4 naming no Service Management responsibility for HR. Platform Administrator exclusion follows PRD §10.1's restriction against participating in tenant day-to-day operations.

---

## ID-028 — Cross-Business Platform Customer Identity

**Decision:**  
The Customer model follows TAS §6's `PlatformCustomer`/`BusinessCustomer` split: one `PlatformCustomer` (platform identity, linked 1:1 to a `User`) may have multiple `BusinessCustomer` relationship records, one per business it has interacted with. A single Customer account may authenticate once and interact with multiple, independent businesses, consistent with BR-039.

PRD §10.6/§11's "Customer accounts are isolated per business... Version 1 does not include a global customer identity shared across businesses" is treated as superseded, less-precise narrative language, resolved in favor of TAS §6's explicit column-level schema, BR-039's formally numbered rule, and `IMPLEMENTATION_PLAN.md`'s own Milestone 6 scope line, which names the Platform/Business Customer model directly.

**Reason:**  
Resolved during Milestone 6 planning to remove a direct contradiction between §10.6/§11 and §17.4/BR-039/TAS §6. The later, more specific and detailed sources were preferred over the earlier summary language, consistent with how prior milestones resolved internal PRD/TAS gaps (e.g. ID-012, ID-018).

---

## ID-029 — Customer Personal Profile Fields Live on `UserProfile`

**Decision:**  
PRD §17.2's Personal Information (First Name, Last Name, Gender, Date of Birth), Contact Information (Mobile Number, Email), and Address Information (Address Line, City, State, Country, Postal Code) fields are not represented anywhere in TAS §6's `PlatformCustomer`/`BusinessCustomer` schema. These fields are added as new nullable columns (`gender`, `date_of_birth`, `address_line`, `city`, `state`, `country_id`, `postal_code`) on the existing `UserProfile` table, which already holds `first_name`/`last_name`/`phone` for every `User` (previously staff-only). `PlatformCustomer` remains TAS-literal (`user_id`, `preferred_language`, `preferred_timezone`, `created_at`) and does not duplicate identity fields.

**Reason:**  
Resolved during Milestone 6 planning. `UserProfile` already exists as the 1:1 "person profile" table keyed by `user_id`; extending it with nullable, additive columns avoids inventing a second first/last-name field on `PlatformCustomer` and follows CLAUDE.md's reuse-existing-patterns guidance. Putting the fields on `BusinessCustomer` instead was rejected because it would duplicate personal data per business relationship, contradicting TAS §6's own "while keeping one platform login" framing.

---

## ID-030 — Every Customer, Including Walk-Ins, Has a Backing User/PlatformCustomer

**Decision:**  
Every `BusinessCustomer` row always references a `PlatformCustomer` (`platform_customer_id` is `NOT NULL`); there is no "login-less" Customer record. For a staff-created walk-in customer with no existing platform identity, a `User` row is created using the same mechanical placeholder mechanism already established for staff invitations (ID-005): a randomly generated, never-disclosed placeholder username (`secrets.token_hex(8)`-based) and an unusable random password hash. These placeholders are overwritten only if the person later sets real credentials (e.g. via self-registration reuse, ID-031).

**Reason:**  
Resolved during Milestone 6 planning, directly extending the already-approved ID-005 precedent to a new actor type rather than inventing an undefined "claim account later" linking workflow. This is also what makes BR-039's cross-business account portability work uniformly regardless of whether the first business relationship originated from self-registration or staff creation.

---

## ID-031 — Customer Identity Reuse and Collision Rules

**Decision:**  
- **Walk-in creation:** if the supplied email matches an existing `User`, that `User`/`PlatformCustomer` is reused as-is (mirroring ID-007) and only a new `BusinessCustomer` row is created for the current business. If no email is supplied, a new placeholder identity (ID-030) is always created — mobile number is never used as an identity-matching key, since it is not a documented identity field and is not guaranteed unique.
- **Self-registration:** if the supplied email matches an existing **placeholder** `User` (one created via walk-in creation and never claimed), that row's username/password are overwritten with the newly supplied real credentials in place (mirroring ID-005's "placeholders overwritten only when accepted" language), rather than the registration failing on a unique-email conflict. If the email matches an existing **non-placeholder** (already-claimed) account, registration fails normally (409).
- `BusinessCustomer` carries `UniqueConstraint(business_id, platform_customer_id)`, mirroring `business_members`' existing `UniqueConstraint(business_id, user_id)`.

**Reason:**  
Resolved during Milestone 6 planning. No PRD/TAS text defines customer email/mobile uniqueness or reuse rules at all (confirmed absent by repo-wide search of the frozen documents). This decision is the minimal extension of the already-approved ID-005/ID-007 staff-identity precedent to the Customer actor type, avoiding any new, undocumented mechanism.

---

## ID-032 — Customer Management Is Business-Scoped, Not Branch-Scoped

**Decision:**  
`BusinessCustomer` carries no `branch_id` and no branch-ownership concept. Both Business Owner and Branch Manager have business-wide Customer Management authority (list/search/create/edit/status) across the entire business, not restricted to a single branch. PRD §26.3's "cannot... View another branch's customers" is read as forward-referencing the booking-level branch attribution that will exist once Booking (Milestone 7) links Customer↔Branch, not as a Milestone 6 Customer-record restriction — consistent with PRD §17.1's explicit framing of Customer as a *business*-specific entity, and with §10.3's own unqualified Permissions wording ("Create Customers. Edit Customers.") over its looser Responsibilities phrasing ("branch customers").

**Reason:**  
Resolved during Milestone 6 planning. TAS §6's `BusinessCustomer` schema has no branch column, so a branch-restricted reading would require inventing both a new denormalized field and its visibility semantics — a mechanism no PRD/TAS text defines. The business-scoped reading requires no invented schema and matches the literal TAS Customer model exactly.

---

## ID-033 — `customer_number` Generation

**Decision:**  
`BusinessCustomer.customer_number` is system-generated at creation as `f"CUST-{business_customer.id:06d}"`, obtained via `db.flush()` to read the row's DB-assigned auto-increment `id` before commit — the same flush-then-read-PK pattern already used elsewhere in the codebase (`crud_business.py`, `crud_resource.py`, `crud_service.py`, `crud_branch.py`). `UniqueConstraint(business_id, customer_number)` is added as a DB-level safety net; because `id` is a global auto-increment, the generated value is in practice globally unique, a strictly stronger guarantee than the required per-business uniqueness.

**Reason:**  
Resolved during Milestone 6 planning. TAS §6 lists `customer_number` as a column with no generation or format rule, and no existing project convention for generated human-readable codes exists (`Resource.code`, the closest analog, is a plain optional user-supplied field with no generation logic). A sequential-per-business counter was considered and rejected because it would require either a race-prone `SELECT MAX+1` or a new sequence-tracking table/column — an invented stateful mechanism the frozen documents don't call for. Reusing the existing flush-then-read-PK idiom is collision-safe by construction and introduces no new mechanism.

---

## ID-034 — Customer Self-Registration Uses a Dedicated Endpoint

**Decision:**  
Customer self-registration is implemented as a new `POST /customers/register` endpoint, creating `User` + `UserProfile` + `UserRole(CUSTOMER)` + `PlatformCustomer` in one transaction, with fields matching PRD §17.5 (First Name, Last Name, Email, Mobile, Password). The existing legacy `POST /auth/register` (pre-refactor flat-model endpoint, creating a bare `User(role="user")` with no profile/role/tenant linkage) is left completely unchanged.

**Reason:**  
Resolved during Milestone 6 planning. `/auth/register` is still actively exercised by existing regression tests (`test_bookings.py`, `test_password_reset.py`, `test_auth.py`, `test_staff.py`) and produces a different, non-tenant-aware `User` shape than what PRD §17.5 requires for Customer registration; repurposing it in place would risk breaking existing passing tests, violating CLAUDE.md's "preserve existing working functionality" rule. A new dedicated endpoint has no such risk.