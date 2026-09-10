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

Implementation is complete and test-clean on `feature/payments-financial-policies` (not yet merged into `main`).

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

Complete remaining mandatory V1 cross-cutting functionality, including:

- Remaining non-financial required email notifications (financial notifications are Milestone 8 scope — see the Milestone 8 / Milestone 9 Notification Boundary above)
- General notification hardening, reusing the Celery + Redis + Celery Beat infrastructure introduced in Milestone 8 (ID-049) rather than a second mechanism
- Required soft-delete/status lifecycle corrections
- Remaining V1 audit coverage
- Required search/filter/pagination behavior
- Dashboard foundation required by V1
- Password-policy correction if still outstanding
- Cross-role authorization and tenant-isolation verification — must explicitly include the Milestone 8 financial surfaces (payments, holds, coupons, refunds, platform-fee configuration) alongside all prior milestones
- Full regression testing — must explicitly include Milestone 8 functionality
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