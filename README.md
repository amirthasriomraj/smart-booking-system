# 🚀 Smart Booking & Notification System

A full-stack production-ready application built using **FastAPI, React, PostgreSQL, Redis, Docker, and Nginx**.

This project demonstrates **real-world backend engineering practices** including authentication, security, containerization, and scalable architecture.

---

## 🧱 Tech Stack

### 🔙 Backend

* FastAPI
* SQLAlchemy ORM
* PostgreSQL
* Redis (for caching & rate limiting)
* JWT Authentication (Access + Refresh Tokens)
* CSRF Protection
* Alembic (Database migrations)

### 🎨 Frontend

* React (Vite)
* Axios (with interceptors)
* Protected Routes

### ⚙️ DevOps

* Docker & Docker Compose
* Nginx Reverse Proxy
* Same-Origin Architecture

---

## ✨ Features

### 🔐 Authentication & Security

* User Registration & Login
* Access Token + Refresh Token flow
* Refresh Token Rotation (Replay attack protection)
* HTTPOnly Cookies for security
* CSRF Protection (Double Submit Cookie)
* Password Reset Flow (secure token-based with expiry)
* Email-based password reset (SMTP configured)

### 👥 Authorization

* Role-Based Access Control (RBAC)
* Admin vs User permissions

### 📅 Booking System

* Create, update, delete bookings
* User-specific bookings
* Admin can manage all bookings

### 👤 User Profile

* View and update profile information

### 📬 Notifications & Async Design

* Email-based password reset system
* Secure token generation and expiry handling
* Designed for future async/background task integration

### ⚡ System Design Highlights

* Clean API architecture with routers
* Middleware for logging & security headers
* Centralized exception handling
* Scalable Docker-based setup
* Secure cookie + CSRF-based authentication system

---

## 🏗️ Project Structure

```
smart-booking-system/
│
├── backend/              # FastAPI backend
│   ├── routers/          # API routes
│   ├── models.py         # Database models
│   ├── schemas.py        # Pydantic schemas
│   ├── crud.py           # DB operations
│   ├── auth.py           # Auth logic
│   ├── dependencies.py   # Auth dependencies
│   ├── database.py       # DB connection
│   ├── main.py           # App entry point
│   ├── docker-compose.yml
│   └── Dockerfile
│
├── frontend/             # React frontend
│   ├── src/
│   └── Dockerfile
│
├── .env.example          # Environment variables template
├── .gitignore
└── README.md
```

---

## ⚙️ Setup Instructions

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/smart-booking-system.git
cd smart-booking-system
```

---

### 2️⃣ Setup Environment Variables

```bash
cp .env.example backend/.env
```

Update values inside `.env` as needed.

---

### 3️⃣ Run with Docker

```bash
docker-compose up --build
```

---

### 4️⃣ Access the Application

* Frontend → http://localhost/
* Backend API → http://localhost/api/
* Swagger Docs → http://localhost/docs

---

## 🔐 Authentication Flow

* Login returns **access token (short-lived)** + **refresh token (cookie)**
* Access token used for API requests
* Refresh token automatically rotates on expiry
* CSRF token required for secure refresh
* Refresh token rotation prevents replay attacks

---

## 🧪 Testing (Upcoming)

* Pytest-based backend testing
* Auth flow testing
* RBAC validation
* Booking ownership tests

---

## 🚀 CI/CD (Upcoming)

* GitHub Actions pipeline
* Automated testing on push
* Docker image build

---

## 🧠 Key Engineering Concepts Demonstrated

* Secure authentication system design
* Token lifecycle management
* Backend API structuring
* Dockerized microservice architecture
* Reverse proxy and routing
* Full-stack integration

---

## 📌 Future Improvements

* Advanced rate limiting (per-user, per-endpoint strategies)
* Monitoring & observability (Prometheus + Grafana)
* Email queue optimization (Celery / background workers)
* Real-time notifications (WebSockets)

---

## 👨‍💻 Author

**Amirtha Sri Omraj**

---

## ⭐ If you found this useful

Give this repo a star ⭐ — it helps!
