import { useState } from "react"
import { useSearchParams, useNavigate } from "react-router-dom"
import api from "../api/api"

export default function ResetPassword() {

  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const token = searchParams.get("token")

  const [password, setPassword] = useState("")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")

  const handleSubmit = async (e) => {
    e.preventDefault()

    try {

      await api.post("/auth/reset-password", {
        token,
        new_password: password
      })

      setMessage("Password reset successful! Redirecting to login...")

      setTimeout(() => {
        navigate("/login")
      }, 2000)

    } catch {

      setError("Invalid or expired token")

    }
  }

  return (
    <div>

      <h1>Reset Password</h1>

      {message && <p style={{ color: "green" }}>{message}</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}

      <form onSubmit={handleSubmit}>

        <input
          type="password"
          placeholder="New Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        <br />

        <button type="submit">
          Reset Password
        </button>

      </form>

    </div>
  )
}