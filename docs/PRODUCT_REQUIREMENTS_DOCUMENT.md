# Smart Booking System
## Product Requirements Document (PRD)

**Version:** 1.0  
**Status:** Frozen (Version 1 Product Design)  
**Prepared By:** Amirtha Sri Omraj  
**Document Type:** Product Requirements Document (PRD)

---

# Revision History

| Version | Date | Description |
|----------|------|-------------|
| 1.0 | August 2026 | Initial frozen product design |

---

# Table of Contents

1. Introduction
2. Product Vision
3. Problem Statement
4. Product Goals
5. Target Users
6. Product Scope
7. Out of Scope
8. Product Principles
9. Terminology
10. User Roles
11. Tenant Registration
12. Branch Lifecycle
13. Resource Management
14. Service Management
15. Customer Management
16. Booking Lifecycle
17. Approval Workflows
18. Notifications
19. Audit & History
20. Business Rules
21. Non-Functional Requirements
22. Future Roadmap

---

# 1. Introduction

## 1.1 Purpose

Smart Booking System is a cloud-based, multi-tenant Software-as-a-Service (SaaS) platform designed to help businesses manage appointments, customers, resources, employees, branches and business operations through a single configurable platform.

Unlike traditional appointment software built for one specific industry, Smart Booking System is designed around a **generic resource model**, allowing businesses from different industries to use the same platform without changing the core product.

The purpose of this document is to define the functional requirements, business rules, workflows and product behaviour before implementation begins.

This document intentionally avoids implementation details. Technical design decisions are documented separately in the **Technical Architecture Specification (TAS)**.

---

## 1.2 Objectives

The objectives of this Product Requirements Document are:

- Define the complete product scope.
- Freeze Version 1 functional behaviour.
- Document all user roles and permissions.
- Define approval workflows.
- Define booking workflows.
- Serve as the single source of truth for product behaviour.
- Prevent requirement ambiguity during implementation.

---

# 2. Product Vision

## Vision Statement

Build a production-grade, configurable, multi-tenant appointment and resource management platform that enables businesses of different industries to operate using a common booking engine.

The platform should support businesses ranging from small local stores to enterprise organizations while maintaining complete tenant isolation and allowing each business to configure its own operational rules.

---

## Long-Term Vision

The long-term vision is to evolve Smart Booking System into a global SaaS platform capable of supporting businesses across multiple industries without changing the underlying architecture.

Examples include:

- Hospitals
- Clinics
- Beauty Salons
- Spas
- Sports Academies
- Swimming Pools
- Tennis Courts
- Coaching Centres
- Coworking Spaces
- Photography Studios
- Equipment Rentals
- Consultation Services
- Government Appointment Systems

The platform should remain industry-agnostic, with configuration replacing hard-coded business logic wherever possible.

---

# 3. Problem Statement

Many businesses continue to rely on spreadsheets, paper registers, phone calls, or disconnected software to manage appointments and resources.

Existing appointment software is often tailored to a specific industry, making it difficult to adapt to businesses with different operational models.

Despite differences in industry, these businesses share a common requirement:

> Allocate an available resource for a specific service at a specific date and time.

The resource may represent:

- A person (doctor, trainer, consultant)
- A physical asset (court, swimming pool, meeting room)
- Equipment (camera, vehicle, laboratory equipment)

Smart Booking System abstracts this concept into a configurable resource model, enabling the same platform to support multiple business types.

---

# 4. Product Goals

## Primary Goals

- Build a production-ready SaaS platform.
- Support multiple independent businesses (tenants).
- Ensure strict tenant isolation.
- Provide configurable booking workflows.
- Support approval-based governance.
- Maintain complete auditability.
- Deliver production-grade security.
- Design for scalability and future expansion.

## Secondary Goals

- Demonstrate real-world software engineering practices.
- Showcase multi-tenant architecture.
- Support AWS cloud deployment.
- Provide a strong portfolio project for backend/software engineering interviews.
- Serve as the foundation for future commercial SaaS offerings.

---

# 5. Target Users

The platform is intended for businesses that manage appointments or reservable resources.

Example industries include:

- Healthcare
- Wellness
- Fitness
- Education
- Sports
- Hospitality
- Professional Services
- Equipment Rentals

The platform is not customized for any single industry. Instead, businesses configure:

- Resources
- Services
- Working hours
- Booking rules
- Resource categories

to match their operational requirements.

---

# 6. Product Scope (Version 1)

Version 1 includes the following major modules:

### Platform Administration

- Platform administrator dashboard
- Business approval
- Branch approval
- Business suspension
- Business activation
- Global monitoring

### Business Management

- Business registration
- Business profile
- Business configuration
- Business approval workflow

### Branch Management

- Multiple branches
- Branch approval
- Branch configuration
- Branch managers

### User Management

- Business Owners
- Branch Managers
- Human Resources
- Customers
- Invitations
- Authentication
- Authorization

### Resource Management

The system supports both human and non-human resources.

Examples:

Human Resources:
- Doctor
- Trainer
- Coach
- Employee
- Consultant

Non-Human Resources:
- Tennis Court
- Swimming Pool
- Meeting Room
- Studio
- Equipment
- Vehicle

Resources may optionally have login credentials if they represent employees.

### Service Management

- Business service templates
- Branch service inheritance
- Branch service overrides
- Approval workflow
- Service availability
- Service duration

### Customer Management

- Customer registration
- Walk-in customers
- Customer history
- Booking history

### Appointment Management

- Booking creation
- Availability checking
- Resource assignment
- Manual reassignment
- Rescheduling
- Cancellation
- Booking history

### Notification Module

Email notifications for:

- Registration
- Invitations
- Password reset
- Booking confirmation
- Booking cancellation
- Booking rescheduling
- Business approval
- Branch approval
- Service approval

### Audit Module

Permanent audit logs for:

- Approvals
- Administrative actions
- Booking history
- User actions

---

# 7. Out of Scope (Version 1)

The following features are intentionally excluded from Version 1:

- Online payment gateways
- Subscription billing
- SMS notifications
- WhatsApp notifications
- Mobile applications
- AI recommendations
- Marketplace discovery
- Public APIs
- Multi-language support

These capabilities are reserved for future releases.

---

# 8. Product Principles

Every product decision should follow these principles:

### Multi-Tenant First

Every feature must support multiple businesses sharing the same platform while maintaining complete tenant isolation.

### Generic Resource Model

Resources are not assumed to be employees.

A resource may represent:

- A person
- A room
- A sports court
- A swimming pool
- Equipment
- A laboratory
- A vehicle

### Configuration Over Customization

Businesses configure behaviour instead of requiring code changes.

Examples include:

- Resource categories
- Business categories
- Services
- Working hours
- Booking rules

### Approval-Based Governance

Critical operations require approval before becoming active.

Examples:

- Business registration
- Branch creation
- Branch service overrides

### Auditability

Every significant action must be traceable.

The system records:

- Who performed the action
- When it occurred
- Previous value
- New value
- Reason (where applicable)

### Scalability

The architecture must support future expansion without major redesign.

Examples include:

- Multiple countries
- Multiple time zones
- Additional notification providers
- Subscription plans
- Payment gateways

---

# 9. Terminology

| Term | Description |
|------|-------------|
| Platform | Smart Booking System SaaS platform |
| Tenant | A registered business using the platform |
| Business Owner | Primary administrator of a tenant |
| Branch | Physical location belonging to a business |
| Resource | Human or non-human entity that can be booked |
| Resource Category | Business-defined grouping of resources |
| Service Template | Business-level definition of a service |
| Branch Service | Branch-specific implementation of a service |
| Customer | End user receiving a service |
| Booking | Reservation of a resource for a service |
| Approval | Authorization required before activation |
| Audit Log | Permanent record of important actions |

---

# 10. User Roles

Smart Booking System follows a hierarchical role-based access control (RBAC) model. Each role has clearly defined responsibilities and permissions within the platform.

---

## 10.1 Platform Administrator

The Platform Administrator manages the Smart Booking System itself and has visibility across all tenants (businesses). This role is responsible for maintaining platform integrity, approving new businesses and branches, and handling platform-level operations.

### Responsibilities

- Approve or reject new business registrations.
- Suspend or reactivate businesses.
- Approve or reject new branch requests.
- View all businesses and their branches.
- Monitor platform usage.
- Access platform-wide audit logs.
- Manage platform configuration.

### Restrictions

The Platform Administrator does **not** participate in the daily operations of any tenant. They cannot create bookings or manage customers for a business unless explicitly impersonating a tenant in a future version.

---

## 10.2 Business Owner

The Business Owner is the primary administrator of a tenant (business). Every business must have exactly one Business Owner.

The Business Owner has full administrative control over every branch belonging to their business.

### Responsibilities

- Manage business profile.
- Create branch requests.
- Manage all approved branches.
- Approve branch service overrides.
- Create business-level service templates.
- Invite Branch Managers.
- Invite Human Resource users.
- Manage all customers.
- Manage all resources.
- View business-wide analytics.
- Configure business policies.

