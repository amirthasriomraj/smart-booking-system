import React from "react"
import { useState, useContext } from "react"
import { useNavigate, Link } from "react-router-dom"
import api from "../api/api"
import { AuthContext } from "../auth/AuthContextOnly"

export default function Login() {

  const navigate = useNavigate()
  const { fetchUserContext } = useContext(AuthContext)

  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  const handleSubmit = async (e) => {

    e.preventDefault()

    try {

      const formData = new URLSearchParams()
      formData.append("username", username)
      formData.append("password", password)

      const response = await api.post("/auth/login", formData)

      const accessToken = response.data.access_token

      localStorage.setItem("access_token", accessToken)

      // Fetch real role/business context before navigating
      await fetchUserContext()

      navigate("/dashboard")

    } catch {

      setError("Invalid username or password")

    }

  }

  return (
    <div>

      <h1>Login</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <form onSubmit={handleSubmit}>

        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />

        <br />

        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <br />

        <button type="submit">
          Login
        </button>

      </form>

      <p>
        New business? <Link to="/register">Register your business</Link>
      </p>

    </div>
  )
}