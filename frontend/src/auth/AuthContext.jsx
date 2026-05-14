import { useState, useEffect } from "react"
import api from "../api/api"
import { AuthContext } from "./AuthContextOnly"

function getCookie(name) {
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)

  if (parts.length === 2) {
    return parts.pop().split(";").shift()
  }

  return null
}

export function AuthProvider({ children }) {
  const publicRoutes = ["/login", "/register", "/reset-password"]
  const currentPath = window.location.pathname

  const shouldSkipAuth = publicRoutes.includes(currentPath)

  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!shouldSkipAuth)

  useEffect(() => {
    if (shouldSkipAuth) {
      return
    }

    const restoreSession = async () => {
      const csrfToken = getCookie("csrf_token")

      if (!csrfToken) {
        setLoading(false)
        return
      }

      try {
        const response = await api.post(
          "/auth/refresh",
          {},
          {
            withCredentials: true,
            headers: {
              "X-CSRF-Token": csrfToken
            }
          }
        )

        const newAccessToken = response.data.access_token

        localStorage.setItem("access_token", newAccessToken)

        setUser({
          authenticated: true,
          role: "user"
        })

      } catch {
        localStorage.removeItem("access_token")
        setUser(null)

      } finally {
        setLoading(false)
      }
    }

    restoreSession()
  }, [shouldSkipAuth])

  const logout = async () => {
    try {
      await api.post("/auth/logout")
    } catch {
      console.warn("Logout request failed")
    }

    localStorage.removeItem("access_token")
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, setUser, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}