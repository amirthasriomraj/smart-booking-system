import React, { useState, useEffect } from "react"
import {
  browseBusinesses,
  browseBranches,
  browseServices,
  getCustomerBranchAvailability,
  createCustomerBooking,
} from "../api/api"
import { extractErrorMessage } from "../api/errors"
import Navbar from "../components/Navbar"

// Milestone 6 covered "browse/select business, branch, service" (workflow
// 90.3); Milestone 7 continues the same flow into availability + booking.
export default function CustomerBrowse() {
  const [businesses, setBusinesses] = useState([])
  const [selectedBusinessId, setSelectedBusinessId] = useState(null)
  const [branches, setBranches] = useState([])
  const [selectedBranchId, setSelectedBranchId] = useState(null)
  const [services, setServices] = useState([])
  const [selectedServiceId, setSelectedServiceId] = useState(null)
  const [date, setDate] = useState("")
  const [slots, setSlots] = useState(null)
  const [selectedSlot, setSelectedSlot] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [confirmation, setConfirmation] = useState(null)
  const [error, setError] = useState("")

  const selectedBusiness = businesses.find((b) => b.id === selectedBusinessId)
  const selectedBranch = branches.find((br) => br.id === selectedBranchId)
  const selectedService = services.find((s) => s.id === selectedServiceId)

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
    setSlots(null)
    setSelectedSlot(null)
    setConfirmation(null)
  }

  const handleSelectBranch = (branchId) => {
    setSelectedBranchId(branchId)
    setServices([])
    setSelectedServiceId(null)
    setSlots(null)
    setSelectedSlot(null)
    setConfirmation(null)
  }

  const handleSelectService = (serviceId) => {
    setSelectedServiceId(serviceId)
    setSlots(null)
    setSelectedSlot(null)
    setConfirmation(null)
  }

  const handleDateChange = (e) => {
    setDate(e.target.value)
    setSlots(null)
    setSelectedSlot(null)
    setConfirmation(null)
  }

  const handleCheckAvailability = async (e) => {
    e.preventDefault()
    setError("")
    setSlots(null)
    setSelectedSlot(null)
    setConfirmation(null)
    try {
      const response = await getCustomerBranchAvailability(selectedBranchId, selectedServiceId, date)
      setSlots(response.data.slots)
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to load availability"))
    }
  }

  // Selecting a time only stages it — it does not create a booking.
  const handleSelectSlot = (slot) => {
    setError("")
    setSelectedSlot(slot)
  }

  const handleConfirmBooking = async () => {
    if (submitting || !selectedSlot) {
      return
    }
    setError("")
    setSubmitting(true)
    try {
      const response = await createCustomerBooking({
        branch_service_id: selectedServiceId,
        booking_date: date,
        start_time: selectedSlot.start_time,
      })
      setConfirmation(response.data)
      setSlots(null)
      setSelectedSlot(null)
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to create booking"))
    } finally {
      setSubmitting(false)
    }
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
          <h2>3. Select a Service</h2>
          <ul>
            {services.map((s) => (
              <li key={s.id}>
                <button onClick={() => handleSelectService(s.id)}>
                  {s.name} — {s.duration} min — ₹{s.price}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {selectedServiceId && (
        <>
          <h2>4. Select a Date</h2>
          <form onSubmit={handleCheckAvailability}>
            <input type="date" value={date} onChange={handleDateChange} required />
            {" "}
            <button type="submit">Check Availability</button>
          </form>

          {slots && (
            <>
              <h2>5. Select a Time</h2>
              <ul>
                {slots.length === 0 && <li>No available slots for this date.</li>}
                {slots.map((slot) => (
                  <li key={slot.start_time}>
                    <button onClick={() => handleSelectSlot(slot)}>
                      {slot.start_time} - {slot.end_time}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}

          {selectedSlot && (
            <>
              <h2>6. Confirm Booking</h2>
              <ul>
                <li>Business: {selectedBusiness?.business_name}</li>
                <li>Branch: {selectedBranch?.branch_name}</li>
                <li>Service: {selectedService?.name}</li>
                <li>Date: {date}</li>
                <li>Time: {selectedSlot.start_time} - {selectedSlot.end_time}</li>
                <li>Price: ₹{selectedService?.price}</li>
              </ul>
              <button onClick={handleConfirmBooking} disabled={submitting}>
                {submitting ? "Confirming…" : "Confirm Booking"}
              </button>
            </>
          )}
        </>
      )}

      {confirmation && (
        <p style={{ color: "green" }}>
          Booking confirmed for {confirmation.booking_date} at {confirmation.start_time}. See it under{" "}
          <a href="/customer/bookings">My Bookings</a>.
        </p>
      )}
    </div>
  )
}
