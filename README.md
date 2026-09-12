# 🚀 Smart Booking System

A production-style, multi-tenant B2B appointment/resource booking platform built with **FastAPI, React, PostgreSQL, Redis, Celery, Docker, and Nginx**, with integrated Razorpay payments.

Businesses (clinics, salons, sports centres, studios, and similar service providers) register on the platform, get approved by a Platform Administrator, and run one or more branches — each with its own staff, bookable resources, services, and customers — through role-based dashboards. Customers can self-register, browse businesses/branches/services, and book, reschedule, cancel, and pay for appointments through a dedicated customer portal.

---

## 🧱 Tech Stack

### 🔙 Backend
- FastAPI
- SQLAlchemy ORM
- PostgreSQL
- Redis (rate limiting, Celery broker/result backend)
- Celery + Celery Beat (scheduled/background jobs — payment reminders, deposit deadlines, expired-hold cleanup)
- JWT Authentication (Access + Refresh Tokens, rotation)
- CSRF Protection
- Alembic (Database migrations)
- Razorpay (online payments, Test Mode)
- SMTP Email Integration
- Pytest

### 🎨 Frontend
- React (Vite)
- Axios (with interceptors)
- React Router
- Role-gated Protected Routes (Platform Admin, Business Owner, Branch Manager, HR, Resource, Customer)

### ⚙️ DevOps / Infrastructure
- Docker / Docker Compose
- Nginx Reverse Proxy
- Same-Origin Architecture
- GitHub Actions CI

---

## ✨ Features

### 🏢 Multi-Tenant Business & Branch Management
- Business self-registration with Platform Admin approval/rejection
- Business suspend/reactivate lifecycle
- Multi-branch support per business, each with its own approval lifecycle and working hours
- Independent branch operational activation/deactivation

### 👥 Staff, Roles & Authorization
- Role-Based Access Control: Platform Admin, Business Owner, Branch Manager, HR User, Resource User, Customer
- Staff invitation and onboarding (Branch Manager, HR, Resource User) with token-based acceptance
- Branch Manager transfer between branches, with full assignment history
- Application-layer tenant isolation enforced on every business-scoped query

### 🧰 Resource & Service Management
- Generic, business-configurable Resource model (people or non-human resources) with per-resource working hours
- Business-level Service Templates with branch-level inheritance and overrides
- Business Owner approval workflow for branch service overrides

### 👤 Customer Management & Portal
- Customer self-registration and staff-created/walk-in customers
- Cross-business customer identity with business-scoped customer records
- Customer portal: browse businesses/branches/services, book, reschedule, cancel, view history

### 📅 Booking Engine
- Availability validation across business/branch/service/resource state and working hours
- Manual or automatic ("first available") resource assignment
- Reschedule and cancellation with full immutable booking history
- Double-booking and buffer-time protection at both the application and database layer

### 💳 Payments, Deposits, Coupons & Refunds
- Razorpay online payments (Test Mode) plus cash/offline and direct-external payment recording
- Concurrency-safe booking holds during checkout
- Security deposits with reminder/deadline scheduling and automatic default-cancellation
- Coupons/promotions (business-wide or branch-specific, approval-gated)
- Refunds (calculated, staff-overridden, or gateway-routed) with full financial audit trail
- Platform-configurable online-transaction fees with per-booking snapshotting

### 🔐 Authentication & Security
- JWT Access Token + Refresh Token flow with rotation (replay-attack protection)
- HTTPOnly cookie-based refresh token storage
- CSRF protection (double-submit cookie pattern)
- Password reset flow (token-based, expiring, audited)
- Redis-backed API rate limiting

### 📊 Audit, Notifications & Dashboards
- Immutable, append-only audit logging across business-critical actions
- Event-driven notifications (booking, approval, financial, and account lifecycle events) with delivery persistence
- Per-role dashboards with search, filtering, and pagination on business-wide list views

### ⚡ System Design Highlights
- Modular router-based API architecture (16 routers, layered into routers → services/crud → models)
- Request logging and security-headers middleware
- Centralized exception handling with a consistent response envelope
- Same-origin production architecture behind Nginx
- Containerized full-stack setup with CI-based quality validation

---

## 🏗️ Project Architecture

```text
                        ┌──────────────┐
                        │   Browser    │
                        └──────┬───────┘
                               │
                               ▼
                      ┌──────────────────┐
                      │      Nginx       │
                      │ Reverse Proxy    │
                      └──────┬─────┬─────┘
                             │     │
                             │     │
                             ▼     ▼
                   ┌────────────┐ ┌────────────┐
                   │  Frontend  │ │  FastAPI   │
                   │   React    │ │  Backend   │
                   └────────────┘ └─────┬──────┘
                                         │
                    ┌───────────┬───────┼───────┬──────────────┐
                    │           │       │        │              │
                    ▼           ▼       ▼        ▼              ▼
             ┌───────────┐┌───────────┐┌─────────┐┌──────────┐┌───────────┐
             │PostgreSQL ││   Redis   ││ Celery  ││ Razorpay ││ SMTP Mail │
             └───────────┘└───────────┘└─────────┘└──────────┘└───────────┘
```

---

## 📂 Project Structure

