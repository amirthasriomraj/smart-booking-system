import React, { useContext, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import Navbar from "../components/Navbar"
import { AuthContext } from "../auth/AuthContextOnly"
import { getPlatformAnalytics, getBusinessReports } from "../api/api"

// PRD §35 Dashboard Overview — "Each role receives a dedicated dashboard
// containing only relevant functionality." This is the per-role landing
// page/hub; the linked pages themselves already exist (or were added
// alongside this in M9 Phase 6).
export default function Dashboard() {
  const { user } = useContext(AuthContext)

  const roleCode = user?.business?.role_code
  const isPlatformAdmin = user?.is_platform_admin
  const isOwner = roleCode === "BUSINESS_OWNER" && user?.business?.status === "Active"
  const isBranchManager = roleCode === "BRANCH_MANAGER"
  const isHr = roleCode === "HR_USER"
  const isResourceUser = roleCode === "RESOURCE_USER"
  const isCustomer = !!user?.customer

  const [analytics, setAnalytics] = useState(null)
  const [reports, setReports] = useState(null)

  useEffect(() => {
    if (isPlatformAdmin) {
      getPlatformAnalytics().then((r) => setAnalytics(r.data)).catch(() => {})
    }
  }, [isPlatformAdmin])

  useEffect(() => {
    if (isOwner) {
      getBusinessReports(user.business.id).then((r) => setReports(r.data)).catch(() => {})
    }
  }, [isOwner, user?.business?.id])

  return (
    <div>
      <Navbar />

      <h1>Dashboard</h1>

      {isPlatformAdmin && (
        <section>
          <h2>Platform Analytics</h2>
          {analytics && (
            <ul>
              <li>Total Businesses: {analytics.total_businesses}</li>
              <li>Pending Approvals: {analytics.pending_business_approvals}</li>
              <li>Active Businesses: {analytics.active_businesses}</li>
              <li>Active Branches: {analytics.active_branches}</li>
            </ul>
          )}
          <h2>Modules</h2>
          <ul>
            <li><Link to="/admin">Businesses &amp; Branch Approvals</Link></li>
            <li><Link to="/admin/audit-logs">Audit Logs</Link></li>
            <li><Link to="/admin/notifications">Notifications</Link></li>
            <li><Link to="/admin">Configuration (Business Categories)</Link></li>
            <li><Link to="/admin/platform-fee">Configuration (Platform Fee)</Link></li>
          </ul>
        </section>
      )}

      {isOwner && (
        <section>
          <h2>Reports</h2>
          {reports && (
            <ul>
              <li>Total Bookings: {reports.total_bookings}</li>
              <li>Completed Bookings: {reports.completed_bookings}</li>
              <li>Cancelled Bookings: {reports.cancelled_bookings}</li>
              <li>Active Branches: {reports.active_branches}</li>
              <li>Active Resources: {reports.active_resources}</li>
            </ul>
          )}
          <h2>Modules</h2>
          <ul>
            <li><Link to="/business/profile">Business Profile</Link></li>
            <li><Link to="/business/branches">Branches</Link></li>
            <li><Link to="/business/services">Services &amp; Approvals</Link></li>
            <li><Link to="/business/resources">Resources</Link></li>
            <li><Link to="/business/staff">Employees</Link></li>
            <li><Link to="/business/customers">Customers</Link></li>
            <li><Link to="/business/bookings">Bookings</Link></li>
            <li><Link to="/business/audit-history">Audit History</Link></li>
          </ul>
        </section>
      )}

      {isBranchManager && (
        <section>
          <h2>Modules</h2>
          <ul>
            <li><Link to="/business/branch-overview">Branch Overview &amp; Working Hours</Link></li>
            <li><Link to="/business/resources">Resources</Link></li>
            <li><Link to="/business/customers">Customers</Link></li>
            <li><Link to="/business/bookings">Bookings</Link></li>
            <li><Link to="/business/services">Service Requests</Link></li>
          </ul>
        </section>
      )}

      {isHr && (
        <section>
          <h2>Modules</h2>
          <ul>
            <li><Link to="/business/staff">Employees, Invitations &amp; Transfers</Link></li>
            <li><Link to="/business/resources">Resource Accounts</Link></li>
          </ul>
        </section>
      )}

      {isResourceUser && (
        <section>
          <h2>Modules</h2>
          <ul>
            <li><Link to="/resource/schedule">My Schedule</Link></li>
            <li><Link to="/profile">My Profile</Link></li>
          </ul>
        </section>
      )}

      {isCustomer && (
        <section>
          <h2>Modules</h2>
          <ul>
            <li><Link to="/customer/profile">Profile</Link></li>
            <li><Link to="/customer/bookings">My Appointments</Link></li>
            <li><Link to="/customer/browse">Book New Appointment</Link></li>
          </ul>
        </section>
      )}
    </div>
  )
}
