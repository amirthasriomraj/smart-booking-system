import React from "react"
import { BrowserRouter, Routes, Route } from "react-router-dom"

import Login from "./pages/Login"
import Register from "./pages/Register"
import Dashboard from "./pages/Dashboard"
import Profile from "./pages/Profile"
import Admin from "./pages/Admin"
import BranchManagement from "./pages/BranchManagement"
import BusinessProfile from "./pages/BusinessProfile"
import StaffManagement from "./pages/StaffManagement"
import ResourceManagement from "./pages/ResourceManagement"
import ServiceManagement from "./pages/ServiceManagement"
import BookingManagement from "./pages/BookingManagement"
import CouponManagement from "./pages/CouponManagement"
import PlatformFeeManagement from "./pages/PlatformFeeManagement"
import ResetPassword from "./pages/ResetPassword"
import AcceptInvitation from "./pages/AcceptInvitation"
import CustomerRegister from "./pages/CustomerRegister"
import CustomerLogin from "./pages/CustomerLogin"
import CustomerProfile from "./pages/CustomerProfile"
import CustomerBrowse from "./pages/CustomerBrowse"
import CustomerBookings from "./pages/CustomerBookings"
import CustomerManagement from "./pages/CustomerManagement"
import AdminAuditLogs from "./pages/AdminAuditLogs"
import AdminNotifications from "./pages/AdminNotifications"
import BusinessAuditHistory from "./pages/BusinessAuditHistory"
import BranchOverview from "./pages/BranchOverview"
import ResourcePortal from "./pages/ResourcePortal"
import BookingHistory from "./pages/BookingHistory"
import BranchAuditHistory from "./pages/BranchAuditHistory"
import BusinessNotifications from "./pages/BusinessNotifications"
import BranchNotifications from "./pages/BranchNotifications"

import ProtectedRoute from "./components/ProtectedRoute"

function App() {
  return (
    <BrowserRouter>

      <Routes>

        {/* ✅ DEFAULT ROUTE */}
        <Route path="/" element={<Login />} />

        {/* Public routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/accept-invitation" element={<AcceptInvitation />} />

        {/* Customer Portal — public routes (TAS Part 5 §3: a distinct
            "Customer Booking Portal" route, separate from staff/admin Login) */}
        <Route path="/customer/register" element={<CustomerRegister />} />
        <Route path="/customer/login" element={<CustomerLogin />} />

        {/* Protected routes */}
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/profile" element={<Profile />} />
          {/* Role-gated inside the component itself: Business Owner, Branch
              Manager, and HR User each see a different subset (ID-016). */}
          <Route path="/business/resources" element={<ResourceManagement />} />
          {/* Role-gated inside the component itself: Business Owner and
              Branch Manager only — HR User and Platform Admin have no
              Service Management access (ID-027). */}
          <Route path="/business/services" element={<ServiceManagement />} />
          {/* Role-gated inside the component itself: Business Owner and
              Branch Manager, business-wide — Customer Management has no
              branch scoping (ID-032). */}
          <Route path="/business/customers" element={<CustomerManagement />} />
          {/* Role-gated inside the component itself: Business Owner
              (business-wide) and Branch Manager (own branch only) — HR User
              and Resource User have no booking-management access
              (Milestone 7). */}
          <Route path="/business/bookings" element={<BookingManagement />} />
          {/* Role-gated inside the component itself: Business Owner
              (business-wide) and Branch Manager (own branch, subject to
              approval) — Milestone 8 Coupons & Promotions (rule 10). */}
          <Route path="/business/coupons" element={<CouponManagement />} />
          {/* M9 Phase 6c: Branch Manager's own assigned branch (backend
              also allows the Business Owner business-wide); gated generically
              here since the page itself handles "not assigned to a branch". */}
          <Route path="/business/branch-overview" element={<BranchOverview />} />
          {/* M9 Phase 6c: Resource User self-service (PRD §35 Resource
              Dashboard) — any authenticated user, the backend rejects
              anyone with no linked Resource. */}
          <Route path="/resource/schedule" element={<ResourcePortal />} />
          {/* M9 follow-up fix: Booking History — Business Owner (business-
              wide, with a Branch filter) or Branch Manager (their own
              branch only); the page itself picks the right endpoint per
              role and the backend enforces the scoping either way. */}
          <Route path="/business/booking-history" element={<BookingHistory />} />
          {/* M9 follow-up fix: Branch Manager's own Audit History /
              Notifications — gated generically, same pattern as Branch
              Overview above; backend enforces the branch scoping. */}
          <Route path="/business/branch-audit-history" element={<BranchAuditHistory />} />
          <Route path="/business/branch-notifications" element={<BranchNotifications />} />
        </Route>

        {/* Customer Portal — protected routes (Milestone 6, extended in Milestone 7) */}
        <Route element={<ProtectedRoute customerOnly={true} />}>
          <Route path="/customer/profile" element={<CustomerProfile />} />
          <Route path="/customer/browse" element={<CustomerBrowse />} />
          <Route path="/customer/bookings" element={<CustomerBookings />} />
        </Route>

        {/* Admin routes */}
        <Route element={<ProtectedRoute adminOnly={true} />}>
          <Route path="/admin" element={<Admin />} />
          {/* Milestone 8: Platform Admin fee authority (ID-051, rule 17-19). */}
          <Route path="/admin/platform-fee" element={<PlatformFeeManagement />} />
          {/* M9 Phase 6c: Platform Administrator Dashboard modules. */}
          <Route path="/admin/audit-logs" element={<AdminAuditLogs />} />
          <Route path="/admin/notifications" element={<AdminNotifications />} />
        </Route>

        {/* Business Owner routes */}
        <Route element={<ProtectedRoute businessOwnerOnly={true} />}>
          <Route path="/business/branches" element={<BranchManagement />} />
          <Route path="/business/profile" element={<BusinessProfile />} />
          {/* M9 Phase 6c: Business Owner Dashboard — Audit History module. */}
          <Route path="/business/audit-history" element={<BusinessAuditHistory />} />
          {/* M9 follow-up fix: Business Owner Notifications. */}
          <Route path="/business/notifications" element={<BusinessNotifications />} />
        </Route>

        {/* Business Owner or HR — M9 Phase 6, PRD §10.4 Employee transfers */}
        <Route element={<ProtectedRoute ownerOrHrOnly={true} />}>
          <Route path="/business/staff" element={<StaffManagement />} />
        </Route>

      </Routes>

    </BrowserRouter>
  )
}

export default App