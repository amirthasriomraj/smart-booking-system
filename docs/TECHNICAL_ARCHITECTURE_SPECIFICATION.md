# Smart Booking System
## Technical Architecture Specification (TAS)

**Version:** 1.0  
**Status:** Version 1.0 – Frozen  
**Prepared By:** Amirtha Sri Omraj  
**Document Type:** Technical Architecture Specification

---

# Revision History

| Version | Date | Description |
|----------|------|-------------|
| 1.0 | August 2026 | Initial Technical Architecture – Approved & Frozen |

---

# Table of Contents

Part 1 – System Architecture & High-Level Design

1. Introduction
2. Technical Objectives
3. Architecture Principles
4. System Overview
5. High-Level Architecture
6. Multi-Tenant Strategy
7. Technology Stack
8. Component Architecture
9. Deployment Environments
10. Architectural Decisions (ADR)

---

# 1. Introduction

## Purpose

This document translates the approved Product Requirements Document (PRD) into a complete technical architecture for implementation.

It defines:

- Overall system architecture
- Backend architecture
- Frontend architecture
- Infrastructure
- Database architecture
- Security architecture
- Deployment strategy
- Engineering standards

This document serves as the primary implementation guide for Version 1 and is considered the approved technical baseline for implementation.

Any future architectural modifications shall follow the Change Request (CR) process to ensure consistency with the Product Requirements Document (PRD).

---

# Relationship with PRD

The Product Requirements Document defines **what** the platform should do.

The Technical Architecture Specification defines **how** those requirements will be implemented.

No functional requirements should be introduced in this document that are not already approved in the PRD.

---

# Audience

This document is intended for:

- Backend Developers
- Frontend Developers
- DevOps Engineers
- Software Architects
- QA Engineers
- Future Contributors

---

# 2. Technical Objectives

Version 1 aims to achieve the following engineering goals.

## Primary Objectives

- Production-quality backend architecture
- Scalable multi-tenant SaaS design
- Maintainable codebase
- Strong security foundation
- High code readability
- Modular implementation
- Cloud-ready deployment
- Testability

---

## Secondary Objectives

The project should also demonstrate:

- Clean Architecture principles
- SOLID principles
- REST API design
- Database normalization
- Authentication best practices
- Docker deployment
- AWS deployment
- Engineering documentation

These objectives directly support the project's role as a portfolio piece for backend software engineering interviews.

---

# 3. Architecture Principles

The architecture is guided by the following principles.

---

## AP-001 Modular Design

Every module should have a clearly defined responsibility.

Examples:

Authentication

Booking Engine

Approval Engine

Notification Engine

Audit Engine

Each module should evolve independently without affecting unrelated modules.

---

## AP-002 Separation of Concerns

Responsibilities are separated into distinct layers.

Presentation Layer

↓

API Layer

↓

Service Layer

↓

Repository Layer

↓

Database

Business logic must never be implemented inside API controllers.

---

## AP-003 Multi-Tenant First

Every architectural decision must consider tenant isolation.

Examples:

- Database queries
- Authorization
- Search
- Reporting
- Notifications

Tenant isolation is a mandatory requirement.

---

## AP-004 Configuration over Hardcoding

Business behaviour should be configurable wherever possible.

Examples:

- Working Hours
- Services
- Resource Categories
- Booking Rules

This avoids source code changes for business-specific requirements.

---

## AP-005 Security by Design

Security should exist at every architectural layer.

Authentication

↓

Authorization

↓

Validation

↓

Business Rules

↓

Database

Security is not a separate module.

It is embedded throughout the application.

---

## AP-006 Auditability

Every critical business operation should generate an immutable audit record.

The audit system must operate independently of business modules.

---

## AP-007 Scalability

The architecture should support:

- Additional businesses
- Additional branches
- Additional users
- Additional bookings

without requiring structural redesign.

---

## AP-008 Maintainability

The system should prioritize:

- Readability
- Small modules
- Clear naming
- Documentation
- Reusability

over clever or overly complex implementations.

---

# 4. System Overview

Smart Booking System is a web-based, multi-tenant Software-as-a-Service (SaaS) platform.

The system enables independent businesses to manage:

- Branches
- Customers
- Resources
- Services
- Appointments

through a shared platform while maintaining strict tenant isolation.

---

# Logical Architecture

+-------------------------------------------------------------+
|                     Smart Booking System                     |
+-------------------------------------------------------------+

                Platform Administration
                         │
         ┌───────────────┴───────────────┐
         │                               │
   Business A                      Business B
         │                               │
  ┌──────┴──────┐                ┌───────┴───────┐
  │             │                │               │
Branch A1   Branch A2        Branch B1      Branch B2
  │             │                │               │
Resources    Customers       Resources      Customers
  │             │                │               │
Bookings     Services       Bookings       Services

Every business operates independently while sharing the same application infrastructure.

---

# 5. High-Level Architecture

The application follows a layered architecture.

                    React Frontend
                           │
                    REST API (FastAPI)
                           │
                  Authentication Layer
                           │
                  Authorization Layer
                           │
                  Application Services
                           │
                  Repository Layer
                           │
                     PostgreSQL
                           │
                         Redis

Supporting Components

- SMTP Email Service
- Audit Engine
- Notification Engine
- Logging
- File Storage

