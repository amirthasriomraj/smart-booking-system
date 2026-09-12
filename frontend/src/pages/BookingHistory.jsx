import React, { useContext, useEffect, useState, useCallback } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import { listBusinessBookings, getBranchBookingHistory, listBranchesForBusiness } from "../api/api"

const PAGE_SIZE = 20

// M9 follow-up fix: a read-only, filterable Booking History view — distinct
// from the operational Booking Management console. Business Owner sees
// business-wide history with a Branch filter; Branch Manager sees only
// their own assigned branch's history (enforced server-side either way).
export default function BookingHistory() {
  const { user } = useContext(AuthContext)
  const isOwner = user?.business?.role_code === "BUSINESS_OWNER"
  const businessId = user?.business?.id
  const branchId = user?.business?.branch_id

  const [branches, setBranches] = useState([])
  const [selectedBranchId, setSelectedBranchId] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [page, setPage] = useState(1)

  const [bookings, setBookings] = useState([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [error, setError] = useState("")

  useEffect(() => {
    if (isOwner && businessId) {
      listBranchesForBusiness(businessId).then((r) => setBranches(r.data.items)).catch(() => {})
    }
  }, [isOwner, businessId])

  const load = useCallback(() => {
    const params = {
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      page,
      page_size: PAGE_SIZE,
    }
    if (isOwner && businessId) {
      if (selectedBranchId) {
        params.branch_id = selectedBranchId
      }
      listBusinessBookings(businessId, params)
        .then((response) => {
          setBookings(response.data.items)
          setTotal(response.data.total)
          setTotalPages(response.data.total_pages)
        })
        .catch(() => setError("Failed to load booking history"))
    } else if (!isOwner && branchId) {
      getBranchBookingHistory(branchId, params)
        .then((response) => {
          setBookings(response.data.items)
          setTotal(response.data.total)
          setTotalPages(response.data.total_pages)
        })
        .catch(() => setError("Failed to load booking history"))
    }
  }, [isOwner, businessId, branchId, selectedBranchId, dateFrom, dateTo, page])

  useEffect(() => {
    load()
  }, [load])

  const handleFilterChange = (setter) => (value) => {
    setter(value)
    setPage(1)
  }

  if (!isOwner && !branchId) {
    return <p>You are not currently assigned to a branch.</p>
  }

  return (
    <div>
      <h1>Booking History</h1>
      {error && <p style={{ color: "red" }}>{error}</p>}

      {isOwner && (
        <select value={selectedBranchId} onChange={(e) => handleFilterChange(setSelectedBranchId)(e.target.value)}>
          <option value="">All branches</option>
          {branches.map((b) => (
            <option key={b.id} value={b.id}>{b.branch_name}</option>
          ))}
        </select>
      )}
      {" "}
      <label>
        From: <input type="date" value={dateFrom} onChange={(e) => handleFilterChange(setDateFrom)(e.target.value)} />
      </label>
      {" "}
      <label>
        To: <input type="date" value={dateTo} onChange={(e) => handleFilterChange(setDateTo)(e.target.value)} />
      </label>

      <p>{total} total bookings — page {page} of {totalPages || 1}.</p>

      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Time</th>
            <th>Branch</th>
            <th>Service</th>
            <th>Customer</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {bookings.map((b) => (
            <tr key={b.id}>
              <td>{b.booking_date}</td>
              <td>{b.start_time}–{b.end_time}</td>
              <td>{b.branch_name}</td>
              <td>{b.service_name}</td>
              <td>{b.customer_name ?? `#${b.customer_id}`}</td>
              <td>{b.status}</td>
            </tr>
          ))}
          {bookings.length === 0 && (
            <tr><td colSpan="6">No matching bookings.</td></tr>
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
