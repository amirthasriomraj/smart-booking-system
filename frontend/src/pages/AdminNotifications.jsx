import React, { useEffect, useState, useCallback } from "react"
import { getAdminNotifications } from "../api/api"

const PAGE_SIZE = 20

// PRD §35 Platform Administrator Dashboard — Notifications module.
export default function AdminNotifications() {
  const [notifications, setNotifications] = useState([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState("")
  const [error, setError] = useState("")

  const load = useCallback(() => {
    getAdminNotifications({ status: status || undefined, page, page_size: PAGE_SIZE })
      .then((response) => {
        setNotifications(response.data.items)
        setTotal(response.data.total)
        setTotalPages(response.data.total_pages)
      })
      .catch(() => setError("Failed to load notifications"))
  }, [status, page])

  useEffect(() => {
    load()
  }, [load])

  const handleStatusChange = (value) => {
    setStatus(value)
    setPage(1)
  }

  return (
    <div>
      <h1>Notifications</h1>
      {error && <p style={{ color: "red" }}>{error}</p>}

      <select value={status} onChange={(e) => handleStatusChange(e.target.value)}>
        <option value="">All statuses</option>
        <option value="Sent">Sent</option>
        <option value="Failed">Failed</option>
        <option value="Pending">Pending</option>
      </select>

      <p>{total} total notifications — page {page} of {totalPages || 1}.</p>

      <table>
        <thead>
          <tr>
            <th>When</th>
            <th>Business</th>
            <th>Type</th>
            <th>Channel</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {notifications.map((n) => (
            <tr key={n.id}>
              <td>{n.created_at}</td>
              <td>{n.business_id ?? "—"}</td>
              <td>{n.notification_type}</td>
              <td>{n.channel}</td>
              <td>{n.status}</td>
            </tr>
          ))}
          {notifications.length === 0 && (
            <tr><td colSpan="5">No matching notifications.</td></tr>
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