---

# Why Layered Architecture?

Alternative considered:

Fat Controllers

Reason rejected:

- Difficult to maintain
- Business logic duplication
- Poor testability

Chosen approach:

Layered Architecture

Reasons:

✔ Clear responsibilities

✔ Easy testing

✔ Easy maintenance

✔ Scalable

✔ Industry standard

---

# 6. Multi-Tenant Strategy

Version 1 adopts a **Shared Database, Shared Schema** architecture.

Every business (tenant) shares the same PostgreSQL database and schema.

Each tenant-owned entity includes a Tenant Identifier (Business ID), ensuring data isolation at the application level.

This strategy was selected because it provides:

- Lower operational cost
- Simpler deployments
- Easier maintenance
- Faster feature delivery
- Efficient use of infrastructure

Future versions may evolve to support database-per-tenant or schema-per-tenant architectures if required by enterprise customers.

---

# Tenant Isolation Principles

Every tenant-owned entity must include:

- Business ID
- Branch ID (where applicable)

Every query executed by the application must be scoped to the authenticated Business unless the caller is a Platform Administrator.

Cross-tenant access is prohibited.

---

# 7. Technology Stack

## Backend

- Python
- FastAPI
- SQLAlchemy ORM
- Alembic
- Pydantic

---

## Frontend

- React
- React Router
- Axios
- Vite

---

## Database

- PostgreSQL

---

## Cache

- Redis

Uses include:

- Rate limiting
- Token management
- Future caching
- Future background processing

---

## Infrastructure

- Docker
- Docker Compose
- Nginx

---

## Cloud

Primary target:

AWS

Planned services:

- EC2 (initial deployment)
- RDS PostgreSQL (future migration)
- ElastiCache Redis (future migration)
- S3 (file storage)
- CloudWatch (logging & monitoring)

---

# Why These Technologies?

FastAPI

Reasons:

- Excellent performance
- Async support
- Automatic OpenAPI generation
- Strong typing
- Modern Python ecosystem

React

Reasons:

- Large ecosystem
- Component architecture
- Excellent developer experience
- Widely adopted

PostgreSQL

Reasons:

- ACID compliance
- Rich indexing
- JSON support
- Mature ecosystem

Redis

Reasons:

- Extremely fast
- Ideal for caching
- Token storage
- Future background jobs

---

# 8. Component Architecture

The application is divided into independent components.

Core Components:

- Authentication
- Authorization
- Business Management
- Branch Management
- Customer Management
- Resource Management
- Service Management
- Booking Engine
- Approval Engine
- Notification Engine
- Audit Engine
- Reporting
- File Management

Each component communicates through clearly defined service interfaces.

Direct cross-component database manipulation is discouraged.

---

# 9. Deployment Environments

The platform supports multiple environments.

Development

- Local Docker
- Debug enabled

Testing

- Separate database
- Test configuration

Production

- Debug disabled
- HTTPS
- Secure headers
- Managed secrets
- Monitoring enabled

Configuration is environment-driven rather than code-driven.

---

# 10. Architecture Decision Records (ADR)

Major architectural decisions are documented for future reference.

| ADR | Decision | Status |
|------|----------|--------|
| ADR-001 | Shared Database, Shared Schema | Accepted |
| ADR-002 | Layered Architecture | Accepted |
| ADR-003 | FastAPI Backend | Accepted |
| ADR-004 | React Frontend | Accepted |
| ADR-005 | PostgreSQL Primary Database | Accepted |
| ADR-006 | Redis for Caching & Token Management | Accepted |
| ADR-007 | JWT Authentication with Refresh Token Rotation | Accepted |
| ADR-008 | Docker-Based Deployment | Accepted |
| ADR-009 | AWS as Primary Cloud Platform | Accepted |

---

# Part 2 – Domain Model & Database Design

---

# Table of Contents

1. Domain-Driven Design
2. Core Domain
3. Domain Boundaries
4. Aggregate Design
5. Database Design Principles
6. Tenant Isolation Strategy
7. Entity Overview
8. Relationships
9. Entity Lifecycle
10. Database Naming Standards
11. Primary Key Strategy
12. Audit Strategy

---

# 1. Domain-Driven Design

## Overview

Smart Booking System is modeled around business domains rather than database tables.

Instead of asking:

> "What tables do we need?"

we first ask:

> "What business concepts exist?"

Each business concept eventually becomes one or more database entities.

This approach results in a cleaner, more maintainable architecture.

---

# 2. Core Domain

The platform consists of the following domains.

Platform

↓

Business

↓

Branch

↓

Customer

↓

Resource

↓

Service

↓

Booking

↓

Notification

↓

Audit

Each domain owns its own responsibilities.

Cross-domain communication should occur through service interfaces rather than direct manipulation.

---

# 3. Domain Boundaries

Each domain owns specific responsibilities.

## Platform Domain

Responsible for:

- Platform administrators
- Business approvals
- Branch approvals
- Platform configuration

---

## Business Domain

Responsible for:

- Business profile
- Business configuration
- Business settings

---

## Branch Domain

Responsible for:

- Branch profile
- Working hours
- Local configuration

---

## Customer Domain

Responsible for:

- Platform customer account
- Business customer profile
- Customer preferences
- Customer history

---

