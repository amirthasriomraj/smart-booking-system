import React, { useEffect, useState, useCallback } from "react"
import {
  listBusinesses,
  getPlatformFeeSettings,
  setDefaultPlatformFee,
  setBusinessFeeOverride,
  removeBusinessFeeOverride,
} from "../api/api"
import { extractErrorMessage } from "../api/errors"

// Platform Fee configuration (ID-051, rule 17-19; Platform Admin only).
// This only manages the *current* configured rate — a booking's actual fee
// is snapshotted server-side at its first financial transaction and never
// re-read from here afterward, so changing a rate here never retroactively
// changes an already-snapshotted booking.
export default function PlatformFeeManagement() {
  const [settings, setSettings] = useState(null)
  const [businesses, setBusinesses] = useState([])
  const [defaultFeeInput, setDefaultFeeInput] = useState("")
  const [defaultReason, setDefaultReason] = useState("")
  const [overrideBusinessId, setOverrideBusinessId] = useState("")
  const [overrideFeeInput, setOverrideFeeInput] = useState("")
  const [overrideReason, setOverrideReason] = useState("")
  const [removeReasons, setRemoveReasons] = useState({})

  const [error, setError] = useState("")
  const [message, setMessage] = useState("")

  const load = useCallback(() => {
    getPlatformFeeSettings()
      .then((r) => {
        setSettings(r.data)
        setDefaultFeeInput(r.data.default_fee_percentage)
      })
      .catch(() => setError("Failed to load platform fee settings"))
  }, [])

  useEffect(() => {
    load()
    listBusinesses("Active").then((r) => setBusinesses(r.data.items)).catch(() => {})
  }, [load])

  const handleSetDefault = async (e) => {
    e.preventDefault()
    setError("")
    try {
      const response = await setDefaultPlatformFee({
        fee_percentage: defaultFeeInput,
        reason: defaultReason || undefined,
      })
      setSettings(response.data)
      setDefaultReason("")
      setMessage("Default platform fee updated.")
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to update default fee"))
    }
  }

  const handleSetOverride = async (e) => {
    e.preventDefault()
    setError("")
    if (!overrideBusinessId) {
      setError("Select a business")
      return
    }
    try {
      const response = await setBusinessFeeOverride(Number(overrideBusinessId), {
        fee_percentage: overrideFeeInput,
        reason: overrideReason,
      })
      setSettings(response.data)
      setOverrideBusinessId("")
      setOverrideFeeInput("")
      setOverrideReason("")
      setMessage("Business fee override set.")
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to set business fee override"))
    }
  }

  const handleRemoveOverride = async (businessId) => {
    setError("")
    const reason = removeReasons[businessId]
    if (!reason) {
      setError("A reason is required to remove a business fee override")
      return
    }
    try {
      const response = await removeBusinessFeeOverride(businessId, { reason })
      setSettings(response.data)
      setMessage("Business fee override removed — that business now uses the platform default.")
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to remove business fee override"))
    }
  }

  if (!settings) {
    return (
      <div>
        <h1>Platform Fee Configuration</h1>
        {error && <p style={{ color: "red" }}>{error}</p>}
        {!error && <p>Loading…</p>}
      </div>
    )
  }

  return (
    <div>
      <h1>Platform Fee Configuration</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      <h2>Platform Default Fee</h2>
      <p>Current default: {settings.default_fee_percentage}%</p>
      <form onSubmit={handleSetDefault}>
        <input
          type="number" min="0" max="100" step="0.01"
          value={defaultFeeInput}
          onChange={(e) => setDefaultFeeInput(e.target.value)}
          required
        />
        {" %  "}
        <input
          placeholder="Reason (optional)"
          value={defaultReason}
          onChange={(e) => setDefaultReason(e.target.value)}
          style={{ width: "220px" }}
        />
        {" "}
        <button type="submit">Update Default</button>
      </form>

      <h2>Business Overrides</h2>
      <ul>
        {settings.overrides.map((o) => (
          <li key={o.business_id} style={{ marginBottom: "8px" }}>
            {o.business_name} — {o.fee_percentage}%
            {" "}
            <input
              placeholder="Reason to remove"
              value={removeReasons[o.business_id] || ""}
              onChange={(e) => setRemoveReasons({ ...removeReasons, [o.business_id]: e.target.value })}
              style={{ width: "180px" }}
            />
            {" "}
            <button onClick={() => handleRemoveOverride(o.business_id)}>Remove Override</button>
          </li>
        ))}
        {settings.overrides.length === 0 && <li>No business-specific overrides — every business uses the default.</li>}
      </ul>

      <h3>Set / Update a Business Override</h3>
      <form onSubmit={handleSetOverride}>
        <select value={overrideBusinessId} onChange={(e) => setOverrideBusinessId(e.target.value)} required>
          <option value="">Select Business</option>
          {businesses.map((b) => (
            <option key={b.id} value={b.id}>{b.business_name}</option>
          ))}
        </select>
        {" "}
        <input
          type="number" min="0" max="100" step="0.01" placeholder="Fee %"
          value={overrideFeeInput}
          onChange={(e) => setOverrideFeeInput(e.target.value)}
          required
        />
        {" "}
        <input
          placeholder="Reason (required)"
          value={overrideReason}
          onChange={(e) => setOverrideReason(e.target.value)}
          required
          style={{ width: "220px" }}
        />
        {" "}
        <button type="submit">Set Override</button>
      </form>
    </div>
  )
}
