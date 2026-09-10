import React, { useState, useEffect, useContext } from "react"
import {
  browseBusinesses,
  browseBranches,
  browseServices,
  getCustomerBranchAvailability,
  customerCheckout,
  customerCreateCheckoutHold,
  customerRefreshCheckoutHold,
  customerCreateCheckoutPayment,
  verifyCustomerCheckout,
} from "../api/api"
import { extractErrorMessage } from "../api/errors"
import { openRazorpayCheckout } from "../utils/razorpay"
import { isDepositEligible, DEPOSIT_MIN_DAYS } from "../utils/depositEligibility"
import { AuthContext } from "../auth/AuthContextOnly"
import Navbar from "../components/Navbar"

// Milestone 6 covered "browse/select business, branch, service" (workflow
// 90.3); Milestone 7 continued into availability + booking; Milestone 8
// replaces the old direct "Confirm Booking" call with real checkout
// (rule 11) — every customer booking now goes through server-authoritative
// pricing/coupon/deposit calculation and (unless a 100%-off coupon makes
// the total ₹0) an online payment, verified server-side only. The browser
// is never trusted to declare a payment successful on its own.
//
// Manual-acceptance fix: selecting a slot now creates a checkout hold and
// shows the resulting authoritative price/coupon/deposit breakdown
// ("review") before any payment happens — no pricing/coupon math is ever
// duplicated client-side. Changing the coupon or payment option marks the
// review stale; "Update Summary" recomputes it for the SAME slot via the
// same hold-refresh pattern the staff checkout flow already uses. None of
// hold creation, refresh, or the review display contacts Razorpay — the
// backend only creates a real order when the customer explicitly clicks
// the final Proceed to Pay action for a non-stale review, and Razorpay
// Checkout is only opened once that order creation succeeds.
export default function CustomerBrowse() {
  const { user } = useContext(AuthContext)
  const [businesses, setBusinesses] = useState([])
  const [selectedBusinessId, setSelectedBusinessId] = useState(null)
  const [branches, setBranches] = useState([])
  const [selectedBranchId, setSelectedBranchId] = useState(null)
  const [services, setServices] = useState([])
  const [selectedServiceId, setSelectedServiceId] = useState(null)
  const [date, setDate] = useState("")
  const [slots, setSlots] = useState(null)
  const [selectedSlot, setSelectedSlot] = useState(null)

  const [paymentOption, setPaymentOption] = useState("Full")
  const [couponCode, setCouponCode] = useState("")

  // The Booking & Payment Summary review: the backend's authoritative
  // response from creating/refreshing a checkout hold. `kind` is "Hold"
  // (a real 6-minute hold + Razorpay order exist; hold_id is set) or
  // "NoPaymentRequired" (a 100%-off coupon made the total ₹0 — rule 10/13
  // — no hold/order was created at all).
  const [review, setReview] = useState(null)
  const [reviewInputs, setReviewInputs] = useState(null)
  const [reviewSubmitting, setReviewSubmitting] = useState(false)

  const [submitting, setSubmitting] = useState(false)
  const [confirmation, setConfirmation] = useState(null)
  const [error, setError] = useState("")

  const selectedBusiness = businesses.find((b) => b.id === selectedBusinessId)
  const selectedBranch = branches.find((br) => br.id === selectedBranchId)
  const selectedService = services.find((s) => s.id === selectedServiceId)

  const depositEligible = selectedSlot ? isDepositEligible(date, selectedSlot.start_time) : false
  // Deposit is never actually offered unless the selected slot qualifies —
  // this collapses back to "Full" for an ineligible slot regardless of
  // what the dropdown was last set to (e.g. from an earlier, eligible slot).
  const effectivePaymentOption = depositEligible ? paymentOption : "Full"

  // Whether the displayed `review` still matches the live coupon/payment-
  // option inputs. Derived, never a separately-tracked flag.
  const isReviewStale = !!review && !!reviewInputs && (
    reviewInputs.paymentOption !== effectivePaymentOption ||
    reviewInputs.couponCode !== couponCode
  )

  useEffect(() => {
    browseBusinesses()
      .then((response) => setBusinesses(response.data))
      .catch(() => setError("Failed to load businesses"))
  }, [])

  useEffect(() => {
    if (!selectedBusinessId) {
      return
    }
    browseBranches(selectedBusinessId)
      .then((response) => setBranches(response.data))
      .catch(() => setError("Failed to load branches"))
  }, [selectedBusinessId])

  useEffect(() => {
    if (!selectedBranchId) {
      return
    }
    browseServices(selectedBranchId)
      .then((response) => setServices(response.data))
      .catch(() => setError("Failed to load services"))
  }, [selectedBranchId])

  // Business/branch/service/date all determine slot identity — changing
  // any of them invalidates whatever review/hold exists (the slot it was
  // computed for no longer applies). Any real hold left behind simply
  // expires on its own within its 6-minute window.
  const invalidateReview = () => {
    setReview(null)
    setReviewInputs(null)
  }

  const handleSelectBusiness = (businessId) => {
    setSelectedBusinessId(businessId)
    setSelectedBranchId(null)
    setBranches([])
    setServices([])
    setSlots(null)
    setSelectedSlot(null)
    setConfirmation(null)
    invalidateReview()
  }

  const handleSelectBranch = (branchId) => {
    setSelectedBranchId(branchId)
    setServices([])
    setSelectedServiceId(null)
    setSlots(null)
    setSelectedSlot(null)
    setConfirmation(null)
    invalidateReview()
  }

  const handleSelectService = (serviceId) => {
    setSelectedServiceId(serviceId)
    setSlots(null)
    setSelectedSlot(null)
    setConfirmation(null)
    invalidateReview()
  }

  const handleDateChange = (e) => {
    setDate(e.target.value)
    setSlots(null)
    setSelectedSlot(null)
    setConfirmation(null)
    invalidateReview()
  }

  const handleCheckAvailability = async (e) => {
    e.preventDefault()
    setError("")
    setSlots(null)
    setSelectedSlot(null)
    setConfirmation(null)
    invalidateReview()
    try {
      const response = await getCustomerBranchAvailability(selectedBranchId, selectedServiceId, date)
      setSlots(response.data.slots)
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load availability"))
    }
  }

  // The single function building/rebuilding the review for one fixed slot
  // — used both for the first build (slot selection) and every later
  // "Update Summary" click. Never creates a Booking; only ever creates or
  // releases a hold. No pricing/coupon math happens here — the backend's
  // response is displayed as-is.
  const rebuildReview = async (slot) => {
    setError("")
    setReviewSubmitting(true)
    try {
      const response = (review?.kind === "Hold" && review.hold_id)
        ? await customerRefreshCheckoutHold(review.hold_id, {
            coupon_code: couponCode || undefined,
            payment_option: effectivePaymentOption,
          })
        : await customerCreateCheckoutHold({
            branch_service_id: selectedServiceId,
            booking_date: date,
            start_time: slot.start_time,
            coupon_code: couponCode || undefined,
            payment_option: effectivePaymentOption,
          })
      setReview(response.data)
      setReviewInputs({ paymentOption: effectivePaymentOption, couponCode })
    } catch (err) {
      if (err?.response?.status === 409) {
        setReview(null)
        setReviewInputs(null)
        setSelectedSlot(null)
        setError("This slot is no longer available — please check availability and select a slot again.")
      } else {
        setError(extractErrorMessage(err, "Failed to build the checkout summary"))
      }
    } finally {
      setReviewSubmitting(false)
    }
  }

  // Selecting a time only stages it and builds the first review — it does
  // not create a booking or a payment yet.
  const handleSelectSlot = (slot) => {
    setError("")
    setConfirmation(null)
    setSelectedSlot(slot)
    rebuildReview(slot)
  }

  const handleUpdateSummary = () => {
    if (!selectedSlot || reviewSubmitting) {
      return
    }
    rebuildReview(selectedSlot)
  }

  const handleConfirm = async () => {
    if (submitting || !review || isReviewStale) {
      return
    }
    setError("")
    setSubmitting(true)
    try {
      if (review.kind === "NoPaymentRequired") {
        // rule 10/13: a legitimate 100%-off booking skips Razorpay
        // entirely. Re-validated fresh (no hold was ever held for this
        // slot) via the existing one-shot endpoint, which already
        // implements that frozen path unchanged.
        const response = await customerCheckout({
          branch_service_id: selectedServiceId,
          booking_date: date,
          start_time: selectedSlot.start_time,
          payment_option: effectivePaymentOption,
          coupon_code: couponCode || undefined,
        })
        const body = response.data
        if (body.status === "Confirmed") {
          setConfirmation(body.booking)
        } else {
          // Rare race: the amount is no longer ₹0 (e.g. the coupon's
          // capacity was exhausted in the interim) — the backend
          // correctly fell back to a real payment; complete it the same
          // way as the "Hold" branch below.
          const razorpayResponse = await openRazorpayCheckout({
            orderId: body.razorpay_order_id, keyId: body.razorpay_key_id,
            amount: body.amount_due, currency: body.currency,
            name: selectedBusiness?.business_name, description: selectedService?.name,
            prefillEmail: user?.email,
          })
          const verifyResponse = await verifyCustomerCheckout(body.hold_id, {
            razorpay_payment_id: razorpayResponse.razorpay_payment_id,
            razorpay_signature: razorpayResponse.razorpay_signature,
          })
          setConfirmation(verifyResponse.data.booking)
        }
      } else {
        // Hold — this is the first point that contacts Razorpay: only now,
        // after the customer has explicitly clicked Proceed to Pay for a
        // non-stale, already-reviewed hold, does the backend create a real
        // order. Razorpay Checkout is only opened once that succeeds. Its
        // own success callback is not proof of payment; the backend's
        // verify endpoint re-checks the signature and the payment's
        // captured status/amount server-side before confirming the booking.
        const paymentResponse = await customerCreateCheckoutPayment(review.hold_id)
        const paymentBody = paymentResponse.data
        const razorpayResponse = await openRazorpayCheckout({
          orderId: paymentBody.razorpay_order_id, keyId: paymentBody.razorpay_key_id,
          amount: paymentBody.amount_due, currency: paymentBody.currency,
          name: selectedBusiness?.business_name, description: selectedService?.name,
          prefillEmail: user?.email,
        })
        const verifyResponse = await verifyCustomerCheckout(review.hold_id, {
          razorpay_payment_id: razorpayResponse.razorpay_payment_id,
          razorpay_signature: razorpayResponse.razorpay_signature,
        })
        setConfirmation(verifyResponse.data.booking)
      }
      setSlots(null)
      setSelectedSlot(null)
      invalidateReview()
    } catch (err) {
      if (err?.response) {
        setError(extractErrorMessage(err, "Checkout failed"))
      } else {
        // Razorpay widget rejection (closed/failed) — no server response.
        setError(err.message || "Payment was not completed")
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <Navbar />
      <h1>Browse Businesses</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <h2>1. Select a Business</h2>
      <ul>
        {businesses.map((b) => (
          <li key={b.id}>
            <button onClick={() => handleSelectBusiness(b.id)}>
              {b.business_name}
            </button>
          </li>
        ))}
      </ul>

      {selectedBusinessId && (
        <>
          <h2>2. Select a Branch</h2>
          <ul>
            {branches.map((br) => (
              <li key={br.id}>
                <button onClick={() => handleSelectBranch(br.id)}>
                  {br.branch_name}
                  {br.city ? ` (${br.city})` : ""}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {selectedBranchId && (
        <>
          <h2>3. Select a Service</h2>
          <ul>
            {services.map((s) => (
              <li key={s.id}>
                <button onClick={() => handleSelectService(s.id)}>
                  {s.name} — {s.duration} min — ₹{s.price}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {selectedServiceId && (
        <>
          <h2>4. Select a Date</h2>
          <form onSubmit={handleCheckAvailability}>
            <input type="date" value={date} onChange={handleDateChange} required />
            {" "}
            <button type="submit">Check Availability</button>
          </form>

          {slots && (
            <>
              <h2>5. Select a Time</h2>
              <ul>
                {slots.length === 0 && <li>No available slots for this date.</li>}
                {slots.map((slot) => (
                  <li key={slot.start_time}>
                    <button onClick={() => handleSelectSlot(slot)}>
                      {slot.start_time} - {slot.end_time}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}

          {selectedSlot && (
            <>
              <h2>6. Checkout</h2>
              <ul>
                <li>Business: {selectedBusiness?.business_name}</li>
                <li>Branch: {selectedBranch?.branch_name}</li>
                <li>Service: {selectedService?.name}</li>
                <li>Date: {date}</li>
                <li>Time: {selectedSlot.start_time} - {selectedSlot.end_time}</li>
              </ul>

              <label>
                Payment option:{" "}
                <select value={effectivePaymentOption} onChange={(e) => setPaymentOption(e.target.value)} disabled={!depositEligible}>
                  <option value="Full">Pay in full now</option>
                  {depositEligible && <option value="Deposit">Pay deposit now</option>}
                </select>
              </label>
              {!depositEligible && (
                <p>Deposit is only available for appointments at least {DEPOSIT_MIN_DAYS} days away — full payment only.</p>
              )}
              <br />
              <label>
                Coupon code (optional):{" "}
                <input
                  type="text"
                  value={couponCode}
                  onChange={(e) => setCouponCode(e.target.value)}
                  placeholder="e.g. SAVE10"
                />
              </label>

              {review && (
                <div style={{ border: "2px solid #333", padding: "10px", marginTop: "10px" }}>
                  <h3>Booking &amp; Payment Summary</h3>
                  <ul>
                    <li>Base/calculated price: ₹{review.calculated_price}</li>
                    {review.coupon_code && <li>Coupon "{review.coupon_code}": -₹{review.discount_amount}</li>}
                    <li><strong>Final booking amount: ₹{review.final_amount}</strong></li>
                    <li>Payment option: {review.payment_option}</li>
                    {review.kind === "NoPaymentRequired" ? (
                      <li><strong>Amount due now: ₹0 — no payment required</strong></li>
                    ) : (
                      <li><strong>Amount due now: ₹{review.amount_due_now}</strong></li>
                    )}
                    {review.deposit_amount != null && (
                      <li>
                        Deposit amount: ₹{review.deposit_amount}
                        {review.deposit_percentage != null && ` (${review.deposit_percentage}%)`}
                      </li>
                    )}
                    {review.balance_due != null && <li>Remaining balance: ₹{review.balance_due}</li>}
                    {review.balance_due_at && <li>Balance due by: {new Date(review.balance_due_at).toLocaleString()}</li>}
                  </ul>

                  {isReviewStale && (
                    <p style={{ color: "#b30000", fontWeight: "bold" }}>
                      The coupon or payment option above has changed since this summary was built.
                      Click <strong>Update Summary</strong> before you can pay.
                    </p>
                  )}

                  <button type="button" onClick={handleUpdateSummary} disabled={reviewSubmitting}>
                    {reviewSubmitting ? "Updating…" : "Update Summary"}
                  </button>
                  {" "}
                  <button onClick={handleConfirm} disabled={submitting || reviewSubmitting || isReviewStale}>
                    {submitting ? "Processing…" : review.kind === "NoPaymentRequired" ? "Confirm Booking" : "Proceed to Pay"}
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {confirmation && (
        <p style={{ color: "green" }}>
          Booking confirmed for {confirmation.booking_date} at {confirmation.start_time}. See it under{" "}
          <a href="/customer/bookings">My Bookings</a>.
        </p>
      )}
    </div>
  )
}