## Resource Domain

Responsible for:

- Human resources
- Non-human resources
- Resource availability
- Resource categories

---

## Service Domain

Responsible for:

- Service templates
- Branch services
- Service approvals

---

## Booking Domain

Responsible for:

- Availability
- Booking lifecycle
- Rescheduling
- Cancellation
- Resource assignment

---

## Audit Domain

Responsible for:

- Immutable history
- Change tracking
- Compliance records

---

## Notification Domain

Responsible for:

- Email notifications
- Future notification providers

---

# 4. Aggregate Design

The system follows Aggregate Root principles.

Aggregate Roots:

Platform

Business

Branch

Customer

Booking

These entities own their internal consistency.

Other entities should not modify aggregate internals directly.

---

# Aggregate Example

Business

├── Branches

├── Service Templates

├── Employees

└── Settings

Business becomes the Aggregate Root.

A Service cannot belong to two Businesses.

---

# Booking Aggregate

Booking

├── Customer

├── Service

├── Resource

├── Audit History

└── Notification Events

Booking controls the integrity of the appointment.

---

# 5. Database Design Principles

The database follows these principles.

---

## DB-001

Normalization before optimization.

Target:

Third Normal Form (3NF)

Denormalization only when justified.

---

## DB-002

Every table represents one business concept.

Avoid mixing unrelated responsibilities.

---

## DB-003

No duplicated business data.

Relationships should replace duplication.

---

## DB-004

Use foreign keys wherever ownership exists.

---

## DB-005

Business identifiers remain immutable.

---

## DB-006

Every table includes timestamps.

Minimum:

created_at

updated_at

Future:

deleted_at (soft delete)

---

## DB-007

Soft deletion preferred over physical deletion.

---

# 6. Tenant Isolation Strategy

Version 1 uses:

Shared Database

Shared Schema

Application-level isolation.

Every tenant-owned entity contains:

business_id

Some entities additionally contain:

branch_id

---

# Entities requiring business_id

- Branch
- Customer Profile
- Resource
- Resource Category
- Service Template
- Branch Service
- Booking
- Audit Log

---

# Platform Tables

Platform-owned tables do NOT contain business_id.

Examples:

Platform Admin

Business

Country

Business Categories

---

# Why Shared Database?

Alternatives considered:

Database per tenant

Schema per tenant

Reasons rejected for Version 1:

- Increased operational complexity
- Higher infrastructure cost
- Difficult local development

Chosen strategy:

Shared Database

Reasons:

✔ Easier deployment

✔ Lower AWS cost

✔ Simpler migrations

✔ Ideal for startup SaaS

Future migration remains possible.

---

# 7. Entity Overview

Version 1 introduces the following entities.

Platform

PlatformAdmin

Business

Branch

BusinessCategory

Country

Identity

User

Role

RefreshToken

PasswordResetToken

Customer

PlatformCustomer

BusinessCustomer

Branch Operations

ResourceCategory

Resource

ResourceWorkingHours

BusinessWorkingHours

BranchWorkingHours

Services

ServiceTemplate

BranchService

ServiceApproval

Bookings

Booking

BookingHistory

BookingStatusHistory

Notifications

Notification

EmailLog

Audit

AuditLog

Infrastructure

UploadedFile

SystemSetting

---

# 8. High-Level Entity Relationships

Platform

│

├── Businesses

│

├── Countries

│

└── Categories

Business

│

├── Branches

├── Service Templates

├── Resource Categories

├── Employees

├── Customers

└── Settings

Branch

│

├── Resources

├── Branch Services

├── Working Hours

└── Bookings

Booking

│

├── Customer

├── Service

├── Resource

├── History

└── Notifications

---

# 9. Entity Lifecycle

Example:

Business

Pending

↓

Approved

↓

Active

↓

Suspended

↓

Archived

---

Booking

Confirmed

↓

Completed

OR

Cancelled

---

Resource

Created

↓

Configured

↓

Active

↓

Suspended

↓

Archived

---

Branch Service

Inherited

↓

Modified

↓

Pending Approval

↓

Approved

---

# 10. Database Naming Standards

Tables

snake_case

Examples:

businesses

branches

service_templates

booking_history

---

Columns

snake_case

Examples:

business_id

created_at

resource_category_id

---

Foreign Keys

Always end with:

_id

Examples:

customer_id

branch_id

service_template_id

---

Indexes

Prefix:

idx_

Example:

idx_booking_date

---

Unique Constraints

Prefix:

uq_

Example:

uq_business_email

---

# 11. Primary Key Strategy

Every table uses:

BIGINT Auto Increment IDs

Reasons:

- Simple
- Fast joins
- Easy debugging
- Excellent PostgreSQL performance

Public APIs may later expose UUIDs while keeping BIGINT keys internally.

---

# 12. Audit Strategy

Auditing is implemented as a dedicated domain rather than embedded in business tables.

Every significant operation creates an AuditLog entry.

Audit entries include:

- Entity Type
- Entity ID
- Action
- Previous State
- New State
- Actor
- Timestamp
- Reason (Optional)

Audit records are append-only and cannot be modified.

---

# Part 3 – Database Schema & Entity Design

---

# Table of Contents

