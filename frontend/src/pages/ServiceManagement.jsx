import React, { useContext, useEffect, useState, useCallback } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import {
  listBranchesForBusiness,
  listResourceCategories,
  listServiceTemplates,
  createServiceTemplate,
  activateServiceTemplate,
  deactivateServiceTemplate,
  listBranchServicesForBranch,
  listBranchServicesForBusiness,
  updateBranchService,
  submitBranchServiceOverride,
  listServiceApprovals,
  decideServiceApproval,
} from "../api/api"

const emptyTemplateForm = {
  name: "",
  description: "",
  default_duration: "",
  default_price: "",
  default_buffer_minutes: "",
  default_resource_category_ids: [],
}

const emptyConfigForm = { duration: "", price: "", resource_category_ids: [] }

function selectedIds(event) {
  return Array.from(event.target.selectedOptions, (option) => Number(option.value))
}

export default function ServiceManagement() {
  const { user } = useContext(AuthContext)
  const businessId = user?.business?.id
  const roleCode = user?.business?.role_code
  const isOwner = roleCode === "BUSINESS_OWNER"
  const isBranchManager = roleCode === "BRANCH_MANAGER"

  // Branch Manager is always scoped to their own currently-assigned branch;
  // this is derived directly from auth context, not stored/synced as state
  // (same pattern as ResourceManagement.jsx).
  const effectiveBranchId = isBranchManager ? (user?.business?.branch_id ?? null) : null

  const [branches, setBranches] = useState([])
  const [selectedBranchId, setSelectedBranchId] = useState(null)
  const [categories, setCategories] = useState([])
  const [templates, setTemplates] = useState([])
  const [branchServices, setBranchServices] = useState([])
  const [approvals, setApprovals] = useState([])

  const [templateForm, setTemplateForm] = useState(emptyTemplateForm)

  const [editingServiceId, setEditingServiceId] = useState(null)
  const [editForm, setEditForm] = useState(emptyConfigForm)

  const [overridingServiceId, setOverridingServiceId] = useState(null)
  const [overrideForm, setOverrideForm] = useState(emptyConfigForm)

  const [decisionComments, setDecisionComments] = useState({})

  const [error, setError] = useState("")
  const [message, setMessage] = useState("")

  useEffect(() => {
    if (!businessId) {
      return
    }
    listResourceCategories(businessId).then((r) => setCategories(r.data)).catch(() => {})
    listServiceTemplates(businessId).then((r) => setTemplates(r.data)).catch(() => setError("Failed to load service templates"))
    if (isOwner) {
      listBranchesForBusiness(businessId)
        .then((r) => setBranches(r.data.filter((b) => b.approval_status === "Approved")))
        .catch(() => {})
    }
  }, [businessId, isOwner])

  const loadBranchServices = useCallback(() => {
    if (isOwner) {
      if (selectedBranchId) {
        listBranchServicesForBranch(selectedBranchId).then((r) => setBranchServices(r.data)).catch(() => setError("Failed to load services"))
      } else {
        listBranchServicesForBusiness(businessId).then((r) => setBranchServices(r.data)).catch(() => setError("Failed to load services"))
      }
      return
    }
    if (effectiveBranchId) {
      listBranchServicesForBranch(effectiveBranchId).then((r) => setBranchServices(r.data)).catch(() => setError("Failed to load services"))
    }
  }, [businessId, isOwner, selectedBranchId, effectiveBranchId])

  const loadApprovals = useCallback(() => {
    if (!businessId) {
      return
    }
    listServiceApprovals(businessId).then((r) => setApprovals(r.data)).catch(() => {})
  }, [businessId])

  useEffect(() => {
    loadBranchServices()
    loadApprovals()
  }, [loadBranchServices, loadApprovals])

  const categoryName = (id) => categories.find((c) => c.id === id)?.category_name || id
  const categoryNames = (ids) => (ids && ids.length > 0 ? ids.map(categoryName).join(", ") : "none")
  const templateName = (id) => templates.find((t) => t.id === id)?.name || `Service #${id}`
  const branchName = (id) => branches.find((b) => b.id === id)?.branch_name || `Branch #${id}`

  // Only the fields that actually differ between what's live today and what
  // was proposed, rendered as old -> new, rather than dumping every proposed
  // field regardless of whether it changed.
  const configDiff = (previous, proposed) => {
    const diffs = []
    if (String(previous.duration) !== String(proposed.duration)) {
      diffs.push(`duration: ${previous.duration} min → ${proposed.duration} min`)
    }
    if (String(previous.price) !== String(proposed.price)) {
      diffs.push(`price: ${previous.price} → ${proposed.price}`)
    }
    const prevCats = [...(previous.resource_category_ids || [])].sort().join(",")
    const propCats = [...(proposed.resource_category_ids || [])].sort().join(",")
    if (prevCats !== propCats) {
      diffs.push(`categories: ${categoryNames(previous.resource_category_ids)} → ${categoryNames(proposed.resource_category_ids)}`)
    }
    return diffs
  }

  const handleCreateTemplate = async (e) => {
    e.preventDefault()
    setError("")
    try {
      await createServiceTemplate(businessId, {
        name: templateForm.name,
        description: templateForm.description || null,
        default_duration: Number(templateForm.default_duration),
        default_price: templateForm.default_price,
        default_buffer_minutes: templateForm.default_buffer_minutes ? Number(templateForm.default_buffer_minutes) : null,
        default_resource_category_ids: templateForm.default_resource_category_ids,
      })
      setTemplateForm(emptyTemplateForm)
      listServiceTemplates(businessId).then((r) => setTemplates(r.data))
      loadBranchServices()
      setMessage("Service Template created — inherited by every branch.")
    } catch (err) {
      setError(err.response?.data?.error?.message || "Failed to create Service Template")
    }
  }

  const handleToggleTemplateStatus = async (template) => {
    setError("")
    try {
      if (template.status === "Active") {
        await deactivateServiceTemplate(template.id)
      } else {
        await activateServiceTemplate(template.id)
      }
      listServiceTemplates(businessId).then((r) => setTemplates(r.data))
    } catch {
      setError("Failed to update Service Template status")
    }
  }

  const startEdit = (branchService) => {
    setEditingServiceId(branchService.id)
    setEditForm({
      duration: branchService.duration,
      price: branchService.price,
      resource_category_ids: branchService.resource_category_ids,
    })
  }

  const cancelEdit = () => {
    setEditingServiceId(null)
    setEditForm(emptyConfigForm)
  }

  const handleDirectUpdate = async (e) => {
    e.preventDefault()
    setError("")
    try {
      await updateBranchService(editingServiceId, {
        duration: Number(editForm.duration),
        price: editForm.price,
        resource_category_ids: editForm.resource_category_ids,
      })
      cancelEdit()
      loadBranchServices()
      setMessage("Service updated.")
    } catch (err) {
      setError(err.response?.data?.error?.message || "Failed to update service")
    }
  }

  const startOverride = (branchService) => {
    setOverridingServiceId(branchService.id)
    setOverrideForm({
      duration: branchService.duration,
      price: branchService.price,
      resource_category_ids: branchService.resource_category_ids,
    })
  }

  const cancelOverride = () => {
    setOverridingServiceId(null)
    setOverrideForm(emptyConfigForm)
  }

  const handleSubmitOverride = async (e) => {
    e.preventDefault()
    setError("")
    try {
      await submitBranchServiceOverride(overridingServiceId, {
        duration: Number(overrideForm.duration),
        price: overrideForm.price,
        resource_category_ids: overrideForm.resource_category_ids,
      })
      cancelOverride()
      loadBranchServices()
      loadApprovals()
      setMessage("Override submitted — pending Business Owner approval.")
    } catch (err) {
      setError(err.response?.data?.error?.message || "Failed to submit override")
    }
  }

  const handleDecision = async (approvalId, decision) => {
    setError("")
    try {
      await decideServiceApproval(approvalId, decision, decisionComments[approvalId] || null)
      loadApprovals()
      loadBranchServices()
      setMessage(`Override ${decision.toLowerCase()}.`)
    } catch (err) {
      setError(err.response?.data?.error?.message || "Failed to decide on override")
    }
  }

  if (!businessId) {
    return <p>You do not have an active business.</p>
  }

  if (!isOwner && !isBranchManager) {
    return <p>You are not authorized to manage services.</p>
  }

  const pendingApprovals = approvals.filter((a) => a.decision === "Pending")
  const decidedApprovals = approvals.filter((a) => a.decision !== "Pending")

  return (
    <div>
      <h1>Services</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      {isOwner && (
        <>
          <h2>Service Templates</h2>
          <ul>
            {templates.map((t) => (
              <li key={t.id}>
                <strong>{t.name}</strong>
                {" — "}{t.default_duration} min, {t.default_price}
                {" — status: "}{t.status}
                {t.default_resource_category_ids.length > 0 && (
                  <> {" — categories: "}{t.default_resource_category_ids.map(categoryName).join(", ")}</>
                )}
                {" "}
                <button onClick={() => handleToggleTemplateStatus(t)}>
                  {t.status === "Active" ? "Deactivate" : "Activate"}
                </button>
              </li>
            ))}
          </ul>

          <h3>Create Service Template</h3>
          <p>Automatically inherited by every branch (existing and future).</p>
          <form onSubmit={handleCreateTemplate}>
            <input
              placeholder="Service Name"
              value={templateForm.name}
              onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
              required
            />
            <br />
            <input
              placeholder="Description (optional)"
              value={templateForm.description}
              onChange={(e) => setTemplateForm({ ...templateForm, description: e.target.value })}
            />
            <br />
            <input
              type="number"
              min="1"
              placeholder="Default Duration (minutes)"
              value={templateForm.default_duration}
              onChange={(e) => setTemplateForm({ ...templateForm, default_duration: e.target.value })}
              required
            />
            <br />
            <input
              type="number"
              min="0"
              step="0.01"
              placeholder="Default Price"
              value={templateForm.default_price}
              onChange={(e) => setTemplateForm({ ...templateForm, default_price: e.target.value })}
              required
            />
            <br />
            <input
              type="number"
              min="0"
              placeholder="Default Buffer (minutes, optional)"
              value={templateForm.default_buffer_minutes}
              onChange={(e) => setTemplateForm({ ...templateForm, default_buffer_minutes: e.target.value })}
            />
            <br />
            <label>Default Resource Categories:</label>
            <br />
            <select
              multiple
              value={templateForm.default_resource_category_ids}
              onChange={(e) => setTemplateForm({ ...templateForm, default_resource_category_ids: selectedIds(e) })}
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.category_name}</option>
              ))}
            </select>
            <br />
            <button type="submit">Create Service Template</button>
          </form>

          <h2>Branch Services</h2>
          <select
            value={selectedBranchId || ""}
            onChange={(e) => setSelectedBranchId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">All Branches</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>{b.branch_name}</option>
            ))}
          </select>
        </>
      )}

      {isBranchManager && <h2>My Branch's Services</h2>}

      <ul>
        {branchServices.map((bs) => (
          <li key={bs.id} style={{ marginBottom: "10px" }}>
            {editingServiceId === bs.id ? (
              <form onSubmit={handleDirectUpdate} style={{ display: "inline" }}>
                <input
                  type="number"
                  min="1"
                  value={editForm.duration}
                  onChange={(e) => setEditForm({ ...editForm, duration: e.target.value })}
                  required
                />
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={editForm.price}
                  onChange={(e) => setEditForm({ ...editForm, price: e.target.value })}
                  required
                />
                <select
                  multiple
                  value={editForm.resource_category_ids}
                  onChange={(e) => setEditForm({ ...editForm, resource_category_ids: selectedIds(e) })}
                >
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>{c.category_name}</option>
                  ))}
                </select>
                <button type="submit">Save</button>
                {" "}
                <button type="button" onClick={cancelEdit}>Cancel</button>
              </form>
            ) : overridingServiceId === bs.id ? (
              <form onSubmit={handleSubmitOverride} style={{ display: "inline" }}>
                <input
                  type="number"
                  min="1"
                  value={overrideForm.duration}
                  onChange={(e) => setOverrideForm({ ...overrideForm, duration: e.target.value })}
                  required
                />
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={overrideForm.price}
                  onChange={(e) => setOverrideForm({ ...overrideForm, price: e.target.value })}
                  required
                />
                <select
                  multiple
                  value={overrideForm.resource_category_ids}
                  onChange={(e) => setOverrideForm({ ...overrideForm, resource_category_ids: selectedIds(e) })}
                >
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>{c.category_name}</option>
                  ))}
                </select>
                <button type="submit">Submit for Approval</button>
                {" "}
                <button type="button" onClick={cancelOverride}>Cancel</button>
              </form>
            ) : (
              <>
                {" duration: "}{bs.duration} min{" — price: "}{bs.price}
                {" — status: "}{bs.status}
                {bs.pending_approval && " (override pending approval)"}
                {bs.resource_category_ids.length > 0 && (
                  <> {" — categories: "}{bs.resource_category_ids.map(categoryName).join(", ")}</>
                )}
                {" "}
                {isOwner && (
                  <button onClick={() => startEdit(bs)}>Edit</button>
                )}
                {" "}
                {isBranchManager && !bs.pending_approval && (
                  <button onClick={() => startOverride(bs)}>Submit Override</button>
                )}
              </>
            )}
          </li>
        ))}
      </ul>

      <h2>Pending Approvals</h2>
      <ul>
        {pendingApprovals.map((a) => (
          <li key={a.id} style={{ marginBottom: "10px" }}>
            <strong>{templateName(a.service_template_id)}</strong>
            {isOwner && <> {" at "}{branchName(a.branch_id)}</>}
            {" — requested by "}{a.requested_by_email}
            <br />
            {configDiff(a.previous_configuration, a.proposed_configuration).join("; ") || "no field changes"}
            {isOwner && (
              <>
                <br />
                <input
                  placeholder="Comments (optional)"
                  value={decisionComments[a.id] || ""}
                  onChange={(e) => setDecisionComments({ ...decisionComments, [a.id]: e.target.value })}
                />
                {" "}
                <button onClick={() => handleDecision(a.id, "Approved")}>Approve</button>
                {" "}
                <button onClick={() => handleDecision(a.id, "Rejected")}>Reject</button>
              </>
            )}
          </li>
        ))}
        {pendingApprovals.length === 0 && <li>None.</li>}
      </ul>

      <h2>Approval History</h2>
      <ul>
        {decidedApprovals.map((a) => (
          <li key={a.id} style={{ marginBottom: "10px" }}>
            <strong>{templateName(a.service_template_id)}</strong>
            {isOwner && <> {" at "}{branchName(a.branch_id)}</>}
            {" — requested by "}{a.requested_by_email}
            {" — "}{a.decision}
            {a.approved_by_email && ` by ${a.approved_by_email}`}
            {a.comments && ` — "${a.comments}"`}
            <br />
            {configDiff(a.previous_configuration, a.proposed_configuration).join("; ") || "no field changes"}
          </li>
        ))}
      </ul>
    </div>
  )
}
