import React from "react"
import { BrowserRouter, Routes, Route } from "react-router-dom"

import Login from "./pages/Login"
import Register from "./pages/Register"
import Dashboard from "./pages/Dashboard"
import Profile from "./pages/Profile"
import Admin from "./pages/Admin"
import ResetPassword from "./pages/ResetPassword"

import ProtectedRoute from "./components/ProtectedRoute"

function App() {
  return (
    <BrowserRouter>

      <Routes>

        {/* ✅ DEFAULT ROUTE */}
        <Route path="/" element={<Login />} />

        {/* Public routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/reset-password" element={<ResetPassword />} />

        {/* Protected routes */}
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/profile" element={<Profile />} />
        </Route>

        {/* Admin routes */}
        <Route element={<ProtectedRoute adminOnly={true} />}>
          <Route path="/admin" element={<Admin />} />
        </Route>

      </Routes>

    </BrowserRouter>
  )
}

export default App