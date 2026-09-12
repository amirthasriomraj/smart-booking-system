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

export const suspendBusiness = (businessId) => {
  return api.post(`/businesses/${businessId}/suspend`)
}

export const reactivateBusiness = (businessId) => {
  return api.post(`/businesses/${businessId}/reactivate`)
}

export const listCountries = () => api.get("/businesses/countries")

/*
Business Profile (Business Owner) — M9 Phase 6
*/

export const getBusinessProfile = (businessId) => api.get(`/businesses/${businessId}`)

export const updateBusinessProfile = (businessId, data) => api.patch(`/businesses/${businessId}`, data)

export const getBusinessAuditHistory = (businessId, params = {}) => {
  return api.get(`/businesses/${businessId}/audit-logs`, { params })
}

export const getBusinessAuditLogFilterOptions = (businessId) => {
  return api.get(`/businesses/${businessId}/audit-logs/filters`)
}

export const getBusinessNotifications = (businessId, params = {}) => {
  return api.get(`/businesses/${businessId}/notifications`, { params })
}

export const getBusinessReports = (businessId) => api.get(`/businesses/${businessId}/reports`)

/*
Branch Manager / Business Owner Daily Reports — M9 Phase 6
*/

export const getBranchDailyReport = (branchId, params = {}) => {
  return api.get(`/branches/${branchId}/reports/daily`, { params })
}

/*
Branch Manager Audit History / Notifications — M9 follow-up fix
*/

export const getBranchAuditHistory = (branchId, params = {}) => {
  return api.get(`/branches/${branchId}/audit-logs`, { params })
}

export const getBranchAuditLogFilterOptions = (branchId) => {
  return api.get(`/branches/${branchId}/audit-logs/filters`)
}

export const getBranchNotifications = (branchId, params = {}) => {
  return api.get(`/branches/${branchId}/notifications`, { params })
}

export const getBranchBookingHistory = (branchId, params = {}) => {
  return api.get(`/branches/${branchId}/booking-history`, { params })
}

/*
Platform Admin: Audit Logs, Notifications, Analytics — M9 Phase 6
*/

export const getAdminAuditLogs = (params = {}) => api.get("/admin/audit-logs", { params })

export const getAuditLogFilterOptions = () => api.get("/admin/audit-logs/filters")

export const getAdminNotifications = (params = {}) => api.get("/admin/notifications", { params })

export const getPlatformAnalytics = () => api.get("/admin/platform-analytics")

/*
Resource User self-service — M9 Phase 6
*/

export const getResourceUserBookings = (scope = "upcoming") => {
  return api.get("/resource/bookings", { params: { scope } })
}

/*
Business Category admin CRUD (Platform Admin)
*/

export const listBusinessCategoriesAdmin = () => api.get("/businesses/categories/admin")

export const createBusinessCategory = (data) => api.post("/businesses/categories", data)

export const updateBusinessCategory = (categoryId, data) => {
  return api.patch(`/businesses/categories/${categoryId}`, data)
}

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

// Read-only: the price difference/default payment method a reschedule
// would produce right now (rule 14) — no reschedule/Payment/Refund yet.
export const previewReschedulePriceDifference = (bookingId) => {
  return api.get(`/bookings/${bookingId}/reschedule-preview`)
}

// Staff manually confirms a reschedule-difference collection that wasn't
// captured synchronously (Direct UPI/Bank Transfer, or an Email Payment
// Link the customer has since paid).
export const confirmRescheduleDifferencePayment = (bookingId) => {
  return api.post(`/bookings/${bookingId}/reschedule-difference/confirm-payment`)
}