1. Entity Design Principles
2. Identity & Access Management
3. Platform Administration
4. Business Management
5. Branch Management
6. Customer Management
7. Resource Management
8. Service Management
9. Booking Management
10. Audit & Notifications
11. Relationship Summary
12. ER Diagram (Logical)

---

# 1. Entity Design Principles

Every entity should represent a single business concept.

Rules:

- Single Responsibility
- Strong Referential Integrity
- Minimal Data Duplication
- Soft Delete Support
- Audit Friendly
- Tenant Safe

Each table includes:

- id
- created_at
- updated_at
- optional deleted_at (future)
- version (future optimistic locking)

---

# 2. Identity & Access Management

The identity system is intentionally separated from business membership.

## Users

Represents a platform identity.

A user may be:

- Platform Administrator
- Business Owner
- Branch Manager
- Human Resource User
- Resource User
- Customer

### Suggested Columns

- id
- username
- email
- password_hash
- email_verified
- is_active
- last_login_at
- created_at
- updated_at

This table contains **authentication information only**.

---

## Roles

Master table defining platform roles.

Columns:

- id
- code
- name
- description

Examples:

- PLATFORM_ADMIN
- BUSINESS_OWNER
- BRANCH_MANAGER
- HR_USER
- RESOURCE_USER
- CUSTOMER

---

## User Roles

Supports future extensibility if a user may hold multiple roles.

Columns:

- id
- user_id
- role_id

Although Version 1 typically assigns one primary role, this design avoids future schema changes.

---

## Refresh Tokens

Stores hashed refresh tokens.

Columns:

- id
- user_id
- token_hash
- expires_at
- revoked
- replaced_by_token_id
- created_at

---

# 3. Platform Administration

## Countries

Master table.

Columns:

- id
- iso_code
- name
- currency_code
- timezone

---

## Business Categories

Examples:

- Salon
- Clinic
- Hospital
- Sports Centre
- Coaching Institute

Columns:

- id
- name
- description
- is_active

---

## Businesses

Represents a tenant.

Columns:

- id
- business_name
- business_category_id
- owner_user_id
- country_id
- status
- approved_by
- approved_at
- created_at
- updated_at

Business status:

- Pending
- Active
- Suspended
- Rejected

---

# 4. Branch Management

## Branches

Each branch belongs to exactly one Business.

Columns:

- id
- business_id
- branch_name
- address
- city
- state
- postal_code
- country_id
- phone
- email
- status
- approved_by
- approved_at
- created_at
- updated_at

Indexes:

- business_id
- status
- city

---

## Branch Working Hours

Separate table.

Reason:

Avoid repeating seven weekday columns inside Branch.

Columns:

- id
- branch_id
- weekday
- opening_time
- closing_time
- is_closed

---

# 5. Business Membership

Instead of storing employee information directly in the User table, membership is modeled explicitly.

## Business Members

Columns:

- id
- business_id
- user_id
- role_id
- status
- joined_at
- left_at

Rules:

- One active membership per business.
- Employees cannot belong to multiple businesses simultaneously.
- Business Owner is represented here as the primary owner membership.

---

## Branch Assignments

Allows employee transfers without losing history.

Columns:

- id
- business_member_id
- branch_id
- assigned_from
- assigned_to
- is_current

Only one current assignment is permitted.

---

# 6. Customer Management

The customer model is divided into identity and business relationship.

## Platform Customers

Represents the customer's platform identity.

Columns:

- id
- user_id
- preferred_language
- preferred_timezone
- created_at

One account may book with multiple businesses.

---

## Business Customers

Represents the relationship between a customer and a specific business.

Columns:

- id
- business_id
- platform_customer_id
- customer_number
- notes
- status
- first_visit_at
- last_visit_at
- created_at

This allows:

- Business-specific notes
- Loyalty programs (future)
- Visit history
- Preferences

while keeping one platform login.

---

# 7. Resource Management

## Resource Categories

Defined by each Business.

Columns:

- id
- business_id
- category_name
- description
- created_at

Examples:

Doctor

Coach

Swimming Pool

Court

Meeting Room

---

## Resources

Represents both human and non-human resources.

Columns:

- id
- branch_id
- resource_category_id
- linked_user_id (nullable)
- resource_name
- code
- description
- status
- requires_login
- created_at

If requires_login = false,

linked_user_id remains NULL.

---

## Resource Working Hours

Allows overriding inherited branch hours.

Columns:

- id
- resource_id
- weekday
- opening_time
- closing_time
- is_closed

---

# 8. Service Management

## Service Templates

Owned by Business.

Columns:

- id
- business_id
- name
- description
- default_duration
- default_price
- status

---

## Branch Services

Inherited from templates.

Columns:

- id
- branch_id
- service_template_id
- duration
- price
- status
- pending_approval

---

## Service Approvals

Tracks override approvals.

Columns:

- id
- branch_service_id
- requested_by
- approved_by
- decision
- comments
- decided_at

---

# 9. Booking Management

## Bookings

Core transactional table.

Columns:

- id
- business_id
- branch_id
- customer_id
- service_id
- resource_id
- booking_date
- start_time
- end_time
- status
- created_by
- created_at
- updated_at

Indexes:

- business_id
- branch_id
- booking_date
- resource_id
- status

Unique Constraint:

(resource_id, booking_date, start_time)

---

## Booking History

Immutable history.

