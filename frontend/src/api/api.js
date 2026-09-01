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
Current user context (Milestone 2)
*/

export const getMe = () => api.get("/auth/me")

/*
Business Owner registration (public)
*/

export const listBusinessCategories = () => api.get("/businesses/categories")

export const registerBusiness = (data) => api.post("/businesses/register", data)

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

/*
Resource Management helpers (Milestone 4)
*/

export const listResourceCategories = (businessId) => {
  return api.get(`/businesses/${businessId}/resource-categories`)
}

export const createResourceCategory = (businessId, data) => {
  return api.post(`/businesses/${businessId}/resource-categories`, data)
}

export const updateResourceCategory = (categoryId, data) => {
  return api.patch(`/resource-categories/${categoryId}`, data)
}

export const listResourcesForBranch = (branchId) => {
  return api.get(`/branches/${branchId}/resources`)
}

export const listResourcesForBusiness = (businessId) => {
  return api.get(`/businesses/${businessId}/resources`)
}

export const createResource = (branchId, data) => {
  return api.post(`/branches/${branchId}/resources`, data)
}

export const updateResource = (resourceId, data) => {
  return api.patch(`/resources/${resourceId}`, data)
}

export const activateResource = (resourceId) => api.post(`/resources/${resourceId}/activate`)

export const suspendResource = (resourceId) => api.post(`/resources/${resourceId}/suspend`)

export const getResourceWorkingHours = (resourceId) => api.get(`/resources/${resourceId}/working-hours`)

export const upsertResourceWorkingHours = (resourceId, hours) => {
  return api.put(`/resources/${resourceId}/working-hours`, { hours })
}

export const listResourceUsers = (businessId) => {
  return api.get(`/businesses/${businessId}/resource-users`)
}

export const inviteResourceUser = (businessId, resourceId, email) => {
  return api.post(`/businesses/${businessId}/resources/${resourceId}/invite-user`, { email })
}

export const resendResourceInvite = (memberId) => {
  return api.post(`/business-members/${memberId}/resend-resource-invite`)
}

export const deactivateResourceUser = (memberId) => {
  return api.post(`/business-members/${memberId}/deactivate-resource-user`)
}

/*
Service Management helpers (Milestone 5)
*/

export const listServiceTemplates = (businessId) => {
  return api.get(`/businesses/${businessId}/service-templates`)
}

export const createServiceTemplate = (businessId, data) => {
  return api.post(`/businesses/${businessId}/service-templates`, data)
}

export const getServiceTemplate = (templateId) => api.get(`/service-templates/${templateId}`)

export const activateServiceTemplate = (templateId) => api.post(`/service-templates/${templateId}/activate`)

export const deactivateServiceTemplate = (templateId) => api.post(`/service-templates/${templateId}/deactivate`)

export const listBranchServicesForBranch = (branchId) => {
  return api.get(`/branches/${branchId}/branch-services`)
}

export const listBranchServicesForBusiness = (businessId) => {
  return api.get(`/businesses/${businessId}/branch-services`)
}

export const getBranchService = (branchServiceId) => api.get(`/branch-services/${branchServiceId}`)

export const updateBranchService = (branchServiceId, data) => {
  return api.patch(`/branch-services/${branchServiceId}`, data)
}

export const submitBranchServiceOverride = (branchServiceId, data) => {
  return api.post(`/branch-services/${branchServiceId}/submit-override`, data)
}

export const listServiceApprovals = (businessId) => {
  return api.get(`/businesses/${businessId}/service-approvals`)
}

export const decideServiceApproval = (approvalId, decision, comments) => {
  return api.post(`/service-approvals/${approvalId}/decide`, { decision, comments })
}

/*
Customer Management helpers (Milestone 6)
*/

export const registerCustomer = (data) => {
  return api.post("/customers/register", data)
}

export const getMyCustomerProfile = () => api.get("/customers/me")

export const updateMyCustomerProfile = (data) => api.patch("/customers/me", data)

export const listBusinessCustomers = (businessId, params = {}) => {
  return api.get(`/businesses/${businessId}/customers`, { params })
}

export const createWalkInCustomer = (businessId, data) => {
  return api.post(`/businesses/${businessId}/customers`, data)
}

export const getBusinessCustomer = (customerId) => api.get(`/business-customers/${customerId}`)

export const updateBusinessCustomer = (customerId, data) => {
  return api.patch(`/business-customers/${customerId}`, data)
}

export const setCustomerStatus = (customerId, status) => {
  return api.patch(`/business-customers/${customerId}/status`, { status })
}

export const browseBusinesses = () => api.get("/customer/businesses")

export const browseBranches = (businessId) => api.get(`/customer/businesses/${businessId}/branches`)

export const browseServices = (branchId) => api.get(`/customer/branches/${branchId}/services`)

/*
Booking helpers (Milestone 7)
*/

// Availability Engine — staff-facing
export const getBranchAvailability = (branchId, branchServiceId, date, resourceId) => {
  return api.get(`/branches/${branchId}/availability`, {
    params: { branch_service_id: branchServiceId, date, resource_id: resourceId || undefined }
  })
}

// Staff booking management
export const createStaffBooking = (branchId, data) => {
  return api.post(`/branches/${branchId}/bookings`, data)
}

export const listBranchBookings = (branchId, params = {}) => {
  return api.get(`/branches/${branchId}/bookings`, { params })
}

export const listBusinessBookings = (businessId, params = {}) => {
  return api.get(`/businesses/${businessId}/bookings`, { params })
}

export const getBooking = (bookingId) => api.get(`/bookings/${bookingId}`)

export const getBookingHistory = (bookingId) => api.get(`/bookings/${bookingId}/history`)

export const rescheduleBooking = (bookingId, data) => {
  return api.post(`/bookings/${bookingId}/reschedule`, data)
}

export const cancelBooking = (bookingId, reason) => {
  return api.post(`/bookings/${bookingId}/cancel`, { reason })
}

export const reassignBookingResource = (bookingId, resourceId) => {
  return api.post(`/bookings/${bookingId}/reassign-resource`, { resource_id: resourceId })
}

export const completeBooking = (bookingId) => api.post(`/bookings/${bookingId}/complete`)

// Customer self-service
export const getCustomerBranchAvailability = (branchId, branchServiceId, date, resourceId) => {
  return api.get(`/customer/branches/${branchId}/availability`, {
    params: { branch_service_id: branchServiceId, date, resource_id: resourceId || undefined }
  })
}

export const createCustomerBooking = (data) => api.post("/customer/bookings", data)

export const listCustomerBookings = () => api.get("/customer/bookings")

export const getCustomerBooking = (bookingId) => api.get(`/customer/bookings/${bookingId}`)

export const rescheduleCustomerBooking = (bookingId, data) => {
  return api.post(`/customer/bookings/${bookingId}/reschedule`, data)
}

export const cancelCustomerBooking = (bookingId, reason) => {
  return api.post(`/customer/bookings/${bookingId}/cancel`, { reason })
}

export default api