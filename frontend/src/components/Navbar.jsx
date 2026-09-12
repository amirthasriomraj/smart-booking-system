import { Link, useNavigate } from "react-router-dom"
import { useContext } from "react"

import api from "../api/api"
import { AuthContext } from "../auth/AuthContextOnly"

export default function Navbar() {

  const { user, logout } = useContext(AuthContext)
  const navigate = useNavigate()

  const isPlatformAdmin = user?.is_platform_admin
  const isActiveBusinessOwner = user?.business?.role_code === "BUSINESS_OWNER" && user?.business?.status === "Active"
  const canManageStaff =
    user?.business?.status === "Active" &&
    ["BUSINESS_OWNER", "HR_USER"].includes(user?.business?.role_code)
  const canManageResources =
    user?.business?.status === "Active" &&
    ["BUSINESS_OWNER", "BRANCH_MANAGER", "HR_USER"].includes(user?.business?.role_code)
  const canManageServices =
    user?.business?.status === "Active" &&
    ["BUSINESS_OWNER", "BRANCH_MANAGER"].includes(user?.business?.role_code)
  const canManageCustomers =
    user?.business?.status === "Active" &&
    ["BUSINESS_OWNER", "BRANCH_MANAGER"].includes(user?.business?.role_code)
  const canManageBookings =
    user?.business?.status === "Active" &&
    ["BUSINESS_OWNER", "BRANCH_MANAGER"].includes(user?.business?.role_code)
  const canManageCoupons =
    user?.business?.status === "Active" &&
    ["BUSINESS_OWNER", "BRANCH_MANAGER"].includes(user?.business?.role_code)
  const isBranchManager = user?.business?.role_code === "BRANCH_MANAGER" && user?.business?.status === "Active"
  const isResourceUser = user?.business?.role_code === "RESOURCE_USER"
  const isCustomer = !!user?.customer

  const handleLogout = async () => {

    try {

      await api.post("/auth/logout")

    } catch (error) {

      console.error("Logout failed", error)

    }

    logout()

    // Customers have their own public login page; every other role uses
    // the staff/admin one — preserved exactly as before for all of them.
    navigate(isCustomer ? "/customer/login" : "/login")

  }

  return (

    <nav style={{ marginBottom: "20px" }}>

      <Link to="/dashboard">Dashboard</Link>

      {" | "}

      <Link to="/profile">Profile</Link>

      {isPlatformAdmin && (
        <>
          {" | "}
          <Link to="/admin">Admin</Link>
          {" | "}
          <Link to="/admin/platform-fee">Platform Fee</Link>
          {" | "}
          <Link to="/admin/audit-logs">Audit Logs</Link>
          {" | "}
          <Link to="/admin/notifications">Notifications</Link>
        </>
      )}

      {isActiveBusinessOwner && (
        <>
          {" | "}
          <Link to="/business/profile">Business Profile</Link>
          {" | "}
          <Link to="/business/branches">My Branches</Link>
          {" | "}
          <Link to="/business/booking-history">Booking History</Link>
          {" | "}
          <Link to="/business/audit-history">Audit History</Link>
          {" | "}
          <Link to="/business/notifications">Notifications</Link>
        </>
      )}

      {isBranchManager && (
        <>
          {" | "}
          <Link to="/business/branch-overview">Branch Overview</Link>
          {" | "}
          <Link to="/business/booking-history">Booking History</Link>
          {" | "}
          <Link to="/business/branch-audit-history">Audit History</Link>
          {" | "}
          <Link to="/business/branch-notifications">Notifications</Link>
        </>
      )}

      {isResourceUser && (
        <>
          {" | "}
          <Link to="/resource/schedule">My Schedule</Link>
        </>
      )}

      {canManageStaff && (
        <>
          {" | "}
          <Link to="/business/staff">Staff</Link>
        </>
      )}

      {canManageResources && (
        <>
          {" | "}
          <Link to="/business/resources">Resources</Link>
        </>
      )}

      {canManageServices && (
        <>
          {" | "}
          <Link to="/business/services">Services</Link>
        </>
      )}

      {canManageCustomers && (
        <>
          {" | "}
          <Link to="/business/customers">Customers</Link>
        </>
      )}

      {canManageBookings && (
        <>
          {" | "}
          <Link to="/business/bookings">Bookings</Link>
        </>
      )}

      {canManageCoupons && (
        <>
          {" | "}
          <Link to="/business/coupons">Coupons</Link>
        </>
      )}

      {isCustomer && (
        <>
          {" | "}
          <Link to="/customer/profile">My Profile</Link>
          {" | "}
          <Link to="/customer/browse">Browse</Link>
          {" | "}
          <Link to="/customer/bookings">My Bookings</Link>
        </>
      )}

      {" | "}

      <button onClick={handleLogout}>
        Logout
      </button>

    </nav>

  )

}