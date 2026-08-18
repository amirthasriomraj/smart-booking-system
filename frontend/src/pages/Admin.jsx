import React, { useCallback, useEffect, useState } from "react"
import {
  listBusinesses,
  approveBusiness,
  rejectBusiness,
  listBranches,
  approveBranch,
  rejectBranch,
} from "../api/api"

export default function Admin() {
  const [businesses, setBusinesses] = useState([])
  const [branches, setBranches] = useState([])
  const [error, setError] = useState("")

  const loadBusinesses = useCallback(() => {
    listBusinesses("Pending")
      .then((response) => setBusinesses(response.data))
      .catch(() => setError("Failed to load pending businesses"))
  }, [])

  const loadBranches = useCallback(() => {
    listBranches("Pending")
      .then((response) => setBranches(response.data))
      .catch(() => setError("Failed to load pending branches"))
  }, [])

  useEffect(() => {
    loadBusinesses()
    loadBranches()
  }, [loadBusinesses, loadBranches])

  const handleApproveBusiness = async (id) => {
    await approveBusiness(id)
    loadBusinesses()
  }

  const handleRejectBusiness = async (id) => {
    await rejectBusiness(id)
    loadBusinesses()
  }

  const handleApproveBranch = async (id) => {
    await approveBranch(id)
    loadBranches()
  }

  const handleRejectBranch = async (id) => {
    await rejectBranch(id)
    loadBranches()
  }

  return (
    <div>
      <h1>Admin Panel</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <h2>Pending Businesses</h2>
      {businesses.length === 0 && <p>No pending businesses.</p>}
      <ul>
        {businesses.map((business) => (
          <li key={business.id}>
            {business.business_name}
            {" "}
            <button onClick={() => handleApproveBusiness(business.id)}>Approve</button>
            {" "}
            <button onClick={() => handleRejectBusiness(business.id)}>Reject</button>
          </li>
        ))}
      </ul>

      <h2>Pending Branches</h2>
      {branches.length === 0 && <p>No pending branches.</p>}
      <ul>
        {branches.map((branch) => (
          <li key={branch.id}>
            {branch.branch_name} (business #{branch.business_id})
            {" "}
            <button onClick={() => handleApproveBranch(branch.id)}>Approve</button>
            {" "}
            <button onClick={() => handleRejectBranch(branch.id)}>Reject</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