Columns:

- id
- booking_id
- action
- previous_state
- new_state
- performed_by
- performed_at

---

# 10. Audit & Notifications

## Audit Logs

Stores all critical system events.

Columns:

- id
- business_id (nullable)
- entity_type
- entity_id
- action
- previous_value
- new_value
- performed_by
- reason
- created_at

---

## Notifications

Tracks notification requests.

Columns:

- id
- recipient_user_id
- notification_type
- channel
- status
- payload
- created_at
- sent_at

---

## Email Logs

Stores email delivery attempts.

Columns:

- id
- notification_id
- smtp_provider
- delivery_status
- provider_reference
- attempted_at

---

# 11. Relationship Summary

Platform

├── Countries

├── Business Categories

└── Businesses

Business

├── Branches

├── Members

├── Customers

├── Resource Categories

├── Service Templates

└── Audit Logs

Branch

├── Resources

├── Branch Services

├── Bookings

└── Working Hours

Booking

├── History

└── Notifications

---

# 12. Logical ER Diagram

Platform
│
├── Business
│   ├── Branch
│   │   ├── Resource
│   │   ├── Branch Service
│   │   ├── Booking
│   │   └── Branch Working Hours
│   │
│   ├── Resource Category
│   ├── Service Template
│   ├── Business Member
│   └── Business Customer
│
└── User
    ├── Roles
    ├── Platform Customer
    └── Refresh Token

---

# Part 4 – Core Business Engines

---

# Table of Contents

1. Engine Architecture
2. Booking Engine
3. Availability Engine
4. Resource Assignment Engine
5. Service Inheritance Engine
6. Approval Engine
7. Notification Engine
8. Audit Engine
9. Search Engine
10. Engine Communication

---

# 1. Engine Architecture

## Overview

Instead of embedding business logic throughout controllers or service classes, Smart Booking System organizes complex workflows into specialized business engines.

Each engine owns one specific business responsibility.

Benefits include:

- Clear separation of concerns
- High maintainability
- Better unit testing
- Easier future enhancements
- Improved scalability

---

## Engine Interaction

Customer Request

↓

API Layer

↓

Application Service

↓

Business Engine

↓

Repository Layer

↓

Database

Business engines never communicate directly with HTTP requests or database sessions. They operate through application services and repositories.

---

# 2. Booking Engine

## Responsibility

The Booking Engine is responsible for the complete booking lifecycle.

It handles:

- Booking creation
- Validation
- Rescheduling
- Cancellation
- Resource reassignment
- Booking completion

---

## Booking Creation Flow

Customer / Staff

↓

Booking Request

↓

Business Validation

↓

Branch Validation

↓

Service Validation

↓

Availability Engine

↓

Resource Assignment Engine

↓

Booking Persisted

↓

Audit Engine

↓

Notification Engine

↓

Response Returned

---

## Booking Validation Rules

Before a booking is created, the Booking Engine validates:

- Business is active
- Branch is approved
- Service is approved
- Customer exists
- Resource exists
- Resource is active
- Resource belongs to the selected branch
- Requested time is within working hours
- Requested slot is available

Only after all validations pass is the booking committed.

---

## Booking State Machine

Draft (internal only)

↓

Confirmed

↓

Completed

OR

Cancelled

Future states such as "Checked In", "In Progress", and "No Show" can be introduced without redesigning the engine.

---

# 3. Availability Engine

## Responsibility

Determines whether a requested booking slot is available.

This engine is intentionally independent of booking creation so it can be reused by:

- Customer Portal
- Staff Portal
- Future mobile applications
- Third-party APIs

---

## Availability Calculation

The engine evaluates:

Business Status

↓

Branch Status

↓

Working Hours

↓

Service Availability

↓

Resource Availability

↓

Existing Bookings

↓

Maintenance Blocks (future)

↓

Return Available Slots

---

## Inputs

- Business ID
- Branch ID
- Service ID
- Requested Date
- Optional Resource ID

---

## Outputs

- Available Time Slots
- Available Resources
- Validation Messages

---

## Design Principle

The Availability Engine never creates bookings.

Its only responsibility is determining availability.

---

# 4. Resource Assignment Engine

## Responsibility

Determines which resource should fulfill a booking.

---

## Assignment Modes

### Manual Assignment

The customer or staff selects a specific resource.

Examples:

- Doctor
- Coach
- Tennis Court

The engine validates:

- Resource belongs to branch
- Resource supports the selected service
- Resource is available

---

### Automatic Assignment

If resource selection is disabled by the business, the engine automatically selects an appropriate resource.

Selection criteria may include:

- First available
- Least booked
- Round-robin (future)
- Custom algorithm (future)

Version 1 uses **First Available**.

---

## Future Extensibility

The assignment strategy should be configurable per business without changing application code.

---

# 5. Service Inheritance Engine

## Responsibility

Maintains synchronization between Business Service Templates and Branch Services.

---

## Workflow

Business Owner creates Service Template

↓

Branch inherits template

↓

Branch Manager customizes service

↓

Pending Approval

↓

Business Owner approves

↓

Branch Service updated

---

## Design Principles

- Templates remain immutable.
- Branch overrides do not modify the original template.
- Multiple branches may override the same template independently.

---

# 6. Approval Engine

## Responsibility