export const cancelBooking = (bookingId, reason, refundOverrideAmount) => {
  return api.post(`/bookings/${bookingId}/cancel`, {
    reason,
    refund_override_amount: refundOverrideAmount || undefined,
  })
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

export const listCustomerBookings = (params = {}) => api.get("/customer/bookings", { params })

export const getCustomerBooking = (bookingId) => api.get(`/customer/bookings/${bookingId}`)

export const rescheduleCustomerBooking = (bookingId, data) => {
  return api.post(`/customer/bookings/${bookingId}/reschedule`, data)
}

export const cancelCustomerBooking = (bookingId, reason) => {
  return api.post(`/customer/bookings/${bookingId}/cancel`, { reason })
}

/*
Payments / Checkout helpers (Milestone 8)
*/

// Customer checkout
export const customerCheckout = (data) => api.post("/customer/checkout", data)

export const verifyCustomerCheckout = (holdId, data) => {
  return api.post(`/customer/checkout/${holdId}/verify`, data)
}

// Customer checkout review — selecting a slot creates a hold with the
// authoritative price/coupon/deposit breakdown (no Booking yet); changing
// the coupon or payment option requires refreshing it for the same slot.
export const customerCreateCheckoutHold = (data) => api.post("/customer/checkout/hold", data)

export const customerRefreshCheckoutHold = (holdId, data) => {
  return api.post(`/customer/checkout/${holdId}/refresh`, data)
}

// Phase 2 — called only on the final Book/Proceed to Pay click; creates
// the real Razorpay order for an already-reviewed hold.
export const customerCreateCheckoutPayment = (holdId) => {
  return api.post(`/customer/checkout/${holdId}/pay`)
}

export const initiateBalancePayment = (bookingId) => {
  return api.post(`/customer/bookings/${bookingId}/pay-balance`)
}

export const verifyBalancePayment = (bookingId, data) => {
  return api.post(`/customer/bookings/${bookingId}/pay-balance/verify`, data)
}

export const verifyReschedulePriceDifference = (bookingId, data) => {
  return api.post(`/customer/bookings/${bookingId}/pay-reschedule-difference/verify`, data)
}

// Staff checkout — two-phase: selecting a slot only acquires a 10-minute
// hold with the authoritative price/coupon/deposit breakdown (Phase 1);
// a separate finalize call per payment method actually creates the
// Payment/Booking (Phase 2), using that same hold_id.
export const staffCreateCheckoutHold = (branchId, data) => {
  return api.post(`/branches/${branchId}/checkout/hold`, data)
}

// Recomputes the summary for the SAME slot after a pricing-affecting
// input changes (coupon/price override/payment option); safely releases
// the existing hold and acquires a new one under the new terms.
export const staffRefreshCheckoutHold = (holdId, data) => {
  return api.post(`/holds/${holdId}/refresh`, data)
}

// Explicitly releases an abandoned hold — called when the customer/
// branch/service/date changes underneath an already-acquired hold.
export const staffDiscardCheckoutHold = (holdId) => {
  return api.post(`/holds/${holdId}/discard`)
}

export const staffFinalizeCashHold = (holdId, data) => {
  return api.post(`/holds/${holdId}/checkout/cash`, data)
}

export const staffFinalizeEmailLinkHold = (holdId) => {
  return api.post(`/holds/${holdId}/checkout/email-link`)
}

export const staffFinalizeExternalHold = (holdId) => {
  return api.post(`/holds/${holdId}/checkout/external`)
}

export const confirmExternalPayment = (holdId) => {
  return api.post(`/holds/${holdId}/confirm-external-payment`)
}

export const staffReserveWithoutPayment = (branchId, data) => {
  return api.post(`/branches/${branchId}/checkout/reserve-without-payment`, data)
}

// Payment / refund history
export const getBookingPaymentHistory = (bookingId) => {
  return api.get(`/bookings/${bookingId}/payments`)
}

export const getCustomerBookingPaymentHistory = (bookingId) => {
  return api.get(`/customer/bookings/${bookingId}/payments`)
}

// Standalone refund (partial/full), independent of cancellation.
export const refundBooking = (bookingId, data) => {
  return api.post(`/bookings/${bookingId}/refund`, data)
}

/*
Coupon helpers (Milestone 8)
*/

export const listCoupons = (businessId) => api.get(`/businesses/${businessId}/coupons`)

export const createCoupon = (businessId, data) => {
  return api.post(`/businesses/${businessId}/coupons`, data)
}

export const getCoupon = (couponId) => api.get(`/coupons/${couponId}`)

export const approveCoupon = (couponId, comments) => {
  return api.post(`/coupons/${couponId}/approve`, { comments })
}

export const rejectCoupon = (couponId, comments) => {
  return api.post(`/coupons/${couponId}/reject`, { comments })
}

export const setCouponStatus = (couponId, status) => {
  return api.patch(`/coupons/${couponId}/status`, { status })
}

/*
Platform Fee configuration helpers (Milestone 8, Platform Admin)
*/

export const getPlatformFeeSettings = () => api.get("/platform-fee-settings")

export const setDefaultPlatformFee = (data) => {
  return api.post("/platform-fee-settings/default", data)
}

export const setBusinessFeeOverride = (businessId, data) => {
  return api.post(`/businesses/${businessId}/fee-override`, data)
}

export const removeBusinessFeeOverride = (businessId, data) => {
  return api.post(`/businesses/${businessId}/fee-override/remove`, data)
}

export default api