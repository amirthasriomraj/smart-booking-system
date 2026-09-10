const CHECKOUT_SCRIPT_SRC = "https://checkout.razorpay.com/v1/checkout.js"

let scriptPromise = null

function loadRazorpayScript() {
  if (window.Razorpay) {
    return Promise.resolve()
  }
  if (!scriptPromise) {
    scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script")
      script.src = CHECKOUT_SCRIPT_SRC
      script.onload = () => resolve()
      script.onerror = () => reject(new Error("Failed to load the Razorpay checkout script"))
      document.body.appendChild(script)
    })
  }
  return scriptPromise
}

// Opens the Razorpay Checkout widget for a server-created order and
// resolves with { razorpay_payment_id, razorpay_order_id, razorpay_signature }
// on success. This is ONLY the browser-side handoff — the caller must
// always send these back to the backend's own verify endpoint, since the
// backend re-verifies the signature and confirms capture server-side
// (money is never treated as received just because this widget said so).
export function openRazorpayCheckout({ orderId, keyId, amount, currency, name, description, prefillEmail, prefillContact }) {
  return loadRazorpayScript().then(() => {
    return new Promise((resolve, reject) => {
      const options = {
        key: keyId,
        order_id: orderId,
        amount: amount ? Math.round(Number(amount) * 100) : undefined,
        currency: currency || "INR",
        name: name || "Booking Payment",
        description: description || "",
        prefill: {
          email: prefillEmail || undefined,
          contact: prefillContact || undefined,
        },
        handler: (response) => resolve(response),
        modal: {
          ondismiss: () => reject(new Error("Payment window was closed before completion")),
        },
      }
      const instance = new window.Razorpay(options)
      instance.on("payment.failed", (response) => {
        reject(new Error(response?.error?.description || "Payment failed"))
      })
      instance.open()
    })
  })
}
