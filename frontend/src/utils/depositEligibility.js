// Mirrors the backend's rule exactly (crud_payment.py: DEPOSIT_MIN_DAYS = 7,
// pricing.is_deposit_eligible: (appointment_datetime - now) >= 7*24h,
// computed as naive datetimes with no timezone conversion). This is a
// display-only convenience so the Deposit option isn't offered when it
// would just be rejected — the backend re-validates and remains
// authoritative (_require_deposit_eligible) regardless of what this shows.
export const DEPOSIT_MIN_DAYS = 7

export function isDepositEligible(dateStr, timeStr) {
  if (!dateStr || !timeStr) {
    return false
  }
  // Interpreted as UTC (not the browser's local timezone) to match the
  // backend's naive datetime.combine(...) vs datetime.utcnow() comparison.
  const appointment = new Date(`${dateStr}T${timeStr}Z`)
  const now = new Date()
  const minMs = DEPOSIT_MIN_DAYS * 24 * 60 * 60 * 1000
  return appointment.getTime() - now.getTime() >= minMs
}
