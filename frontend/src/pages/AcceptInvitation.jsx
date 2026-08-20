import { useState, useEffect } from "react"
import { useSearchParams, useNavigate } from "react-router-dom"
import { getInvitationStatus, acceptInvitation } from "../api/api"

const ROLE_LABELS = {
  BRANCH_MANAGER: "Branch Manager",
  HR_USER: "HR User",
}

export default function AcceptInvitation() {

  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get("token")

  const [status, setStatus] = useState(null)
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")

  useEffect(() => {
    if (!token) {
      return
    }
    getInvitationStatus(token)
      .then((response) => setStatus(response.data))
      .catch(() => setError("Invalid or expired invitation link"))
  }, [token])

  if (!token) {
    return <p style={{ color: "red" }}>Missing invitation token</p>
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError("")

    try {

      const payload = status?.requires_credential_setup
        ? { token, username, password }
        : { token }

      await acceptInvitation(payload)

      setMessage("Invitation accepted! Redirecting to login...")

      setTimeout(() => {
        navigate("/login")
      }, 2000)

    } catch {

      setError("Invalid or expired invitation link")

    }
  }

  if (error) {
    return <p style={{ color: "red" }}>{error}</p>
  }

  if (!status) {
    return <p>Loading...</p>
  }

  return (
    <div>

      <h1>Join {status.business_name}</h1>
      <p>
        You have been invited as {ROLE_LABELS[status.role_code] || status.role_code}
        {status.branch_name ? ` for ${status.branch_name}` : ""}.
      </p>

      {message && <p style={{ color: "green" }}>{message}</p>}

      <form onSubmit={handleSubmit}>

        {status.requires_credential_setup ? (
          <>
            <input
              placeholder="Choose a username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
            <br />
            <input
              type="password"
              placeholder="Choose a password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <br />
          </>
        ) : (
          <p>Your existing account will be used — no new password needed.</p>
        )}

        <button type="submit">
          Accept Invitation
        </button>

      </form>

    </div>
  )
}
