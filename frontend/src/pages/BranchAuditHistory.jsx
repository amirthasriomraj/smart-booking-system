import React, { useContext, useEffect, useState, useCallback } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import { getBranchAuditHistory, getBranchAuditLogFilterOptions } from "../api/api"

const PAGE_SIZE = 20

// Branch Manager's own Audit History (M9 follow-up fix) — scoped to their
// assigned branch only, enforced server-side. Mirrors the Business Owner's
// Audit History page but with no Branch filter, since it's already
// implicitly one branch.
export default function BranchAuditHistory() {
  const { user } = useContext(AuthContext)
  const branchId = user?.business?.branch_id

  const [entityTypes, setEntityTypes] = useState([])
  const [actions, setActions] = useState([])
  const [entityType, setEntityType] = useState("")
  const [action, setAction] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [page, setPage] = useState(1)

  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!branchId) {
      return
    }
    getBranchAuditLogFilterOptions(branchId)
      .then((r) => {
        setEntityTypes(r.data.entity_types)
        setActions(r.data.actions)
      })
      .catch(() => {})
  }, [branchId])

  const load = useCallback(() => {
    if (!branchId) {
      return
    }
    getBranchAuditHistory(branchId, {
      entity_type: entityType || undefined,
      action: action || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      page,
      page_size: PAGE_SIZE,
    })
      .then((response) => {
        setLogs(response.data.items)
        setTotal(response.data.total)
        setTotalPages(response.data.total_pages)
      })
      .catch(() => setError("Failed to load audit history"))
  }, [branchId, entityType, action, dateFrom, dateTo, page])

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
      <h1>Audit History</h1>
      {error && <p style={{ color: "red" }}>{error}</p>}

      <select value={entityType} onChange={(e) => handleFilterChange(setEntityType)(e.target.value)}>
        <option value="">All entity types</option>
        {entityTypes.map((et) => (
          <option key={et} value={et}>{et}</option>
        ))}
      </select>
      {" "}
      <select value={action} onChange={(e) => handleFilterChange(setAction)(e.target.value)}>
        <option value="">All actions</option>
        {actions.map((a) => (
          <option key={a} value={a}>{a}</option>
        ))}
      </select>
      {" "}
      <label>
        From: <input type="date" value={dateFrom} onChange={(e) => handleFilterChange(setDateFrom)(e.target.value)} />
      </label>
      {" "}
      <label>
        To: <input type="date" value={dateTo} onChange={(e) => handleFilterChange(setDateTo)(e.target.value)} />
      </label>

      <p>{total} total entries — page {page} of {totalPages || 1}.</p>

      <table>
        <thead>
          <tr>
            <th>When</th>
            <th>Entity</th>
            <th>Action</th>
            <th>Performed By</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id}>
              <td>{log.created_at}</td>
              <td>{log.entity_type} #{log.entity_id}</td>
              <td>{log.action}</td>
              <td>{log.performed_by ?? "system"}</td>
              <td>{log.reason ?? ""}</td>
            </tr>
          ))}
          {logs.length === 0 && (
            <tr><td colSpan="5">No matching audit log entries.</td></tr>
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