Processes all approval workflows.

Supported approval types:

- Business Registration
- Branch Creation
- Branch Service Overrides

Future approval types can be added without changing the engine architecture.

---

## Generic Approval Flow

Approval Request

↓

Validation

↓

Decision

↓

Audit Entry

↓

Notification

↓

Business Action

---

## Engine Output

Every approval returns:

- Status
- Decision
- Reviewer
- Timestamp
- Comments (optional)

---

# 7. Notification Engine

## Responsibility

Generates notification events.

The Notification Engine does **not** contain business logic.

It simply receives events and delivers notifications.

---

## Notification Flow

Business Event

↓

Notification Event

↓

Channel Selection

↓

Email Provider

↓

Delivery Status

↓

Email Log

---

## Supported Channel (Version 1)

- Email

Future channels:

- SMS
- WhatsApp
- Push Notifications
- In-App Notifications

---

## Design Principle

Business operations should succeed even if notification delivery fails.

Notification failures must not roll back completed transactions.

---

# 8. Audit Engine

## Responsibility

Records immutable audit events for all critical operations.

---

## Auditable Actions

- Business Approval
- Branch Approval
- Service Approval
- Booking Creation
- Booking Update
- Booking Cancellation
- Booking Reschedule
- Resource Reassignment
- Customer Creation
- Employee Invitation

---

## Audit Flow

Business Operation

↓

Audit Event Created

↓

Audit Record Persisted

↓

Business Transaction Completes

Audit records are append-only and never updated.

---

# 9. Search Engine

## Responsibility

Provides reusable search capabilities across modules.

Supported entities:

- Businesses
- Branches
- Customers
- Resources
- Services
- Bookings

---

## Features

- Pagination
- Filtering
- Sorting
- Keyword Search

Future enhancements:

- Full-text search
- Fuzzy search
- Elasticsearch/OpenSearch integration

---

# 10. Engine Communication

Business engines should not call each other directly.

Instead, orchestration occurs through the Application Service layer.

Example:

BookingService

├── AvailabilityEngine

├── ResourceAssignmentEngine

├── BookingRepository

├── AuditEngine

└── NotificationEngine

This keeps engines independent and easier to test.

---

# Architectural Principles

✔ Single Responsibility

✔ Stateless Engines

✔ Reusable Components

✔ Transaction Boundaries Managed by Services

✔ Infrastructure Independent

✔ Easily Extensible

---

# Part 5 – Backend Design & API Specification

---

# Table of Contents

1. Backend Architecture
2. Folder Structure
3. Layered Design
4. API Design Standards
5. Request & Response Standards
6. Error Handling
7. Validation Strategy
8. Transaction Management
9. File Management
10. API Versioning
11. Coding Standards

---

# 1. Backend Architecture

The backend follows a layered architecture to ensure separation of concerns, maintainability, and testability.

Client

↓

API Router

↓

Application Service

↓

Business Engine

↓

Repository

↓

Database

Each layer has a clearly defined responsibility.

---

# Layer Responsibilities

## API Layer

Responsible for:

- HTTP endpoints
- Request parsing
- Authentication
- Authorization
- Returning HTTP responses

The API layer must not contain business logic.

---

## Service Layer

Responsible for:

- Coordinating business workflows
- Managing transactions
- Calling business engines
- Orchestrating repositories

The service layer acts as the application orchestrator.

---

## Business Engine Layer

Responsible for reusable business rules.

Examples:

- Booking Engine
- Availability Engine
- Approval Engine

Business engines are independent of HTTP and database implementation details.

---

## Repository Layer

Responsible for:

- Database access
- Query construction
- Persistence

Repositories never contain business rules.

---

## Infrastructure Layer

Responsible for:

- Email
- Redis
- File Storage
- Logging
- External APIs

Infrastructure code should never be referenced directly from business logic.

---

# 2. Backend Folder Structure

```
backend/

├── app/
│
├── api/
│   ├── dependencies/
│   ├── middleware/
│   ├── routers/
│   └── responses/
│
├── core/
│   ├── config.py
│   ├── security.py
│   ├── logging.py
│   ├── exceptions.py
│   └── constants.py
│
├── models/
│
├── schemas/
│
├── repositories/
│
├── services/
│
├── engines/
│
├── infrastructure/
│   ├── email/
│   ├── storage/
│   ├── cache/
│   └── notifications/
│
├── utils/
│
├── migrations/
│
├── tests/
│
└── main.py
```

---

# Why This Structure?

Current project:

- routers
- crud.py
- models.py
- schemas.py

Suitable for a learning project.

Version 1:

As the platform grows, responsibilities should be split into dedicated packages.

Benefits:

✔ Easier navigation

✔ Smaller files

✔ Better testing

✔ Better scalability

---

# 3. Layered Design

Example:

Customer creates booking.

Request

↓

Booking Router

↓

Booking Service

↓

Booking Engine

↓

Availability Engine

↓

Resource Assignment Engine

↓

Booking Repository

↓

Database

↓

Audit Engine

↓

Notification Engine

↓

Response

The Router knows nothing about booking logic.

The Repository knows nothing about booking rules.

---

# 4. API Design Standards

REST principles will be followed.

Examples:

GET /api/v1/businesses

GET /api/v1/branches

POST /api/v1/bookings

