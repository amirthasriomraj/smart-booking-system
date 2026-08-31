import React, { useEffect, useState, useCallback } from "react"
import { getMyCustomerProfile, updateMyCustomerProfile } from "../api/api"
import { extractErrorMessage } from "../api/errors"
import Navbar from "../components/Navbar"

const emptyForm = {
  first_name: "",
  last_name: "",
  mobile_number: "",
  gender: "",
  date_of_birth: "",
  address_line: "",
  city: "",
  state: "",
  postal_code: "",
}

export default function CustomerProfile() {
  const [profile, setProfile] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")

  const load = useCallback(() => {
    getMyCustomerProfile()
      .then((response) => {
        setProfile(response.data)
        setForm({
          first_name: response.data.first_name || "",
          last_name: response.data.last_name || "",
          mobile_number: response.data.mobile_number || "",
          gender: response.data.gender || "",
          date_of_birth: response.data.date_of_birth || "",
          address_line: response.data.address_line || "",
          city: response.data.city || "",
          state: response.data.state || "",
          postal_code: response.data.postal_code || "",
        })
      })
      .catch(() => setError("Failed to load profile"))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError("")
    setMessage("")
    try {
      const payload = { ...form, date_of_birth: form.date_of_birth || null }
      const response = await updateMyCustomerProfile(payload)
      setProfile(response.data)
      setMessage("Profile updated.")
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to update profile"))
    }
  }

  return (
    <div>
      <Navbar />
      <h1>My Profile</h1>

      {!profile ? (
        <p>{error || "Loading..."}</p>
      ) : (
        <>
          <p>Email: {profile.email}</p>

          {error && <p style={{ color: "red" }}>{error}</p>}
          {message && <p style={{ color: "green" }}>{message}</p>}

          <form onSubmit={handleSubmit}>
            <input
              type="text"
              placeholder="First Name"
              value={form.first_name}
              onChange={(e) => setForm({ ...form, first_name: e.target.value })}
            />
            <br />
            <input
              type="text"
              placeholder="Last Name"
              value={form.last_name}
              onChange={(e) => setForm({ ...form, last_name: e.target.value })}
            />
            <br />
            <input
              type="text"
              placeholder="Mobile Number"
              value={form.mobile_number}
              onChange={(e) => setForm({ ...form, mobile_number: e.target.value })}
            />
            <br />
            <input
              type="text"
              placeholder="Gender"
              value={form.gender}
              onChange={(e) => setForm({ ...form, gender: e.target.value })}
            />
            <br />
            <input
              type="date"
              value={form.date_of_birth}
              onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })}
            />
            <br />
            <input
              type="text"
              placeholder="Address Line"
              value={form.address_line}
              onChange={(e) => setForm({ ...form, address_line: e.target.value })}
            />
            <br />
            <input
              type="text"
              placeholder="City"
              value={form.city}
              onChange={(e) => setForm({ ...form, city: e.target.value })}
            />
            <br />
            <input
              type="text"
              placeholder="State"
              value={form.state}
              onChange={(e) => setForm({ ...form, state: e.target.value })}
            />
            <br />
            <input
              type="text"
              placeholder="Postal Code"
              value={form.postal_code}
              onChange={(e) => setForm({ ...form, postal_code: e.target.value })}
            />
            <br />
            <button type="submit">Save</button>
          </form>
        </>
      )}
    </div>
  )
}