### Permissions

Business Owners can:

- Create services.
- Edit services.
- Archive services.
- Create resources.
- Archive resources.
- Create customers.
- Create bookings.
- Override bookings.
- View all bookings.
- Transfer employees between branches.
- Approve branch customizations.

### Restrictions

A Business Owner:

- cannot belong to another business.
- cannot become a Branch Manager.
- cannot become a Human Resource user.
- cannot become a Resource.
- cannot own multiple businesses.
- may register as a **Customer** using a different personal email address if they wish to consume services offered by another business.

This design keeps business ownership unambiguous and mirrors how many SaaS platforms maintain a single ownership identity per organization.

---

## 10.3 Branch Manager

A Branch Manager administers a single approved branch.

Branch Managers are responsible for the day-to-day operations of their assigned branch.

### Responsibilities

- Manage branch resources.
- Manage branch customers.
- Create bookings.
- Reschedule bookings.
- Cancel bookings.
- Manage branch working hours.
- Customize inherited services.
- Create branch-specific services.

### Permissions

Branch Managers can:

- Invite Resources with login access.
- Create Resources without login.
- Create Customers.
- Edit Customers.
- Assign Resources.
- Override resource assignments.
- View branch reports.

### Restrictions

A Branch Manager:

- belongs to exactly one branch at any point in time.
- may be transferred to another branch within the same business.
- cannot manage two branches simultaneously.
- cannot belong to another business.
- cannot approve their own service modifications.

Any service customization performed by a Branch Manager must be approved by the Business Owner before becoming active.

---

## 10.4 Human Resource User

The Human Resource role manages employee-related operations for the business.

Typical responsibilities include:

- Employee onboarding.
- Employee invitations.
- Employee records.
- Resource login management.
- Employee transfers.

Human Resource users cannot modify bookings unless explicitly granted future permissions.

---

## 10.5 Resource

A Resource represents anything that can be reserved.

Resources are intentionally generic.

Examples include:

### Human Resources

- Doctor
- Coach
- Trainer
- Consultant
- Therapist
- Employee

### Non-Human Resources

- Swimming Pool
- Tennis Court
- Meeting Room
- Laboratory
- Vehicle
- Camera
- Studio

Resources may optionally receive login credentials.

If login credentials are provided, the Resource can:

- View assigned bookings.
- Update booking status (future versions).
- Manage personal availability (future versions).

Otherwise, the Resource exists only as a schedulable entity.

---

## 10.6 Customer

Customers consume services offered by businesses.

Customers may:

- Register themselves.
- Be created by a Business Owner.
- Be created by a Branch Manager.

Customer accounts are isolated per business.

Version 1 does not include a global customer identity shared across businesses.

---

# 11. User Identity Rules

To maintain tenant isolation and simplify permission management, Smart Booking System enforces the following identity rules.

## Business Owner

A Business Owner:

- owns exactly one business.
- cannot belong to another business.
- cannot simultaneously hold any other employee role.

If the same individual wants to own another business, they must register using a different email address.

---

## Branch Manager

A Branch Manager:

- belongs to one business.
- belongs to one branch.
- may transfer between branches within the same business.
- cannot work in two branches simultaneously.
- cannot belong to another business.

---

## Human Resource User

Human Resource users follow the same identity rules as Branch Managers.

---

## Resource

Resources belong to one branch at a time.

Future versions may allow historical transfers while preserving booking history.

---

## Customer

Customers are scoped to a single business.

Future releases may introduce a unified customer identity spanning multiple businesses.

---

# 12. Tenant Registration

Tenant registration creates a new business on the platform.

The registration process is intentionally lightweight to encourage onboarding while ensuring platform governance through approvals.

---

## Step 1 – Owner Registration

The future Business Owner provides:

### Personal Information

- Username
- Email Address
- Password

### Business Information

- Business Name
- Business Category
- Country

Business Categories may include:

- Clinic
- Hospital
- Salon
- Spa
- Sports Centre
- Fitness Centre
- Coaching Institute
- Photography Studio
- Equipment Rental
- Professional Services
- Other

The list is configurable by the Platform Administrator.

---

## Step 2 – Verification

After successful registration:

- Owner account is created.
- Business is created in **Pending Approval** state.
- Owner receives verification and status notifications.

---

## Step 3 – Platform Approval

The Platform Administrator reviews the application.

Possible outcomes:

### Approved

Business becomes Active.

Owner gains access to the Business Dashboard.

### Rejected

Business remains inactive.

Reason for rejection is recorded and communicated.

---

## Step 4 – Initial Business Setup

After approval, the Business Owner completes setup by configuring:

- Business profile.
- Branding.
- Working preferences.
- Notification preferences.

---

## Step 5 – First Branch Creation

Every business must create at least one branch before accepting bookings.

During initial registration, branch details are **not** collected.

Instead, after login, the Business Owner creates the first branch by providing:

- Branch Name
- Address
- City
- State
- Country
- Contact Information

The newly created branch enters **Pending Approval**.

No bookings may be accepted until at least one branch has been approved by the Platform Administrator.

---

# 13. Branch Lifecycle

Every branch follows the lifecycle below:

Pending Creation

↓

Pending Approval

↓

Approved

↓

Active

↓

Suspended (optional)

↓

Archived (future)

---

## Pending Approval

While a branch is pending approval:

- Resources may be configured.
- Services may be configured.
- Working hours may be configured.
- Customers may be imported.

Bookings are **not** permitted.

---

## Approved

Once approved:

- Branch becomes operational.
- Bookings become available.
- Resources become schedulable.
- Customers may reserve services.

---

## Suspension

Suspended branches:

- cannot receive new bookings.
- retain historical records.
- remain visible in reports.

---

# 14. Resource Management

## 14.1 Overview

The Resource module is the core abstraction of Smart Booking System.

Unlike traditional appointment systems that assume appointments are always assigned to employees, Smart Booking System introduces a **generic Resource model**.

A Resource represents **anything that can be reserved or assigned to perform a service**.

This design allows the platform to support multiple industries without changing the underlying booking engine.

Examples include:

### Human Resources

- Doctor
- Trainer
- Coach
- Therapist
- Consultant
- Teacher
- Technician
- Beautician

### Non-Human Resources

- Swimming Pool
- Tennis Court
- Football Ground
- Conference Room
- Meeting Room
- Studio
- Camera
- Laboratory
- Vehicle
- Equipment

The booking engine treats all Resources equally.

Only their configuration differs.

---

# 14.2 Resource Categories

Each Business defines its own Resource Categories.

Resource Categories are **business-specific**.

Different businesses may use completely different categories.

Example:

Hospital

- Doctor
- Nurse
- Lab Technician

Sports Academy

- Cricket Ground
- Football Ground
- Coach

Photography Studio

- Camera
- Studio
- Photographer

Salon

- Hair Stylist
- Beautician
- Facial Room

This flexibility allows Smart Booking System to remain industry independent.

---

# 14.3 Resource Attributes

Every Resource contains the following information.

## Basic Information

- Resource Name
- Resource Code (optional)
- Resource Category
- Branch
- Status

---

## Scheduling Information

- Working Hours
- Weekly Availability
- Break Timings
- Maximum Bookings Per Day
- Booking Buffer Time

---

## Login Information

A Resource may optionally receive login credentials.

Examples:

Doctor

✔ Login Required

Swimming Pool

✘ Login Not Required

Meeting Room

✘ Login Not Required

Trainer

✔ Login Required

If login credentials are created, the Resource becomes an authenticated user with the Resource role.

---

## Status

A Resource can have one of the following statuses:

- Pending
- Active
- Suspended
- Archived (Future)

Only Active Resources can receive bookings.

---

# 14.4 Resource Lifecycle

Create

↓

Configure

↓

(Optional) Invite Login

↓

Activate

↓

Available for Booking

↓

Suspend

↓

Archive (Future)

---

# 14.5 Resource Creation

Resources may be created by:

- Business Owner
- Branch Manager

If the creator chooses to provide login credentials:

1. Resource record is created.

2. Login invitation email is generated.

3. Resource activates account using invitation.

If login credentials are not provided:

The Resource functions purely as a schedulable asset.

---

# 14.6 Resource Availability

Availability determines whether bookings can be assigned.

Availability depends on:

- Working Hours
- Holidays
- Manual Blocking
- Existing Bookings
- Temporary Suspension

The Booking Engine must consider all of these before confirming a booking.

---

# 15. Service Management

Services define what a business offers to customers.

Unlike Resources, Services follow an inheritance model.

Business

↓

Branch

↓

Booking

This allows businesses to standardize services while giving branches controlled flexibility.

---

# 15.1 Service Templates

Service Templates are created by the Business Owner.

Examples:

Haircut

Swimming Class

General Consultation

MRI Scan

Court Booking

