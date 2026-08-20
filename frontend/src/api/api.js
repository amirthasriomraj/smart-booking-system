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

/*
Current user context (Milestone 2)
*/

export const getMe = () => api.get("/auth/me")

/*
Business helpers (Platform Admin)
*/

export const listBusinesses = (status) => {
  return api.get("/businesses", { params: status ? { status } : {} })
}

export const approveBusiness = (businessId) => {
  return api.post(`/businesses/${businessId}/approve`)
}

export const rejectBusiness = (businessId, reason) => {
  return api.post(`/businesses/${businessId}/reject`, { reason })
}

export const listCountries = () => api.get("/businesses/countries")

/*
Branch helpers (Business Owner)
*/

export const listBranchesForBusiness = (businessId) => {
  return api.get(`/businesses/${businessId}/branches`)
}

export const createBranch = (businessId, data) => {
  return api.post(`/businesses/${businessId}/branches`, data)
}

export const getBranch = (branchId) => api.get(`/branches/${branchId}`)

export const updateBranch = (branchId, data) => {
  return api.patch(`/branches/${branchId}`, data)
}

export const activateBranch = (branchId) => api.post(`/branches/${branchId}/activate`)

export const deactivateBranch = (branchId) => api.post(`/branches/${branchId}/deactivate`)

export const getWorkingHours = (branchId) => api.get(`/branches/${branchId}/working-hours`)

export const upsertWorkingHours = (branchId, hours) => {
  return api.put(`/branches/${branchId}/working-hours`, { hours })
}

/*
Branch helpers (Platform Admin)
*/

export const listBranches = (approvalStatus) => {
  return api.get("/branches", { params: approvalStatus ? { approval_status: approvalStatus } : {} })
}

export const approveBranch = (branchId) => api.post(`/branches/${branchId}/approve`)

export const rejectBranch = (branchId, reason) => {
  return api.post(`/branches/${branchId}/reject`, { reason })
}

/*
Staff / employee onboarding helpers (Milestone 3)
*/

export const listStaffForBusiness = (businessId) => {
  return api.get(`/businesses/${businessId}/staff`)
}

export const inviteStaffMember = (businessId, data) => {
  return api.post(`/businesses/${businessId}/staff/invite`, data)
}

export const resendStaffInvite = (businessId, memberId) => {
  return api.post(`/businesses/${businessId}/staff/${memberId}/resend-invite`)
}

export const transferBranchManager = (memberId, branchId) => {
  return api.post(`/business-members/${memberId}/transfer-branch`, { branch_id: branchId })
}

export const deactivateStaffMember = (memberId) => {
  return api.post(`/business-members/${memberId}/deactivate`)
}

export const getInvitationStatus = (token) => {
  return api.get("/auth/accept-invitation", { params: { token } })
}

export const acceptInvitation = (data) => {
  return api.post("/auth/accept-invitation", data)
}

export default api