import { Link, useNavigate } from "react-router-dom"
import { useContext } from "react"

import api from "../api/api"
import { AuthContext } from "../auth/AuthContextOnly"

export default function Navbar() {

  const { logout } = useContext(AuthContext)
  const navigate = useNavigate()

  const handleLogout = async () => {

    try {

      await api.post("/auth/logout")

    } catch (error) {

      console.error("Logout failed", error)

    }

    logout()

    navigate("/login")

  }

  return (

    <nav style={{ marginBottom: "20px" }}>

      <Link to="/dashboard">Dashboard</Link>

      {" | "}

      <Link to="/profile">Profile</Link>

      {" | "}

      <button onClick={handleLogout}>
        Logout
      </button>

    </nav>

  )

}