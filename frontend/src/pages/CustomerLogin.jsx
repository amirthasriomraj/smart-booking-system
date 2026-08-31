import React, { useState, useContext } from "react"
import { useNavigate, Link } from "react-router-dom"
import api from "../api/api"
import { AuthContext } from "../auth/AuthContextOnly"

export default function CustomerLogin() {
  const navigate = useNavigate()
  const { fetchUserContext } = useContext(AuthContext)

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError("")

    try {
      // Customer login handles are the customer's own email (ID-034), but
      // the shared /auth/login endpoint is unchanged — it just takes
      // whatever value is in `username`.
      const formData = new URLSearchParams()
      formData.append("username", email)
      formData.append("password", password)

      const response = await api.post("/auth/login", formData)
      localStorage.setItem("access_token", response.data.access_token)

      await fetchUserContext()
      navigate("/customer/profile")
    } catch {
      setError("Invalid email or password")
    }
  }

  return (
    <div>
      <h1>Customer Login</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <form onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <br />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <br />
        <button type="submit">Login</button>
      </form>

      <p>
        New here? <Link to="/customer/register">Create an account</Link>
      </p>
    </div>
  )
}
