import React, { useContext, useEffect, useState } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import {
  listBranchesForBusiness,
  createBranch,
  activateBranch,
  deactivateBranch,
  getWorkingHours,
  upsertWorkingHours,
  listCountries,
} from "../api/api"

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

const emptyForm = {
  branch_name: "",
  address: "",
  city: "",
  state: "",
  postal_code: "",
  country_id: "",
  phone: "",
  email: "",
}

export default function BranchManagement() {
  const { user } = useContext(AuthContext)
  const businessId = user?.business?.id

  const [branches, setBranches] = useState([])
  const [countries, setCountries] = useState([])
  const [error, setError] = useState("")
  const [form, setForm] = useState(emptyForm)

  const [selectedBranchId, setSelectedBranchId] = useState(null)
  const [workingHours, setWorkingHours] = useState({})

  const loadBranches = async () => {
    try {
      const response = await listBranchesForBusiness(businessId)
      setBranches(response.data)
    } catch {
      setError("Failed to load branches")
    }
  }

  useEffect(() => {
    if (!businessId) {
      return
    }
    loadBranches()
    listCountries().then((response) => setCountries(response.data)).catch(() => {})
  }, [businessId])

  const handleCreate = async (e) => {
    e.preventDefault()
    try {
      await createBranch(businessId, {
        ...form,
        country_id: Number(form.country_id),
      })
      setForm(emptyForm)
      loadBranches()
    } catch {
      setError("Failed to create branch")
    }
  }

  const handleActivate = async (branchId) => {
    try {
      await activateBranch(branchId)
      loadBranches()
    } catch {
      setError("Failed to activate branch")
    }
  }

  const handleDeactivate = async (branchId) => {
    try {
      await deactivateBranch(branchId)
      loadBranches()
    } catch {
      setError("Failed to deactivate branch")
    }
  }

  const openWorkingHours = async (branchId) => {
    setSelectedBranchId(branchId)
    try {
      const response = await getWorkingHours(branchId)
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
    }))

    try {
      await upsertWorkingHours(selectedBranchId, hours)
    } catch {
      setError("Failed to save working hours")
    }
  }

  if (!businessId) {
    return <p>You do not have an active business.</p>
  }

  return (
    <div>
      <h1>My Branches</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <ul>
        {branches.map((branch) => (
          <li key={branch.id} style={{ marginBottom: "8px" }}>
            <strong>{branch.branch_name}</strong>
            {" — approval: "}{branch.approval_status}
            {", active: "}{branch.is_active ? "Yes" : "No"}
            {" "}
            {branch.approval_status === "Approved" && !branch.is_active && (
              <button onClick={() => handleActivate(branch.id)}>Activate</button>
            )}
            {branch.is_active && (
              <button onClick={() => handleDeactivate(branch.id)}>Deactivate</button>
            )}
            {" "}
            <button onClick={() => openWorkingHours(branch.id)}>Working Hours</button>
          </li>
        ))}
      </ul>

      <h2>Create Branch</h2>
      <form onSubmit={handleCreate}>
        <input
          placeholder="Branch Name"
          value={form.branch_name}
          onChange={(e) => setForm({ ...form, branch_name: e.target.value })}
          required
        />
        <br />
        <input
          placeholder="Address"
          value={form.address}
          onChange={(e) => setForm({ ...form, address: e.target.value })}
        />
        <br />
        <input
          placeholder="City"
          value={form.city}
          onChange={(e) => setForm({ ...form, city: e.target.value })}
        />
        <br />
        <input
          placeholder="State"
          value={form.state}
          onChange={(e) => setForm({ ...form, state: e.target.value })}
        />
        <br />
        <input
          placeholder="Postal Code"
          value={form.postal_code}
          onChange={(e) => setForm({ ...form, postal_code: e.target.value })}
        />
        <br />
        <select
          value={form.country_id}
          onChange={(e) => setForm({ ...form, country_id: e.target.value })}
          required
        >
          <option value="">Select Country</option>
          {countries.map((country) => (
            <option key={country.id} value={country.id}>{country.name}</option>
          ))}
        </select>
        <br />
        <input
          placeholder="Phone"
          value={form.phone}
          onChange={(e) => setForm({ ...form, phone: e.target.value })}
        />
        <br />
        <input
          placeholder="Email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
        <br />
        <button type="submit">Create Branch</button>
      </form>

      {selectedBranchId && (
        <div>
          <h2>Working Hours — Branch #{selectedBranchId}</h2>
          {WEEKDAYS.map((label, weekday) => {
            const row = workingHours[weekday] || { weekday, opening_time: "", closing_time: "", is_closed: false }
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
                  </>
                )}
              </div>
            )
          })}
          <button onClick={saveWorkingHours}>Save Working Hours</button>
        </div>
      )}
    </div>
  )
}
