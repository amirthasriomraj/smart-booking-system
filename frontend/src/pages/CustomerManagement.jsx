import React, { useContext, useEffect, useState, useCallback } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import {
  listBusinessCustomers,
  createWalkInCustomer,
  updateBusinessCustomer,
  setCustomerStatus,
} from "../api/api"
import { extractErrorMessage } from "../api/errors"

const emptyCreateForm = {
  first_name: "",
  last_name: "",
  mobile_number: "",
  email: "",
  notes: "",
}

const emptyEditForm = {
  first_name: "",
  last_name: "",
  mobile_number: "",
  notes: "",
  email: "",
}

// A walk-in created without an email gets this placeholder domain
// (backend crud_customer.PLACEHOLDER_EMAIL_DOMAIN) — its presence means the
// identity is still unclaimed, so staff may back-fill a real email here.
// Once claimed (a real email/login exists), the email field is not editable.
const PLACEHOLDER_EMAIL_SUFFIX = "@placeholder.smartbooking.local"
const isUnclaimedPlaceholder = (customer) => customer.email?.endsWith(PLACEHOLDER_EMAIL_SUFFIX)

export default function CustomerManagement() {
  const { user } = useContext(AuthContext)
  const businessId = user?.business?.id
  const roleCode = user?.business?.role_code
  // ID-032: Customer Management is business-wide for both roles — no branch scoping.
  const canManage = ["BUSINESS_OWNER", "BRANCH_MANAGER"].includes(roleCode)

  const [customers, setCustomers] = useState([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState("")
  const [form, setForm] = useState(emptyCreateForm)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState(emptyEditForm)

  const load = useCallback(() => {
    if (!businessId) {
      return
    }
    listBusinessCustomers(businessId, { search: search || undefined })
      .then((response) => {
        setCustomers(response.data.data)
        setTotal(response.data.total)
      })
      .catch(() => setError("Failed to load customers"))
  }, [businessId, search])

  useEffect(() => {
    load()
  }, [load])

  const handleCreate = async (e) => {
    e.preventDefault()
    setError("")
    setMessage("")
    try {
      const payload = { ...form, email: form.email || undefined }
      await createWalkInCustomer(businessId, payload)
      setForm(emptyCreateForm)
      setMessage("Customer created.")
      load()
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to create customer"))
    }
  }

  const startEdit = (customer) => {
    setEditingId(customer.id)
    setEditForm({
      first_name: customer.first_name || "",
      last_name: customer.last_name || "",
      mobile_number: customer.mobile_number || "",
      notes: customer.notes || "",
      // Placeholder email isn't meaningful to show for editing — start blank
      // so staff type the customer's real one.
      email: "",
    })
  }

  const handleSaveEdit = async (customerId, customer) => {
    setError("")
    try {
      const payload = { ...editForm }
      // Only send email when it's actually editable and was filled in —
      // never attempt to change it for an already-claimed customer.
      if (!isUnclaimedPlaceholder(customer) || !payload.email) {
        delete payload.email
      }
      await updateBusinessCustomer(customerId, payload)
      setEditingId(null)
      load()
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to update customer"))
    }
  }

  const handleToggleStatus = async (customer) => {
    setError("")
    try {
      await setCustomerStatus(customer.id, customer.status === "Active" ? "Inactive" : "Active")
      load()
    } catch {
      setError("Failed to update status")
    }
  }

  if (!businessId) {
    return <p>You do not have an active business.</p>
  }

  if (!canManage) {
    return <p>You are not authorized to manage customers.</p>
  }

  return (
    <div>
      <h1>Customers</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      <input
        type="text"
        placeholder="Search by name, mobile, email, or customer ID"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ width: "320px" }}
      />
      <p>{total} customer(s)</p>

      <ul>
        {customers.map((c) => (
          <li key={c.id} style={{ marginBottom: "8px" }}>
            {editingId === c.id ? (
              <>
                <input
                  type="text"
                  value={editForm.first_name}
                  onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
                />
                <input
                  type="text"
                  value={editForm.last_name}
                  onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
                />
                <input
                  type="text"
                  value={editForm.mobile_number}
                  onChange={(e) => setEditForm({ ...editForm, mobile_number: e.target.value })}
                />
                <input
                  type="text"
                  placeholder="Notes"
                  value={editForm.notes}
                  onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                />
                {isUnclaimedPlaceholder(c) && (
                  <input
                    type="email"
                    placeholder="Add email (lets this customer log in later)"
                    value={editForm.email}
                    onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                  />
                )}
                <button onClick={() => handleSaveEdit(c.id, c)}>Save</button>
                <button onClick={() => setEditingId(null)}>Cancel</button>
              </>
            ) : (
              <>
                <strong>{c.customer_number}</strong>
                {" — "}
                {c.first_name} {c.last_name}
                {" — "}
                {c.mobile_number}
                {c.email && !isUnclaimedPlaceholder(c) && <>{" — "}{c.email}</>}
                {" — status: "}
                {c.status}
                {" "}
                <button onClick={() => startEdit(c)}>Edit</button>{" "}
                <button onClick={() => handleToggleStatus(c)}>
                  {c.status === "Active" ? "Deactivate" : "Activate"}
                </button>
              </>
            )}
          </li>
        ))}
      </ul>

      <h2>Create Walk-In Customer</h2>
      <form onSubmit={handleCreate}>
        <input
          type="text"
          placeholder="First Name"
          value={form.first_name}
          onChange={(e) => setForm({ ...form, first_name: e.target.value })}
          required
        />
        <br />
        <input
          type="text"
          placeholder="Last Name"
          value={form.last_name}
          onChange={(e) => setForm({ ...form, last_name: e.target.value })}
          required
        />
        <br />
        <input
          type="text"
          placeholder="Mobile Number"
          value={form.mobile_number}
          onChange={(e) => setForm({ ...form, mobile_number: e.target.value })}
          required
        />
        <br />
        <input
          type="email"
          placeholder="Email (optional)"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
        <br />
        <input
          type="text"
          placeholder="Notes (optional)"
          value={form.notes}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
        />
        <br />
        <button type="submit">Create Customer</button>
      </form>
    </div>
  )
}