Equipment Rental

A Service Template acts as the master definition.

---

## Service Template Fields

Every template contains:

- Service Name

- Description

- Duration

- Default Price

- Default Resource Categories

- Default Buffer Time

- Default Working Rules

- Active Status

---

# 15.2 Branch Services

When a Branch is created:

It automatically inherits every Service Template from the Business.

Initially:

Branch Service

=

Business Service Template

No duplication of business logic should occur.

Branch Services maintain a reference to their originating template.

---

# 15.3 Branch Overrides

Branches may customize inherited services.

Examples:

Business

Haircut

₹300

30 Minutes

Branch A

Haircut

₹350

45 Minutes

Branch B

Haircut

₹250

30 Minutes

Branch-specific changes allow operational flexibility.

---

# 15.4 Approval Workflow

To preserve business consistency:

Any Branch customization requires Business Owner approval before becoming active.

Examples requiring approval:

- Price changes

- Duration changes

- Resource Category changes

- Service availability changes

Until approval:

Existing approved configuration continues to operate.

---

# 15.5 Service Lifecycle

Draft

↓

Pending Approval

↓

Approved

↓

Active

↓

Suspended

↓

Archived (Future)

Only Approved services can receive bookings.

---

# 15.6 Service Assignment

A Service may be assigned to one or more Resource Categories.

Example:

Swimming Lesson

↓

Allowed Categories

- Coach

- Swimming Pool

Medical Consultation

↓

Allowed Categories

Doctor

Meeting Reservation

↓

Allowed Categories

Conference Room

The Booking Engine validates that assigned Resources belong to an allowed category.

---

# 16. Working Hours

Working Hours determine when bookings may occur.

Working Hours exist at multiple levels.

Business

↓

Branch

↓

Resource (Future)

---

# 16.1 Business Working Hours

Business Working Hours represent the default schedule.

Example:

Monday

09:00–18:00

Tuesday

09:00–18:00

...

These defaults are inherited by newly created branches.

---

# 16.2 Branch Working Hours

Each Branch inherits Business Working Hours.

Branch Managers may customize them.

Examples:

Holiday

Weekend Changes

Extended Hours

Reduced Hours

Branch modifications become effective immediately unless future policy requires approval.

---

# 16.3 Booking Validation

A booking is valid only if:

✔ Branch is Active

✔ Service is Active

✔ Resource is Active

✔ Resource is Available

✔ Requested time falls inside Working Hours

✔ Slot is unoccupied

Otherwise the booking request is rejected.

---

# 16.4 Resource Capacity (Future)

Future versions may support capacity-based resources.

Examples:

Swimming Pool

Capacity

30

Current Bookings

22

Remaining Capacity

8

Version 1 assumes one booking occupies one resource.

Capacity booking will be introduced in a later release without changing the overall architecture.

---

# 17. Customer Management

## 17.1 Overview

Customers are the recipients of services offered by a Business.

Customers may either:

- Register themselves (future enhancement)
- Be created by a Business Owner
- Be created by a Branch Manager

Version 1 treats Customers as business-specific entities. A customer created under one Business is not automatically available to another Business.

This ensures tenant isolation and avoids accidental sharing of customer information.

---

## 17.2 Customer Profile

Each customer record contains:

### Personal Information

- First Name
- Last Name
- Gender (Optional)
- Date of Birth (Optional)

### Contact Information

- Mobile Number
- Email Address (Optional)

### Address Information

- Address Line
- City
- State
- Country
- Postal Code

### System Information

- Customer ID
- Business ID
- Registration Date
- Status
- Notes (Optional)

---

## 17.3 Customer Status

A Customer may have one of the following statuses:

- Active
- Inactive
- Archived (Future)

Inactive customers cannot make new bookings but their historical booking records remain available.

---

## 17.4 Customer Creation

Customers can be onboarded through the following methods.

### Customer Self Registration

Customers can register themselves through the public customer portal.

Upon successful registration, a Platform Customer account is created.

Customers can subsequently authenticate and make appointments with one or more businesses.

### Business Owner Dashboard

Business Owners can manually create customer records for walk-in customers or customers who request assistance.

### Branch Manager Dashboard

Branch Managers can manually create customer records directly from their assigned branch.

### Walk-In Registration

During appointment creation, a Branch Manager or Business Owner may register a new customer without requiring a separate registration workflow.

---

## 17.5 Customer Self Registration

Customers may independently register an account using the public customer portal.

Registration includes:

- First Name
- Last Name
- Email Address
- Mobile Number
- Password

Future versions may include email verification.

After successful registration, customers can:

- Login
- Manage their profile
- Book appointments
- View booking history
- Cancel appointments (subject to business policy)
- Reschedule appointments (subject to business policy)

---

## 17.6 Customer Search

Users should be able to search customers using:

- Name
- Mobile Number
- Email
- Customer ID

Future versions may support fuzzy search.

---

# 18. Booking Management

## 18.1 Overview

The Booking module is the heart of Smart Booking System.

A Booking reserves a Resource for a Customer to receive a Service at a specified Branch during a scheduled time slot.

Every booking belongs to exactly:

- One Business
- One Branch
- One Customer
- One Service
- One Resource

---

## 18.2 Booking Components

Each booking contains:

### Business Information

- Business
- Branch

### Customer Information

- Customer

### Service Information

- Selected Service

### Resource Information

- Assigned Resource

### Schedule

- Date
- Start Time
- End Time

### Booking Metadata

- Booking Status
- Created By
- Created At
- Last Updated

---

## 18.3 Booking Lifecycle

Every booking follows the lifecycle below.

Draft

↓

Confirmed

↓

Completed

OR

Cancelled

OR

No Show (Future)

A booking never physically disappears from the system.

---

## 18.4 Booking Creation

Bookings may be created through the following channels.

### Customer Self Booking

Customers can create appointments through the public booking portal.

Booking flow:

Customer Login

↓

Select Business

↓

Select Branch

↓

Select Service

↓

Select Available Date

↓

Select Available Time

↓

Booking Validation

↓

Booking Confirmation

### Business Owner

Business Owners may create bookings on behalf of customers.

### Branch Manager

Branch Managers may create bookings for walk-in or assisted customers.

---

### Booking Validation

Before confirming a booking the system verifies:

✔ Business is Active

✔ Branch is Approved

✔ Branch is Active

✔ Service is Active

✔ Resource is Active

✔ Resource belongs to Branch

✔ Resource Category is allowed

✔ Requested slot is available

✔ Booking falls within Working Hours

Only if all validations succeed is the booking confirmed.

---

## 18.5 Booking Statuses

Version 1 supports:

### Confirmed

Booking successfully created.

### Completed

Service successfully delivered.

### Cancelled

Booking cancelled before completion.

Future versions may include:

- Pending Payment
- Checked In
- In Progress
- No Show
- Refunded

---

## 18.6 Booking Confirmation

Once confirmed:

- Resource schedule becomes unavailable.
- Customer receives confirmation notification.
- Audit record is created.

---

## 18.7 Booking Completion

Completion indicates that the scheduled service has been delivered.

Completion:

- updates booking status.
- records completion timestamp.
- creates audit history.

---

# 19. Booking Rescheduling

## 19.1 Overview

Rescheduling changes the booking date, time and/or assigned Resource without creating a new booking.

The original Booking ID remains unchanged.

This preserves reporting accuracy and historical continuity.

---

## 19.2 Reschedule Rules

Rescheduling validates:

- Resource availability
- Working hours
- Service availability
- Branch availability

If validation fails, rescheduling is rejected.

---

## 19.3 Audit Requirement

Every reschedule creates a permanent history entry.

Example:

Previous Date

↓

15 August

New Date

↓

17 August

Previous Resource

↓

Coach Rahul

New Resource

↓

Coach Arjun

Both values remain permanently visible in booking history.

---

# 20. Booking Cancellation

Bookings may be cancelled by:

- Business Owner
- Branch Manager

Future Versions:

- Customer

---

## Cancellation Behaviour

Cancellation:

- releases Resource availability.
- changes booking status.
- preserves booking history.
- records cancellation timestamp.

Bookings are never deleted.

---

## Cancellation Reason

The cancelling user may optionally record a reason.

Examples:

- Customer Request
- Resource Unavailable
- Emergency Closure
- Weather Conditions

The reason becomes part of the audit log.

---

# 21. Manual Booking Overrides

Business Owners and Branch Managers may manually override Resource assignments.

Examples:

Original Resource

↓

Court 1

Override

↓

Court 2

or

Original Resource

↓

Doctor A

Override

↓

Doctor B

Overrides are useful when:

- Resource unavailable
- Maintenance
- Emergency
- Employee leave

---

## Override Rules

Overrides must satisfy:

✔ Same Branch

✔ Allowed Resource Category

✔ Available Schedule

Otherwise the override is rejected.

---

# 22. Booking History

Every booking maintains immutable historical records.

Examples:

Booking Created

↓