PUT /api/v1/bookings/{id}

DELETE /api/v1/bookings/{id}

PATCH is used only for partial updates.

Resource names remain plural.

---

# API Naming

Good

/bookings

/resources

/customers

/services

Avoid

/getBookings

/createBooking

/updateBooking

---

# 5. Request & Response Standards

Every API returns a consistent response format.

Successful response:

```json
{
  "success": true,
  "data": { },
  "meta": { }
}
```

Error response:

```json
{
  "success": false,
  "error": {
    "code": "BOOKING_NOT_FOUND",
    "message": "Booking not found."
  }
}
```

Benefits:

- Predictable API behavior
- Easier frontend integration
- Better client-side error handling

---

# Pagination Standard

Collection endpoints support:

- page
- page_size
- sort
- order

Example:

GET /bookings?page=1&page_size=20

Response:

- items
- total
- page
- page_size
- total_pages

---

# Filtering Standard

Supported via query parameters.

Examples:

GET /bookings?status=confirmed

GET /resources?category=coach

GET /customers?name=amirtha

Filters are combinable.

---

# Sorting Standard

Examples:

GET /bookings?sort=date

GET /bookings?sort=-created_at

"-" indicates descending order.

---

# 6. Error Handling

Errors are centralized.

Categories:

400

Bad Request

401

Unauthorized

403

Forbidden

404

Not Found

409

Conflict

422

Validation Error

500

Internal Server Error

Controllers should never manually construct error responses.

Custom exceptions are translated by global exception handlers.

---

# 7. Validation Strategy

Validation occurs at multiple layers.

Request Validation

↓

Business Validation

↓

Database Constraints

Examples:

Request Validation

Required fields

Business Validation

Booking overlap

Database Validation

Unique constraints

Each layer protects against different failure scenarios.

---

# 8. Transaction Management

Transactions are controlled by the Service Layer.

Example:

Booking Service

Start Transaction

↓

Create Booking

↓

Create Audit

↓

Queue Notification

↓

Commit

If any critical operation fails before commit, the transaction rolls back.

Notification delivery itself is asynchronous and must not cause rollback after a successful commit.

---

# 9. File Management

Uploads include:

- Profile images
- Documents

Storage abstraction is used.

Version 1:

Local storage (development)

AWS S3 (production-ready)

Business logic never interacts directly with filesystem paths.

---

# 10. API Versioning

Versioning is URI-based.

Example:

/api/v1/

Future:

/api/v2/

Multiple API versions may coexist during migration.

Breaking changes require a new API version.

---

# 11. Coding Standards

General

- PEP 8 compliant
- Type hints required
- Docstrings for public methods
- Meaningful naming

Functions

- One responsibility
- Small and focused

Services

- Orchestrate workflows
- No SQL queries

Repositories

- Database access only
- No business rules

Engines

- Stateless
- Reusable
- Business logic only

Models

- Persistence only
- No business logic

Schemas

- Request/response validation only

Logging

- Structured logs
- No sensitive information

Tests

- Unit tests for business logic
- Integration tests for APIs

---

# Development Principles

✔ SOLID

✔ DRY

✔ KISS

✔ Clean Architecture

✔ Explicit over implicit

✔ Composition over inheritance where practical

---

# Part 6 – Frontend Architecture

---

# Table of Contents

1. Frontend Philosophy
2. Application Architecture
3. Folder Structure
4. Routing Strategy
5. Authentication Flow
6. Dashboard Architecture
7. State Management
8. API Integration
9. UI Design Principles
10. Performance Strategy

---

# 1. Frontend Philosophy

The frontend is responsible for presenting business functionality while keeping business logic in the backend.

Responsibilities include:

- User Interface
- Client-side Validation
- Authentication State
- Navigation
- API Communication

Business rules remain in the backend.

---

# 2. Application Architecture

The frontend follows a component-based architecture using React.

Browser

↓

React Application

↓

Pages

↓

Reusable Components

↓

API Layer

↓

Backend REST API

Each component has a single responsibility.

---

# 3. Folder Structure

frontend/

├── src/
│
├── api/
│
├── assets/
│
├── auth/
│
├── components/
│
├── hooks/
│
├── layouts/
│
├── pages/
│
├── routes/
│
├── services/
│
├── store/
│
├── styles/
│
├── utils/
│
└── main.jsx

---

# 4. Routing Strategy

Public Routes

- Login
- Register
- Forgot Password
- Customer Booking Portal

Protected Routes

- Platform Admin
- Business Owner
- Branch Manager
- HR User
- Resource User
- Customer Dashboard

Route Guards enforce authentication and authorization.

---

# 5. Authentication Flow

User Login

↓

Backend Authentication

↓

JWT Access Token

↓

Refresh Token

↓

Store Authentication State

↓

Access Protected Pages

Expired access tokens are renewed using refresh tokens.

---

# 6. Dashboard Architecture

Platform Admin Dashboard

- Business Approvals
- Branch Approvals
- Platform Settings

Business Owner Dashboard

- Business Profile
- Branches
- Services
- Resources
- Customers
- Reports

Branch Manager Dashboard

- Daily Appointments
- Resources
- Customers
- Walk-in Bookings

Resource Dashboard

- Assigned Schedule
- Availability
- Profile

Customer Dashboard

