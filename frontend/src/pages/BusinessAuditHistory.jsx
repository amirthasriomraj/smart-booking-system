import React, { useContext, useEffect, useState, useCallback } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import { getBusinessAuditHistory, getBusinessAuditLogFilterOptions, listBranchesForBusiness } from "../api/api"

const PAGE_SIZE = 20

// PRD §35 Business Owner Dashboard — Audit History module (business-scoped,
// distinct from the Platform Admin's platform-wide Audit Logs).
export default function BusinessAuditHistory() {
  const { user } = useContext(AuthContext)
  const businessId = user?.business?.id

  const [branches, setBranches] = useState([])
  const [entityTypes, setEntityTypes] = useState([])
  const [actions, setActions] = useState([])
  const [branchId, setBranchId] = useState("")
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
    if (!businessId) {
      return
    }
    listBranchesForBusiness(businessId).then((r) => setBranches(r.data.items)).catch(() => {})
    getBusinessAuditLogFilterOptions(businessId)
      .then((r) => {
        setEntityTypes(r.data.entity_types)
        setActions(r.data.actions)
      })
      .catch(() => {})
  }, [businessId])

  const load = useCallback(() => {
    if (!businessId) {
      return
    }
    getBusinessAuditHistory(businessId, {
      branch_id: branchId || undefined,
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
  }, [businessId, branchId, entityType, action, dateFrom, dateTo, page])

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
      <h1>Audit History</h1>
      {error && <p style={{ color: "red" }}>{error}</p>}

      <select value={branchId} onChange={(e) => handleFilterChange(setBranchId)(e.target.value)}>
        <option value="">All branches</option>
        {branches.map((b) => (
          <option key={b.id} value={b.id}>{b.branch_name}</option>
        ))}
      </select>
      {" "}
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