Resource Changed

↓

Service Changed

↓

Time Changed

↓

Completed

Every event stores:

- Action
- Previous Value
- New Value
- User
- Timestamp

History cannot be modified.

---

# 23. Notifications

Version 1 includes email notifications.

Notifications are generated for:

### Account Events

- Registration
- Password Reset
- Invitation Acceptance

### Business Events

- Business Approved
- Business Rejected

### Branch Events

- Branch Approved
- Branch Rejected

### Service Events

- Service Override Approved
- Service Override Rejected

### Booking Events

- Booking Created
- Booking Rescheduled
- Booking Cancelled
- Booking Completed

Notification providers remain configurable for future expansion.

---

# 24. Booking Rules Summary

The booking engine enforces the following mandatory rules.

A booking cannot be created unless:

✔ Business is Active

✔ Branch is Approved

✔ Service is Approved

✔ Resource is Active

✔ Resource belongs to Branch

✔ Resource Category matches Service

✔ Working Hours permit booking

✔ Slot is available

✔ Customer exists

These validations guarantee consistent booking behaviour across all industries.

---

# 25. Approval Workflows

## 25.1 Overview

Approval workflows ensure that critical changes within the platform are reviewed before becoming operational.

This governance model balances flexibility for tenants with administrative control, maintaining consistency and preventing unauthorized operational changes.

Every approval action generates an immutable audit record.

---

# 25.2 Approval Levels

The platform contains two independent approval layers.

## Platform-Level Approval

Performed by:

- Platform Administrator

Applies to:

- Business Registration
- New Branch Creation

---

## Business-Level Approval

Performed by:

- Business Owner

Applies to:

- Branch Service Overrides
- New Branch Services
- Future configurable business operations

---

# 25.3 Business Registration Approval

Business Registration Flow

Business Owner Registration

↓

Business Created

↓

Pending Approval

↓

Platform Administrator Review

↓

Approved

OR

Rejected

---

## Approved

If approved:

- Business Status becomes Active.
- Owner gains dashboard access.
- Initial branch setup becomes available.

---

## Rejected

If rejected:

- Business remains inactive.
- Owner receives rejection notification.
- Rejection reason is stored.

---

# 25.4 Branch Approval

Branch Creation

↓

Pending Approval

↓

Platform Administrator Review

↓

Approved

↓

Operational

Until approval:

✔ Branch configuration allowed

✔ Resources can be created

✔ Services can be configured

✘ Bookings NOT allowed

---

# 25.5 Service Override Approval

When a Branch Manager customizes an inherited service:

Inherited Service

↓

Branch Modification

↓

Pending Approval

↓

Business Owner Review

↓

Approved

OR

Rejected

Until approval:

Existing approved service continues operating.

Pending changes remain invisible to customers.

---

## Approval Actions

Business Owner may:

- Approve
- Reject
- Request Modification (Future)

---

# 25.6 Future Approval Workflows

The approval engine is designed for future expansion.

Potential future approvals include:

- Discount approval
- Refund approval
- Employee transfer approval
- Leave approval
- Bulk import approval
- Resource archive approval

No architectural redesign should be required to support additional approval types.

---

# 26. Ownership Hierarchy

The ownership hierarchy defines administrative authority throughout the platform.

Platform Administrator

↓

Business Owner

↓

Branch Manager

↓

Human Resource User

↓

Resource

↓

Customer

Permissions always flow downward.

Lower-level users cannot override higher-level decisions.

---

# 26.1 Platform Administrator Authority

The Platform Administrator controls:

- Businesses
- Branch approvals
- Platform configuration
- Global monitoring
- Platform audit logs

Platform Administrators never participate in day-to-day tenant operations.

---

# 26.2 Business Owner Authority

Business Owners control every branch within their business.

Responsibilities include:

- Business settings
- Service templates
- Employee invitations
- Branch approvals (business-level operations)
- Customer management
- Reporting

Business Owners have visibility across all branches belonging to their tenant.

---

# 26.3 Branch Manager Authority

Branch Managers control only their assigned branch.

They cannot:

- Access another branch
- View another branch's customers
- Modify another branch's services

Their permissions are limited to branch operations.

---

# 27. Permission Principles

The authorization system follows several guiding principles.

---

## Least Privilege

Users receive only the permissions required to perform their responsibilities.

---

## Tenant Isolation

Users cannot access data belonging to another business.

Tenant isolation applies to:

- Customers
- Resources
- Services
- Bookings
- Reports
- Audit Logs

---

## Branch Isolation

Branch Managers cannot manage resources or bookings belonging to another branch.

---

## Approval Before Activation

Changes requiring approval never become active until approved.

---

## Immutable History

Operational history cannot be edited or deleted.

---

# 28. Data Isolation Rules

Tenant isolation is one of the platform's most important architectural requirements.

Every business must behave as if it owns its own isolated system.

Businesses cannot:

- View another business
- Search another business
- Access another business's customers
- Access another business's bookings
- Access another business's reports

Platform Administrators remain the only exception.

---

# 29. Soft Delete Policy

Version 1 introduces a consistent lifecycle strategy.

Business data should rarely be physically deleted.

Instead, entities should transition through status changes.

Example lifecycle:

Active

↓

Suspended

↓

Archived

↓

(Permanent deletion only under controlled maintenance)

---

## Benefits

Soft deletion preserves:

- Historical reports
- Audit trails
- Booking history
- Regulatory compliance
- Data recovery

Future implementation should provide configurable retention policies.

---

# 30. Audit & Compliance

Every significant action must generate an audit event.

Audit entries cannot be modified by application users.

---

## Auditable Events

Examples include:

Business Approved

Branch Approved

Branch Rejected

Service Created

Service Updated

Service Override Submitted

Service Override Approved

Customer Created

Customer Updated

Booking Created

Booking Updated

Booking Rescheduled

Booking Cancelled

Resource Created

Resource Updated

Employee Invited

Employee Transfer

Role Changes

Permission Changes

Password Reset

Login (Future)

Logout (Future)

---

## Audit Entry Structure

Every audit record stores:

- Event ID
- Event Type
- Entity Type
- Entity Identifier
- Previous Value
- New Value
- Performed By
- Timestamp
- Reason (Optional)

---

# 31. Compliance Principles

Although Version 1 is not intended to satisfy specific legal compliance frameworks, the architecture should support future compliance requirements such as:

- GDPR
- HIPAA (future healthcare deployments)
- ISO 27001 operational practices
- SOC 2 operational controls

The audit model and soft-delete strategy are designed with future compliance in mind.

---

# 32. Version 1 Functional Freeze

The following capabilities are considered frozen for Version 1 and should not be changed without updating this document:

✔ Multi-tenant architecture

✔ One Business Owner per Business

✔ Generic Resource model

✔ Branch inheritance model

✔ Service Template architecture

✔ Branch Service Overrides

✔ Platform approval for Businesses

✔ Platform approval for Branches

✔ Business Owner approval for Service Overrides

✔ Immutable audit history

✔ Tenant isolation

✔ Branch isolation

✔ Resource-based booking engine

Any future enhancement should extend these principles rather than replace them.

---

# 33. Authentication

## 33.1 Overview

Authentication verifies the identity of every user before allowing access to the platform.

Version 1 supports secure email-based authentication using JWT access tokens and rotating refresh tokens.

The authentication system is designed to be independent of business logic so that future authentication providers (Google, Microsoft, SSO, etc.) can be added without major architectural changes.

---

## 33.2 Supported Authentication Methods

Version 1 supports:

- Username/Email + Password Login
- JWT Access Token
- Refresh Token Rotation
- Password Reset via Email

Future versions may support:

- Google Sign-In
- Microsoft Login
- Apple Login
- Enterprise Single Sign-On (SSO)
- Multi-Factor Authentication (MFA)

---

## 33.3 Password Policy

Passwords must satisfy configurable minimum security requirements.

Default Version 1 policy:

- Minimum length
- Uppercase letter
- Lowercase letter
- Number
- Special character

Passwords are never stored in plain text.

Only securely hashed passwords are persisted.

---

## 33.4 Password Reset

Users may reset forgotten passwords through email verification.

Flow:

Forgot Password

↓

Email Verification

↓

Secure Reset Link

↓

Password Validation

↓

Password Updated

↓

Existing reset token invalidated

Reset links are:

- Single-use
- Time limited
- Cryptographically secure

---

# 34. Authorization

## 34.1 Overview

After authentication, every request is authorized according to Role-Based Access Control (RBAC).

Authorization ensures that users may perform only the actions permitted for their role.

---

## 34.2 Authorization Levels

Platform Level

↓

Business Level

↓

Branch Level

↓

Resource Level

↓

Customer Level

Every API request validates:

- Authenticated user
- Business ownership
- Branch access
- Resource ownership (where applicable)
- Required permission

---

## 34.3 Permission Inheritance

Permissions inherit downward.

Platform Administrator

↓

