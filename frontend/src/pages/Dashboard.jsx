import React from "react"
import { useEffect, useState } from "react"
import { getBookings, createBooking, deleteBooking } from "../api/api"
import Navbar from "../components/Navbar"

export default function Dashboard() {

  const [bookings, setBookings] = useState([])
  const [date, setDate] = useState("")
  const [time, setTime] = useState("")

  const [limit] = useState(5)
  const [offset, setOffset] = useState(0)

  const fetchBookings = async () => {

    try {

      const response = await getBookings(limit, offset)

      setBookings(response.data.data)

    } catch (error) {

      console.error("Failed to fetch bookings", error)

    }

  }

  useEffect(() => {
    fetchBookings()
  }, [offset])


  const handleCreateBooking = async (e) => {

    e.preventDefault()

    try {

      await createBooking({
        date,
        time
      })

      setDate("")
      setTime("")

      fetchBookings()

    } catch (error) {

      console.error("Failed to create booking", error)

      alert("Failed to create booking")

    }

  }


  const handleDeleteBooking = async (bookingId) => {

    try {

      await deleteBooking(bookingId)

      fetchBookings()

    } catch (error) {

      console.error("Failed to delete booking", error)

      alert("Failed to delete booking")

    }

  }


  const nextPage = () => {
    setOffset(offset + limit)
  }

  const previousPage = () => {

    if (offset === 0) return

    setOffset(offset - limit)

  }


  return (

    <div>

      <Navbar />

      <h1>User Dashboard</h1>

      <h2>Create Booking</h2>

      <form onSubmit={handleCreateBooking}>

        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          required
        />

        <input
          type="time"
          value={time}
          onChange={(e) => setTime(e.target.value)}
          required
        />

        <button type="submit">
          Create Booking
        </button>

      </form>


      <h2>Your Bookings</h2>

      {bookings.length === 0 ? (

        <p>No bookings found.</p>

      ) : (

        <table border="1" cellPadding="8">

          <thead>
            <tr>
              <th>ID</th>
              <th>Date</th>
              <th>Time</th>
              <th>Action</th>
            </tr>
          </thead>

          <tbody>

            {bookings.map((booking) => (

              <tr key={booking.id}>

                <td>{booking.id}</td>

                <td>{booking.date}</td>

                <td>{booking.time}</td>

                <td>
                  <button
                    onClick={() => handleDeleteBooking(booking.id)}
                  >
                    Delete
                  </button>
                </td>

              </tr>

            ))}

          </tbody>

        </table>

      )}


      <div style={{ marginTop: "20px" }}>

        <button onClick={previousPage}>
          Previous
        </button>

        <span style={{ margin: "0 10px" }}>
          Offset: {offset}
        </span>

        <button onClick={nextPage}>
          Next
        </button>

      </div>

    </div>

  )

}