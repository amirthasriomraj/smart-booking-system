import React, { useContext, useEffect, useState, useCallback } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import {
  listBranchesForBusiness,
  listResourceCategories,
  createResourceCategory,
  updateResourceCategory,
  listResourcesForBranch,
  listResourcesForBusiness,
  createResource,
  updateResource,
  activateResource,
  suspendResource,
  getResourceWorkingHours,
  upsertResourceWorkingHours,
  listResourceUsers,
  inviteResourceUser,
  resendResourceInvite,
  deactivateResourceUser,
} from "../api/api"
import { extractErrorMessage } from "../api/errors"

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

const emptyCategoryForm = { category_name: "", description: "" }

const emptyResourceForm = {
  resource_name: "",
  resource_category_id: "",
  code: "",
  requires_login: false,
  max_bookings_per_day: "",
  booking_buffer_minutes: "",
}

export default function ResourceManagement() {
  const { user } = useContext(AuthContext)
  const businessId = user?.business?.id
  const roleCode = user?.business?.role_code
  const isOwner = roleCode === "BUSINESS_OWNER"
  const isBranchManager = roleCode === "BRANCH_MANAGER"
  const isHr = roleCode === "HR_USER"

  const [branches, setBranches] = useState([])
  const [selectedBranchId, setSelectedBranchId] = useState(null)
  const [categories, setCategories] = useState([])
  const [resources, setResources] = useState([])
  const [resourceUsers, setResourceUsers] = useState([])

  const [categoryForm, setCategoryForm] = useState(emptyCategoryForm)
  const [resourceForm, setResourceForm] = useState(emptyResourceForm)
  const [inviteEmail, setInviteEmail] = useState({})

  const [editingCategoryId, setEditingCategoryId] = useState(null)
  const [categoryEditForm, setCategoryEditForm] = useState(emptyCategoryForm)

  const [editingResourceId, setEditingResourceId] = useState(null)
  const [resourceEditForm, setResourceEditForm] = useState(emptyResourceForm)

  const [workingHoursResourceId, setWorkingHoursResourceId] = useState(null)
  const [workingHours, setWorkingHours] = useState({})

  const [error, setError] = useState("")
  const [message, setMessage] = useState("")

  // Branch Manager is always scoped to their own currently-assigned branch;
  // this is derived directly from auth context, not stored/synced as state.
  const effectiveBranchId = isBranchManager ? (user?.business?.branch_id ?? null) : selectedBranchId

  useEffect(() => {
    if (!businessId) {
      return
    }
    listResourceCategories(businessId).then((r) => setCategories(r.data)).catch(() => {})
    if (isOwner) {
      listBranchesForBusiness(businessId)
        .then((r) => setBranches(r.data.filter((b) => b.approval_status === "Approved")))
        .catch(() => {})
    }
  }, [businessId, isOwner])

  const loadResources = useCallback(() => {
    if (isHr) {
      listResourcesForBusiness(businessId).then((r) => setResources(r.data)).catch(() => setError("Failed to load resources"))
      return
    }
    if (!effectiveBranchId) {
      return
    }
    listResourcesForBranch(effectiveBranchId).then((r) => setResources(r.data)).catch(() => setError("Failed to load resources"))
  }, [businessId, effectiveBranchId, isHr])

  // No branch selected (Owner hasn't picked one yet): render as empty rather
  // than clearing `resources` state synchronously from an effect.
  const displayedResources = !isHr && !effectiveBranchId ? [] : resources

  const loadResourceUsers = useCallback(() => {
    if (!businessId) {
      return
    }
    listResourceUsers(businessId).then((r) => setResourceUsers(r.data)).catch(() => {})
  }, [businessId])

  useEffect(() => {
    loadResources()
    loadResourceUsers()
  }, [loadResources, loadResourceUsers])

  const handleCreateCategory = async (e) => {
    e.preventDefault()
    setError("")
    try {
      await createResourceCategory(businessId, categoryForm)
      setCategoryForm(emptyCategoryForm)
      listResourceCategories(businessId).then((r) => setCategories(r.data))
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to create category"))
    }
  }

  const handleCreateResource = async (e) => {
    e.preventDefault()
    setError("")
    if (!effectiveBranchId) {
      setError("Select a branch first")
      return
    }
    try {
      await createResource(effectiveBranchId, {
        resource_name: resourceForm.resource_name,
        resource_category_id: Number(resourceForm.resource_category_id),
        code: resourceForm.code || null,
        requires_login: resourceForm.requires_login,
        max_bookings_per_day: resourceForm.max_bookings_per_day ? Number(resourceForm.max_bookings_per_day) : null,
        booking_buffer_minutes: resourceForm.booking_buffer_minutes ? Number(resourceForm.booking_buffer_minutes) : null,
      })
      setResourceForm(emptyResourceForm)
      loadResources()
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to create resource"))
    }
  }

  const startEditCategory = (category) => {
    setEditingCategoryId(category.id)
    setCategoryEditForm({ category_name: category.category_name, description: category.description || "" })
  }

  const cancelEditCategory = () => {
    setEditingCategoryId(null)
    setCategoryEditForm(emptyCategoryForm)
  }

  const handleUpdateCategory = async (e) => {
    e.preventDefault()
    setError("")
    try {
      await updateResourceCategory(editingCategoryId, categoryEditForm)
      cancelEditCategory()
      listResourceCategories(businessId).then((r) => setCategories(r.data))
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to update category"))
    }
  }

  const startEditResource = (resource) => {
    setEditingResourceId(resource.id)
    setResourceEditForm({
      resource_name: resource.resource_name,
      resource_category_id: String(resource.resource_category_id),
      code: resource.code || "",
      description: resource.description || "",
      max_bookings_per_day: resource.max_bookings_per_day ?? "",
      booking_buffer_minutes: resource.booking_buffer_minutes ?? "",
    })
  }

  const cancelEditResource = () => {
    setEditingResourceId(null)
    setResourceEditForm(emptyResourceForm)
  }

  const handleUpdateResource = async (e) => {
    e.preventDefault()
    setError("")
    try {
      await updateResource(editingResourceId, {
        resource_name: resourceEditForm.resource_name,
        resource_category_id: Number(resourceEditForm.resource_category_id),
        code: resourceEditForm.code || null,
        description: resourceEditForm.description || null,
        max_bookings_per_day: resourceEditForm.max_bookings_per_day ? Number(resourceEditForm.max_bookings_per_day) : null,
        booking_buffer_minutes: resourceEditForm.booking_buffer_minutes ? Number(resourceEditForm.booking_buffer_minutes) : null,
      })
      cancelEditResource()
      loadResources()
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to update resource"))
    }
  }

  const handleActivate = async (resourceId) => {
    setError("")
    try {
      await activateResource(resourceId)
      loadResources()
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to activate resource"))
    }
  }

  const handleSuspend = async (resourceId) => {
    setError("")
    try {
      await suspendResource(resourceId)
      loadResources()
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to suspend resource"))
    }
  }

  const openWorkingHours = async (resourceId) => {
    setWorkingHoursResourceId(resourceId)
    try {
      const response = await getResourceWorkingHours(resourceId)
      const byWeekday = {}
      response.data.forEach((row) => {
        byWeekday[row.weekday] = row
      })
      setWorkingHours(byWeekday)
    } catch {
      setError("Failed to load working hours")
    }
  }

  const handleWorkingHourChange = (weekday, field, value) => {
    setWorkingHours((prev) => ({
      ...prev,
      [weekday]: { ...(prev[weekday] || { weekday }), [field]: value },
    }))
  }

  const saveWorkingHours = async () => {
    const hours = Object.values(workingHours).map((row) => ({
      weekday: row.weekday,
      opening_time: row.is_closed ? null : (row.opening_time || null),
      closing_time: row.is_closed ? null : (row.closing_time || null),
      is_closed: !!row.is_closed,
      break_start_time: row.is_closed ? null : (row.break_start_time || null),
      break_end_time: row.is_closed ? null : (row.break_end_time || null),
    }))
    try {
      await upsertResourceWorkingHours(workingHoursResourceId, hours)
      setMessage("Working hours saved.")
    } catch {
      setError("Failed to save working hours")
    }
  }

  const handleInvite = async (resourceId) => {
    const email = inviteEmail[resourceId]
    if (!email) {
      return
    }
    setError("")
    setMessage("")
    try {
      await inviteResourceUser(businessId, resourceId, email)
      setInviteEmail({ ...inviteEmail, [resourceId]: "" })
      setMessage("Invitation sent.")
      loadResourceUsers()
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to invite resource user"))
    }
  }

  const handleResend = async (memberId) => {
    setError("")
    try {
      await resendResourceInvite(memberId)
      setMessage("Invitation resent.")
    } catch {
      setError("Failed to resend invitation")
    }
  }

  const handleDeactivate = async (memberId) => {
    setError("")
    try {
      await deactivateResourceUser(memberId)
      loadResourceUsers()
    } catch {
      setError("Failed to deactivate resource user")
    }
  }

  if (!businessId) {
    return <p>You do not have an active business.</p>
  }

  if (!isOwner && !isBranchManager && !isHr) {
    return <p>You are not authorized to manage resources.</p>
  }

  return (
    <div>
      <h1>Resources</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      {!isHr && (
        <>
          <h2>Resource Categories</h2>
          <ul>
            {categories.map((c) => (
              <li key={c.id}>
                {editingCategoryId === c.id ? (
                  <form onSubmit={handleUpdateCategory} style={{ display: "inline" }}>
                    <input
                      value={categoryEditForm.category_name}
                      onChange={(e) => setCategoryEditForm({ ...categoryEditForm, category_name: e.target.value })}
                      required
                    />
                    {" "}
                    <input
                      placeholder="Description"
                      value={categoryEditForm.description}
                      onChange={(e) => setCategoryEditForm({ ...categoryEditForm, description: e.target.value })}
                    />
                    {" "}
                    <button type="submit">Save</button>
                    {" "}
                    <button type="button" onClick={cancelEditCategory}>Cancel</button>
                  </form>
                ) : (
                  <>
                    {c.category_name}{c.description ? ` — ${c.description}` : ""}
                    {isOwner && (
                      <>
                        {" "}
                        <button onClick={() => startEditCategory(c)}>Edit</button>
                      </>
                    )}
                  </>
                )}
              </li>
            ))}
          </ul>

          {isOwner && (
            <form onSubmit={handleCreateCategory}>
              <input
                placeholder="Category Name"
                value={categoryForm.category_name}
                onChange={(e) => setCategoryForm({ ...categoryForm, category_name: e.target.value })}
                required
              />
              {" "}
              <input
                placeholder="Description"
                value={categoryForm.description}
                onChange={(e) => setCategoryForm({ ...categoryForm, description: e.target.value })}
              />
              {" "}
              <button type="submit">Add Category</button>
            </form>
          )}

          {isOwner && (
            <>
              <h2>Branch</h2>
              <select
                value={selectedBranchId || ""}
                onChange={(e) => setSelectedBranchId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Select Branch</option>
                {branches.map((b) => (
                  <option key={b.id} value={b.id}>{b.branch_name}</option>
                ))}
              </select>
            </>
          )}
        </>
      )}

      <h2>{isHr ? "Resources (read-only)" : "Resources"}</h2>
      <ul>
        {displayedResources.map((r) => (
          <li key={r.id} style={{ marginBottom: "10px" }}>
            {editingResourceId === r.id ? (
              <form onSubmit={handleUpdateResource}>
                <input
                  value={resourceEditForm.resource_name}
                  onChange={(e) => setResourceEditForm({ ...resourceEditForm, resource_name: e.target.value })}
                  required
                />
                <br />
                <select
                  value={resourceEditForm.resource_category_id}
                  onChange={(e) => setResourceEditForm({ ...resourceEditForm, resource_category_id: e.target.value })}
                  required
                >
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>{c.category_name}</option>
                  ))}
                </select>
                <br />
                <input
                  placeholder="Code (optional)"
                  value={resourceEditForm.code}
                  onChange={(e) => setResourceEditForm({ ...resourceEditForm, code: e.target.value })}
                />
                <br />
                <input
                  placeholder="Description (optional)"
                  value={resourceEditForm.description}
                  onChange={(e) => setResourceEditForm({ ...resourceEditForm, description: e.target.value })}
                />
                <br />
                <input
                  type="number"
                  min="1"
                  placeholder="Max Bookings Per Day"
                  value={resourceEditForm.max_bookings_per_day}
                  onChange={(e) => setResourceEditForm({ ...resourceEditForm, max_bookings_per_day: e.target.value })}
                />
                <br />
                <input
                  type="number"
                  min="0"
                  placeholder="Booking Buffer (minutes)"
                  value={resourceEditForm.booking_buffer_minutes}
                  onChange={(e) => setResourceEditForm({ ...resourceEditForm, booking_buffer_minutes: e.target.value })}
                />
                <br />
                {" login required: "}{r.requires_login ? "Yes" : "No"}
                {" (not editable)"}
                <br />
                <button type="submit">Save</button>
                {" "}
                <button type="button" onClick={cancelEditResource}>Cancel</button>
              </form>
            ) : (
              <>
                <strong>{r.resource_name}</strong>
                {" — status: "}{r.status}
                {" — login required: "}{r.requires_login ? "Yes" : "No"}
                {r.requires_login && (r.linked_user_id ? " (linked)" : " (not linked)")}
                {" "}
                {!isHr && (
                  <button onClick={() => startEditResource(r)}>Edit</button>
                )}
                {" "}
                {!isHr && r.status !== "Active" && (
                  <button onClick={() => handleActivate(r.id)}>Activate</button>
                )}
                {" "}
                {!isHr && r.status === "Active" && (
                  <button onClick={() => handleSuspend(r.id)}>Suspend</button>
                )}
                {" "}
                {!isHr && (
                  <button onClick={() => openWorkingHours(r.id)}>Working Hours</button>
                )}
                {" "}
                {r.requires_login && !r.linked_user_id && (
                  <>
                    <input
                      type="email"
                      placeholder="Resource user email"
                      value={inviteEmail[r.id] || ""}
                      onChange={(e) => setInviteEmail({ ...inviteEmail, [r.id]: e.target.value })}
                    />
                    <button onClick={() => handleInvite(r.id)}>Invite Login</button>
                  </>
                )}
              </>
            )}
          </li>
        ))}
      </ul>

      {!isHr && (
        <>
          <h2>Create Resource</h2>
          <form onSubmit={handleCreateResource}>
            <input
              placeholder="Resource Name"
              value={resourceForm.resource_name}
              onChange={(e) => setResourceForm({ ...resourceForm, resource_name: e.target.value })}
              required
            />
            <br />
            <select
              value={resourceForm.resource_category_id}
              onChange={(e) => setResourceForm({ ...resourceForm, resource_category_id: e.target.value })}
              required
            >
              <option value="">Select Category</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.category_name}</option>
              ))}
            </select>
            <br />
            <input
              placeholder="Code (optional)"
              value={resourceForm.code}
              onChange={(e) => setResourceForm({ ...resourceForm, code: e.target.value })}
            />
            <br />
            <label>
              <input
                type="checkbox"
                checked={resourceForm.requires_login}
                onChange={(e) => setResourceForm({ ...resourceForm, requires_login: e.target.checked })}
              />
              {" Requires Login"}
            </label>
            <br />
            <input
              type="number"
              min="1"
              placeholder="Max Bookings Per Day"
              value={resourceForm.max_bookings_per_day}
              onChange={(e) => setResourceForm({ ...resourceForm, max_bookings_per_day: e.target.value })}
            />
            <br />
            <input
              type="number"
              min="0"
              placeholder="Booking Buffer (minutes)"
              value={resourceForm.booking_buffer_minutes}
              onChange={(e) => setResourceForm({ ...resourceForm, booking_buffer_minutes: e.target.value })}
            />
            <br />
            <button type="submit">Create Resource</button>
          </form>
        </>
      )}

      {workingHoursResourceId && !isHr && (
        <div>
          <h2>Working Hours — Resource #{workingHoursResourceId}</h2>
          {WEEKDAYS.map((label, weekday) => {
            const row = workingHours[weekday] || { weekday, opening_time: "", closing_time: "", is_closed: false, break_start_time: "", break_end_time: "" }
            return (
              <div key={weekday}>
                <span style={{ display: "inline-block", width: "100px" }}>{label}</span>
                <label>
                  <input
                    type="checkbox"
                    checked={!!row.is_closed}
                    onChange={(e) => handleWorkingHourChange(weekday, "is_closed", e.target.checked)}
                  />
                  {" Closed"}
                </label>
                {" "}
                {!row.is_closed && (
                  <>
                    <input
                      type="time"
                      value={row.opening_time || ""}
                      onChange={(e) => handleWorkingHourChange(weekday, "opening_time", e.target.value)}
                    />
                    {" - "}
                    <input
                      type="time"
                      value={row.closing_time || ""}
                      onChange={(e) => handleWorkingHourChange(weekday, "closing_time", e.target.value)}
                    />
                    {" break: "}
                    <input
                      type="time"
                      value={row.break_start_time || ""}
                      onChange={(e) => handleWorkingHourChange(weekday, "break_start_time", e.target.value)}
                    />
                    {" - "}
                    <input
                      type="time"
                      value={row.break_end_time || ""}
                      onChange={(e) => handleWorkingHourChange(weekday, "break_end_time", e.target.value)}
                    />
                  </>
                )}
              </div>
            )
          })}
          <button onClick={saveWorkingHours}>Save Working Hours</button>
        </div>
      )}

      <h2>Resource Users</h2>
      <ul>
        {resourceUsers.map((m) => (
          <li key={m.id}>
            <strong>{m.email}</strong>
            {" — status: "}{m.status}
            {" "}
            {m.status === "Pending" && (
              <button onClick={() => handleResend(m.id)}>Resend Invite</button>
            )}
            {" "}
            {m.status !== "Inactive" && (
              <button onClick={() => handleDeactivate(m.id)}>Deactivate</button>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
