import React, { useContext, useEffect, useState, useCallback } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import {
  listBranchesForBusiness,
  listBranchServicesForBranch,
  listBusinessCustomers,
  listResourcesForBranch,
  getBranchAvailability,
  createStaffBooking,
  listBranchBookings,
  getBookingHistory,
  rescheduleBooking,
  cancelBooking,
  reassignBookingResource,
  completeBooking,
} from "../api/api"
import { extractErrorMessage } from "../api/errors"

const emptyCreateForm = { customerId: "", branchServiceId: "", date: "" }

// Business Owner (business-wide) / Branch Manager (own branch only) booking
// management (PRD §18.4, §21; ID-039, ID-041). HR User and Resource User
// have no booking-management access (not named anywhere in the PRD's
// booking sections).
export default function BookingManagement() {
  const { user } = useContext(AuthContext)
  const businessId = user?.business?.id
  const roleCode = user?.business?.role_code
  const isOwner = roleCode === "BUSINESS_OWNER"
  const isBranchManager = roleCode === "BRANCH_MANAGER"

  // Branch Manager is always scoped to their own currently-assigned branch
  // (same pattern as ResourceManagement.jsx / ServiceManagement.jsx).
  const effectiveBranchId = isBranchManager ? (user?.business?.branch_id ?? null) : null

  const [branches, setBranches] = useState([])
  const [selectedBranchId, setSelectedBranchId] = useState(null)
  const branchId = isOwner ? selectedBranchId : effectiveBranchId

  const [branchServices, setBranchServices] = useState([])
  const [customers, setCustomers] = useState([])
  const [resources, setResources] = useState([])
  const [bookings, setBookings] = useState([])

  const [createForm, setCreateForm] = useState(emptyCreateForm)
  const [slots, setSlots] = useState(null)
  const [slotResourceChoice, setSlotResourceChoice] = useState({})

  const [rescheduleId, setRescheduleId] = useState(null)
  const [rescheduleForm, setRescheduleForm] = useState({ booking_date: "", start_time: "", resource_id: "" })
  const [reassignId, setReassignId] = useState(null)
  const [reassignResourceId, setReassignResourceId] = useState("")
  const [historyForId, setHistoryForId] = useState(null)
  const [history, setHistory] = useState([])
  const [cancelReasons, setCancelReasons] = useState({})

  const [statusFilter, setStatusFilter] = useState("")
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")

  useEffect(() => {
    if (!businessId) {
      return
    }
    if (isOwner) {
      listBranchesForBusiness(businessId)
        .then((r) => setBranches(r.data.filter((b) => b.approval_status === "Approved" && b.is_active)))
        .catch(() => {})
    }
    listBusinessCustomers(businessId, { limit: 100 }).then((r) => setCustomers(r.data.data)).catch(() => {})
  }, [businessId, isOwner])

  useEffect(() => {
    if (!branchId) {
      return
    }
    listBranchServicesForBranch(branchId)
      .then((r) => setBranchServices(r.data.filter((bs) => bs.status === "Approved")))
      .catch(() => {})
    listResourcesForBranch(branchId).then((r) => setResources(r.data)).catch(() => {})
  }, [branchId])

  const loadBookings = useCallback(() => {
    if (!branchId) {
      return
    }
    const params = statusFilter ? { status: statusFilter } : {}
    listBranchBookings(branchId, params).then((r) => setBookings(r.data)).catch(() => setError("Failed to load bookings"))
  }, [branchId, statusFilter])

  useEffect(() => {
    loadBookings()
  }, [loadBookings])

  const activeResources = resources.filter((r) => r.status === "Active")
  const resourceName = (id) => resources.find((r) => r.id === id)?.resource_name || `Resource #${id}`

  const handleCheckAvailability = async (e) => {
    e.preventDefault()
    setError("")
    setSlots(null)
    setSlotResourceChoice({})
    try {
      const response = await getBranchAvailability(branchId, Number(createForm.branchServiceId), createForm.date)
      setSlots(response.data.slots)
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load availability"))
    }
  }

  const handleBookSlot = async (slot) => {
    setError("")
    const resourceId = slotResourceChoice[slot.start_time]
    try {
      await createStaffBooking(branchId, {
        customer_id: Number(createForm.customerId),
        branch_service_id: Number(createForm.branchServiceId),
        booking_date: createForm.date,
        start_time: slot.start_time,
        resource_id: resourceId ? Number(resourceId) : undefined,
      })
      setSlots(null)
      loadBookings()
      setMessage("Booking created.")
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to create booking"))
    }
  }

  const startReschedule = (booking) => {
    setRescheduleId(booking.id)
    setRescheduleForm({ booking_date: booking.booking_date, start_time: booking.start_time, resource_id: "" })
  }

  const handleReschedule = async (e) => {
    e.preventDefault()
    setError("")
    try {
      await rescheduleBooking(rescheduleId, {
        booking_date: rescheduleForm.booking_date,
        start_time: rescheduleForm.start_time,
        resource_id: rescheduleForm.resource_id ? Number(rescheduleForm.resource_id) : undefined,
      })
      setRescheduleId(null)
      loadBookings()
      setMessage("Booking rescheduled.")
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to reschedule booking"))
    }
  }

  const handleCancel = async (bookingId) => {
    setError("")
    try {
      await cancelBooking(bookingId, cancelReasons[bookingId] || null)
      loadBookings()
      setMessage("Booking cancelled.")
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to cancel booking"))
    }
  }

  const handleReassign = async (e) => {
    e.preventDefault()
    setError("")
    try {
      await reassignBookingResource(reassignId, Number(reassignResourceId))
      setReassignId(null)
      setReassignResourceId("")
      loadBookings()
      setMessage("Resource reassigned.")
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to reassign resource"))
    }
  }

  const handleComplete = async (bookingId) => {
    setError("")
    try {
      await completeBooking(bookingId)
      loadBookings()
      setMessage("Booking marked completed.")
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to complete booking"))
    }
  }

  const toggleHistory = async (bookingId) => {
    if (historyForId === bookingId) {
      setHistoryForId(null)
      return
    }
    try {
      const response = await getBookingHistory(bookingId)
      setHistory(response.data)
      setHistoryForId(bookingId)
    } catch {
      setError("Failed to load booking history")
    }
  }

  if (!businessId) {
    return <p>You do not have an active business.</p>
  }

  if (!isOwner && !isBranchManager) {
    return <p>You are not authorized to manage bookings.</p>
  }

  return (
    <div>
      <h1>Bookings</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      {isOwner && (
        <>
          <label>Branch: </label>
          <select
            value={selectedBranchId || ""}
            onChange={(e) => setSelectedBranchId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Select a branch</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>{b.branch_name}</option>
            ))}
          </select>
        </>
      )}

      {!branchId && <p>Select a branch to manage bookings.</p>}

      {branchId && (
        <>
          <h2>Create Booking</h2>
          <form onSubmit={handleCheckAvailability}>
            <select
              value={createForm.customerId}
              onChange={(e) => setCreateForm({ ...createForm, customerId: e.target.value })}
              required
            >
              <option value="">Select Customer</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {`${c.first_name || ""} ${c.last_name || ""}`.trim() || c.email} ({c.customer_number})
                </option>
              ))}
            </select>
            {" "}
            <select
              value={createForm.branchServiceId}
              onChange={(e) => setCreateForm({ ...createForm, branchServiceId: e.target.value })}
              required
            >
              <option value="">Select Service</option>
              {branchServices.map((bs) => (
                <option key={bs.id} value={bs.id}>{bs.service_name} ({bs.duration} min)</option>
              ))}
            </select>
            {" "}
            <input
              type="date"
              value={createForm.date}
              onChange={(e) => setCreateForm({ ...createForm, date: e.target.value })}
              required
            />
            {" "}
            <button type="submit">Check Availability</button>
          </form>

          {slots && (
            <ul>
              {slots.length === 0 && <li>No available slots.</li>}
              {slots.map((slot) => (
                <li key={slot.start_time}>
                  {slot.start_time} - {slot.end_time}
                  {" "}
                  <select
                    value={slotResourceChoice[slot.start_time] || ""}
                    onChange={(e) => setSlotResourceChoice({ ...slotResourceChoice, [slot.start_time]: e.target.value })}
                  >
                    <option value="">Auto-assign (First Available)</option>
                    {slot.available_resource_ids.map((rid) => (
                      <option key={rid} value={rid}>{resourceName(rid)}</option>
                    ))}
                  </select>
                  {" "}
                  <button onClick={() => handleBookSlot(slot)}>Book</button>
                </li>
              ))}
            </ul>
          )}

          <h2>Bookings</h2>
          <label>Status: </label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All</option>
            <option value="Confirmed">Confirmed</option>
            <option value="Completed">Completed</option>
            <option value="Cancelled">Cancelled</option>
          </select>

          <ul>
            {bookings.map((b) => (
              <li key={b.id} style={{ marginBottom: "10px" }}>
                <strong>{b.booking_date} {b.start_time}-{b.end_time}</strong>
                {" — "}{b.service_name}
                {" — customer: "}{b.customer_name || b.customer_number}
                {" — resource: "}{b.resource_name}
                {" — status: "}{b.status}
                {b.cancellation_reason && ` (${b.cancellation_reason})`}
                <br />

                {rescheduleId === b.id ? (
                  <form onSubmit={handleReschedule} style={{ display: "inline" }}>
                    <input
                      type="date"
                      value={rescheduleForm.booking_date}
                      onChange={(e) => setRescheduleForm({ ...rescheduleForm, booking_date: e.target.value })}
                      required
                    />
                    <input
                      type="time"
                      step="1"
                      value={rescheduleForm.start_time}
                      onChange={(e) => setRescheduleForm({ ...rescheduleForm, start_time: e.target.value })}
                      required
                    />
                    <button type="submit">Save</button>
                    {" "}
                    <button type="button" onClick={() => setRescheduleId(null)}>Cancel</button>
                  </form>
                ) : reassignId === b.id ? (
                  <form onSubmit={handleReassign} style={{ display: "inline" }}>
                    <select value={reassignResourceId} onChange={(e) => setReassignResourceId(e.target.value)} required>
                      <option value="">Select Resource</option>
                      {activeResources.map((r) => (
                        <option key={r.id} value={r.id}>{r.resource_name}</option>
                      ))}
                    </select>
                    <button type="submit">Save</button>
                    {" "}
                    <button type="button" onClick={() => setReassignId(null)}>Cancel</button>
                  </form>
                ) : (
                  b.status === "Confirmed" && (
                    <>
                      <button onClick={() => startReschedule(b)}>Reschedule</button>
                      {" "}
                      <button onClick={() => setReassignId(b.id)}>Reassign Resource</button>
                      {" "}
                      <input
                        placeholder="Cancellation reason (optional)"
                        value={cancelReasons[b.id] || ""}
                        onChange={(e) => setCancelReasons({ ...cancelReasons, [b.id]: e.target.value })}
                        style={{ width: "180px" }}
                      />
                      {" "}
                      <button onClick={() => handleCancel(b.id)}>Cancel Booking</button>
                      {" "}
                      <button onClick={() => handleComplete(b.id)}>Mark Completed</button>
                    </>
                  )
                )}
                {" "}
                <button onClick={() => toggleHistory(b.id)}>
                  {historyForId === b.id ? "Hide History" : "History"}
                </button>

                {historyForId === b.id && (
                  <ul>
                    {history.map((h) => (
                      <li key={h.id}>{h.action} — {new Date(h.performed_at).toLocaleString()}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
            {bookings.length === 0 && <li>No bookings found.</li>}
          </ul>
        </>
      )}
    </div>
  )
}
