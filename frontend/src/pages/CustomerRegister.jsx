import React, { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import { registerCustomer } from "../api/api"
import { extractErrorMessage } from "../api/errors"

const emptyForm = {
  first_name: "",
  last_name: "",
  email: "",
  mobile_number: "",
  password: "",
}

export default function CustomerRegister() {
  const navigate = useNavigate()
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState("")

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError("")
    try {
      await registerCustomer(form)
      navigate("/customer/login")
    } catch (err) {
      setError(extractErrorMessage(err, "Registration failed"))
    }
  }

  return (
    <div>
      <h1>Create Your Account</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <form onSubmit={handleSubmit}>
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
          type="email"
          placeholder="Email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
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
          type="password"
          placeholder="Password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          required
        />
        <br />
        <button type="submit">Register</button>
      </form>

      <p>
        Already have an account? <Link to="/customer/login">Login</Link>
      </p>
    </div>
  )
}