Business Owner

↓

Branch Manager

↓

Human Resource User

↓

Resource

A lower role never automatically gains permissions belonging to a higher role.

---

# 35. Dashboard Overview

Each role receives a dedicated dashboard containing only relevant functionality.

---

## Platform Administrator Dashboard

Modules:

- Businesses
- Branch Approvals
- Platform Analytics
- Audit Logs
- Configuration
- Notifications

---

## Business Owner Dashboard

Modules:

- Business Profile
- Branches
- Services
- Resources
- Employees
- Customers
- Reports
- Approvals
- Audit History

---

## Branch Manager Dashboard

Modules:

- Branch Overview
- Resources
- Customers
- Bookings
- Service Requests
- Working Hours
- Daily Reports

---

## Human Resource Dashboard

Modules:

- Employees
- Invitations
- Transfers
- Resource Accounts

---

## Resource Dashboard (Optional Login)

Modules:

- Today's Schedule
- Upcoming Bookings
- Personal Availability (Future)
- Profile

## Customer Dashboard

The Customer Dashboard provides customers with self-service capabilities.

Modules include:

- Profile Management
- Upcoming Appointments
- Appointment History
- Book New Appointment
- Reschedule Appointment
- Cancel Appointment
- Notification Preferences (Future)

---

# 36. Reporting

Version 1 includes operational reporting.

Reports include:

Business Reports

- Total Bookings
- Completed Bookings
- Cancelled Bookings
- Active Branches
- Active Resources

Branch Reports

- Daily Bookings
- Resource Utilization
- Service Popularity

Customer Reports

- Booking History
- Visit Frequency

Future versions will introduce advanced analytics and visual dashboards.

---

# 37. Notification System

## Overview

Notifications keep users informed about important events.

The notification engine is event-driven.

Business logic triggers notification events rather than sending emails directly.

This design allows future support for:

- Email
- SMS
- WhatsApp
- Push Notifications
- In-App Notifications

without changing business workflows.

---

## Version 1 Notification Types

### Authentication

- Welcome Email
- Password Reset
- Invitation Accepted

---

### Platform

- Business Approved
- Business Rejected
- Branch Approved
- Branch Rejected

---

### Services

- Service Override Submitted
- Service Override Approved
- Service Override Rejected

---

### Bookings

- Booking Confirmation
- Booking Cancellation
- Booking Reschedule
- Booking Completion

---

## Delivery Principles

Notification failures must never interrupt business operations.

Business transactions complete successfully even if notification delivery fails.

Failed notifications should be eligible for retry mechanisms in future versions.

---

# 38. Search

Version 1 provides search functionality across major entities.

Supported searches include:

Customers

- Name
- Mobile
- Email

Resources

- Name
- Category

Bookings

- Booking ID
- Customer
- Resource
- Date

Services

- Name

Branches

- Name

Businesses (Platform Admin only)

- Business Name
- Category
- Country

---

# 39. Filtering & Sorting

Users should be able to filter and sort operational data.

Examples:

Bookings

Filter by:

- Date
- Status
- Resource
- Customer
- Service

Sort by:

- Date
- Time
- Recently Created

Resources

Filter by:

- Category
- Status
- Branch

Customers

Filter by:

- Active
- Inactive

Future versions may introduce saved filters.

---

# 40. Pagination

All list endpoints should support pagination.

Default behavior:

- Configurable page size
- Total record count
- Current page
- Total pages

Large datasets should never be returned in a single response.

---

# 41. Error Handling Principles

The platform should provide clear, consistent error responses.

Errors should:

- Explain what failed.
- Avoid exposing sensitive system details.
- Provide meaningful validation messages.
- Maintain a consistent API structure.

Unexpected system failures should be logged for administrators while returning safe responses to users.

---

# 42. Non-Functional Requirements

## 42.1 Overview

Non-functional requirements define how the platform should operate rather than what functionality it provides.

These requirements guide architectural decisions to ensure the platform is secure, scalable, reliable, maintainable, and production-ready.

---

# 43. Performance Requirements

## 43.1 API Response Time

Target API response times:

- Simple CRUD operations: < 300 ms
- Search operations: < 500 ms
- Booking operations: < 700 ms
- Dashboard summaries: < 1 second

These targets apply under normal operating conditions.

---

## 43.2 Concurrent Users

Version 1 should comfortably support:

- Hundreds of concurrent users
- Multiple businesses operating simultaneously
- Thousands of daily bookings

The architecture should scale horizontally without requiring major redesign.

---

## 43.3 Database Performance

Database queries should:

- Use indexes on frequently searched columns
- Avoid unnecessary joins
- Minimize N+1 query problems
- Support pagination for large datasets

Frequently queried entities include:

- Businesses
- Branches
- Resources
- Services
- Customers
- Bookings

---

# 44. Scalability

## 44.1 Horizontal Scalability

Application servers should remain stateless.

All shared state must be stored externally, allowing multiple application instances to run simultaneously behind a load balancer.

---

## 44.2 Vertical Scalability

The platform should also support increasing CPU, memory, and storage resources without architectural changes.

---

## 44.3 Database Growth

The database design should support:

- Millions of bookings
- Millions of customers
- Thousands of businesses
- Thousands of branches

Entity relationships should remain performant as data grows.

---

# 45. Availability

Version 1 targets high availability suitable for business applications.

Future deployments should support:

- Rolling deployments
- Zero or minimal downtime releases
- Automatic restart of failed services

---

## Planned Availability Target

Target uptime:

99.9%

Future enterprise deployments may target higher service-level objectives.

---

# 46. Reliability

The platform should behave predictably even during failures.

Requirements include:

- Graceful error handling
- Transaction consistency
- Safe rollback on failures
- Recovery after unexpected crashes

Critical operations should never leave the system in an inconsistent state.

---

# 47. Security Requirements

Security is a core architectural principle rather than an optional feature.

---

## Authentication Security

Requirements:

- Secure password hashing
- JWT access tokens
- Refresh token rotation
- Token revocation
- Password reset expiration
- Secure session management

---

## Authorization Security

Every request must verify:

- Authenticated identity
- Business ownership
- Branch access
- Role permissions

Unauthorized requests must be rejected.

---

## Data Protection

Sensitive information should be protected both in transit and at rest.

Examples include:

- Password hashes
- Refresh token hashes
- Password reset tokens
- Personally identifiable customer information

---

## API Security

The API should include:

- Request validation
- Consistent error handling
- Rate limiting
- Secure headers
- Input sanitization

Future versions may include:

- API keys
- OAuth
- IP allow-lists

---

# 48. Auditability

Every critical business action should be traceable.

Audit history should include:

- Actor
- Timestamp
- Previous value
- New value
- Reason (where applicable)

Audit records are immutable.

---

# 49. Logging

The platform should produce structured application logs.

Important events include:

Authentication

- Login
- Logout
- Password reset

Business

- Business approval
- Branch approval

Bookings

- Booking creation
- Booking updates
- Booking cancellation
- Booking completion

System

- Unexpected exceptions
- External service failures
- Background job failures

Logs should support future centralized monitoring solutions.

---

# 50. Monitoring

Future deployments should support infrastructure and application monitoring.

Metrics may include:

- CPU utilization
- Memory usage
- API latency
- Error rate
- Active users
- Booking throughput
- Database health

Monitoring should enable proactive issue detection.

---

# 51. Backup & Recovery

The production environment should support scheduled database backups.

Requirements:

- Automated backups
- Backup retention policy
- Point-in-time recovery (future)
- Disaster recovery procedures

Backups should be tested periodically.

---

# 52. Maintainability

The codebase should emphasize long-term maintainability.

Principles include:

- Modular architecture
- Clear separation of concerns
- Consistent coding standards
- Comprehensive documentation
- Reusable components

Business logic should remain independent of infrastructure concerns.

---

# 53. Testability

The system should support automated testing.

Testing layers include:

- Unit Tests
- Integration Tests
- API Tests
- End-to-End Tests (future)

Critical business workflows should have automated test coverage.

---

# 54. Deployment

Deployments should be repeatable and automated.

Version 1 targets containerized deployment using Docker.

Future deployments may include:

- CI/CD pipelines
- Blue-green deployments
- Rolling deployments

Deployment should require minimal manual intervention.

---

# 55. Browser & Device Compatibility

The web application should support current versions of major browsers.

Target browsers:

- Google Chrome
- Microsoft Edge
- Mozilla Firefox
- Safari

The user interface should be responsive across:

- Desktop
- Tablet
- Mobile

---

# 56. Internationalization

Although Version 1 focuses primarily on the Indian market, the architecture should support future international expansion.

Future capabilities include:

- Multiple countries
- Multiple currencies
- Multiple time zones
- Localization
- Language translations

The data model should avoid assumptions that restrict global adoption.

---

# 57. Extensibility

The platform should be designed to accommodate future enhancements without requiring significant architectural changes.

Examples include:

