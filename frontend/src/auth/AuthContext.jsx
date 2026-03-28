import React, { createContext, useState, useEffect } from "react"
import api from "../api/api"

export const AuthContext = createContext()

function getCookie(name) {
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) {
    return parts.pop().split(";").shift()
  }
  return null
}

export function AuthProvider({ children }) {

  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {

    const publicRoutes = ["/login", "/register", "/reset-password"]
    const currentPath = window.location.pathname

    if (publicRoutes.includes(currentPath)) {
      setLoading(false)
      return
    }

    const restoreSession = async () => {

      const csrfToken = getCookie("csrf_token")

      // 🔥 CRITICAL FIX: Skip refresh if no CSRF cookie
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

      } catch (error) {

        localStorage.removeItem("access_token")
        setUser(null)

      }

      setLoading(false)
    }

    restoreSession()

  }, [])

  const logout = async () => {

    try {
      await api.post("/auth/logout")
    } catch (err) {}

    localStorage.removeItem("access_token")
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, setUser, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}