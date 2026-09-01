import React from "react"
import { BrowserRouter, Routes, Route } from "react-router-dom"

import Login from "./pages/Login"
import Register from "./pages/Register"
import Dashboard from "./pages/Dashboard"
import Profile from "./pages/Profile"
import Admin from "./pages/Admin"
import BranchManagement from "./pages/BranchManagement"
import StaffManagement from "./pages/StaffManagement"
import ResourceManagement from "./pages/ResourceManagement"
import ServiceManagement from "./pages/ServiceManagement"
import BookingManagement from "./pages/BookingManagement"
import ResetPassword from "./pages/ResetPassword"
import AcceptInvitation from "./pages/AcceptInvitation"
import CustomerRegister from "./pages/CustomerRegister"
import CustomerLogin from "./pages/CustomerLogin"
import CustomerProfile from "./pages/CustomerProfile"
import CustomerBrowse from "./pages/CustomerBrowse"
import CustomerBookings from "./pages/CustomerBookings"
import CustomerManagement from "./pages/CustomerManagement"

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
        </Route>

        {/* Business Owner routes */}
        <Route element={<ProtectedRoute businessOwnerOnly={true} />}>
          <Route path="/business/branches" element={<BranchManagement />} />
          <Route path="/business/staff" element={<StaffManagement />} />
        </Route>

      </Routes>

    </BrowserRouter>
  )
}

export default App