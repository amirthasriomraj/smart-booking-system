import React, { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { registerBusiness, listBusinessCategories, listCountries } from "../api/api"
import { extractErrorMessage } from "../api/errors"

const emptyForm = {
  username: "",
  email: "",
  password: "",
  business_name: "",
  business_category_id: "",
  country_id: "",
}

// Business Owner self-registration (PRD §12 Steps 1-3), calling the existing
// POST /businesses/register endpoint. The created Business starts Pending —
// this form does not activate or approve it; that remains a separate
// Platform Admin action.
export default function Register() {
  const [categories, setCategories] = useState([])
  const [countries, setCountries] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState("")
  const [registered, setRegistered] = useState(false)

  useEffect(() => {
    listBusinessCategories().then((r) => setCategories(r.data)).catch(() => {})
    listCountries().then((r) => setCountries(r.data)).catch(() => {})
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError("")
    try {
      await registerBusiness({
        username: form.username,
        email: form.email,
        password: form.password,
        business_name: form.business_name,
        business_category_id: Number(form.business_category_id),
        country_id: Number(form.country_id),
      })
      setRegistered(true)
    } catch (err) {
      setError(extractErrorMessage(err, "Registration failed"))
    }
  }

  if (registered) {
    return (
      <div>
        <h1>Registration Submitted</h1>
        <p>
          Your business has been registered and is pending Platform Admin approval.
          You can log in once it has been approved.
        </p>
        <p>
          <Link to="/login">Go to Login</Link>
        </p>
      </div>
    )
  }

  return (
    <div>
      <h1>Register Your Business</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Username"
          value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })}
          required
        />
        <br />
        <input
          type="email"
          placeholder="Email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          required
        />
        <br />
        <input
          type="password"
          placeholder="Password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          required
        />
        <br />
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
        <button type="submit">Register</button>
      </form>

      <p>
        Already have an account? <Link to="/login">Login</Link>
      </p>
    </div>
  )
}
