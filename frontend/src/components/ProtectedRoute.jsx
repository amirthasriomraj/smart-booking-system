import { useContext } from "react"
import { Navigate, Outlet } from "react-router-dom"
import { AuthContext } from "../auth/AuthContextOnly"

export default function ProtectedRoute({ adminOnly=false, businessOwnerOnly=false, customerOnly=false }) {

    const { user, loading } = useContext(AuthContext)

    // wait until session restore finishes
    if (loading) {
        return <div>Loading...</div>
    }

    if (!user) {
        return <Navigate to={customerOnly ? "/customer/login" : "/login"} />
    }

    if (adminOnly && !user.is_platform_admin) {
        return <Navigate to="/dashboard" />
    }

    if (
        businessOwnerOnly &&
        !(user.business?.role_code === "BUSINESS_OWNER" && user.business?.status === "Active")
    ) {
        return <Navigate to="/dashboard" />
    }

    if (customerOnly && !user.customer) {
        return <Navigate to="/dashboard" />
    }

    return <Outlet />
}