import React, { useContext, useEffect, useState, useCallback } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import { getBranchNotifications } from "../api/api"

const PAGE_SIZE = 20

// Branch Manager's Notifications history (M9 follow-up fix) — scoped to
// their assigned branch only, enforced server-side.
export default function BranchNotifications() {
  const { user } = useContext(AuthContext)
  const branchId = user?.business?.branch_id

  const [status, setStatus] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [page, setPage] = useState(1)

  const [notifications, setNotifications] = useState([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [error, setError] = useState("")

  const load = useCallback(() => {
    if (!branchId) {
      return
    }
    getBranchNotifications(branchId, {
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
  }, [branchId, status, dateFrom, dateTo, page])

  useEffect(() => {
    load()
  }, [load])

  const handleFilterChange = (setter) => (value) => {
    setter(value)
    setPage(1)
  }

  if (!branchId) {
    return <p>You are not currently assigned to a branch.</p>
  }

  return (
    <div>
      <h1>Notifications</h1>
      {error && <p style={{ color: "red" }}>{error}</p>}

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
