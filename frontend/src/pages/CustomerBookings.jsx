import React, { useEffect, useState, useCallback } from "react"
import {
  listCustomerBookings,
  getCustomerBranchAvailability,
  rescheduleCustomerBooking,
  cancelCustomerBooking,
} from "../api/api"
import { extractErrorMessage } from "../api/errors"
import Navbar from "../components/Navbar"

// PRD §35 Customer Dashboard: Upcoming Appointments, Appointment History,
// Reschedule Appointment, Cancel Appointment. Customer self-cancel/
// reschedule resolved in favor of V1 scope (ID-035).
//
// Reschedule goes through the same Availability Engine the customer used to
// book (Reschedule -> select date -> Check Availability -> select an
// available slot -> Confirm Reschedule) rather than raw date/time entry, so
// the customer only ever sees slots the engine actually reports as bookable.
// No resource_id is ever sent from here — the backend prefers keeping the
// currently-assigned resource if it's still free, and otherwise falls back
// to automatic "First Available" reassignment on its own; customers have no
// manual resource picker (that stays a staff-only action, §21).
export default function CustomerBookings() {
  const [bookings, setBookings] = useState([])

  const [rescheduleId, setRescheduleId] = useState(null)
  const [rescheduleDate, setRescheduleDate] = useState("")
  const [rescheduleSlots, setRescheduleSlots] = useState(null)
  const [rescheduleSelectedSlot, setRescheduleSelectedSlot] = useState(null)
  const [rescheduleSubmitting, setRescheduleSubmitting] = useState(false)

  const [error, setError] = useState("")
  const [message, setMessage] = useState("")

  const load = useCallback(() => {
    listCustomerBookings()
      .then((response) => setBookings(response.data))
      .catch(() => setError("Failed to load your bookings"))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const today = new Date().toISOString().slice(0, 10)
  const upcoming = bookings.filter((b) => b.status === "Confirmed" && b.booking_date >= today)
  const history = bookings.filter((b) => b.status !== "Confirmed" || b.booking_date < today)

  const startReschedule = (booking) => {
    setError("")
    setRescheduleId(booking.id)
    setRescheduleDate(booking.booking_date)
    setRescheduleSlots(null)
    setRescheduleSelectedSlot(null)
  }

  const cancelReschedule = () => {
    setRescheduleId(null)
    setRescheduleDate("")
    setRescheduleSlots(null)
    setRescheduleSelectedSlot(null)
  }

  const handleRescheduleDateChange = (e) => {
    setRescheduleDate(e.target.value)
    setRescheduleSlots(null)
    setRescheduleSelectedSlot(null)
  }

  const handleCheckRescheduleAvailability = async (e, booking) => {
    e.preventDefault()
    setError("")
    setRescheduleSlots(null)
    setRescheduleSelectedSlot(null)
    try {
      const response = await getCustomerBranchAvailability(booking.branch_id, booking.branch_service_id, rescheduleDate)
      setRescheduleSlots(response.data.slots)
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load availability"))
    }
  }

  const handleSelectRescheduleSlot = (slot) => {
    setRescheduleSelectedSlot(slot)
  }

  const handleConfirmReschedule = async (bookingId) => {
    if (rescheduleSubmitting || !rescheduleSelectedSlot) {
      return
    }
    setError("")
    setRescheduleSubmitting(true)
    try {
      await rescheduleCustomerBooking(bookingId, {
        booking_date: rescheduleDate,
        start_time: rescheduleSelectedSlot.start_time,
      })
      cancelReschedule()
      load()
      setMessage("Booking rescheduled.")
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to reschedule booking"))
    } finally {
      setRescheduleSubmitting(false)
    }
  }

  const handleCancel = async (bookingId) => {
    setError("")
    try {
      await cancelCustomerBooking(bookingId)
      load()
      setMessage("Booking cancelled.")
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to cancel booking"))
    }
  }

  const renderBooking = (b) => (
    <li key={b.id} style={{ marginBottom: "10px" }}>
      <strong>{b.booking_date} {b.start_time}-{b.end_time}</strong>
      {" — "}{b.service_name}{" at "}{b.branch_name}
      {" — status: "}{b.status}
      {b.cancellation_reason && ` (${b.cancellation_reason})`}
      <br />

      {b.status === "Confirmed" && (
        rescheduleId === b.id ? (
          <div>
            <form onSubmit={(e) => handleCheckRescheduleAvailability(e, b)}>
              <input type="date" value={rescheduleDate} onChange={handleRescheduleDateChange} required />
              {" "}
              <button type="submit">Check Availability</button>
              {" "}
              <button type="button" onClick={cancelReschedule}>Cancel</button>
            </form>

            {rescheduleSlots && (
              <ul>
                {rescheduleSlots.length === 0 && <li>No available slots for this date.</li>}
                {rescheduleSlots.map((slot) => (
                  <li key={slot.start_time}>
                    <button onClick={() => handleSelectRescheduleSlot(slot)}>
                      {slot.start_time} - {slot.end_time}
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {rescheduleSelectedSlot && (
              <div>
                <p>
                  New time: {rescheduleDate} {rescheduleSelectedSlot.start_time} - {rescheduleSelectedSlot.end_time}
                </p>
                <button onClick={() => handleConfirmReschedule(b.id)} disabled={rescheduleSubmitting}>
                  {rescheduleSubmitting ? "Confirming…" : "Confirm Reschedule"}
                </button>
              </div>
            )}
          </div>
        ) : (
          <>
            <button onClick={() => startReschedule(b)}>Reschedule</button>
            {" "}
            <button onClick={() => handleCancel(b.id)}>Cancel Booking</button>
          </>
        )
      )}
    </li>
  )

  return (
    <div>
      <Navbar />
      <h1>My Bookings</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      <h2>Upcoming Appointments</h2>
      <ul>
        {upcoming.map(renderBooking)}
        {upcoming.length === 0 && <li>No upcoming appointments.</li>}
      </ul>

      <h2>Appointment History</h2>
      <ul>
        {history.map(renderBooking)}
        {history.length === 0 && <li>No past appointments.</li>}
      </ul>
    </div>
  )
}
