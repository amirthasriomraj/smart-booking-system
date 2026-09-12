import React, { useEffect, useState, useCallback } from "react"
import { getAdminAuditLogs, getAuditLogFilterOptions } from "../api/api"

const PAGE_SIZE = 20

// PRD §35 Platform Administrator Dashboard — Audit Logs module.
export default function AdminAuditLogs() {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [page, setPage] = useState(1)
  const [entityTypes, setEntityTypes] = useState([])
  const [actions, setActions] = useState([])
  const [entityType, setEntityType] = useState("")
  const [action, setAction] = useState("")
  const [error, setError] = useState("")

  useEffect(() => {
    getAuditLogFilterOptions()
      .then((response) => {
        setEntityTypes(response.data.entity_types)
        setActions(response.data.actions)
      })
      .catch(() => {})
  }, [])

  const load = useCallback(() => {
    getAdminAuditLogs({
      entity_type: entityType || undefined,
      action: action || undefined,
      page,
      page_size: PAGE_SIZE,
    })
      .then((response) => {
        setLogs(response.data.items)
        setTotal(response.data.total)
        setTotalPages(response.data.total_pages)
      })
      .catch(() => setError("Failed to load audit logs"))
  }, [entityType, action, page])

  useEffect(() => {
    load()
  }, [load])

  // Any filter change resets back to page 1 — otherwise a narrower result
  // set could leave the view stranded past its own last page.
  const handleEntityTypeChange = (value) => {
    setEntityType(value)
    setPage(1)
  }

  const handleActionChange = (value) => {
    setAction(value)
    setPage(1)
  }

  return (
    <div>
      <h1>Audit Logs</h1>
      {error && <p style={{ color: "red" }}>{error}</p>}

      <select value={entityType} onChange={(e) => handleEntityTypeChange(e.target.value)}>
        <option value="">All entity types</option>
        {entityTypes.map((et) => (
          <option key={et} value={et}>{et}</option>
        ))}
      </select>
      {" "}
      <select value={action} onChange={(e) => handleActionChange(e.target.value)}>
        <option value="">All actions</option>
        {actions.map((a) => (
          <option key={a} value={a}>{a}</option>
        ))}
      </select>

      <p>{total} total entries — page {page} of {totalPages || 1}.</p>

      <table>
        <thead>
          <tr>
            <th>When</th>
            <th>Business</th>
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
              <td>{log.business_id ?? "—"}</td>
              <td>{log.entity_type} #{log.entity_id}</td>
              <td>{log.action}</td>
              <td>{log.performed_by ?? "system"}</td>
              <td>{log.reason ?? ""}</td>
            </tr>
          ))}
          {logs.length === 0 && (
            <tr><td colSpan="6">No matching audit log entries.</td></tr>
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
