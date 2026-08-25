import { Link, useNavigate } from "react-router-dom"
import { useContext } from "react"

import api from "../api/api"
import { AuthContext } from "../auth/AuthContextOnly"

export default function Navbar() {

  const { user, logout } = useContext(AuthContext)
  const navigate = useNavigate()

  const isPlatformAdmin = user?.is_platform_admin
  const isActiveBusinessOwner = user?.business?.role_code === "BUSINESS_OWNER" && user?.business?.status === "Active"
  const canManageResources =
    user?.business?.status === "Active" &&
    ["BUSINESS_OWNER", "BRANCH_MANAGER", "HR_USER"].includes(user?.business?.role_code)

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

      {isPlatformAdmin && (
        <>
          {" | "}
          <Link to="/admin">Admin</Link>
        </>
      )}

      {isActiveBusinessOwner && (
        <>
          {" | "}
          <Link to="/business/branches">My Branches</Link>
          {" | "}
          <Link to="/business/staff">Staff</Link>
        </>
      )}

      {canManageResources && (
        <>
          {" | "}
          <Link to="/business/resources">Resources</Link>
        </>
      )}

      {" | "}

      <button onClick={handleLogout}>
        Logout
      </button>

    </nav>

  )

}