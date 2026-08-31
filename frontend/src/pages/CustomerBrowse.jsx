import React, { useState, useEffect } from "react"
import { browseBusinesses, browseBranches, browseServices } from "../api/api"
import Navbar from "../components/Navbar"

// Milestone 6 stops at "browse/select business, branch, service" (workflow
// 90.3) — actual availability calculation and booking are Milestone 7.
export default function CustomerBrowse() {
  const [businesses, setBusinesses] = useState([])
  const [selectedBusinessId, setSelectedBusinessId] = useState(null)
  const [branches, setBranches] = useState([])
  const [selectedBranchId, setSelectedBranchId] = useState(null)
  const [services, setServices] = useState([])
  const [error, setError] = useState("")

  useEffect(() => {
    browseBusinesses()
      .then((response) => setBusinesses(response.data))
      .catch(() => setError("Failed to load businesses"))
  }, [])

  useEffect(() => {
    if (!selectedBusinessId) {
      return
    }
    browseBranches(selectedBusinessId)
      .then((response) => setBranches(response.data))
      .catch(() => setError("Failed to load branches"))
  }, [selectedBusinessId])

  useEffect(() => {
    if (!selectedBranchId) {
      return
    }
    browseServices(selectedBranchId)
      .then((response) => setServices(response.data))
      .catch(() => setError("Failed to load services"))
  }, [selectedBranchId])

  const handleSelectBusiness = (businessId) => {
    setSelectedBusinessId(businessId)
    setSelectedBranchId(null)
    setBranches([])
    setServices([])
  }

  const handleSelectBranch = (branchId) => {
    setSelectedBranchId(branchId)
    setServices([])
  }

  return (
    <div>
      <Navbar />
      <h1>Browse Businesses</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <h2>1. Select a Business</h2>
      <ul>
        {businesses.map((b) => (
          <li key={b.id}>
            <button onClick={() => handleSelectBusiness(b.id)}>
              {b.business_name}
            </button>
          </li>
        ))}
      </ul>

      {selectedBusinessId && (
        <>
          <h2>2. Select a Branch</h2>
          <ul>
            {branches.map((br) => (
              <li key={br.id}>
                <button onClick={() => handleSelectBranch(br.id)}>
                  {br.branch_name}
                  {br.city ? ` (${br.city})` : ""}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {selectedBranchId && (
        <>
          <h2>3. Available Services</h2>
          <ul>
            {services.map((s) => (
              <li key={s.id}>
                {s.name} — {s.duration} min — ₹{s.price}
              </li>
            ))}
          </ul>
          <p>
            <em>Booking is coming soon.</em>
          </p>
        </>
      )}
    </div>
  )
}
