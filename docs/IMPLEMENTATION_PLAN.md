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

**Status: COMPLETED**

Implementation is already merged into `main`.

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

**Status: COMPLETED**

Implementation is already merged into `main`.

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

**Status: COMPLETED**

Implementation is already merged into `main`.

Delivered:

- Replaced/generalized the legacy booking structure as required by V1
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

Branch booking eligibility respects the approved Branch lifecycle rules recorded in `IMPLEMENTATION_DECISIONS.md`.

---

## Milestone 8 — Payments, Financial Policies & Promotions

**Status: COMPLETED**

Implementation is already merged into `main`.

Scope approved via the M8 pre-freeze audit and `IMPLEMENTATION_DECISIONS.md` ID-044–ID-056, which promote this functionality from the frozen PRD/TAS's Version 2/deferred scope into V1 (ID-044). The frozen PRD/TAS are not rewritten; ID-044–ID-056 are the authoritative record of what changed and why.

Scope:

- Razorpay online payment integration (Test Mode for development; production Route activation tracked as a separate deployment prerequisite per ID-055)
- Cash/offline and direct-external payment recording
- `BookingHold` domain concept and concurrency-safe hold acquisition (ID-046), independent of `Booking.status` (ID-045)
- Customer checkout flow (6-minute hold) and staff-side checkout flows: interactive/walk-in cash, emailed payment link, direct external payment, Reserve Without Payment (10-minute holds where applicable, per ID-046)
- Security deposit collection, 7-day eligibility rule, and balance-payment lifecycle (72-hour reminder, 48-hour deadline)
- Automatic 48-hour balance-default cancellation and deposit forfeiture (ID-048) — the platform's first system-triggered booking cancellation
- Customer cancellation refund-bracket policy; customer reschedule 24-hour/one-time limit; unrestricted staff override with mandatory reason (ID-047, superseding ID-035's "identical rules" clause)
- Reschedule price-difference collection/refund
- Manual base-price and final-price overrides with full audit trail
- Coupons/promotions: configuration, business-wide and branch-specific (approval-gated) scope, redemption, concurrency-safe usage-limit enforcement (ID-056)
- Refunds: calculated refund, authorized override, and gateway-vs-manual refund routing (ID-053)
- Platform online-transaction-fee configuration, inheritance, per-booking snapshot, and proportional earn/reversal (ID-051); gateway/provider fees and tax kept distinct and not invented (ID-052)
- Financial audit/history covering the full event lifecycle (hold created/expired, payment initiated/succeeded/failed, deposit paid, balance reminder sent, balance paid, balance defaulted, coupon applied, price overridden, refund calculated/overridden/completed, etc.)
- Background/scheduled job infrastructure: Celery + Redis + Celery Beat (ID-049), reused by Milestone 9
- Financial concurrency and idempotency guarantees, including safe handling of payment success after hold expiry (ID-056)
- M8-scope financial notifications and any notification/email-log persistence needed for their reliability/auditability (ID-050 — see Milestone 8 / Milestone 9 Notification Boundary below)
- Required backend/frontend functionality and tests

Do not implement Loyalty programs, Memberships, SMS/WhatsApp notifications, subscription billing, multi-currency pricing, or any other V2/deferred item not explicitly named above or in ID-044.

### Milestone 8 / Milestone 9 Notification Boundary (ID-050)

Milestone 8 owns every notification directly caused by M8 financial/payment behavior: payment-link email, full-payment confirmation, deposit-payment confirmation, 72-hour balance reminder, balance-paid/fully-paid confirmation, 48-hour balance-default cancellation notice, deposit-forfeiture notice, cancellation/refund financial outcome, refund initiated/completed notices, reschedule financial-adjustment notices, and staff-side financial cancellation/reschedule notices. If reliable delivery/auditability of these requires persisting notification/delivery state (the `Notifications`/`Email Logs` tables TAS Part 3 §10 defines but that were never built through M7), that foundation is built here, in Milestone 8 — not deferred to Milestone 9. Milestone 9 retains only the remaining non-financial V1 notifications and general notification hardening; there is exactly one notification subsystem, not two.

### Milestone 8 Required Infrastructure

Celery, Celery Beat, and the project's existing Redis instance are added as the background/scheduled-job foundation (ID-049), used for the 72-hour reminder, the 48-hour balance-deadline enforcement, expired-hold cleanup, and other retryable financial/notification work. Every scheduled task re-validates current database state before mutating a booking/hold/payment and is idempotent.

### Milestone 8 Acceptance Verification

Full backend regression suite: **313 passed, 1 skipped, 0 failed** (including the two previously flaky `test_m8_cancellation_reschedule.py` tests, fixed to derive appointment date/time from a single computed datetime instead of splitting `date.today()` from a separately-offset `.time()`, which discarded midnight-rollover — a test-only fix, no production behavior changed).

Live, real Razorpay Test Mode verification (not just mocked/unit-tested) was performed end-to-end against the actual customer UI and a live Razorpay Test Mode account:

- Confirmed the backend correctly reads `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` / `RAZORPAY_WEBHOOK_SECRET` and authenticates against Razorpay's API (read-only call), with no secret values ever exposed.
- Confirmed, live, that selecting a service/date/time and coupon/summary refreshes create/refresh only the `CustomerCheckout` `BookingHold` and never contact Razorpay — order creation happens only at the customer's own "Proceed to Pay" action, exactly per ID-046/ID-054.
- Completed a real customer checkout through the actual frontend: hold → Razorpay order creation → Razorpay Checkout (Test Mode) → domestic test-card payment → server-side capture verification (`fetch_payment` status check, not signature alone) → `Booking` Confirmed + `BookingFinancial` `FullyPaid` with the correct amount.
- Stood up a real webhook endpoint (ngrok tunnel to the local nginx entrypoint, `RAZORPAY_WEBHOOK_SECRET` configured) and confirmed a live, Razorpay-signed `payment.captured` delivery was correctly received, signature-verified, deduplicated by `provider_event_id`, and reconciled.
- **Finalization-race defect found and fixed during this live verification (closing a gap in ID-056):** once the webhook was live, it and a client-triggered finalization (customer `/verify`, or staff manual confirm) could both call `_finalize_hold_to_booking` for the same hold/payment. Whichever call arrived second saw the hold already `Completed` and — before the fix — was treated as a genuinely lost/expired hold, triggering an automatic Razorpay refund of a payment that had, in fact, already paid for a real Confirmed booking. Fixed in `crud_payment._finalize_hold_to_booking` by making finalization idempotent on `payment.booking_id`: a payment already linked to a booking short-circuits to that existing booking rather than re-entering the lost-hold branch. The genuine lost/expired-hold auto-refund path (payment captured against a hold that never won any finalization) is unchanged and still covered by the pre-existing `test_payment_after_lost_hold_triggers_automatic_refund_not_double_booking`. Regression-tested both race directions (webhook-first and verify-first) in `backend/tests/test_m8_finalization_race.py`, confirming no duplicate `Booking`/`Payment` and no spurious `Refund` in either direction. Re-verified live afterward: a subsequent Test Mode payment captured, was reconciled by the webhook, and produced exactly one Confirmed booking with no refund.

---

## Milestone 9 — V1 Notifications, Hardening & Final Integration

**Status: PLANNED**

(Renumbered from the original Milestone 8 to accommodate Milestone 8 — Payments, Financial Policies & Promotions, inserted ahead of it per the M8 pre-freeze audit decision.)

Complete remaining mandatory V1 cross-cutting functionality. Scope below is organized into phases following a pre-implementation gap analysis against the frozen PRD/TAS and the current Milestone 1–8 implementation; it narrows nothing frozen and adds nothing beyond what the PRD/TAS already require. `IMPLEMENTATION_DECISIONS.md` remains authoritative and is unchanged by this update except where a phase below explicitly notes a decision still to be recorded there.

### Milestone 9 Phase 1 — Soft-Delete / Status-Lifecycle Corrections

- Business suspend/reactivate: Platform Admin can transition a Business `Active -> Suspended -> Active`. Booking-blocking for non-Active businesses already exists; this phase adds the crud functions, endpoints, and audit actions (`BUSINESS_SUSPENDED`/`BUSINESS_REACTIVATED`), plus admin frontend UI, mirroring the existing Resource suspend/activate pattern.
- Business Category admin CRUD: create, update, and activate/deactivate only — no delete/archive (PRD: "The list is configurable by the Platform Administrator"; mirrors the minimal-CRUD precedent already used for Resource Category, ID-015).
- `User.is_active` admin surface: confirmed already complete and working (existing legacy endpoints, tested, per ID-008). No PRD/TAS requirement exists for a frontend surface — **excluded from M9 scope**.

### Milestone 9 Phase 2 — Audit Coverage Completion

- Add an audit log entry to the password-reset flow (PRD §30 "Password Reset" is a listed auditable event; the reset feature exists today but writes no audit entry).
- Role/Permission Changes (PRD §30): confirmed **N/A for V1** — no role-reassignment feature exists anywhere in the codebase, and the TAS states V1 deliberately assigns one fixed role per identity. This is a decision, not a build item; to be formally recorded in `IMPLEMENTATION_DECISIONS.md` when M9 decisions are finalized.

### Milestone 9 Phase 3 — Password-Policy Correction

- Add the missing special-character rule to the shared password validator (PRD §33.3's five-part policy — length/upper/lower/number/special-character — is only four-fifths enforced today). One shared fix applies uniformly across registration, password reset, invitation acceptance, and customer registration, since all four paths already funnel through the same validator.

### Milestone 9 Phase 4 — Notifications

- Implement the 6 missing non-financial notification triggers required by PRD §23/§37: Welcome Email (registration), Invitation Accepted, Business Approved, Business Rejected, Branch Approved, Branch Rejected. (Financial notifications remain Milestone 8 scope per the Notification Boundary above; the remaining 7 non-financial triggers — booking confirmation/cancellation/reschedule/completion, service override submitted/approved/rejected — are already implemented.)
- Extend notification persistence to all non-financial notifications, both the 6 new ones and the 7 already-implemented ones, by routing them through the same Notification/Email Log persistence mechanism Milestone 8 already built and currently uses only for financial events. This closes a gap against PRD §83's general acceptance criterion ("Notification history is recorded for auditing purposes"), which is not scoped to financial events only.
- General notification hardening continues to reuse the Celery + Redis + Celery Beat infrastructure introduced in Milestone 8 (ID-049) rather than a second mechanism.

### Milestone 9 Phase 5 — Search / Filter / Pagination

- Add search, filter, and pagination to the Resource, Booking, Service, Branch, and Business (Platform Admin) list endpoints per PRD §38–§40 (currently these endpoints accept little to no query parameters).
- Complete the Customer list endpoint: add the missing Active/Inactive filter, and normalize pagination to the standard `page`/`page_size`/`total`/`total_pages` shape (it currently uses a nonstandard `limit`/`offset`/`total` shape with no `total_pages`).

### Milestone 9 Phase 6 — Dashboard Foundation

- Build the per-role dashboard modules named in PRD §35, using Phase 5's list endpoints for list-based modules and the PRD §36 reporting metrics for Reports/Daily Reports modules. No per-role dashboard shell currently exists; role differentiation today happens only at the navigation-link level.
- Add a Business Profile view/edit surface (backend update endpoint + frontend page), per PRD §72's explicit acceptance criteria ("Business profile can be viewed" / "can be updated") — this surface does not exist today, distinct from both business registration and the personal user profile page.
- Extend the existing branch-transfer mechanism's caller authorization to include the HR role (PRD §10.4 lists "Employee transfers" as an HR responsibility), and surface it in HR's UI. Today the mechanism is Business-Owner-only; HR has no access to it at all. The existing Branch-Manager-only transferee restriction (ID-011) is unchanged.
- Present the existing Service Approval workflow (built in Milestone 5) with role-appropriate frontend framing: "Service Requests" (submission/status view) for Branch Manager, "Approvals" (decision queue) for Business Owner. Same backend entity and endpoints — frontend presentation only, no new backend work.
- Branch Manager "Working Hours" module: implementation confirmed this was **not** already satisfied as originally classified here — the branch working-hours endpoints (view/update) were backend-restricted to the Business Owner only, with no Branch Manager access at either layer, contradicting PRD §10.3's "Manage branch working hours" responsibility. Fixed as part of Phase 6c: authorization extended to the Business Owner (business-wide, unchanged) or the Branch Manager currently assigned to that branch, with a frontend surface (the "Branch Overview" page) making working hours reachable and editable for the assigned Branch Manager.
- Confirmed already satisfied and **excluded from new work**: the Customer Dashboard's 6-module granularity (already covered by 3 existing pages; PRD §35 requires the 6 capabilities, not 6 separate routes).
- Remaining modules still needing scoping/sizing at implementation-planning time: Platform Administrator Analytics, Audit Logs (needs a new backend read endpoint — the write path already exists — plus a frontend view), Configuration, and Notifications; Business Owner Reports and Audit History; Branch Manager Daily Reports and Branch Overview; the entire Resource-role portal (Today's Schedule, Upcoming Bookings, Profile), which currently has no page and no navigation entry point at all.

### Milestone 9 Phase 7 — Cross-Role Authorization & Tenant-Isolation Verification

- Cross-role authorization and tenant-isolation verification — must explicitly include the Milestone 8 financial surfaces (payments, holds, coupons, refunds, platform-fee configuration) alongside all prior milestones, and must also cover every new surface introduced in Phases 1–6 above.

### Milestone 9 Phase 8 — Full Regression & Final Integration

- Full regression testing — must explicitly include Milestone 8 functionality.
- End-to-end V1 workflow verification.
- Final frontend/backend integration verification.

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