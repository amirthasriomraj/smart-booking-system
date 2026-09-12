import React, { useContext, useEffect, useState, useCallback } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import {
  listBranchesForBusiness,
  listBranchServicesForBranch,
  listBranchServicesForBusiness,
  listCoupons,
  createCoupon,
  approveCoupon,
  rejectCoupon,
  setCouponStatus,
} from "../api/api"
import { extractErrorMessage } from "../api/errors"

const emptyForm = {
  code: "", branch_id: "", discount_type: "Percentage", discount_value: "",
  min_booking_amount: "0", max_discount: "", valid_from: "", valid_until: "",
  total_usage_limit: "", per_customer_usage_limit: "1", branch_service_ids: [], applicable_weekdays: [],
}

const WEEKDAYS = [
  { value: 0, label: "Mon" }, { value: 1, label: "Tue" }, { value: 2, label: "Wed" },
  { value: 3, label: "Thu" }, { value: 4, label: "Fri" }, { value: 5, label: "Sat" }, { value: 6, label: "Sun" },
]

function selectedIds(event) {
  return Array.from(event.target.selectedOptions, (option) => Number(option.value))
}

function toggleWeekday(list, value) {
  return list.includes(value) ? list.filter((d) => d !== value) : [...list, value].sort()
}

// Coupons & Promotions (rule 10; Milestone 8). A business-wide coupon
// (branch_id omitted) is Business Owner only and auto-approved; a
// branch-scoped coupon created by a Branch Manager requires Business Owner
// approval before it can be redeemed at that branch (same
// current-value/approval-history pattern as Service overrides in
// ServiceManagement.jsx). Actual eligibility/discount/redemption-limit
// calculation happens server-side at checkout — this page only manages
// configuration, approval, and full visibility into every condition
// already stored on the Coupon model (no new rules are introduced here).
export default function CouponManagement() {
  const { user } = useContext(AuthContext)
  const businessId = user?.business?.id
  const roleCode = user?.business?.role_code
  const isOwner = roleCode === "BUSINESS_OWNER"
  const isBranchManager = roleCode === "BRANCH_MANAGER"
  const effectiveBranchId = isBranchManager ? (user?.business?.branch_id ?? null) : null

  const [branches, setBranches] = useState([])
  const [coupons, setCoupons] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [formBranchServices, setFormBranchServices] = useState([])
  // Every branch-service in the business, keyed by id, so coupon details
  // (which only store branch_service_id) can be rendered with real names —
  // a business-wide coupon's applicable services can span multiple branches.
  const [allBranchServices, setAllBranchServices] = useState([])

  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [decisionComments, setDecisionComments] = useState({})

  useEffect(() => {
    if (!businessId) {
      return
    }
    if (isOwner) {
      listBranchesForBusiness(businessId)
        .then((r) => setBranches(r.data.items.filter((b) => b.approval_status === "Approved" && b.is_active)))
        .catch(() => {})
    }
    listBranchServicesForBusiness(businessId).then((r) => setAllBranchServices(r.data.items)).catch(() => {})
  }, [businessId, isOwner])

  const loadCoupons = useCallback(() => {
    if (!businessId) {
      return
    }
    listCoupons(businessId).then((r) => setCoupons(r.data)).catch(() => setError("Failed to load coupons"))
  }, [businessId])

  useEffect(() => {
    loadCoupons()
  }, [loadCoupons])

  // The branch a new coupon will be scoped to: Owner picks it (or leaves
  // blank for business-wide); Branch Manager is always their own branch.
  const formTargetBranchId = isBranchManager ? effectiveBranchId : (form.branch_id ? Number(form.branch_id) : null)

  useEffect(() => {
    if (!formTargetBranchId) {
      return
    }
    listBranchServicesForBranch(formTargetBranchId).then((r) => setFormBranchServices(r.data)).catch(() => {})
  }, [formTargetBranchId])

  // A business-wide coupon may apply to services across any branch (the
  // backend only requires branch_service_id to belong to this business,
  // not to a specific branch — see crud_coupon.create_coupon), so the
  // picker for that case draws from every branch-service in the business.
  const visibleFormBranchServices = formTargetBranchId ? formBranchServices : allBranchServices

  const branchName = (id) => branches.find((b) => b.id === id)?.branch_name || `Branch #${id}`
  const serviceName = (id) => allBranchServices.find((bs) => bs.id === id)?.service_name || `Service #${id}`
  const weekdayLabel = (value) => WEEKDAYS.find((w) => w.value === value)?.label || value

  const handleCreate = async (e) => {
    e.preventDefault()
    setError("")
    try {
      await createCoupon(businessId, {
        code: form.code,
        branch_id: isBranchManager ? effectiveBranchId : (form.branch_id ? Number(form.branch_id) : undefined),
        discount_type: form.discount_type,
        discount_value: form.discount_value,
        min_booking_amount: form.min_booking_amount || "0",
        max_discount: form.max_discount || undefined,
        valid_from: form.valid_from,
        valid_until: form.valid_until,
        applicable_weekdays: form.applicable_weekdays.length > 0 ? form.applicable_weekdays : undefined,
        total_usage_limit: form.total_usage_limit ? Number(form.total_usage_limit) : undefined,
        per_customer_usage_limit: Number(form.per_customer_usage_limit || "1"),
        branch_service_ids: form.branch_service_ids.length > 0 ? form.branch_service_ids : undefined,
      })
      setForm(emptyForm)
      loadCoupons()
      setMessage(
        isBranchManager || form.branch_id
          ? "Coupon created."
          : "Business-wide coupon created."
      )
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to create coupon"))
    }
  }

  const handleDecision = async (couponId, decision) => {
    setError("")
    try {
      if (decision === "Approved") {
        await approveCoupon(couponId, decisionComments[couponId] || null)
      } else {
        await rejectCoupon(couponId, decisionComments[couponId] || null)
      }
      loadCoupons()
      setMessage(`Coupon ${decision.toLowerCase()}.`)
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to decide on coupon"))
    }
  }

  const handleToggleStatus = async (coupon) => {
    setError("")
    try {
      await setCouponStatus(coupon.id, coupon.status === "Active" ? "Inactive" : "Active")
      loadCoupons()
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to update coupon status"))
    }
  }

  if (!businessId) {
    return <p>You do not have an active business.</p>
  }

  if (!isOwner && !isBranchManager) {
    return <p>You are not authorized to manage coupons.</p>
  }

  const pending = coupons.filter((c) => c.approval_status === "Pending")
  const usable = coupons.filter((c) => c.approval_status !== "Pending")

  // All configured conditions for one coupon, rendered consistently in
  // both the Pending and active lists — every field the Coupon model
  // stores, none invented.
  const renderConditions = (c) => (
    <ul>
      <li>Discount: {c.discount_type === "Percentage" ? `${c.discount_value}%` : `₹${c.discount_value}`} off
        {c.max_discount != null && ` (capped at ₹${c.max_discount})`}
      </li>
      <li>Minimum booking amount: ₹{c.min_booking_amount}</li>
      <li>Scope: {c.branch_id ? branchName(c.branch_id) : "business-wide (all branches)"}</li>
      <li>Applicable services: {c.branch_service_ids && c.branch_service_ids.length > 0 ? c.branch_service_ids.map(serviceName).join(", ") : "all services"}</li>
      <li>Applicable weekdays: {c.applicable_weekdays && c.applicable_weekdays.length > 0 ? c.applicable_weekdays.map(weekdayLabel).join(", ") : "all weekdays"}</li>
      <li>Valid: {c.valid_from} to {c.valid_until}</li>
      <li>Usage limit: {c.total_usage_limit != null ? c.total_usage_limit : "unlimited"} total, {c.per_customer_usage_limit} per customer</li>
      <li>Status: {c.status}{c.approval_status && ` — approval: ${c.approval_status}`}</li>
    </ul>
  )

  return (
    <div>
      <h1>Coupons</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      <h2>Create Coupon</h2>
      <form onSubmit={handleCreate}>
        <input
          placeholder="Code (e.g. SAVE10)"
          value={form.code}
          onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
          required
        />
        <br />
        {isOwner && (
          <>
            <label>Scope: </label>
            <select value={form.branch_id} onChange={(e) => setForm({ ...form, branch_id: e.target.value, branch_service_ids: [] })}>
              <option value="">Business-wide (all branches)</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>{b.branch_name} only</option>
              ))}
            </select>
            <br />
          </>
        )}
        {isBranchManager && <p>Scope: your branch (requires Business Owner approval)</p>}

        <select value={form.discount_type} onChange={(e) => setForm({ ...form, discount_type: e.target.value })}>
          <option value="Percentage">Percentage off</option>
          <option value="Fixed">Fixed amount off</option>
        </select>
        {" "}
        <input
          type="number" min="0" step="0.01"
          placeholder={form.discount_type === "Percentage" ? "Discount % (1-100)" : "Discount amount"}
          value={form.discount_value}
          onChange={(e) => setForm({ ...form, discount_value: e.target.value })}
          required
        />
        <br />
        <input
          type="number" min="0" step="0.01" placeholder="Minimum booking amount"
          value={form.min_booking_amount}
          onChange={(e) => setForm({ ...form, min_booking_amount: e.target.value })}
        />
        {" "}
        <input
          type="number" min="0" step="0.01" placeholder="Max discount cap (optional)"
          value={form.max_discount}
          onChange={(e) => setForm({ ...form, max_discount: e.target.value })}
        />
        <br />
        <label>Valid from: </label>
        <input type="date" value={form.valid_from} onChange={(e) => setForm({ ...form, valid_from: e.target.value })} required />
        {" "}
        <label>Valid until: </label>
        <input type="date" value={form.valid_until} onChange={(e) => setForm({ ...form, valid_until: e.target.value })} required />
        <br />
        <input
          type="number" min="0" placeholder="Total usage limit (optional)"
          value={form.total_usage_limit}
          onChange={(e) => setForm({ ...form, total_usage_limit: e.target.value })}
        />
        {" "}
        <input
          type="number" min="1" placeholder="Per-customer usage limit"
          value={form.per_customer_usage_limit}
          onChange={(e) => setForm({ ...form, per_customer_usage_limit: e.target.value })}
        />
        <br />
        <label>Applicable weekdays (none selected = all weekdays):</label>
        <br />
        {WEEKDAYS.map((w) => (
          <label key={w.value} style={{ marginRight: "10px" }}>
            <input
              type="checkbox"
              checked={form.applicable_weekdays.includes(w.value)}
              onChange={() => setForm({ ...form, applicable_weekdays: toggleWeekday(form.applicable_weekdays, w.value) })}
            />
            {" "}{w.label}
          </label>
        ))}
        <br />
        <label>Applicable services (none selected = all services):</label>
        <br />
        <select
          multiple
          value={form.branch_service_ids}
          onChange={(e) => setForm({ ...form, branch_service_ids: selectedIds(e) })}
        >
          {visibleFormBranchServices.map((bs) => (
            <option key={bs.id} value={bs.id}>{bs.service_name}</option>
          ))}
        </select>
        <br />
        <button type="submit">Create Coupon</button>
      </form>

      <h2>Pending Approval</h2>
      <ul>
        {pending.map((c) => (
          <li key={c.id} style={{ marginBottom: "10px" }}>
            <strong>{c.code}</strong>
            {renderConditions(c)}
            {isOwner && (
              <>
                <input
                  placeholder="Comments (optional)"
                  value={decisionComments[c.id] || ""}
                  onChange={(e) => setDecisionComments({ ...decisionComments, [c.id]: e.target.value })}
                />
                {" "}
                <button onClick={() => handleDecision(c.id, "Approved")}>Approve</button>
                {" "}
                <button onClick={() => handleDecision(c.id, "Rejected")}>Reject</button>
              </>
            )}
          </li>
        ))}
        {pending.length === 0 && <li>None.</li>}
      </ul>

      <h2>Coupons</h2>
      <ul>
        {usable.map((c) => (
          <li key={c.id} style={{ marginBottom: "10px" }}>
            <strong>{c.code}</strong>
            {renderConditions(c)}
            {c.approval_status !== "Rejected" && (
              <button onClick={() => handleToggleStatus(c)}>
                {c.status === "Active" ? "Deactivate" : "Activate"}
              </button>
            )}
          </li>
        ))}
        {usable.length === 0 && <li>No coupons yet.</li>}
      </ul>
    </div>
  )
}
