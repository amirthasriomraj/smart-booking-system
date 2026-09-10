import React, { useEffect, useState, useCallback, useContext } from "react"
import {
  listCustomerBookings,
  getCustomerBranchAvailability,
  rescheduleCustomerBooking,
  cancelCustomerBooking,
  initiateBalancePayment,
  verifyBalancePayment,
  verifyReschedulePriceDifference,
  getCustomerBookingPaymentHistory,
} from "../api/api"
import { extractErrorMessage } from "../api/errors"
import { openRazorpayCheckout } from "../utils/razorpay"
import { financialStatusLabel, paymentStatusLabel, refundStatusLabel } from "../utils/financial"
import { AuthContext } from "../auth/AuthContextOnly"
import Navbar from "../components/Navbar"

// PRD §35 Customer Dashboard: Upcoming Appointments, Appointment History,
// Reschedule Appointment, Cancel Appointment. Customer self-cancel/
// reschedule resolved in favor of V1 scope (ID-035). Milestone 8 adds the
// financial layer on top: remaining-balance payment, cancellation refund
// outcomes, reschedule price differences, and a payment/refund history
// view — none of it calculated in the browser, all of it read back from
// what the backend already computed and persisted.
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
  const { user } = useContext(AuthContext)
  const [bookings, setBookings] = useState([])

  const [rescheduleId, setRescheduleId] = useState(null)
  const [rescheduleDate, setRescheduleDate] = useState("")
  const [rescheduleSlots, setRescheduleSlots] = useState(null)
  const [rescheduleSelectedSlot, setRescheduleSelectedSlot] = useState(null)
  const [rescheduleSubmitting, setRescheduleSubmitting] = useState(false)

  const [payingBalanceId, setPayingBalanceId] = useState(null)
  const [historyForId, setHistoryForId] = useState(null)
  const [history, setHistory] = useState(null)

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
  const history_ = bookings.filter((b) => b.status !== "Confirmed" || b.booking_date < today)

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
      const response = await rescheduleCustomerBooking(bookingId, {
        booking_date: rescheduleDate,
        start_time: rescheduleSelectedSlot.start_time,
      })
      const priceAdjustment = response.data.price_adjustment

      if (priceAdjustment?.action === "CollectDifference") {
        const razorpayResponse = await openRazorpayCheckout({
          orderId: priceAdjustment.razorpay_order_id,
          keyId: priceAdjustment.razorpay_key_id,
          amount: priceAdjustment.amount_due,
          prefillEmail: user?.email,
        })
        await verifyReschedulePriceDifference(bookingId, {
          razorpay_payment_id: razorpayResponse.razorpay_payment_id,
          razorpay_signature: razorpayResponse.razorpay_signature,
        })
        setMessage(`Booking rescheduled. Price difference of ₹${priceAdjustment.amount_due} collected.`)
      } else if (priceAdjustment?.action === "RefundIssued") {
        setMessage(`Booking rescheduled. ₹${priceAdjustment.amount_refunded} refund issued for the price difference.`)
      } else {
        setMessage("Booking rescheduled.")
      }

      cancelReschedule()
      load()
    } catch (err) {
      if (err?.response) {
        setError(extractErrorMessage(err, "Failed to reschedule booking"))
      } else {
        setError(err.message || "Reschedule price-difference payment was not completed")
      }
    } finally {
      setRescheduleSubmitting(false)
    }
  }

  const handleCancel = async (bookingId) => {
    setError("")
    try {
      const response = await cancelCustomerBooking(bookingId)
      const refund = response.data.refund
      if (refund && Number(refund.final_amount) > 0) {
        setMessage(
          `Booking cancelled. Refund of ₹${refund.final_amount} ${refund.already_processed ? "was already processed" : "initiated"} — see Payment History for its status.`
        )
      } else {
        setMessage("Booking cancelled.")
      }
      load()
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to cancel booking"))
    }
  }

  const handlePayBalance = async (booking) => {
    setError("")
    setPayingBalanceId(booking.id)
    try {
      const initiateResponse = await initiateBalancePayment(booking.id)
      const razorpayResponse = await openRazorpayCheckout({
        orderId: initiateResponse.data.razorpay_order_id,
        keyId: initiateResponse.data.razorpay_key_id,
        amount: initiateResponse.data.amount_due,
        currency: initiateResponse.data.currency,
        description: `Balance payment — ${booking.service_name}`,
        prefillEmail: user?.email,
      })
      await verifyBalancePayment(booking.id, {
        razorpay_payment_id: razorpayResponse.razorpay_payment_id,
        razorpay_signature: razorpayResponse.razorpay_signature,
      })
      setMessage("Balance paid.")
      load()
    } catch (err) {
      if (err?.response) {
        setError(extractErrorMessage(err, "Failed to pay balance"))
      } else {
        setError(err.message || "Balance payment was not completed")
      }
    } finally {
      setPayingBalanceId(null)
    }
  }

  const toggleHistory = async (bookingId) => {
    if (historyForId === bookingId) {
      setHistoryForId(null)
      return
    }
    setError("")
    try {
      const response = await getCustomerBookingPaymentHistory(bookingId)
      setHistory(response.data)
      setHistoryForId(bookingId)
    } catch {
      setError("Failed to load payment history")
    }
  }

  const renderFinancials = (b) => {
    const label = financialStatusLabel(b.financial_status)
    if (!label) {
      return null
    }
    return (
      <div>
        {label}
        {b.total_amount != null && ` — total ₹${b.total_amount}`}
        {b.amount_paid != null && `, paid ₹${b.amount_paid}`}
        {b.financial_status === "AwaitingBalance" && b.balance_due != null && `, balance due ₹${b.balance_due}`}
        {b.balance_due_at && ` by ${new Date(b.balance_due_at).toLocaleString()}`}
        {b.amount_refunded != null && Number(b.amount_refunded) > 0 && `, refunded ₹${b.amount_refunded}`}
      </div>
    )
  }

  const renderBooking = (b) => (
    <li key={b.id} style={{ marginBottom: "10px" }}>
      <strong>{b.booking_date} {b.start_time}-{b.end_time}</strong>
      {" — "}{b.service_name}{" at "}{b.branch_name}
      {" — status: "}{b.status}
      {b.cancellation_reason && ` (${b.cancellation_reason})`}
      <br />
      {renderFinancials(b)}

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
            {" "}
            {b.financial_status === "AwaitingBalance" && (
              <button onClick={() => handlePayBalance(b)} disabled={payingBalanceId === b.id}>
                {payingBalanceId === b.id ? "Processing…" : `Pay Balance (₹${b.balance_due})`}
              </button>
            )}
          </>
        )
      )}

      {" "}
      <button onClick={() => toggleHistory(b.id)}>
        {historyForId === b.id ? "Hide Payment History" : "Payment History"}
      </button>

      {historyForId === b.id && history && (
        <div style={{ marginLeft: "20px" }}>
          <strong>Payments</strong>
          <ul>
            {history.payments.length === 0 && <li>No payments recorded.</li>}
            {history.payments.map((p) => (
              <li key={p.id}>
                {p.payment_type} via {p.method} — ₹{p.amount} — {paymentStatusLabel(p.status)}
                {" "}({new Date(p.created_at).toLocaleString()})
              </li>
            ))}
          </ul>
          <strong>Refunds</strong>
          <ul>
            {history.refunds.length === 0 && <li>No refunds recorded.</li>}
            {history.refunds.map((r) => (
              <li key={r.id}>
                ₹{r.final_amount} via {r.refund_method} — {refundStatusLabel(r.status)}
                {r.reason && ` — reason: ${r.reason}`}
                {" "}({new Date(r.created_at).toLocaleString()})
              </li>
            ))}
          </ul>
        </div>
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
        {history_.map(renderBooking)}
        {history_.length === 0 && <li>No past appointments.</li>}
      </ul>
    </div>
  )
}
