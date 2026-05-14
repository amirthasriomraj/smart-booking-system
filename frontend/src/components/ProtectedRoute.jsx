import { useContext } from "react"
import { Navigate, Outlet } from "react-router-dom"
import { AuthContext } from "../auth/AuthContextOnly"

export default function ProtectedRoute({ adminOnly=false }) {

    const { user, loading } = useContext(AuthContext)

    // wait until session restore finishes
    if (loading) {
        return <div>Loading...</div>
    }

    if (!user) {
        return <Navigate to="/login" />
    }

    if (adminOnly && user.role !== "admin") {
        return <Navigate to="/dashboard" />
    }

    return <Outlet />
}