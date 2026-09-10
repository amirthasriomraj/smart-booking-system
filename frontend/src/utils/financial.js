// Shared labels for M8 financial/payment states, used by both the
// customer and staff/business booking views so the same status always
// reads the same way everywhere.

export function financialStatusLabel(status) {
  switch (status) {
    case "ReserveWithoutPayment":
      return "Reserved without payment"
    case "AwaitingBalance":
      return "Deposit paid — balance due"
    case "FullyPaid":
      return "Fully paid"
    case "BalanceDefaulted":
      return "Cancelled — balance not paid in time"
    default:
      return status || null
  }
}

export function paymentStatusLabel(status) {
  switch (status) {
    case "Created":
      return "Payment started"
    case "Authorized":
      return "Payment authorized"
    case "Captured":
      return "Paid"
    case "Failed":
      return "Payment failed"
    default:
      return status
  }
}

export function refundStatusLabel(status) {
  switch (status) {
    case "Initiated":
      return "Refund initiated — awaiting provider confirmation"
    case "Completed":
      return "Refund completed"
    case "Failed":
      return "Refund failed"
    default:
      return status
  }
}