- Online payments
- Subscription plans
- Loyalty programs
- Coupons
- WhatsApp integration
- Video consultations
- AI-powered scheduling
- Marketplace features
- Public booking portal

Version 1 should establish a foundation that future versions can extend rather than replace.

---

# 58. Product Roadmap

## 58.1 Vision

Smart Booking System is envisioned as a configurable, enterprise-grade, multi-tenant SaaS platform that can serve appointment-based businesses across multiple industries.

The long-term objective is to provide a single platform capable of supporting businesses ranging from individual professionals to multi-branch enterprises while maintaining tenant isolation, scalability, and extensibility.

---

# 59. Product Evolution Strategy

The product will evolve incrementally through well-defined versions.

Each version builds upon the previous one without introducing breaking architectural changes.

Version 1 establishes the core platform.

Future versions extend the platform through additional modules.

---

# 60. Version 1 Scope

Version 1 delivers the Minimum Viable Product (MVP).

Primary objectives:

- Multi-tenant architecture
- Business registration
- Branch management
- Resource management
- Service templates
- Branch service overrides
- Customer management
- Booking management
- Role-based access control
- Approval workflows
- Audit logging
- Email notifications
- Authentication
- Dashboard foundation

Customer Portal

- Customer self-registration
- Customer authentication
- Customer profile management
- Customer self-booking
- Appointment history
- Appointment cancellation
- Appointment rescheduling

Version 1 intentionally excludes advanced commercial features to keep implementation focused and maintainable.

---

# 61. Version 2 Roadmap

Version 2 expands operational capabilities.

Planned features include:

## Payments

Support online payment providers.

Possible integrations:

- Razorpay
- Stripe
- PayPal (future)

Capabilities:

- Payment collection
- Refunds
- Payment history
- Payment status tracking

---

## Coupons & Promotions

Businesses can create:

- Discount coupons
- Promotional campaigns
- Limited-time offers
- Referral discounts

---

## Staff Availability

Resources with login access may:

- Mark leave
- Block schedules
- Update availability

Booking availability updates automatically.

---

## Calendar Improvements

Support:

- Weekly schedules
- Monthly schedules
- Holiday calendars
- Resource-specific calendars

---

# 62. Version 3 Roadmap

Version 3 focuses on enterprise readiness.

---

## Advanced Reporting

Interactive dashboards including:

- Revenue analytics
- Booking trends
- Resource utilization
- Customer retention
- Peak booking hours

---

## Subscription Plans

Support SaaS monetization through:

- Free plan
- Starter plan
- Professional plan
- Enterprise plan

Plans may define limits on:

- Branches
- Resources
- Employees
- Monthly bookings

---

## Marketplace

Customers may discover businesses through a public marketplace.

Features include:

- Business listings
- Ratings
- Reviews
- Public profiles

---

## Public Booking Pages

Each business receives a customizable public booking page.

Businesses may:

- Customize branding
- Configure booking rules
- Share booking links

---

## Multi-language Support

Businesses may choose preferred language.

Customers may independently select their language.

---

## Multi-currency Support

Businesses operating internationally may configure:

- Currency
- Tax settings
- Regional pricing

---

## AI Assistance

Potential AI features:

- Smart scheduling
- Demand prediction
- Booking recommendations
- Customer behavior analysis
- Automated reminders
- AI-powered business insights

---

# 63. Future Enterprise Features

Long-term roadmap includes:

- White-label deployments
- Franchise management
- Organization hierarchy
- Corporate accounts
- Enterprise SSO
- API integrations
- Webhooks
- ERP integration
- CRM integration
- Payroll integration
- Attendance management
- HR modules

These features are outside the scope of Version 1 but have been considered during architectural planning.

---

# 64. Future Integrations

The platform should support integrations with external systems.

Potential integrations include:

Communication:

- Email providers
- SMS gateways
- WhatsApp Business API

Payments:

- Razorpay
- Stripe
- PayPal

Cloud Storage:

- AWS S3
- Azure Blob Storage
- Google Cloud Storage

Authentication:

- Google
- Microsoft
- Apple

Calendars:

- Google Calendar
- Microsoft Outlook Calendar

Analytics:

- Google Analytics
- Microsoft Clarity

Monitoring:

- Grafana
- Prometheus
- CloudWatch

Messaging:

- RabbitMQ
- Apache Kafka
- AWS SQS

These integrations should remain optional and loosely coupled.

---

# 65. Deployment Evolution

Deployment strategy will mature alongside product growth.

Version 1

- Single-region deployment
- Docker containers
- PostgreSQL
- Redis

Version 2

- CI/CD automation
- Managed database
- Object storage
- Monitoring

Version 3

- Multi-region deployment
- Load balancing
- Auto-scaling
- Disaster recovery
- High availability

---

# 66. Product Design Principles

The platform will continue to follow these core principles throughout its evolution.

## Configurable

Businesses should configure behavior rather than require source-code changes.

---

## Generic

The architecture should remain industry-independent wherever practical.

---

## Modular

Features should be developed as independent modules with minimal coupling.

---

## Secure

Security should be built into every layer rather than added later.

---

## Scalable

The platform should scale with increasing businesses, branches, customers, resources, and bookings.

---

## Maintainable

Code quality and architectural clarity should remain priorities throughout product evolution.

---

## Extensible

Future features should be implemented through extension rather than redesign.

---

# 67. Out of Scope for Version 1

The following features are intentionally excluded from Version 1.

- Online payments
- Coupons
- Loyalty programs
- Memberships
- Ratings & reviews
- Push notifications
- WhatsApp notifications
- Mobile applications
- Marketplace
- Video consultations
- AI scheduling
- Public booking pages
- Multi-language UI
- Multi-currency pricing
- Subscription billing
- White-label support

These exclusions help ensure a focused, production-quality MVP.

---

# 68. Product Success Criteria

Version 1 will be considered successful when it:

- Supports multiple independent businesses
- Allows businesses to manage branches and resources
- Enables configurable service offerings
- Provides reliable booking management
- Maintains strict tenant isolation
- Supports secure authentication and authorization
- Includes approval workflows and audit trails
- Is deployable to a cloud environment
- Demonstrates production-quality engineering practices
- Serves as a strong portfolio project showcasing backend architecture and software engineering skills

---

# 69. Business Rules Catalogue

This chapter consolidates all business rules governing the Smart Booking System.

These rules represent the functional behavior of Version 1 and must be followed consistently throughout implementation.

---

# 69.1 Platform Rules

## BR-001

The platform shall support multiple independent businesses (tenants).

---

## BR-002

Each tenant's data shall remain completely isolated from every other tenant.

---

## BR-003

Only Platform Administrators may view or manage multiple businesses.

---

## BR-004

Platform Administrators shall not participate in the operational management of tenant businesses.

---

# 69.2 Business Rules

## BR-005

Every Business must have exactly one active Business Owner.

---

## BR-006

A Business Owner may own only one Business.

If another business needs to be created, a different email address shall be used.

---

## BR-007

Business Owners cannot simultaneously act as:

- Branch Manager
- Human Resource User
- Resource

within any business.

---

## BR-008

Business registration requires Platform Administrator approval before becoming active.

---

## BR-009

Inactive Businesses cannot accept bookings.

---

## BR-010

Suspended Businesses retain all historical data.

No information shall be permanently deleted.

---

# 69.3 Branch Rules

## BR-011

Every Business must contain at least one Branch.

---

## BR-012

A newly created Branch shall enter the **Pending Approval** state.

---

## BR-013

Only Platform Administrators may approve Branches.

---

## BR-014

Pending Branches may be configured.

Examples:

- Working Hours
- Resources
- Services

However,

Bookings are prohibited until approval.

---

## BR-015

Business Owners have complete visibility across every Branch belonging to their Business.

---

## BR-016

Branch Managers may only access their assigned Branch.

---

# 69.4 Employee Rules

## BR-017

A Branch Manager belongs to exactly one Business.

---

## BR-018

A Branch Manager belongs to exactly one Branch at any point in time.

---

## BR-019

Branch Managers may transfer between Branches within the same Business.

---

## BR-020

Branch Managers cannot manage multiple Branches simultaneously.

---

## BR-021

Human Resource Users follow the same Business and Branch assignment rules as Branch Managers.

---

## BR-022

Employees may move to another Business only after their existing Business membership becomes inactive.

---

# 69.5 Resource Rules

## BR-023

Resources may represent:

- People
- Rooms
- Courts
- Equipment
- Pools
- Vehicles

The platform shall never assume a Resource represents a person.

---

## BR-024

Resources belong to exactly one Branch.

---

## BR-025

Resources inherit Branch Working Hours when first created.

---

## BR-026

Branch Managers or Business Owners may customize Resource availability.

---

## BR-027

Human Resources may optionally receive login credentials.

---

## BR-028

Non-human Resources never receive login credentials.

---

# 69.6 Service Rules

## BR-029

Business Owners create Service Templates.

