import React, { useContext, useEffect, useState, useCallback } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import {
  listBranchesForBusiness,
  listBranchServicesForBranch,
  listBusinessCustomers,
  listResourcesForBranch,
  getBranchAvailability,
  listBranchBookings,
  getBookingHistory,
  rescheduleBooking,
  cancelBooking,
  reassignBookingResource,
  completeBooking,
  staffCreateCheckoutHold,
  staffRefreshCheckoutHold,
  staffDiscardCheckoutHold,
  staffFinalizeCashHold,
  staffFinalizeEmailLinkHold,
  staffFinalizeExternalHold,
  confirmExternalPayment,
  staffReserveWithoutPayment,
  previewReschedulePriceDifference,
  verifyReschedulePriceDifference,
  confirmRescheduleDifferencePayment,
  getBookingPaymentHistory,
  refundBooking,
} from "../api/api"
import { extractErrorMessage } from "../api/errors"
import { openRazorpayCheckout } from "../utils/razorpay"
import { financialStatusLabel, paymentStatusLabel, refundStatusLabel } from "../utils/financial"
import { isDepositEligible, DEPOSIT_MIN_DAYS } from "../utils/depositEligibility"

const emptyCreateForm = { customerId: "", branchServiceId: "", date: "" }
const emptyPriceOverride = { base_price_override: "", final_price_override: "", price_override_reason: "" }

// The only frozen, staff-facing payment methods (business rule 12). The
// BookingHold used to implement Cash/EmailLink/External internally is a
// pure architecture detail — it is never named or exposed to staff.
const PAYMENT_METHOD_LABELS = {
  Cash: "Cash",
  EmailLink: "Email Payment Link",
  External: "Direct UPI / Bank Transfer",
  RWP: "Reserve Without Payment",
}

// The reschedule financial-difference collection methods (rule 14, Part 2)
// — a separate, smaller vocabulary from PAYMENT_METHOD_LABELS above
// because it names the exact values the backend's reschedule endpoints
// use (`payment_method`/`default_payment_method`), which include
// "RazorpayOnline" (never offered at initial staff checkout, since a
// customer's own Razorpay-paid booking can also need a reschedule
// difference) and has no Reserve-Without-Payment entry (RWP has nothing
// to "default" to — staff must always choose explicitly there).
const RESCHEDULE_PAYMENT_METHOD_LABELS = {
  RazorpayOnline: "Razorpay / Online",
  EmailPaymentLink: "Email Payment Link",
  Cash: "Cash",
  ExternalManual: "Direct UPI / Bank Transfer",
}
const RESCHEDULE_PAYMENT_METHODS = ["RazorpayOnline", "EmailPaymentLink", "Cash", "ExternalManual"]

