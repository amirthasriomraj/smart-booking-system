import React, { useContext, useEffect, useState, useCallback } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import { getBusinessNotifications, listBranchesForBusiness } from "../api/api"

const PAGE_SIZE = 20

// Business Owner's Notifications history (M9 follow-up fix) — business-
// scoped, with an optional Branch filter.
export default function BusinessNotifications() {
  const { user } = useContext(AuthContext)
  const businessId = user?.business?.id

  const [branches, setBranches] = useState([])
  const [branchId, setBranchId] = useState("")
  const [status, setStatus] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [page, setPage] = useState(1)

  const [notifications, setNotifications] = useState([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!businessId) {
      return
    }
    listBranchesForBusiness(businessId).then((r) => setBranches(r.data.items)).catch(() => {})
  }, [businessId])

  const load = useCallback(() => {
    if (!businessId) {
      return
    }
    getBusinessNotifications(businessId, {
      branch_id: branchId || undefined,
      status: status || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      page,
      page_size: PAGE_SIZE,
    })
      .then((response) => {
        setNotifications(response.data.items)
        setTotal(response.data.total)
        setTotalPages(response.data.total_pages)
      })
      .catch(() => setError("Failed to load notifications"))
  }, [businessId, branchId, status, dateFrom, dateTo, page])

  useEffect(() => {
    load()
  }, [load])

  const handleFilterChange = (setter) => (value) => {
    setter(value)
    setPage(1)
  }

  if (!businessId) {
    return <p>You do not have an active business.</p>
  }

  return (
    <div>
      <h1>Notifications</h1>
      {error && <p style={{ color: "red" }}>{error}</p>}

      <select value={branchId} onChange={(e) => handleFilterChange(setBranchId)(e.target.value)}>
        <option value="">All branches</option>
        {branches.map((b) => (
          <option key={b.id} value={b.id}>{b.branch_name}</option>
        ))}
      </select>
      {" "}
      <select value={status} onChange={(e) => handleFilterChange(setStatus)(e.target.value)}>
        <option value="">All statuses</option>
        <option value="Sent">Sent</option>
        <option value="Failed">Failed</option>
        <option value="Pending">Pending</option>
      </select>
      {" "}
      <label>
        From: <input type="date" value={dateFrom} onChange={(e) => handleFilterChange(setDateFrom)(e.target.value)} />
      </label>
      {" "}
      <label>
        To: <input type="date" value={dateTo} onChange={(e) => handleFilterChange(setDateTo)(e.target.value)} />
      </label>

      <p>{total} total notifications — page {page} of {totalPages || 1}.</p>

      <table>
        <thead>
          <tr>
            <th>When</th>
            <th>Type</th>
            <th>Channel</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {notifications.map((n) => (
            <tr key={n.id}>
              <td>{n.created_at}</td>
              <td>{n.notification_type}</td>
              <td>{n.channel}</td>
              <td>{n.status}</td>
            </tr>
          ))}
          {notifications.length === 0 && (
            <tr><td colSpan="4">No matching notifications.</td></tr>
          )}
        </tbody>
      </table>

      <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>
        Previous
      </button>
      {" "}
      <button onClick={() => setPage((p) => p + 1)} disabled={page >= totalPages}>
        Next
      </button>
    </div>
  )
}