---

## BR-030

Branches inherit every approved Service Template.

---

## BR-031

Branch Managers may customize inherited Services.

---

## BR-032

Customized Services remain in Pending Approval until approved by the Business Owner.

---

## BR-033

Only approved Services become available for booking.

---

## BR-034

Rejected Service Overrides never replace existing approved Services.

---

# 69.7 Customer Rules

## BR-035

Customers may register their own accounts.

---

## BR-036

Customers may book appointments without employee assistance.

---

## BR-037

Business Owners may manually create Customer records.

---

## BR-038

Branch Managers may manually create Customer records.

---

## BR-039

A single Customer account may book appointments across multiple Businesses.

Business-specific operational information remains isolated for each Business.

---

## BR-040

Customers may update only their own profile information.

---

## BR-041

Customers may only access their own bookings.

---

# 69.8 Booking Rules

## BR-042

Every Booking belongs to exactly:

- One Business
- One Branch
- One Customer
- One Service
- One Resource

---

## BR-043

Bookings require:

✔ Active Business

✔ Approved Branch

✔ Approved Service

✔ Active Resource

✔ Available Time Slot

---

## BR-044

Bookings cannot overlap for the same Resource.

---

## BR-045

Bookings remain permanently stored.

Deletion is prohibited.

---

## BR-046

Rescheduling updates the existing Booking.

A new Booking shall not be created.

---

## BR-047

Booking History records every significant modification.

---

## BR-048

Business Owners and Branch Managers may manually reassign Resources.

---

## BR-049

Resource reassignment validates:

- Availability
- Resource Category
- Working Hours

---

# 69.9 Approval Rules

## BR-050

Business Registration requires Platform approval.

---

## BR-051

Branch Creation requires Platform approval.

---

## BR-052

Branch Service Overrides require Business Owner approval.

---

## BR-053

Every Approval decision generates an Audit Log.

---

# 69.10 Notification Rules

## BR-054

Successful Bookings trigger confirmation notifications.

---

## BR-055

Booking Reschedules trigger notification events.

---

## BR-056

Booking Cancellations trigger notification events.

---

## BR-057

Business and Branch approvals trigger notification events.

---

## BR-058

Service approvals trigger notification events.

---

# 69.11 Audit Rules

## BR-059

Critical operations generate immutable audit records.

---

## BR-060

Audit records cannot be modified.

---

## BR-061

Soft deletion shall be preferred over permanent deletion.

---

## BR-062

Every audit record stores:

- Actor
- Timestamp
- Entity
- Action
- Previous Value
- New Value

---

# 69.12 Security Rules

## BR-063

Every request requires authentication unless explicitly marked public.

---

## BR-064

Authorization checks occur after authentication.

---

## BR-065

Users may only access resources belonging to their authorization scope.

---

## BR-066

Sensitive credentials shall never be stored in plaintext.

---

## BR-067

Refresh Tokens shall support secure rotation and revocation.

---

## BR-068

Password reset tokens shall expire automatically.

---

# 69.13 Future Rules

Future versions may extend this catalogue.

New business rules shall:

- receive unique identifiers,
- document affected modules,
- include acceptance criteria,
- be reviewed before implementation.

Existing rule identifiers must never be reused.

---

# 70. Functional Acceptance Criteria

## 70.1 Overview

This chapter defines the acceptance criteria for Version 1.

Each feature is considered complete only when all associated acceptance criteria have been satisfied.

These acceptance criteria will serve as the baseline for implementation testing, quality assurance, and future regression testing.

---

# 71. Platform Administration

## Business Registration

The feature shall be accepted when:

✔ A prospective Business Owner can submit a registration request.

✔ The Business is created in a Pending Approval state.

✔ The Platform Administrator can approve or reject the Business.

✔ The Business Owner receives notification of the decision.

✔ An approved Business can access the platform.

✔ A rejected Business remains inactive.

---

## Branch Approval

The feature shall be accepted when:

✔ A Business Owner can create a new Branch.

✔ Newly created Branches remain in Pending Approval.

✔ Platform Administrators can approve or reject the Branch.

✔ Approved Branches become operational.

✔ Pending Branches cannot receive bookings.

✔ Branch configuration is permitted before approval.

---

# 72. Business Management

Business Management shall be accepted when:

✔ Business profile can be viewed.

✔ Business profile can be updated.

✔ Business settings persist correctly.

✔ Business configuration is isolated from other tenants.

---

# 73. Branch Management

Branch Management shall be accepted when:

✔ Multiple Branches may exist within a Business.

✔ Branch Managers can only access their assigned Branch.

✔ Business Owners can access every Branch.

✔ Branch Working Hours are configurable.

✔ Branch Resources inherit Business defaults.

---

# 74. User Management

User Management shall be accepted when:

✔ Business Owners can invite Branch Managers.

✔ Business Owners can invite Human Resource users.

✔ Resources may optionally receive login credentials.

✔ Invitation emails are generated.

✔ Invited users can activate their accounts.

✔ Role-based permissions are enforced.

---

# 75. Resource Management

Resource Management shall be accepted when:

✔ Human Resources can be created.

✔ Non-human Resources can be created.

✔ Resource Categories are configurable.

✔ Resources inherit Branch Working Hours.

✔ Resource availability may be customized.

✔ Active Resources become available for booking.

✔ Suspended Resources cannot receive bookings.

---

# 76. Service Management

Service Management shall be accepted when:

✔ Business Owners create Service Templates.

✔ Branches automatically inherit Service Templates.

✔ Branch Managers may customize inherited Services.

✔ Customized Services remain Pending Approval.

✔ Business Owners approve or reject Service changes.

✔ Approved Services become immediately available.

✔ Rejected Services never replace existing approved Services.

---

# 77. Customer Management

Customer Management shall be accepted when:

✔ Customers can register themselves.

✔ Customers can securely log in.

✔ Customers can reset forgotten passwords.

✔ Customers can manage their own profile.

✔ Business Owners can manually create Customers.

✔ Branch Managers can manually create Customers.

✔ Customers can view their booking history.

✔ Customers cannot access another customer's information.

---

# 78. Appointment Booking

Appointment Booking shall be accepted when:

✔ Customers can create bookings.

✔ Business Owners can create bookings.

✔ Branch Managers can create bookings.

✔ Available time slots are calculated correctly.

✔ Double booking is prevented.

✔ Bookings store Business, Branch, Customer, Service and Resource.

✔ Booking confirmation notifications are generated.

---

# 79. Booking Rescheduling

Rescheduling shall be accepted when:

✔ Existing Booking IDs remain unchanged.

✔ Booking History records the modification.

✔ Availability is revalidated.

✔ Notifications are generated.

---

# 80. Booking Cancellation

Cancellation shall be accepted when:

✔ Booking Status changes to Cancelled.

✔ Booking History records the cancellation.

✔ Resource availability is released.

✔ Historical records remain available.

---

# 81. Authentication

Authentication shall be accepted when:

✔ Users authenticate successfully using valid credentials.

✔ Invalid credentials are rejected.

✔ JWT Access Tokens are issued.

✔ Refresh Tokens rotate correctly.

✔ Revoked Refresh Tokens cannot be reused.

✔ Password reset links expire correctly.

---

# 82. Authorization

Authorization shall be accepted when:

✔ Every request validates permissions.

✔ Tenant isolation is enforced.

✔ Branch isolation is enforced.

✔ Unauthorized requests are rejected.

✔ Role hierarchy behaves as specified.

---

# 83. Notifications

Notification functionality shall be accepted when:

✔ Email notifications are generated for supported events.

✔ Notification failures do not interrupt business operations.

✔ Notification history is recorded for auditing purposes.

---

# 84. Audit Logging

Audit Logging shall be accepted when:

✔ Critical operations generate audit records.

✔ Audit records are immutable.

✔ Previous and new values are stored where applicable.

✔ Audit records include actor and timestamp.

---

# 85. Search & Filtering

Search functionality shall be accepted when:

✔ Customers can be searched.

✔ Resources can be searched.

✔ Bookings can be searched.

✔ Services can be searched.

✔ Businesses can be searched by Platform Administrators.

Filtering shall be accepted when:

✔ Lists can be filtered.

✔ Lists can be sorted.

✔ Pagination is supported.

---

# 86. Performance

The platform shall satisfy the following operational expectations:

✔ CRUD operations complete within target response times.

✔ Booking operations remain performant.

✔ Large datasets support pagination.

✔ Database queries use appropriate indexes.

---

# 87. Security

Security shall be accepted when:

✔ Passwords are securely hashed.

✔ Sensitive tokens are never stored in plaintext.

✔ Secure headers are enabled.

✔ Input validation is enforced.

✔ Rate limiting is applied where appropriate.

✔ Authorization prevents privilege escalation.

---

# 88. Deployment

Deployment shall be accepted when:

✔ Application runs in Docker.

✔ Database migrations execute successfully.