- Profile
- Book Appointment
- Upcoming Appointments
- Booking History
- Reschedule
- Cancel Booking

---

# 7. State Management

Version 1 uses:

- React Context
- Local Component State

Future versions may adopt Redux Toolkit if application complexity increases.

---

# 8. API Integration

Axios is used for API communication.

Responsibilities:

- Authorization Header
- Token Refresh
- Global Error Handling
- Request Logging
- Response Interceptors

---

# 9. UI Design Principles

- Responsive Design
- Accessibility
- Consistent Navigation
- Reusable Components
- Clear Feedback
- Minimal User Actions

---

# 10. Performance Strategy

- Lazy Loading
- Route Splitting
- Memoization where appropriate
- API Pagination
- Optimized Rendering

---

# Part 7 – Infrastructure, AWS & DevOps

---

# Table of Contents

1. Deployment Strategy
2. Docker Architecture
3. AWS Architecture
4. Networking
5. Monitoring
6. Logging
7. Backup Strategy
8. CI/CD
9. Security
10. Disaster Recovery

---

# 1. Deployment Strategy

Development

- Local Docker Compose

Testing

- Dedicated Environment

Production

- AWS Deployment

---

# 2. Docker Architecture

Containers:

- Frontend
- Backend
- PostgreSQL
- Redis
- Nginx

Containers communicate over an internal Docker network.

---

# 3. AWS Architecture

Initial Deployment

- EC2
- Docker Compose

Future Production

- Application Load Balancer
- ECS
- RDS PostgreSQL
- ElastiCache Redis
- S3
- CloudWatch

---

# 4. Networking

External Users

↓

HTTPS

↓

Nginx

↓

FastAPI

↓

PostgreSQL

Redis remains internal.

---

# 5. Monitoring

Version 1

- CloudWatch Logs
- Application Logs
- Request Logs
- Error Logs

Future

- Prometheus
- Grafana

---

# 6. Logging

Centralized logging.

Levels:

- INFO
- WARNING
- ERROR
- CRITICAL

Sensitive information is never logged.

---

# 7. Backup Strategy

Database

- Daily Backup

Uploaded Files

- S3 Versioning (future)

Configuration

- Source Control

---

# 8. CI/CD

Future Pipeline

GitHub

↓

GitHub Actions

↓

Testing

↓

Docker Build

↓

Deployment

---

# 9. Security

- HTTPS
- Environment Variables
- JWT
- Secure Headers
- Rate Limiting
- Input Validation

---

# 10. Disaster Recovery

Recovery includes:

- Database Restore
- Container Redeployment
- Configuration Recovery

Recovery procedures will be documented separately.

---

# Part 8 – Development Standards & Implementation Roadmap

---

# Table of Contents

1. Coding Standards
2. Git Workflow
3. Testing Strategy
4. Documentation
5. Claude Code Development Workflow
6. Project Roadmap
7. Risks
8. Change Management
9. Technical Debt
10. Document Status

---

# 1. Coding Standards

- PEP 8
- Type Hints
- SOLID
- DRY
- KISS
- Clean Code

---

# 2. Git Workflow

Main Branch

↓

Feature Branch

↓

Pull Request

↓

Review

↓

Merge

Feature naming:

feature/customer-booking

bugfix/resource-assignment

---

# 3. Testing Strategy

Unit Tests

- Business Engines
- Services

Integration Tests

- APIs
- Database

End-to-End Tests (Future)

- Customer Booking
- Staff Booking

---

# 4. Documentation

Every feature should include:

- Architecture Notes
- API Documentation
- Database Changes
- ADR updates (if applicable)

---

# 5. Claude Code Development Workflow

For each feature:

1. Read the PRD
2. Read the TAS
3. Identify affected modules
4. Generate implementation plan
5. Implement models
6. Implement repositories
7. Implement services
8. Implement business engines
9. Implement APIs
10. Write tests
11. Review
12. Commit

Claude Code should not introduce requirements outside the approved PRD.

---

# 6. Implementation Roadmap

Phase 1

- Project Refactoring
- Folder Structure
- Configuration

Phase 2

- Identity & Authentication

Phase 3

- Business & Branch Management

Phase 4

- Customer Management

Phase 5

- Resource Management

Phase 6

- Service Management

Phase 7

- Booking Engine

Phase 8

- Notifications

Phase 9

- Audit System

Phase 10

- AWS Deployment

---

# 7. Risks

- Tenant Isolation Errors
- Authorization Bugs
- Booking Race Conditions
- Incorrect Availability Calculation
- Deployment Misconfiguration

Mitigation:

- Code Reviews
- Automated Tests
- Architecture Reviews

---

# 8. Change Management

Any architectural change requires:

- Architecture Review
- PRD Consistency Check
- TAS Update
- Implementation Update

---

# 9. Technical Debt

Deferred items:

- Online Payments
- SMS
- WhatsApp
- AI Scheduling
- Mobile Applications
- Multi-language Support

These are intentionally postponed.

---

# 10. Document Status

Document:

Technical Architecture Specification

Version:

1.0

Status:

Version 1.0 – Frozen

Next Phase:

Implementation using Claude Code

---

# End of Technical Architecture Specification

**Document Status: Version 1.0 – Frozen**
**Approved for Implementation**