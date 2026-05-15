# 🚀 Smart Booking System

A production-style full-stack application built using **FastAPI, React, PostgreSQL, Redis, Docker, and Nginx**.

This project demonstrates real-world backend engineering practices including secure authentication, authorization, testing, CI automation, containerization, reverse proxy architecture, and scalable system design.

---

## 🧱 Tech Stack

### 🔙 Backend
- FastAPI
- SQLAlchemy ORM
- PostgreSQL
- Redis (rate limiting)
- JWT Authentication (Access + Refresh Tokens)
- CSRF Protection
- Alembic (Database migrations)
- SMTP Email Integration
- Pytest

### 🎨 Frontend
- React (Vite)
- Axios (with interceptors)
- React Router
- Protected Routes

### ⚙️ DevOps / Infrastructure
- Docker
- Docker Compose
- Nginx Reverse Proxy
- Same-Origin Architecture
- GitHub Actions CI

---

## ✨ Features

### 🔐 Authentication & Security
- User Registration & Login
- JWT Access Token + Refresh Token flow
- Refresh Token Rotation (Replay attack protection)
- HTTPOnly Cookie-based refresh token storage
- CSRF Protection (Double Submit Cookie pattern)
- Secure Logout
- Logout from all active sessions
- Password Reset Flow (token-based with expiry)
- Email-based password reset (SMTP integration)
- Redis-backed API rate limiting

---

### 👥 Authorization
- Role-Based Access Control (RBAC)
- Admin vs User permissions
- Booking ownership authorization
- Protected API endpoints

---

### 📅 Booking System
- Create bookings
- View bookings
- Update bookings
- Delete bookings
- Pagination support
- User-specific booking access
- Ownership enforcement
- Admin visibility/control over booking resources

---

### 👤 User Profile Management
- View profile
- Update profile information
- Upload profile image
- Upload profile documents

---

### 🛠️ Admin User Management
- View all users
- Activate users
- Deactivate users
- Delete users

---

### ⚡ System Design Highlights
- Modular router-based API architecture
- Request logging middleware
- Security headers middleware
- Centralized exception handling
- Same-origin production architecture
- Containerized full-stack setup
- CI-based quality validation

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
                          ┌──────────────┼──────────────┐
                          │              │              │
                          ▼              ▼              ▼
                   ┌───────────┐  ┌───────────┐  ┌───────────┐
                   │PostgreSQL │  │   Redis   │  │ SMTP Mail │
                   └───────────┘  └───────────┘  └───────────┘
```

---

## 📂 Project Structure

```text
smart-booking-system/
│
├── backend/
│   ├── routers/              # API route handlers
│   ├── services/             # Business logic (rate limiter, etc.)
│   ├── core/                 # Redis, logging config, shared utilities
│   ├── alembic/              # Database migrations
│   ├── tests/               # Pytest test suite
│   ├── models.py
│   ├── schemas.py
│   ├── crud.py
│   ├── auth.py
│   ├── dependencies.py
│   ├── database.py
│   ├── config.py
│   ├── main.py
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.dev.yml
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── Dockerfile
│   └── vite.config.js
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── .gitignore
└── README.md
```

---

## 🌐 API Endpoints

### Health Check
- `GET /`

---

### Authentication
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/reset-password`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/logout-all`

---

### Bookings
- `POST /api/v1/bookings`
- `GET /api/v1/bookings`
- `PATCH /api/v1/bookings/{booking_id}`
- `DELETE /api/v1/bookings/{booking_id}`

---

### Profiles
- `GET /api/v1/profiles/profile`
- `PATCH /api/v1/profiles/profile`
- `POST /api/v1/profiles/upload-image`
- `POST /api/v1/profiles/upload-document`

---

### Admin User Management
- `GET /api/v1/users`
- `PATCH /api/v1/users/activate/{user_id}`
- `PATCH /api/v1/users/deactivate/{user_id}`
- `DELETE /api/v1/users/{user_id}`

---

## ⚙️ Local Development Setup

### 1️⃣ Clone Repository

```bash
git clone https://github.com/amirthasriomraj/smart-booking-system.git
cd smart-booking-system
```

---

### 2️⃣ Backend Setup

```bash
cd backend

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

Create:

```bash
backend/.env
```

using:

```bash
backend/.env.example
```

---

### 3️⃣ Frontend Setup

```bash
cd frontend
npm ci
```

---

## 🐳 Run with Docker

From backend:

```bash
docker compose -f docker-compose.dev.yml up --build
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

Backend test suite implemented with **Pytest**.

Current test coverage includes:

- Authentication flows
- User registration
- Login
- Protected route access
- Role-based authorization
- Booking ownership enforcement
- Password reset flow
- Redis dependency mocking
- SMTP email mocking

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

- Secure authentication architecture
- JWT token lifecycle management
- Refresh token rotation
- CSRF protection
- Cookie-based session security
- Role-based authorization
- Ownership-based access control
- Centralized exception handling
- API middleware design
- Dockerized infrastructure
- Reverse proxy routing
- CI automation
- Full-stack API integration
- Production-style backend engineering

---

## 📌 Future Enhancements

Potential next improvements:

- Payment integration
- Booking reminders
- Background task processing
- Real-time notifications
- Admin analytics dashboard
- AI-powered support chatbot
- Multi-tenant SaaS architecture
- Monitoring & observability
- Production deployment automation

---

## 👨‍💻 Author

**Amirtha Sri Omraj**

---

## ⭐ If you found this useful

Give this repository a star ⭐
