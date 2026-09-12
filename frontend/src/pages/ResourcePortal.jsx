import React, { useEffect, useState, useCallback } from "react"
import { Link } from "react-router-dom"
import { getResourceUserBookings } from "../api/api"

// PRD §35 Resource Dashboard (Optional Login) — Today's Schedule and
// Upcoming Bookings modules; Profile links to the existing personal
// profile page. Personal Availability is explicitly Future-tagged (§35,
// §10.5) and intentionally not built here.
export default function ResourcePortal() {
  const [today, setToday] = useState([])
  const [upcoming, setUpcoming] = useState([])
  const [error, setError] = useState("")

  const load = useCallback(() => {
    getResourceUserBookings("today").then((r) => setToday(r.data)).catch(() => setError("Failed to load schedule"))
    getResourceUserBookings("upcoming").then((r) => setUpcoming(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div>
      <h1>My Schedule</h1>
      {error && <p style={{ color: "red" }}>{error}</p>}

      <p><Link to="/profile">My Profile</Link></p>

      <h2>Today's Schedule</h2>
      <ul>
        {today.map((b) => (
          <li key={b.id}>
            {b.start_time}–{b.end_time} — {b.service_name} — {b.customer_name || `Customer #${b.customer_id}`} — {b.status}
          </li>
        ))}
        {today.length === 0 && <li>Nothing scheduled today.</li>}
      </ul>

      <h2>Upcoming Bookings</h2>
      <ul>
        {upcoming.map((b) => (
          <li key={b.id}>
            {b.booking_date} {b.start_time}–{b.end_time} — {b.service_name} — {b.customer_name || `Customer #${b.customer_id}`} — {b.status}
          </li>
        ))}
        {upcoming.length === 0 && <li>No upcoming bookings.</li>}
      </ul>
    </div>
  )
}