/*
 * STAFF CHECKOUT STATE MACHINE (manual-acceptance state-machine audit)
 * ----------------------------------------------------------------------
 * States, kept as separate, single-purpose pieces of state rather than a
 * pile of ad-hoc flags:
 *
 *   selectedSlot  — the slot identity the staff member picked from the
 *                   availability list: { start_time, end_time, resourceId }
 *                   (resourceId is the REQUESTED resource, possibly null
 *                   for auto-assign; null once no slot is selected).
 *
 *   review        — the displayed Booking & Payment Summary, or null.
 *                   Always one shape regardless of payment method:
 *                     { kind: "RWP" | "Hold", resource_id, start_time, end_time,
 *                       ...pricing fields, present only for kind "Hold" }
 *                   "Hold" reviews carry hold_id (a real 10-minute
 *                   StaffCheckout hold, ID-046/ID-054). "RWP" reviews never
 *                   acquire a hold (ID-046) and have no pricing fields.
 *
 *   reviewInputs  — a snapshot of exactly the payment-method/pricing
 *                   inputs that produced the CURRENT `review`:
 *                     { method, paymentOption, couponCode,
 *                       basePriceOverride, finalPriceOverride, priceOverrideReason }
 *                   Comparing this against the live input state below is
 *                   the ONLY source of "is the summary stale" — a derived
 *                   value, never a separately-tracked boolean that could
 *                   drift out of sync.
 *
 *   checkoutMethod, paymentOption, couponCode, priceOverride — the live,
 *                   currently-selected inputs (editable at any time while
 *                   a review is displayed).
 *
 * Transitions:
 *   - Branch / Customer / Service / Date change (slot-identity fields):
 *     `invalidateSlotIdentity()` — discards any Hold, and clears
 *     selectedSlot/review/reviewInputs/slots outright. A fresh Check
 *     Availability + slot selection is mandatory afterward.
 *
 *   - Selecting a slot: sets selectedSlot, then calls `rebuildReview`
 *     (below) to build the FIRST review for it under whatever payment
 *     method/pricing inputs are currently selected.
 *
 *   - Payment method change (Cash/EmailLink/External/RWP) or any pricing
 *     input change (coupon, base/final override + reason, payment
 *     option): no state is cleared and selectedSlot is untouched — the
 *     next render's derived `isReviewStale` simply becomes true (the live
 *     inputs no longer match `reviewInputs`), which disables Confirm and
 *     shows a banner. `Update Summary` calls `rebuildReview` again for the
 *     SAME selectedSlot to resync `review`/`reviewInputs`.
 *
 *   - `rebuildReview(slot)` is the single function implementing every
 *     method-transition case, reused for both the initial slot-selection
 *     build and every later "Update Summary" click:
 *       RWP -> RWP:    no hold ever existed; just restate the plain review.
 *       paid -> RWP:   release the uncommitted hold (staffDiscardCheckoutHold),
 *                      then build a plain review — no hold, no fake Payment.
 *       RWP -> paid:   acquire a brand-new hold for the SAME slot
 *                      (staffCreateCheckoutHold).
 *       paid -> paid:  release+reacquire a hold for the SAME slot under the
 *                      current terms (staffRefreshCheckoutHold) — the
 *                      hold's price_snapshot is never mutated in place
 *                      (ID-054); a fresh hold always carries the new terms.
 *     If the slot can no longer be acquired (409), review/selectedSlot are
 *     cleared and the user must Check Availability + reselect — Confirm
 *     is never reachable in that state because `review` is null.
 *
 *   - Confirm is disabled whenever `!review || isReviewStale` — it can
 *     only run once the displayed summary was built for exactly the
 *     currently-selected slot, payment method, and pricing inputs.
 *
 * Selecting a slot NEVER creates a Booking by itself (only Confirm does,
 * via the matching hold-based finalize endpoint or the direct RWP
 * endpoint), and Update Summary never creates a Booking either — both
 * only ever create/release a *hold*.
 */
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
  // The actual staff-facing payment method: "Cash" | "EmailLink" | "External" | "RWP".
  const [checkoutMethod, setCheckoutMethod] = useState("Cash")
  const [paymentOption, setPaymentOption] = useState("Full")
  const [couponCode, setCouponCode] = useState("")
  const [priceOverride, setPriceOverride] = useState(emptyPriceOverride)
  const [slots, setSlots] = useState(null)
  const [slotResourceChoice, setSlotResourceChoice] = useState({})

  const [selectedSlot, setSelectedSlot] = useState(null)
  const [review, setReview] = useState(null)
  const [reviewInputs, setReviewInputs] = useState(null)
  const [cashReceived, setCashReceived] = useState("")
  const [reviewSubmitting, setReviewSubmitting] = useState(false)

  const [pendingHold, setPendingHold] = useState(null)
  const [confirmingHold, setConfirmingHold] = useState(false)
  const [lastCashChange, setLastCashChange] = useState(null)

  const [rescheduleId, setRescheduleId] = useState(null)
  const [rescheduleForm, setRescheduleForm] = useState({ booking_date: "", start_time: "", resource_id: "", reason: "" })
  // Reschedule financial-difference UI (rule 14, Part 2): a read-only
  // preview (fetched as soon as the reschedule form opens — the price
  // impact doesn't depend on the new date/time, only on the booking's
  // existing terms vs the service's current price) plus the staff's live
  // payment-method choice for a genuine increase. `reschedulePreview` is
  // null while loading; `{action: null, ...}` once loaded with no
  // difference; `{action: "CollectDifference"|"RefundIssued", ...}`
  // otherwise. Undefined until a difference is confirmed at submit time —
  // this state is never used to duplicate the backend's own calculation,
  // only to display its own authoritative response.
  const [reschedulePreview, setReschedulePreview] = useState(null)
  const [reschedulePreviewError, setReschedulePreviewError] = useState("")
  const [reschedulePaymentMethod, setReschedulePaymentMethod] = useState("")
  const [rescheduleOverrideReason, setRescheduleOverrideReason] = useState("")
  const [rescheduleCashReceived, setRescheduleCashReceived] = useState("")
  const [rescheduleSubmitting, setRescheduleSubmitting] = useState(false)
  // A reschedule difference collected via Email Payment Link or Direct
  // UPI/Bank Transfer isn't captured synchronously — this mirrors the
  // existing `pendingHold` pattern above for the original checkout flow.
  const [reschedulePendingConfirmation, setReschedulePendingConfirmation] = useState(null)
  const [reassignId, setReassignId] = useState(null)
  const [reassignResourceId, setReassignResourceId] = useState("")
  const [historyForId, setHistoryForId] = useState(null)
  const [history, setHistory] = useState([])
  const [paymentHistoryForId, setPaymentHistoryForId] = useState(null)
  const [paymentHistory, setPaymentHistory] = useState(null)
  const [cancelReasons, setCancelReasons] = useState({})
  const [refundOverrides, setRefundOverrides] = useState({})
  const [refundingId, setRefundingId] = useState(null)
  const [refundForm, setRefundForm] = useState({ amount: "", reason: "" })
  const [refundSubmitting, setRefundSubmitting] = useState(false)

  const [statusFilter, setStatusFilter] = useState("")
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")

  useEffect(() => {
    if (!businessId) {
      return
    }
    if (isOwner) {
      listBranchesForBusiness(businessId)
        .then((r) => setBranches(r.data.items.filter((b) => b.approval_status === "Approved" && b.is_active)))
        .catch(() => {})
    }
    listBusinessCustomers(businessId, { page_size: 100 }).then((r) => setCustomers(r.data.items)).catch(() => {})
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
  const selectedService = branchServices.find((bs) => bs.id === Number(createForm.branchServiceId))
  const selectedCustomer = customers.find((c) => c.id === Number(createForm.customerId))
  const customerLabel = (c) => (c ? `${`${c.first_name || ""} ${c.last_name || ""}`.trim() || c.email} (${c.customer_number})` : "")

  // Deposit eligibility must always reflect the EXACT currently selected
  // slot's date+time once one is selected — never just the date. Before a
  // slot is chosen, the coarsest safe pre-filter (the chosen date's latest
  // possible moment) is used so the option is never wrongly hidden for an
  // early slot that would in fact qualify.
  const depositEligibleNow = selectedSlot
    ? isDepositEligible(createForm.date, selectedSlot.start_time)
    : (createForm.date ? isDepositEligible(createForm.date, "23:59:59") : false)

  // Manual-acceptance fix: customer, branch, service, and appointment
  // date all determine slot identity. Changing any of them after a
  // Booking & Payment Summary already exists must never leave that
  // summary (or its underlying hold) usable — the slot it was computed
  // for no longer applies. This releases the existing hold (best-effort)
  // and clears every downstream slot/review state, forcing a fresh Check
  // Availability + slot selection before Update Summary/Confirm can be
  // used again.
  const invalidateSlotIdentity = () => {
    if (review?.kind === "Hold" && review.hold_id) {
      staffDiscardCheckoutHold(review.hold_id).catch(() => {})
    }
    setSelectedSlot(null)
    setReview(null)
    setReviewInputs(null)
    setSlots(null)
    setSlotResourceChoice({})
    setCashReceived("")
  }

  const handleCheckAvailability = async (e) => {
    e.preventDefault()
    setError("")
    setSlots(null)
    setSlotResourceChoice({})
    setSelectedSlot(null)
    setReview(null)
    setReviewInputs(null)
    setPendingHold(null)
    setLastCashChange(null)
    try {
      const response = await getBranchAvailability(branchId, Number(createForm.branchServiceId), createForm.date)
      setSlots(response.data.slots)
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load availability"))
    }
  }

  // The pricing-affecting inputs only — never the slot identity itself.
  // Shared by the request payloads below AND by the reviewInputs snapshot
  // that staleness is derived from.
  const buildPricingInputs = () => ({
    coupon_code: couponCode || undefined,
    payment_option: paymentOption,
    base_price_override: priceOverride.base_price_override || undefined,
    final_price_override: priceOverride.final_price_override || undefined,
    price_override_reason: priceOverride.price_override_reason || undefined,
  })

  const currentInputsSnapshot = () => ({
    method: checkoutMethod,
    paymentOption,
    couponCode,
    basePriceOverride: priceOverride.base_price_override,
    finalPriceOverride: priceOverride.final_price_override,
    priceOverrideReason: priceOverride.price_override_reason,
  })

  // The single function implementing every method-transition case (RWP<->RWP,
  // paid->RWP, RWP->paid, paid->paid) for one fixed slot — used both for the
  // very first review build (on slot selection) and every later "Update
  // Summary" click. Never creates a Booking; only ever creates/releases a hold.
  const rebuildReview = async (slot) => {
    setError("")
    if (checkoutMethod !== "RWP" && paymentOption === "Deposit" && !isDepositEligible(createForm.date, slot.start_time)) {
      setError(`Deposit is not available for this time — the appointment is less than ${DEPOSIT_MIN_DAYS} days away. Choose Full payment instead.`)
      return
    }
    setReviewSubmitting(true)
    try {
      if (checkoutMethod === "RWP") {
        // paid -> RWP releases whatever uncommitted hold existed;
        // RWP -> RWP had no hold to release. Either way: no hold, no
        // fake Payment (ID-046).
        if (review?.kind === "Hold" && review.hold_id) {
          staffDiscardCheckoutHold(review.hold_id).catch(() => {})
        }
        setReview({ kind: "RWP", resource_id: slot.resourceId, start_time: slot.start_time, end_time: slot.end_time })
      } else {
        const response = (review?.kind === "Hold" && review.hold_id)
          ? await staffRefreshCheckoutHold(review.hold_id, buildPricingInputs()) // paid -> paid
          : await staffCreateCheckoutHold(branchId, { // RWP -> paid, or the very first build
              customer_id: Number(createForm.customerId),
              branch_service_id: Number(createForm.branchServiceId),
              booking_date: createForm.date,
              start_time: slot.start_time,
              resource_id: slot.resourceId ? Number(slot.resourceId) : undefined,
              ...buildPricingInputs(),
            })
        setReview({ kind: "Hold", ...response.data })
      }
      setReviewInputs(currentInputsSnapshot())
      setCashReceived("")
    } catch (err) {
      if (err?.response?.status === 409) {
        setSelectedSlot(null)
        setReview(null)
        setReviewInputs(null)
        setError("This slot is no longer available — please check availability and select a slot again.")
      } else {
        setError(extractErrorMessage(err, "Failed to update the summary"))
      }
    } finally {
      setReviewSubmitting(false)
    }
  }

  // Selecting a slot never itself creates a Booking — it only stages the
  // slot identity and builds the first review for it.
  const handleSelectSlot = (slot) => {
    setLastCashChange(null)
    const resourceId = slotResourceChoice[slot.start_time]
    const slotIdentity = { start_time: slot.start_time, end_time: slot.end_time, resourceId: resourceId || null }
    setSelectedSlot(slotIdentity)
    setSlots(null)
    rebuildReview(slotIdentity)
  }

  const handleUpdateSummary = () => {
    if (!selectedSlot || reviewSubmitting) {
      return
    }
    rebuildReview(selectedSlot)
  }

  // Whether the displayed `review` still matches the live payment-method
  // and pricing inputs. Derived, never a separately-tracked flag that
  // could drift out of sync with the inputs it describes.
  const isReviewStale = !!review && !!reviewInputs && (
    reviewInputs.method !== checkoutMethod ||
    (checkoutMethod !== "RWP" && (
      reviewInputs.paymentOption !== paymentOption ||
      reviewInputs.couponCode !== couponCode ||
      reviewInputs.basePriceOverride !== priceOverride.base_price_override ||
      reviewInputs.finalPriceOverride !== priceOverride.final_price_override ||
      reviewInputs.priceOverrideReason !== priceOverride.price_override_reason
    ))
  )

  const handleCancelReview = () => {
    if (review?.kind === "Hold" && review.hold_id) {
      staffDiscardCheckoutHold(review.hold_id).catch(() => {})
    }
    setSelectedSlot(null)
    setReview(null)
    setReviewInputs(null)
    setCashReceived("")
  }

  const handleConfirmReview = async () => {
    if (reviewSubmitting || !review || isReviewStale) {
      return
    }
    setError("")
    setReviewSubmitting(true)
    try {
      if (review.kind === "RWP") {
        await staffReserveWithoutPayment(branchId, {
          customer_id: Number(createForm.customerId),
          branch_service_id: Number(createForm.branchServiceId),
          booking_date: createForm.date,
          start_time: review.start_time,
          resource_id: review.resource_id ? Number(review.resource_id) : undefined,
        })
        setSelectedSlot(null)
        setReview(null)
        setReviewInputs(null)
        loadBookings()
        setMessage("Booking reserved without payment.")
        return
      }

      if (checkoutMethod === "Cash") {
        if (!cashReceived) {
          setError("Enter cash received before confirming")
          return
        }
        const response = await staffFinalizeCashHold(review.hold_id, { cash_received: cashReceived })
        setLastCashChange({
          cashReceived: response.data.cash_received,
          amountCharged: response.data.amount_charged,
          changeReturned: response.data.change_returned,
          amountPaid: response.data.booking.amount_paid,
          balanceDue: response.data.booking.balance_due,
          balanceDueAt: response.data.booking.balance_due_at,
        })
        setSelectedSlot(null)
        setReview(null)
        setReviewInputs(null)
        setCashReceived("")
        loadBookings()
        setMessage("Booking created — cash collected.")
        return
      }
      if (checkoutMethod === "EmailLink") {
        const response = await staffFinalizeEmailLinkHold(review.hold_id)
        setPendingHold({ ...response.data, method: "EmailLink" })
        setSelectedSlot(null)
        setReview(null)
        setReviewInputs(null)
        return
      }
      if (checkoutMethod === "External") {
        const response = await staffFinalizeExternalHold(review.hold_id)
        setPendingHold({ ...response.data, method: "External" })
        setSelectedSlot(null)
        setReview(null)
        setReviewInputs(null)
        return
      }
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to complete checkout"))
    } finally {
      setReviewSubmitting(false)
    }
  }

  const handleConfirmPendingPayment = async () => {
    if (!pendingHold) {
      return
    }
    setConfirmingHold(true)
    setError("")
    try {
      await confirmExternalPayment(pendingHold.hold_id)
      setPendingHold(null)
      loadBookings()
      setMessage("Payment confirmed — booking created.")
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to confirm payment"))
    } finally {
      setConfirmingHold(false)
    }
  }

  const startReschedule = (booking) => {
    setError("")
    setRescheduleId(booking.id)
    setRescheduleForm({ booking_date: booking.booking_date, start_time: booking.start_time, resource_id: "", reason: "" })
    setReschedulePreview(null)
    setReschedulePreviewError("")
    setReschedulePaymentMethod("")
    setRescheduleOverrideReason("")
    setRescheduleCashReceived("")
    // The price impact depends only on the booking's existing terms vs
    // the service's current catalog price (rule 14) — never on the new
    // date/time — so it can be fetched immediately, before staff even
    // picks a slot.
    previewReschedulePriceDifference(booking.id)
      .then((response) => {
        setReschedulePreview(response.data)
        if (response.data.action === "CollectDifference") {
          setReschedulePaymentMethod(response.data.default_payment_method || "")
        }
      })
      .catch((err) => setReschedulePreviewError(extractErrorMessage(err, "Failed to calculate the price impact of this reschedule")))
  }

  const cancelReschedule = () => {
    setRescheduleId(null)
    setReschedulePreview(null)
    setReschedulePreviewError("")
    setReschedulePaymentMethod("")
    setRescheduleOverrideReason("")
    setRescheduleCashReceived("")
  }

  // Derived — never separately tracked flags that could drift out of sync
  // with reschedulePreview/reschedulePaymentMethod.
  const rescheduleIsOverride =
    reschedulePreview?.action === "CollectDifference" &&
    !!reschedulePreview.default_payment_method &&
    !!reschedulePaymentMethod &&
    reschedulePaymentMethod !== reschedulePreview.default_payment_method

  const rescheduleNeedsMethodChoice = reschedulePreview?.action === "CollectDifference" && !reschedulePaymentMethod
  const rescheduleNeedsOverrideReason = rescheduleIsOverride && !rescheduleOverrideReason.trim()
  const rescheduleNeedsCashAmount =
    reschedulePreview?.action === "CollectDifference" &&
    reschedulePaymentMethod === "Cash" &&
    (!rescheduleCashReceived || Number(rescheduleCashReceived) < Number(reschedulePreview.amount_due))

  // Live preview only — plain subtraction of two already-known numbers
  // (cash typed by staff vs. the backend's own amount_due), never a
  // recomputation of price logic, mirroring the identical pattern already
  // used for the original staff-checkout cash flow above.
  const rescheduleCashChangePreview =
    reschedulePreview?.action === "CollectDifference" && reschedulePaymentMethod === "Cash" && rescheduleCashReceived !== ""
      ? (Number(rescheduleCashReceived) - Number(reschedulePreview.amount_due)).toFixed(2)
      : null

  const rescheduleSaveDisabled =
    rescheduleSubmitting ||
    reschedulePreview === null ||
    !!reschedulePreviewError ||
    rescheduleNeedsMethodChoice ||
    rescheduleNeedsOverrideReason ||
    rescheduleNeedsCashAmount

  const handleReschedule = async (e) => {
    e.preventDefault()
    setError("")
    // Staff reschedule always requires a non-empty reason (backend is
    // still authoritative — this is just an immediate client-side check).
    if (!rescheduleForm.reason.trim()) {
      setError("A reason is required to reschedule this booking")
      return
    }
    if (rescheduleSaveDisabled) {
      return
    }
    setRescheduleSubmitting(true)
    try {
      const payload = {
        booking_date: rescheduleForm.booking_date,
        start_time: rescheduleForm.start_time,
        resource_id: rescheduleForm.resource_id ? Number(rescheduleForm.resource_id) : undefined,
        reason: rescheduleForm.reason,
      }
      // Payment-method fields are only ever sent when the preview showed a
      // genuine increase — the backend rejects them as unknown fields on
      // the customer endpoint, and they're simply irrelevant otherwise.
      if (reschedulePreview?.action === "CollectDifference") {
        payload.payment_method = reschedulePaymentMethod
        if (rescheduleIsOverride) {
          payload.override_reason = rescheduleOverrideReason
        }
        if (reschedulePaymentMethod === "Cash") {
          payload.cash_received = rescheduleCashReceived
        }
      }

      const response = await rescheduleBooking(rescheduleId, payload)
      const priceAdjustment = response.data.price_adjustment
      const bookingId = rescheduleId
      cancelReschedule()

      if (priceAdjustment?.action === "CollectDifference") {
        if (priceAdjustment.payment_method === "RazorpayOnline") {
          try {
            const razorpayResponse = await openRazorpayCheckout({
              orderId: priceAdjustment.razorpay_order_id,
              keyId: priceAdjustment.razorpay_key_id,
              amount: priceAdjustment.amount_due,
            })
            await verifyReschedulePriceDifference(bookingId, {
              razorpay_payment_id: razorpayResponse.razorpay_payment_id,
              razorpay_signature: razorpayResponse.razorpay_signature,
            })
            setMessage(`Booking rescheduled. Price difference of ₹${priceAdjustment.amount_due} collected via Razorpay.`)
          } catch (payErr) {
            setError(payErr.message || "Reschedule price-difference payment was not completed")
          }
        } else if (priceAdjustment.payment_method === "EmailPaymentLink") {
          setReschedulePendingConfirmation({
            bookingId, method: priceAdjustment.payment_method,
            paymentLink: priceAdjustment.payment_link, amountDue: priceAdjustment.amount_due,
          })
          setMessage(`Booking rescheduled. Payment link sent for the ₹${priceAdjustment.amount_due} difference.`)
        } else if (priceAdjustment.payment_method === "ExternalManual") {
          setReschedulePendingConfirmation({
            bookingId, method: priceAdjustment.payment_method, amountDue: priceAdjustment.amount_due,
          })
          setMessage(`Booking rescheduled. ₹${priceAdjustment.amount_due} difference awaiting Direct UPI/Bank Transfer confirmation.`)
        } else if (priceAdjustment.payment_method === "Cash") {
          const changeNote = Number(priceAdjustment.change_returned || 0) > 0
            ? ` (change returned: ₹${priceAdjustment.change_returned})` : ""
          setMessage(`Booking rescheduled. ₹${priceAdjustment.amount_collected} collected in cash${changeNote}.`)
        }
      } else if (priceAdjustment?.action === "RefundIssued") {
        setMessage(`Booking rescheduled. ₹${priceAdjustment.amount_refunded} refund issued for the price difference.`)
      } else {
        setMessage("Booking rescheduled.")
      }
      loadBookings()
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to reschedule booking"))
    } finally {
      setRescheduleSubmitting(false)
    }
  }

  const handleConfirmRescheduleDifferencePayment = async () => {
    if (!reschedulePendingConfirmation) {
      return
    }
    setError("")
    try {
      await confirmRescheduleDifferencePayment(reschedulePendingConfirmation.bookingId)
      setReschedulePendingConfirmation(null)
      loadBookings()
      setMessage("Reschedule difference payment confirmed.")
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to confirm the reschedule-difference payment"))
    }
  }

  const handleCancel = async (bookingId) => {
    setError("")
    // Staff cancellation always requires a non-empty reason (backend is
    // still authoritative — this is just an immediate client-side check).
    if (!(cancelReasons[bookingId] || "").trim()) {
      setError("A reason is required to cancel this booking")
      return
    }
    try {
      const response = await cancelBooking(bookingId, cancelReasons[bookingId], refundOverrides[bookingId] || null)
      const refund = response.data.refund
      if (refund && Number(refund.final_amount) > 0) {
        setMessage(
          `Booking cancelled. Refund of ₹${refund.final_amount}${refund.overridden ? " (overridden)" : ""} ${refund.already_processed ? "was already processed" : "initiated"} — see Payment History for its status.`
        )
      } else {
        setMessage("Booking cancelled.")
      }
      loadBookings()
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to cancel booking"))
    }
  }

  const startRefund = (bookingId) => {
    setError("")
    setRefundingId(bookingId)
    setRefundForm({ amount: "", reason: "" })
  }

  const cancelRefundForm = () => {
    setRefundingId(null)
    setRefundForm({ amount: "", reason: "" })
  }

  // Standalone refund — deliberately separate from handleCancel above.
  // This never touches the booking's status; it only moves money back,
  // via the same refund distribution/lifecycle the cancel flow uses.
  const handleSubmitRefund = async (e) => {
    e.preventDefault()
    setError("")
    if (refundSubmitting) {
      return
    }
    setRefundSubmitting(true)
    try {
      const response = await refundBooking(refundingId, {
        amount: refundForm.amount, reason: refundForm.reason,
      })
      const refund = response.data.refund
      setMessage(`Refund of ₹${refund.final_amount} initiated — see Payment History for its status. Booking status is unchanged.`)
      cancelRefundForm()
      loadBookings()
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to process refund"))
    } finally {
      setRefundSubmitting(false)
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

  const togglePaymentHistory = async (bookingId) => {
    if (paymentHistoryForId === bookingId) {
      setPaymentHistoryForId(null)
      return
    }
    try {
      const response = await getBookingPaymentHistory(bookingId)
      setPaymentHistory(response.data)
      setPaymentHistoryForId(bookingId)
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

  // Live preview only — plain subtraction of two already-known numbers
  // (cash typed by staff vs. the backend's own amount_due_now), never a
  // recomputation of price/coupon/deposit logic. Only meaningful once the
  // summary is fresh (not stale) and actually for Cash.
  const cashChangePreview =
    review?.kind === "Hold" && !isReviewStale && checkoutMethod === "Cash" && cashReceived !== ""
      ? (Number(cashReceived) - Number(review.amount_due_now)).toFixed(2)
      : null

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
            onChange={(e) => {
              invalidateSlotIdentity()
              setSelectedBranchId(e.target.value ? Number(e.target.value) : null)
            }}
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
              onChange={(e) => {
                invalidateSlotIdentity()
                setCreateForm({ ...createForm, customerId: e.target.value })
              }}
              required
            >
              <option value="">Select Customer</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>{customerLabel(c)}</option>
              ))}
            </select>
            {" "}
            <select
              value={createForm.branchServiceId}
              onChange={(e) => {
                invalidateSlotIdentity()
                setCreateForm({ ...createForm, branchServiceId: e.target.value })
              }}
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
              onChange={(e) => {
                invalidateSlotIdentity()
                const newDate = e.target.value
                setCreateForm({ ...createForm, date: newDate })
                // Deposit eligibility must always reflect the current
                // date — reset an already-selected Deposit back to Full
                // the moment the new date can no longer support it.
                if (paymentOption === "Deposit" && !isDepositEligible(newDate, "23:59:59")) {
                  setPaymentOption("Full")
                }
              }}
              required
            />
            {" "}
            <button type="submit">Check Availability</button>
          </form>

          <div style={{ marginTop: "10px" }}>
            <label>Payment method: </label>
            <select value={checkoutMethod} onChange={(e) => setCheckoutMethod(e.target.value)}>
              <option value="Cash">{PAYMENT_METHOD_LABELS.Cash}</option>
              <option value="EmailLink">{PAYMENT_METHOD_LABELS.EmailLink}</option>
              <option value="External">{PAYMENT_METHOD_LABELS.External}</option>
              <option value="RWP">{PAYMENT_METHOD_LABELS.RWP}</option>
            </select>
            {selectedSlot && (
              <span> (slot stays selected — changing this only marks the summary below as needing an update)</span>
            )}

            {checkoutMethod !== "RWP" && (
              <>
                {" "}
                <label>Payment option: </label>
                <select
                  value={depositEligibleNow ? paymentOption : "Full"}
                  onChange={(e) => setPaymentOption(e.target.value)}
                  disabled={!depositEligibleNow}
                >
                  <option value="Full">Full</option>
                  {depositEligibleNow && <option value="Deposit">Deposit</option>}
                </select>
                {!depositEligibleNow && createForm.date && (
                  <span> (Deposit needs the appointment to be {DEPOSIT_MIN_DAYS}+ days away)</span>
                )}
                {" "}
                <input
                  placeholder="Coupon code (optional)"
                  value={couponCode} onChange={(e) => setCouponCode(e.target.value)}
                  style={{ width: "140px" }}
                />
                <br />
                <details style={{ marginTop: "5px" }}>
                  <summary>Price override (Owner/Branch Manager)</summary>
                  <input
                    type="number" step="0.01" placeholder="Base price override"
                    value={priceOverride.base_price_override}
                    onChange={(e) => setPriceOverride({ ...priceOverride, base_price_override: e.target.value })}
                  />
                  {" "}
                  <input
                    type="number" step="0.01" placeholder="Final price override"
                    value={priceOverride.final_price_override}
                    onChange={(e) => setPriceOverride({ ...priceOverride, final_price_override: e.target.value })}
                  />
                  {" "}
                  <input
                    placeholder="Override reason"
                    value={priceOverride.price_override_reason}
                    onChange={(e) => setPriceOverride({ ...priceOverride, price_override_reason: e.target.value })}
                    style={{ width: "180px" }}
                  />
                </details>
              </>
            )}
          </div>

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
                  <button onClick={() => handleSelectSlot(slot)}>Select</button>
                </li>
              ))}
            </ul>
          )}

          {review && (
            <div style={{ border: "2px solid #333", padding: "10px", marginTop: "10px" }}>
              <h3>Booking &amp; Payment Summary</h3>
              <ul>
                <li>Customer: {customerLabel(selectedCustomer)}</li>
                <li>Service: {selectedService?.service_name}</li>
                <li>Resource: {review.resource_id ? resourceName(review.resource_id) : "Auto-assign (First Available)"}</li>
                <li>Date: {createForm.date}</li>
                <li>Time: {review.start_time} - {review.end_time}</li>

                {review.kind === "RWP" ? (
                  <li>Service price: ₹{selectedService?.price} (not collected — Reserve Without Payment)</li>
                ) : (
                  <>
                    <li>Base/calculated price: ₹{review.calculated_price}</li>
                    {review.base_price_override != null && <li>Base price override: ₹{review.base_price_override}</li>}
                    {review.coupon_code && <li>Coupon "{review.coupon_code}": -₹{review.discount_amount}</li>}
                    {review.final_price_override != null && <li>Final price override: ₹{review.final_price_override}</li>}
                    <li><strong>Final booking amount: ₹{review.final_amount}</strong></li>
                    <li>Payment option: {review.payment_option}</li>
                    <li><strong>Amount due now: ₹{review.amount_due_now}</strong></li>
                    {review.deposit_amount != null && <li>Deposit amount: ₹{review.deposit_amount}</li>}
                    {review.balance_due != null && <li>Remaining balance: ₹{review.balance_due}</li>}
                    {review.balance_due_at && <li>Balance due by: {new Date(review.balance_due_at).toLocaleString()}</li>}
                  </>
                )}
                <li>This summary reflects: {PAYMENT_METHOD_LABELS[reviewInputs?.method] || "—"}</li>
              </ul>

              {isReviewStale && (
                <p style={{ color: "#b30000", fontWeight: "bold" }}>
                  The payment method or pricing inputs above have changed since this summary was built.
                  Click <strong>Update Summary</strong> before you can confirm.
                </p>
              )}

              {!isReviewStale && review.kind === "Hold" && checkoutMethod === "Cash" && (
                <div style={{ marginTop: "5px" }}>
                  <input
                    type="number" step="0.01" placeholder="Cash received"
                    value={cashReceived} onChange={(e) => setCashReceived(e.target.value)}
                    style={{ width: "120px" }}
                  />
                  {cashChangePreview !== null && (
                    <span>
                      {" "}{Number(cashChangePreview) >= 0
                        ? `Change to return: ₹${cashChangePreview}`
                        : `Short by ₹${Math.abs(Number(cashChangePreview)).toFixed(2)}`}
                    </span>
                  )}
                </div>
              )}

              <div style={{ marginTop: "10px" }}>
                <button type="button" onClick={handleUpdateSummary} disabled={reviewSubmitting}>
                  {reviewSubmitting ? "Updating…" : "Update Summary"}
                </button>
                {" "}
                <button onClick={handleConfirmReview} disabled={reviewSubmitting || isReviewStale}>
                  {reviewSubmitting ? "Processing…" :
                    checkoutMethod === "RWP" ? "Confirm Reservation" :
                    checkoutMethod === "Cash" ? "Confirm & Collect Cash" :
                    checkoutMethod === "EmailLink" ? "Send Payment Link" : "Mark Awaiting External Payment"}
                </button>
                {" "}
                <button type="button" onClick={handleCancelReview} disabled={reviewSubmitting}>Back</button>
              </div>
            </div>
          )}

          {lastCashChange && (
            <div style={{ border: "1px solid #ccc", padding: "10px", marginTop: "10px" }}>
              <strong>Cash received: ₹{lastCashChange.cashReceived}</strong>
              {" — amount paid: ₹"}{lastCashChange.amountPaid}
              {" — "}
              <strong>Change to return: ₹{lastCashChange.changeReturned}</strong>
              {lastCashChange.balanceDue != null && Number(lastCashChange.balanceDue) > 0 && (
                <>
                  {" — remaining balance: ₹"}{lastCashChange.balanceDue}
                  {lastCashChange.balanceDueAt && ` (due by ${new Date(lastCashChange.balanceDueAt).toLocaleString()})`}
                </>
              )}
            </div>
          )}

          {pendingHold && (
            <div style={{ border: "1px solid #ccc", padding: "10px", marginTop: "10px" }}>
              <p>
                Awaiting payment ({PAYMENT_METHOD_LABELS[pendingHold.method] || pendingHold.method}) — hold expires{" "}
                {pendingHold.expires_at && new Date(pendingHold.expires_at).toLocaleTimeString()}.
              </p>
              {pendingHold.payment_link && (
                <p>
                  Payment link:{" "}
                  <a href={pendingHold.payment_link} target="_blank" rel="noreferrer">{pendingHold.payment_link}</a>
                </p>
              )}
              <button onClick={handleConfirmPendingPayment} disabled={confirmingHold}>
                {confirmingHold ? "Confirming…" : "Confirm Payment Received"}
              </button>
              {" "}
              <button onClick={() => setPendingHold(null)}>Discard</button>
            </div>
          )}

          {reschedulePendingConfirmation && (
            <div style={{ border: "1px solid #ccc", padding: "10px", marginTop: "10px" }}>
              <p>
                Reschedule difference of ₹{reschedulePendingConfirmation.amountDue} awaiting{" "}
                {RESCHEDULE_PAYMENT_METHOD_LABELS[reschedulePendingConfirmation.method]} confirmation.
              </p>
              {reschedulePendingConfirmation.paymentLink && (
                <p>
                  Payment link:{" "}
                  <a href={reschedulePendingConfirmation.paymentLink} target="_blank" rel="noreferrer">
                    {reschedulePendingConfirmation.paymentLink}
                  </a>
                </p>
              )}
              <button onClick={handleConfirmRescheduleDifferencePayment}>Confirm Payment Received</button>
              {" "}
              <button onClick={() => setReschedulePendingConfirmation(null)}>Dismiss</button>
            </div>
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
                {renderFinancials(b)}

                {rescheduleId === b.id ? (
                  <form onSubmit={handleReschedule} style={{ border: "1px solid #999", padding: "8px", marginTop: "4px" }}>
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
                    <input
                      placeholder="Reason (required)"
                      value={rescheduleForm.reason}
                      onChange={(e) => setRescheduleForm({ ...rescheduleForm, reason: e.target.value })}
                      style={{ width: "200px" }}
                      required
                    />

                    <div style={{ marginTop: "8px" }}>
                      {reschedulePreviewError ? (
                        <p style={{ color: "red" }}>{reschedulePreviewError}</p>
                      ) : reschedulePreview === null ? (
                        <p>Calculating price impact…</p>
                      ) : reschedulePreview.action === null ? (
                        <p>No price difference for the current service price — nothing to collect or refund.</p>
                      ) : reschedulePreview.action === "RefundIssued" ? (
                        <div>
                          <p>
                            Original amount: ₹{reschedulePreview.previous_amount} — new amount: ₹{reschedulePreview.new_amount}
                          </p>
                          <p>
                            <strong>Estimated refund: ₹{reschedulePreview.amount_estimate}</strong>
                            {" "}— refunded automatically via the booking's existing payment method once saved.
                          </p>
                        </div>
                      ) : (
                        <div>
                          <p>
                            Original amount: ₹{reschedulePreview.previous_amount} — new amount: ₹{reschedulePreview.new_amount}
                          </p>
                          <p><strong>Additional amount due: ₹{reschedulePreview.amount_due}</strong></p>
                          <label>
                            Collect via:{" "}
                            <select
                              value={reschedulePaymentMethod}
                              onChange={(e) => { setReschedulePaymentMethod(e.target.value); setRescheduleOverrideReason("") }}
                              required
                            >
                              <option value="">
                                {reschedulePreview.default_payment_method ? "Select…" : "Select a payment method…"}
                              </option>
                              {RESCHEDULE_PAYMENT_METHODS.map((m) => (
                                <option key={m} value={m}>
                                  {RESCHEDULE_PAYMENT_METHOD_LABELS[m]}
                                  {m === reschedulePreview.default_payment_method ? " (default — original payment method)" : ""}
                                </option>
                              ))}
                            </select>
                          </label>
                          {!reschedulePreview.default_payment_method && (
                            <p>This booking has no prior payment on record — a collection method must be chosen.</p>
                          )}

                          {rescheduleIsOverride && (
                            <div style={{ color: "#b30000" }}>
                              <p style={{ fontWeight: "bold", margin: "4px 0" }}>
                                Overriding the default payment method ({RESCHEDULE_PAYMENT_METHOD_LABELS[reschedulePreview.default_payment_method]}).
                                A reason is required.
                              </p>
                              <input
                                placeholder="Reason for using a different payment method (required)"
                                value={rescheduleOverrideReason}
                                onChange={(e) => setRescheduleOverrideReason(e.target.value)}
                                style={{ width: "280px" }}
                                required
                              />
                            </div>
                          )}

                          {reschedulePaymentMethod === "Cash" && (
                            <div style={{ marginTop: "5px" }}>
                              <input
                                type="number" step="0.01" placeholder="Amount received (required)"
                                value={rescheduleCashReceived}
                                onChange={(e) => setRescheduleCashReceived(e.target.value)}
                                style={{ width: "160px" }}
                                required
                              />
                              {rescheduleCashChangePreview !== null && (
                                <span>
                                  {" "}{Number(rescheduleCashChangePreview) >= 0
                                    ? `Change to return: ₹${rescheduleCashChangePreview}`
                                    : `Short by ₹${Math.abs(Number(rescheduleCashChangePreview)).toFixed(2)}`}
                                </span>
                              )}
                            </div>
                          )}
                          {reschedulePaymentMethod === "EmailPaymentLink" && (
                            <p>A Razorpay payment link will be emailed to the customer once saved. If the customer has no email on file, the backend will reject this and the error will be shown here.</p>
                          )}
                          {reschedulePaymentMethod === "ExternalManual" && (
                            <p>The difference will be marked awaiting a Direct UPI/Bank Transfer — confirm it as received once the transfer arrives.</p>
                          )}
                          {reschedulePaymentMethod === "RazorpayOnline" && (
                            <p>A Razorpay checkout will open once saved.</p>
                          )}
                        </div>
                      )}
                    </div>

                    <div style={{ marginTop: "8px" }}>
                      <button type="submit" disabled={rescheduleSaveDisabled}>
                        {rescheduleSubmitting ? "Saving…" : "Save"}
                      </button>
                      {" "}
                      <button type="button" onClick={cancelReschedule}>Cancel</button>
                    </div>
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
                        placeholder="Cancellation reason (required)"
                        value={cancelReasons[b.id] || ""}
                        onChange={(e) => setCancelReasons({ ...cancelReasons, [b.id]: e.target.value })}
                        style={{ width: "220px" }}
                        required
                      />
                      {" "}
                      <input
                        type="number" step="0.01"
                        placeholder="Refund override ₹ (optional)"
                        value={refundOverrides[b.id] || ""}
                        onChange={(e) => setRefundOverrides({ ...refundOverrides, [b.id]: e.target.value })}
                        style={{ width: "160px" }}
                      />
                      {" "}
                      <button onClick={() => handleCancel(b.id)}>Cancel Booking</button>
                      {" "}
                      <button onClick={() => handleComplete(b.id)}>Mark Completed</button>
                    </>
                  )
                )}
                {" "}
                {Number(b.refundable_amount || 0) > 0 && (
                  refundingId === b.id ? (
                    <form onSubmit={handleSubmitRefund} style={{ display: "inline", border: "1px solid #999", padding: "4px" }}>
                      <strong>Refund (does not cancel the booking, up to ₹{b.refundable_amount}): </strong>
                      <input
                        type="number" step="0.01" min="0.01" max={b.refundable_amount} placeholder="Amount ₹"
                        value={refundForm.amount}
                        onChange={(e) => setRefundForm({ ...refundForm, amount: e.target.value })}
                        style={{ width: "100px" }}
                        required
                      />
                      {" "}
                      <input
                        placeholder="Reason (required)"
                        value={refundForm.reason}
                        onChange={(e) => setRefundForm({ ...refundForm, reason: e.target.value })}
                        style={{ width: "220px" }}
                        required
                      />
                      {" "}
                      <button type="submit" disabled={refundSubmitting}>
                        {refundSubmitting ? "Processing…" : "Submit Refund"}
                      </button>
                      {" "}
                      <button type="button" onClick={cancelRefundForm}>Cancel</button>
                    </form>
                  ) : (
                    <button onClick={() => startRefund(b.id)} title="Refund money without cancelling this booking">
                      Refund… (up to ₹{b.refundable_amount})
                    </button>
                  )
                )}
                {" "}
                <button onClick={() => toggleHistory(b.id)}>
                  {historyForId === b.id ? "Hide History" : "History"}
                </button>
                {" "}
                <button onClick={() => togglePaymentHistory(b.id)}>
                  {paymentHistoryForId === b.id ? "Hide Payment History" : "Payment History"}
                </button>

                {historyForId === b.id && (
                  <ul>
                    {history.map((h) => (
                      <li key={h.id}>{h.action} — {new Date(h.performed_at).toLocaleString()}</li>
                    ))}
                  </ul>
                )}

                {paymentHistoryForId === b.id && paymentHistory && (
                  <div style={{ marginLeft: "20px" }}>
                    <strong>Payments</strong>
                    <ul>
                      {paymentHistory.payments.length === 0 && <li>No payments recorded.</li>}
                      {paymentHistory.payments.map((p) => (
                        <li key={p.id}>
                          {p.payment_type} via {p.method} — ₹{p.amount} — {paymentStatusLabel(p.status)}
                          {p.method === "Cash" && p.cash_received != null && (
                            <> (cash received ₹{p.cash_received}, change ₹{p.change_returned})</>
                          )}
                          {" "}({new Date(p.created_at).toLocaleString()})
                        </li>
                      ))}
                    </ul>
                    <strong>Refunds</strong>
                    <ul>
                      {paymentHistory.refunds.length === 0 && <li>No refunds recorded.</li>}
                      {paymentHistory.refunds.map((r) => (
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
            ))}
            {bookings.length === 0 && <li>No bookings found.</li>}
          </ul>
        </>
      )}
    </div>
  )
}
