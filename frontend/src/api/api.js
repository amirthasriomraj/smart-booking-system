import axios from "axios"

/*
Helper: read cookie
*/
function getCookie(name) {
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) {
    return parts.pop().split(";").shift()
  }
  return null
}

/*
🔥 IMPORTANT CHANGE:
Use SAME-ORIGIN via Nginx
*/
const api = axios.create({
  baseURL: "/api/v1",
  withCredentials: true
})

/*
Attach access token automatically
*/
api.interceptors.request.use((config) => {

  const token = localStorage.getItem("access_token")

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

/*
Interceptor for expired access tokens
*/
api.interceptors.response.use(
  (response) => response,
  async (error) => {

    const originalRequest = error.config

    if (
      error.response &&
      error.response.status === 401 &&
      !originalRequest._retry
    ) {

      originalRequest._retry = true

      try {

        const csrfToken = getCookie("csrf_token")

        /*
        🔥 IMPORTANT CHANGE:
        Use SAME-ORIGIN here too
        */
        const refreshResponse = await axios.post(
          "/api/v1/auth/refresh",
          {},
          {
            withCredentials: true,
            headers: {
              "X-CSRF-Token": csrfToken
            }
          }
        )

        const newAccessToken = refreshResponse.data.access_token

        localStorage.setItem("access_token", newAccessToken)

        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`

        return api(originalRequest)

      } catch (refreshError) {

        localStorage.removeItem("access_token")

        window.location.href = "/login"

        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

/*
Booking helpers
*/

export const getBookings = (limit = 10, offset = 0, sort = "date") => {
  return api.get("/bookings", {
    params: { limit, offset, sort }
  })
}

export const createBooking = (data) => {
  return api.post("/bookings", data)
}

export const deleteBooking = (bookingId) => {
  return api.delete(`/bookings/${bookingId}`)
}

export default api