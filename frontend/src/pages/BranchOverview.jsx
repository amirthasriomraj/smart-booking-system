import React, { useContext, useEffect, useState, useCallback } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import { getBranch, getWorkingHours, upsertWorkingHours, getBranchDailyReport } from "../api/api"

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

// PRD §35 Branch Manager Dashboard — "Branch Overview" and "Working Hours"
// modules combined into one landing page: a summary of the Branch Manager's
// own assigned branch (status, today's daily-report counts) plus an
// editable working-hours section (PRD §10.3 "Manage branch working hours").
export default function BranchOverview() {
  const { user } = useContext(AuthContext)
  const branchId = user?.business?.branch_id

  const [branch, setBranch] = useState(null)
  const [report, setReport] = useState(null)
  const [workingHours, setWorkingHours] = useState({})
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")

  const load = useCallback(() => {
    if (!branchId) {
      return
    }
    getBranch(branchId).then((r) => setBranch(r.data)).catch(() => setError("Failed to load branch"))
    getBranchDailyReport(branchId).then((r) => setReport(r.data)).catch(() => {})
    getWorkingHours(branchId)
      .then((r) => {
        const byWeekday = {}
        r.data.forEach((row) => {
          byWeekday[row.weekday] = row
        })
        setWorkingHours(byWeekday)
      })
      .catch(() => {})
  }, [branchId])

  useEffect(() => {
    load()
  }, [load])

  const updateHour = (weekday, field, value) => {
    setWorkingHours((prev) => ({
      ...prev,
      [weekday]: { ...(prev[weekday] || { weekday, is_closed: false }), [field]: value },
    }))
  }

  const saveWorkingHours = async () => {
    setError("")
    setMessage("")
    const hours = WEEKDAYS.map((_, weekday) => {
      const entry = workingHours[weekday]
      return {
        weekday,
        opening_time: entry?.is_closed ? null : entry?.opening_time || null,
        closing_time: entry?.is_closed ? null : entry?.closing_time || null,
        is_closed: !!entry?.is_closed,
      }
    }).filter((entry) => entry.opening_time || entry.closing_time || entry.is_closed)

    try {
      await upsertWorkingHours(branchId, hours)
      setMessage("Working hours saved.")
      load()
    } catch {
      setError("Failed to save working hours")
    }
  }

  if (!branchId) {
    return <p>You are not currently assigned to a branch.</p>
  }

  if (!branch) {
    return <p>Loading...</p>
  }

  return (
    <div>
      <h1>Branch Overview — {branch.branch_name}</h1>
      {error && <p style={{ color: "red" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      <p>
        Approval status: {branch.approval_status} — {branch.is_active ? "Active" : "Inactive"}
      </p>

      {report && (
        <>
          <h2>Today's Snapshot ({report.report_date})</h2>
          <p>Bookings today: {report.daily_bookings}</p>
          <h3>Resource Utilization</h3>
          <ul>
            {report.resource_utilization.map((r) => (
              <li key={r.resource_id}>{r.resource_name}: {r.booking_count}</li>
            ))}
            {report.resource_utilization.length === 0 && <li>None.</li>}
          </ul>
          <h3>Service Popularity</h3>
          <ul>
            {report.service_popularity.map((s) => (
              <li key={s.branch_service_id}>{s.service_name}: {s.booking_count}</li>
            ))}
            {report.service_popularity.length === 0 && <li>None.</li>}
          </ul>
        </>
      )}

      <h2>Working Hours</h2>
      <table>
        <thead>
          <tr>
            <th>Day</th>
            <th>Open</th>
            <th>Close</th>
            <th>Closed</th>
          </tr>
        </thead>
        <tbody>
          {WEEKDAYS.map((label, weekday) => {
            const entry = workingHours[weekday] || {}
            return (
              <tr key={weekday}>
                <td>{label}</td>
                <td>
                  <input
                    type="time"
                    value={entry.opening_time?.slice(0, 5) || ""}
                    onChange={(e) => updateHour(weekday, "opening_time", e.target.value ? `${e.target.value}:00` : null)}
                    disabled={entry.is_closed}
                  />
                </td>
                <td>
                  <input
                    type="time"
                    value={entry.closing_time?.slice(0, 5) || ""}
                    onChange={(e) => updateHour(weekday, "closing_time", e.target.value ? `${e.target.value}:00` : null)}
                    disabled={entry.is_closed}
                  />
                </td>
                <td>
                  <input
                    type="checkbox"
                    checked={!!entry.is_closed}
                    onChange={(e) => updateHour(weekday, "is_closed", e.target.checked)}
                  />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <button onClick={saveWorkingHours}>Save Working Hours</button>
    </div>
  )
}
