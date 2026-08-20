import React, { useContext, useEffect, useState, useCallback } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import {
  listStaffForBusiness,
  inviteStaffMember,
  resendStaffInvite,
  transferBranchManager,
  deactivateStaffMember,
  listBranchesForBusiness,
} from "../api/api"

const emptyForm = {
  email: "",
  role_code: "BRANCH_MANAGER",
  branch_id: "",
}

export default function StaffManagement() {
  const { user } = useContext(AuthContext)
  const businessId = user?.business?.id

  const [staff, setStaff] = useState([])
  const [branches, setBranches] = useState([])
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [form, setForm] = useState(emptyForm)
  const [transferTarget, setTransferTarget] = useState({})

  const loadStaff = useCallback(() => {
    listStaffForBusiness(businessId)
      .then((response) => setStaff(response.data))
      .catch(() => setError("Failed to load staff"))
  }, [businessId])

  useEffect(() => {
    if (!businessId) {
      return
    }
    loadStaff()
    listBranchesForBusiness(businessId)
      .then((response) => setBranches(response.data.filter((b) => b.approval_status === "Approved")))
      .catch(() => {})
  }, [businessId, loadStaff])

  const handleInvite = async (e) => {
    e.preventDefault()
    setError("")
    setMessage("")
    try {
      await inviteStaffMember(businessId, {
        email: form.email,
        role_code: form.role_code,
        branch_id: form.role_code === "BRANCH_MANAGER" ? Number(form.branch_id) : null,
      })
      setForm(emptyForm)
      setMessage("Invitation sent.")
      loadStaff()
    } catch (err) {
      setError(err.response?.data?.error?.message || "Failed to send invitation")
    }
  }

  const handleResend = async (memberId) => {
    setError("")
    setMessage("")
    try {
      await resendStaffInvite(businessId, memberId)
      setMessage("Invitation resent.")
    } catch {
      setError("Failed to resend invitation")
    }
  }

  const handleTransfer = async (memberId) => {
    const branchId = transferTarget[memberId]
    if (!branchId) {
      return
    }
    setError("")
    try {
      await transferBranchManager(memberId, Number(branchId))
      loadStaff()
    } catch {
      setError("Failed to transfer branch")
    }
  }

  const handleDeactivate = async (memberId) => {
    setError("")
    try {
      await deactivateStaffMember(memberId)
      loadStaff()
    } catch {
      setError("Failed to deactivate member")
    }
  }

  if (!businessId) {
    return <p>You do not have an active business.</p>
  }

  return (
    <div>
      <h1>Staff</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      <ul>
        {staff.map((member) => (
          <li key={member.id} style={{ marginBottom: "8px" }}>
            <strong>{member.email}</strong>
            {" — "}{member.role_code}
            {" — status: "}{member.status}
            {member.current_branch_name && <>{" — branch: "}{member.current_branch_name}</>}
            {" "}
            {member.status === "Pending" && (
              <button onClick={() => handleResend(member.id)}>Resend Invite</button>
            )}
            {" "}
            {member.status === "Active" && member.role_code === "BRANCH_MANAGER" && (
              <>
                <select
                  value={transferTarget[member.id] || ""}
                  onChange={(e) => setTransferTarget({ ...transferTarget, [member.id]: e.target.value })}
                >
                  <option value="">Transfer to...</option>
                  {branches
                    .filter((b) => b.id !== member.current_branch_id)
                    .map((b) => (
                      <option key={b.id} value={b.id}>{b.branch_name}</option>
                    ))}
                </select>
                <button onClick={() => handleTransfer(member.id)}>Transfer</button>
              </>
            )}
            {" "}
            {member.status !== "Inactive" && (
              <button onClick={() => handleDeactivate(member.id)}>Deactivate</button>
            )}
          </li>
        ))}
      </ul>

      <h2>Invite Staff</h2>
      <form onSubmit={handleInvite}>
        <input
          type="email"
          placeholder="Email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          required
        />
        <br />
        <select
          value={form.role_code}
          onChange={(e) => setForm({ ...form, role_code: e.target.value, branch_id: "" })}
        >
          <option value="BRANCH_MANAGER">Branch Manager</option>
          <option value="HR_USER">HR User</option>
        </select>
        <br />
        {form.role_code === "BRANCH_MANAGER" && (
          <>
            <select
              value={form.branch_id}
              onChange={(e) => setForm({ ...form, branch_id: e.target.value })}
              required
            >
              <option value="">Select Branch</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>{b.branch_name}</option>
              ))}
            </select>
            <br />
          </>
        )}
        <button type="submit">Send Invitation</button>
      </form>
    </div>
  )
}
