import React, { useContext, useEffect, useState, useCallback } from "react"
import { AuthContext } from "../auth/AuthContextOnly"
import { getBusinessProfile, updateBusinessProfile, listBusinessCategories, listCountries } from "../api/api"
import { extractErrorMessage } from "../api/errors"

// PRD §72 Business Management acceptance: "Business profile can be viewed" /
// "can be updated". Distinct from both business registration (Register.jsx)
// and the personal user profile (Profile.jsx).
export default function BusinessProfile() {
  const { user } = useContext(AuthContext)
  const businessId = user?.business?.id

  const [business, setBusiness] = useState(null)
  const [categories, setCategories] = useState([])
  const [countries, setCountries] = useState([])
  const [form, setForm] = useState({ business_name: "", business_category_id: "", country_id: "" })
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")

  const load = useCallback(() => {
    if (!businessId) {
      return
    }
    getBusinessProfile(businessId)
      .then((response) => {
        setBusiness(response.data)
        setForm({
          business_name: response.data.business_name,
          business_category_id: response.data.business_category_id,
          country_id: response.data.country_id,
        })
      })
      .catch(() => setError("Failed to load business profile"))
  }, [businessId])

  useEffect(() => {
    load()
    listBusinessCategories().then((r) => setCategories(r.data)).catch(() => {})
    listCountries().then((r) => setCountries(r.data)).catch(() => {})
  }, [load])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError("")
    setMessage("")
    try {
      await updateBusinessProfile(businessId, {
        business_name: form.business_name,
        business_category_id: Number(form.business_category_id),
        country_id: Number(form.country_id),
      })
      setMessage("Business profile updated.")
      load()
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to update business profile"))
    }
  }

  if (!businessId) {
    return <p>You do not have an active business.</p>
  }

  if (!business) {
    return <p>Loading...</p>
  }

  return (
    <div>
      <h1>Business Profile</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {message && <p style={{ color: "green" }}>{message}</p>}

      <p>Status: {business.status}</p>

      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Business Name"
          value={form.business_name}
          onChange={(e) => setForm({ ...form, business_name: e.target.value })}
          required
        />
        <br />
        <select
          value={form.business_category_id}
          onChange={(e) => setForm({ ...form, business_category_id: e.target.value })}
          required
        >
          <option value="">Select Business Category</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <br />
        <select
          value={form.country_id}
          onChange={(e) => setForm({ ...form, country_id: e.target.value })}
          required
        >
          <option value="">Select Country</option>
          {countries.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <br />
        <button type="submit">Save</button>
      </form>
    </div>
  )
}
