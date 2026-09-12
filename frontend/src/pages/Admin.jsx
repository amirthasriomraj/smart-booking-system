import React, { useCallback, useEffect, useState } from "react"
import {
  listBusinesses,
  approveBusiness,
  rejectBusiness,
  suspendBusiness,
  reactivateBusiness,
  listBranches,
  approveBranch,
  rejectBranch,
  listBusinessCategoriesAdmin,
  createBusinessCategory,
  updateBusinessCategory,
} from "../api/api"

export default function Admin() {
  const [businesses, setBusinesses] = useState([])
  const [activeBusinesses, setActiveBusinesses] = useState([])
  const [suspendedBusinesses, setSuspendedBusinesses] = useState([])
  const [branches, setBranches] = useState([])
  const [categories, setCategories] = useState([])
  const [newCategoryName, setNewCategoryName] = useState("")
  const [newCategoryDescription, setNewCategoryDescription] = useState("")
  const [error, setError] = useState("")

  const loadBusinesses = useCallback(() => {
    listBusinesses("Pending")
      .then((response) => setBusinesses(response.data.items))
      .catch(() => setError("Failed to load pending businesses"))
  }, [])

  const loadActiveAndSuspendedBusinesses = useCallback(() => {
    listBusinesses("Active")
      .then((response) => setActiveBusinesses(response.data.items))
      .catch(() => setError("Failed to load active businesses"))
    listBusinesses("Suspended")
      .then((response) => setSuspendedBusinesses(response.data.items))
      .catch(() => setError("Failed to load suspended businesses"))
  }, [])

  const loadBranches = useCallback(() => {
    listBranches("Pending")
      .then((response) => setBranches(response.data))
      .catch(() => setError("Failed to load pending branches"))
  }, [])

  const loadCategories = useCallback(() => {
    listBusinessCategoriesAdmin()
      .then((response) => setCategories(response.data))
      .catch(() => setError("Failed to load business categories"))
  }, [])

  useEffect(() => {
    loadBusinesses()
    loadActiveAndSuspendedBusinesses()
    loadBranches()
    loadCategories()
  }, [loadBusinesses, loadActiveAndSuspendedBusinesses, loadBranches, loadCategories])

  const handleApproveBusiness = async (id) => {
    await approveBusiness(id)
    loadBusinesses()
    loadActiveAndSuspendedBusinesses()
  }

  const handleRejectBusiness = async (id) => {
    await rejectBusiness(id)
    loadBusinesses()
  }

  const handleSuspendBusiness = async (id) => {
    await suspendBusiness(id)
    loadActiveAndSuspendedBusinesses()
  }

  const handleReactivateBusiness = async (id) => {
    await reactivateBusiness(id)
    loadActiveAndSuspendedBusinesses()
  }

  const handleApproveBranch = async (id) => {
    await approveBranch(id)
    loadBranches()
  }

  const handleRejectBranch = async (id) => {
    await rejectBranch(id)
    loadBranches()
  }

  const handleCreateCategory = async (event) => {
    event.preventDefault()
    if (!newCategoryName.trim()) return
    await createBusinessCategory({
      name: newCategoryName.trim(),
      description: newCategoryDescription.trim() || null,
    })
    setNewCategoryName("")
    setNewCategoryDescription("")
    loadCategories()
  }

  const handleToggleCategoryActive = async (category) => {
    await updateBusinessCategory(category.id, { is_active: !category.is_active })
    loadCategories()
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

      <h2>Active Businesses</h2>
      {activeBusinesses.length === 0 && <p>No active businesses.</p>}
      <ul>
        {activeBusinesses.map((business) => (
          <li key={business.id}>
            {business.business_name}
            {" "}
            <button onClick={() => handleSuspendBusiness(business.id)}>Suspend</button>
          </li>
        ))}
      </ul>

      <h2>Suspended Businesses</h2>
      {suspendedBusinesses.length === 0 && <p>No suspended businesses.</p>}
      <ul>
        {suspendedBusinesses.map((business) => (
          <li key={business.id}>
            {business.business_name}
            {" "}
            <button onClick={() => handleReactivateBusiness(business.id)}>Reactivate</button>
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

      <h2>Business Categories</h2>
      <ul>
        {categories.map((category) => (
          <li key={category.id}>
            {category.name}
            {category.description ? ` — ${category.description}` : ""}
            {" "}
            ({category.is_active ? "Active" : "Inactive"})
            {" "}
            <button onClick={() => handleToggleCategoryActive(category)}>
              {category.is_active ? "Deactivate" : "Activate"}
            </button>
          </li>
        ))}
      </ul>
      <form onSubmit={handleCreateCategory}>
        <input
          type="text"
          placeholder="Category name"
          value={newCategoryName}
          onChange={(event) => setNewCategoryName(event.target.value)}
        />
        <input
          type="text"
          placeholder="Description (optional)"
          value={newCategoryDescription}
          onChange={(event) => setNewCategoryDescription(event.target.value)}
        />
        <button type="submit">Add Category</button>
      </form>
    </div>
  )
}