✔ Required services start correctly.

✔ Environment configuration is externalized.

✔ Production deployment follows documented procedures.

---

# 89. Overall Version 1 Completion Criteria

Version 1 shall be considered complete when:

✔ All functional requirements defined in this PRD have been implemented.

✔ All acceptance criteria have been satisfied.

✔ All critical defects have been resolved.

✔ Documentation has been finalized.

✔ Technical Architecture Specification matches the implemented system.

✔ Automated tests pass successfully.

✔ Production deployment has been validated.

---

# 90. End-to-End User Workflows

This chapter summarizes the primary workflows supported by Version 1.

---

# 90.1 Business Registration Workflow

Prospective Business Owner

↓

Create Account

↓

Enter Business Details

↓

Business Created (Pending Approval)

↓

Platform Administrator Review

↓

Approved / Rejected

↓

Business Dashboard Access

↓

Configure Business

↓

Create First Branch

↓

Branch Approval

↓

Business Operational

---

# 90.2 Customer Self Registration Workflow

Visitor

↓

Register Account

↓

Platform Customer Account Created

↓

Login

↓

Access Customer Dashboard

↓

Browse Businesses

↓

Book Appointments

---

# 90.3 Customer Booking Workflow

Customer Login

↓

Select Business

↓

Select Branch

↓

Select Service

↓

Select Date

↓

System Calculates Availability

↓

Available Time Slots Displayed

↓

Select Time

↓

Booking Validation

↓

Booking Created

↓

Confirmation Notification

↓

Booking Visible in Customer Dashboard

---

# 90.4 Walk-in Booking Workflow

Customer Arrives

↓

Branch Manager Searches Customer

↓

Customer Exists?

↓

Yes → Continue

↓

No

↓

Create Customer

↓

Create Booking

↓

Confirmation

---

# 90.5 Branch Creation Workflow

Business Owner

↓

Create Branch

↓

Branch Status = Pending Approval

↓

Configure Branch

↓

Platform Administrator Approval

↓

Branch Active

↓

Bookings Enabled

---

# 90.6 Service Override Workflow

Business Owner

↓

Creates Service Template

↓

Branch Inherits Service

↓

Branch Manager Customizes Service

↓

Pending Approval

↓

Business Owner Review

↓

Approved

↓

Branch Service Updated

---

# 90.7 Resource Creation Workflow

Business Owner / Branch Manager

↓

Create Resource

↓

Assign Category

↓

Assign Branch

↓

Working Hours Inherited

↓

Create Login?

↓

Yes → Invitation Sent

↓

No → Resource Ready

↓

Available For Booking

---

# 90.8 Booking Reschedule Workflow

Authorized User

↓

Open Booking

↓

Modify Date/Time

↓

Availability Validation

↓

Resource Validation

↓

Update Booking

↓

Audit Entry

↓

Notification

---

# 91. Assumptions

The following assumptions apply to Version 1.

- Businesses operate independently.
- Every Business has one active Business Owner.
- Businesses manage their own Resources.
- Businesses manage their own Services.
- Resources belong to one Branch.
- Services belong to one Business.
- Branches inherit Business Services.
- Customer self-booking is supported.
- Public booking pages are available.
- Email is the only notification channel.
- One booking occupies one Resource.
- Timezone support is configurable for future international deployment.

---

# 92. Constraints

Version 1 intentionally excludes:

- Online Payments
- Subscription Billing
- Mobile Applications
- WhatsApp Notifications
- SMS Notifications
- Marketplace Discovery
- Multi-language UI
- AI Scheduling

These constraints are intentional to maintain a manageable implementation scope.

---

# 93. Risks

Potential implementation risks include:

- Incorrect tenant isolation
- Booking race conditions
- Resource scheduling conflicts
- Authorization vulnerabilities
- Poor scalability
- Notification delivery failures

The Technical Architecture Specification will define mitigation strategies for each identified risk.

---

# 94. Dependencies

The platform depends on:

Infrastructure

- PostgreSQL
- Redis
- Docker

Application

- FastAPI
- React
- JWT Authentication

External Services

- SMTP Email Provider

Future

- AWS
- Payment Gateway
- SMS Provider
- WhatsApp API

---

# 95. Glossary

| Term | Definition |
|------|------------|
| Tenant | Independent business using the platform |
| Branch | Physical location belonging to a Business |
| Resource | Human or non-human entity capable of receiving bookings |
| Service Template | Master service definition owned by the Business |
| Branch Service | Branch-specific implementation of a Service |
| Booking | Reservation of a Resource for a Customer |
| Customer Portal | Customer-facing application |
| Audit Log | Immutable history of important actions |
| Approval | Workflow requiring authorization before activation |
| RBAC | Role-Based Access Control |

---

# 96. Appendix

The following documents complement this PRD.

- Technical Architecture Specification
- Database Design Document
- API Specification
- UI Design (Future)
- Deployment Guide
- Test Plan

---

# 97. Product Requirements Freeze

This Product Requirements Document (PRD) defines the functional requirements for Version 1 of the Smart Booking System.

Following the review and approval process, this document is considered **functionally frozen**.

All implementation activities shall follow the requirements defined in this document.

Any future enhancement, modification, or deviation shall be managed through the Change Request (CR) process.

---

# 98. Change Management

After the PRD has been frozen, functional changes are not made directly to this document.

Instead, every proposed change shall follow the process below.

Business Requirement

↓

Discussion

↓

Impact Analysis

↓

Architecture Review

↓

Change Request (CR)

↓

PRD Update (if approved)

↓

Technical Architecture Specification Update

↓

Implementation

↓

Testing

↓

Release

This process ensures that business requirements, technical architecture, and implementation remain synchronized throughout the project lifecycle.

---

# 99. Versioning Strategy

The Smart Booking System follows semantic versioning for product documentation.

### Major Version

Used for significant architectural or functional changes.

Example:

Version 2.0

---

### Minor Version

Used for new features that do not introduce breaking changes.

Example:

Version 1.1

---

### Patch Version

Used for documentation corrections, clarifications, or bug fixes.

Example:

Version 1.0.1

---

# 100. Version 1 Deliverables

Version 1 includes the following modules.

### Platform

- Multi-tenant SaaS architecture
- Platform Administration
- Business Approval
- Branch Approval

### Business

- Business Registration
- Business Configuration
- Branch Management

### User Management

- Business Owner
- Branch Manager
- Human Resource User
- Resource User
- Customer

### Customer Portal

- Customer Self Registration
- Customer Login
- Customer Profile Management
- Customer Self Booking
- Booking History
- Appointment Cancellation
- Appointment Rescheduling

### Resource Management

- Human Resources
- Non-Human Resources
- Resource Categories
- Resource Availability

### Service Management

- Business Service Templates
- Branch Service Inheritance
- Branch Service Overrides
- Service Approval Workflow

### Booking Engine

- Booking Creation
- Booking Validation
- Resource Assignment
- Rescheduling
- Cancellation
- Manual Resource Override
- Booking History

### Authentication & Authorization

- JWT Authentication
- Refresh Token Rotation
- Password Reset
- Role-Based Access Control

### Notifications

- Email Notifications

### Audit

- Booking History
- Approval History
- Activity Audit Logs

### Deployment

- Docker
- AWS-Ready Architecture

---

# 101. Project Success Criteria

Version 1 will be considered successful when:

## Business Perspective

- Multiple independent businesses operate on the same platform.
- Customers independently register and book appointments.
- Businesses manage branches, services, and resources effectively.
- Approval workflows operate correctly.

## Technical Perspective

- Multi-tenant isolation is enforced.
- Secure authentication and authorization are implemented.
- Booking conflicts are prevented.
- Audit logging is comprehensive.
- The application is production-ready and deployable to AWS.

## Portfolio Perspective

The project demonstrates:

- SaaS product design
- Multi-tenant architecture
- Backend engineering
- Secure authentication
- Database design
- Production deployment
- Scalable software architecture

The project should be suitable for presentation and discussion during Software Engineer and Backend Developer interviews.

---

# 102. Document Status

Document Name:
Product Requirements Document (PRD)

Project:
Smart Booking System

Version:
1.0

Status:
✅ Frozen

Approved By:
Product Owner

Implementation Status:
Not Started

Next Document:
Technical Architecture Specification (TAS)

---

# 103. Next Phase

The Product Requirements Document serves as the functional baseline for implementation.

The next phase of the project is the preparation of the Technical Architecture Specification (TAS).

The TAS will translate every approved business requirement defined in this PRD into a complete technical design, including:

- System Architecture
- Domain Model
- Database Design
- API Design
- Authentication & Authorization
- Booking Engine
- Approval Engine
- Notification Engine
- AWS Infrastructure
- Deployment Architecture
- Security Architecture
- Development Standards

No new functional requirements shall be introduced during TAS preparation unless approved through the Change Request process.

---

# End of Product Requirements Document

**Document Status: Version 1.0 — Frozen**