```text
smart-booking-system/
│
├── backend/
│   ├── routers/               # API route handlers (16 modules: auth, businesses,
│   │                          #   branches, staff, resources, services, customers,
│   │                          #   bookings, payments, payments_webhook, coupons,
│   │                          #   platform_fee, admin, reports, profiles, users)
│   ├── crud_*.py / crud.py    # Business logic + tenant/role authorization checks
│   ├── services/               # Rate limiter, pricing, file storage
│   ├── engines/ (via crud)     # Availability, approval, notification logic
│   ├── tasks/                  # Celery scheduled/background jobs
│   ├── core/                   # Redis, logging config, shared utilities
│   ├── alembic/                # Database migrations
│   ├── tests/                  # Pytest test suite (29 files)
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   ├── dependencies.py
│   ├── database.py
│   ├── config.py
│   ├── main.py
│   ├── Dockerfile
│   ├── docker-compose.yml       # backend, db, redis, celery_worker, celery_beat
│   └── docker-compose.dev.yml   # frontend, nginx
│
├── frontend/
│   ├── src/
│   │   ├── pages/              # ~30 pages across all roles
│   │   ├── api/                # Axios client + endpoint calls
│   │   ├── auth/                # Auth context, token refresh
│   │   └── components/          # Shared UI + route guards
│   ├── public/
│   ├── Dockerfile
│   └── vite.config.js
│
├── docs/                       # Frozen PRD/TAS, implementation decisions & plan
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── .gitignore
└── README.md
```

---

## 🌐 API Overview

All endpoints are mounted under `/api/v1`. Major route groups:

- **Auth**: register, login, refresh, logout, forgot/reset password, accept-invitation
- **Businesses**: registration, categories, approve/reject/suspend/reactivate, profile, audit logs, notifications
- **Branches**: CRUD, approve/reject, activate/deactivate, working hours, audit logs
- **Staff**: invite/resend/list/deactivate, branch transfer
- **Resources**: categories, resource CRUD, working hours, resource-user accounts
- **Services**: service templates, branch service overrides, approval workflow
- **Customers**: self-registration, business-scoped management, browse endpoints
- **Bookings**: staff and customer booking creation, availability, reschedule, cancel, history, reassignment, completion
- **Payments**: checkout/holds (customer and staff), cash/email-link/external finalization, balance payments, refunds
- **Coupons**, **Platform Fee**, **Admin** (audit logs, notifications, platform analytics), **Reports**, **Profiles**

Interactive API docs are available at `/docs` (Swagger UI) once the backend is running.

---

## ⚙️ Local Development Setup

### 1️⃣ Clone Repository

```bash
git clone https://github.com/amirthasriomraj/smart-booking-system.git
cd smart-booking-system
```

### 2️⃣ Backend Setup

```bash
cd backend

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

Create your local environment file:

```bash
cp env.example .env
```

Then edit `backend/.env` and fill in real values (database URL, `SECRET_KEY`, SMTP credentials, Razorpay Test Mode keys, etc.). `DEBUG` defaults to `false` in code — keep `DEBUG=true` in your local `.env` for the dev-friendly CORS/error-detail behavior.

Apply database migrations:

```bash
alembic upgrade head
```

### 3️⃣ Frontend Setup

```bash
cd frontend
npm ci
```

---

## 🐳 Run with Docker

The stack is split across two Compose files — `docker-compose.yml` (backend, PostgreSQL, Redis, Celery worker/beat) and `docker-compose.dev.yml` (frontend, Nginx) — both must be passed together. From `backend/`:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Application URLs:

- Frontend → http://localhost
- Backend API → http://localhost/api/
- Swagger Docs → http://localhost/docs

---

## 🔐 Authentication Flow

- User logs in with credentials
- Backend returns:
  - short-lived JWT access token
  - refresh token stored in HTTPOnly cookie
- Frontend attaches access token for protected API requests
- On expiry, frontend triggers refresh flow
- CSRF token required for refresh requests
- Refresh token rotates to prevent replay attacks
- Logout invalidates session securely

---

## 🧪 Testing

Backend test suite implemented with **Pytest** (29 files, covering every major feature area).

Coverage includes:

- Authentication, password policy, and password reset flows
- Business/branch registration, approval, suspend/reactivate lifecycle
- Staff invitation, onboarding, and branch-transfer authorization
- Resource and service management with tenant-isolation checks
- Customer registration and business-scoped customer management
- Full booking engine: availability, double-booking/buffer enforcement, reschedule, cancellation
- Payments: checkout, holds, Razorpay webhook signature/idempotency, refunds, deposits, coupons
- Search, filtering, pagination, dashboard/report access scoping
- Notification persistence

Run tests:

```bash
cd backend
source venv/bin/activate
pytest
```

---

## 🤖 CI Pipeline

GitHub Actions automatically validates every push / pull request.

### Backend
- Dependency installation
- Pytest execution

### Frontend
- Dependency installation
- ESLint validation
- Production build validation

### Infrastructure
- Backend Docker image build
- Frontend Docker image build

Triggers:
- Push to `main`
- Pull requests to `main`

---

## 🧠 Key Engineering Concepts Demonstrated

- Multi-tenant SaaS architecture (shared database/schema, application-layer isolation)
- Role-based access control across six distinct roles
- Layered backend architecture (routers → services/crud → models)
- Secure authentication: JWT lifecycle, refresh rotation, CSRF protection, cookie security
- Approval-workflow and immutable-audit-history patterns
- Concurrency-safe booking and payment-hold handling
- Payment gateway integration (Razorpay) with webhook signature verification and idempotency
- Background/scheduled job processing with Celery + Celery Beat
- Centralized exception handling and API middleware design
- Dockerized, reverse-proxied, same-origin production architecture
- CI automation and full-stack API integration

---

## 👨‍💻 Author

**Amirtha Sri Omraj**

---

## ⭐ If you found this useful

Give this repository a star ⭐
