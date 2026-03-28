import React from "react"
import { useEffect, useState } from "react"
import api from "../api/api"
import Navbar from "../components/Navbar"

export default function Profile() {

  const [profile, setProfile] = useState(null)

  useEffect(() => {

    const fetchProfile = async () => {

      try {

        const response = await api.get("/profiles/profile")

        console.log("Profile:", response.data)

        setProfile(response.data)

      } catch (error) {

        console.error("Failed to fetch profile", error)

      }

    }

    fetchProfile()

  }, [])

  return (

    <div>

      <Navbar />

      <h1>User Profile</h1>

      {!profile ? (
        <p>Loading profile...</p>
      ) : (
        <div>
          <p>Profile ID: {profile.id}</p>
          <p>User ID: {profile.user_id}</p>
          <p>First Name: {profile.first_name || "N/A"}</p>
          <p>Last Name: {profile.last_name || "N/A"}</p>
          <p>Phone: {profile.phone || "N/A"}</p>
        </div>
      )}

    </div>

  )

}